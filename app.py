import paramiko
from prometheus_client import start_http_server, Gauge
import re
import logging
import json
import time

from f5_exporter import settings
from f5_exporter import enums


logging.basicConfig(level=settings.LOGLEVEL)
balancer_connection = paramiko.SSHClient()
balancer_connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
# node_info_gauge = Gauge('f5_node_info', 'The main metric for Big-IP F5 balancer', settings.node_info_labels)
node_current_connections_gauge = Gauge(
  'f5_current_connections', 
  'Current connections per node', 
  settings.node_info_labels)
node_max_connections_gauge = Gauge(
  'f5_max_connections', 
  'Current connections per node', 
  settings.node_info_labels)
node_bits_in_gauge = Gauge(
  'f5_bits_in', 
  'Inbound traffic per node', 
  settings.node_info_labels)
node_bits_out_gauge = Gauge(
  'f5_bits_out', 
  'Outbounf traffic per node', 
  settings.node_info_labels)
node_balancing_state_gauge = Gauge(
  'f5_balancing_state', 
  'Balancing state metric. 0 - Offline, 1 - StandBy, 2 - Online, 3 - Out Of Balance by monitor, 4 - Forced Down', 
  settings.node_info_labels)

def prepare_json(data: str) -> str:
  data = data.decode('utf-8')
  data = re.sub(r'ltm pool ([\d\w\-_:.]+)\s{', '\"POOL-\\1\": {', data)
  data = re.sub(r'ltm node ([\d\w\-_:.]+)\s{', '\"\\1\": {', data)
  data = re.sub(r'\s\s\s(members)\s{', '\"\\1\": {', data)
  data = re.sub(r'\s\s\s([\d\w\-_,]+):([\d\w]+)\s{', '\"\\1:\\2\": {', data)
  data = re.sub(r'\s\s\s([\d\w\-_,]+)\s([\d\w\-_\.:,\(\);@\/ ]+)\s+}', '\"\\1\": \"\\2\"}', data)
  data = re.sub(r'\s\s\s([\d\w\-_\.]+)\ ([\d\w\-_\.:,\(\);@\/ ]+)', '\"\\1\": \"\\2\",', data)
  data = re.sub(r'}\s+\"', '},\n   \"', data)
  data = re.sub(r'\%\d{3}', '', data)
  data = re.sub(r'^([\w\W\s\S\d\D]+)$', '{\\1}', data)
  return data

def get_balancer_status(host, connection) -> dict:
  logging.debug(f'Establishing connection with {host}')
  try:
    connection.connect(
      hostname=host, 
      username=settings.F5_USER, 
      password=settings.F5_PASS, 
      port=settings.F5_PORT
    )
  except paramiko.ssh_exception.AuthenticationException:
    logging.error(f'Authentification failed with user {settings.F5_USER}')
    return
  except paramiko.ssh_exception.NoValidConnectionsError:
    logging.error(f'Unable to connect to {host}')
    return
  stdin, stdout, stderr = connection.exec_command('show ltm pool members field-fmt raw')
  # stdin, stdout, stderr = connection.exec_command('cat f5-balancer-response.txt')
  data = stdout.read() + stderr.read()
  data_json = prepare_json(data)
  connection.close()
  logging.debug(f'Connection with {host} successfully closed')
  return dict(json.loads(data_json))

def process_request(t: int) -> None:
    """A dummy function that takes some time."""
    for balancer_host in settings.F5_HOST:
      logging.debug(f'Iterating balancer list, current item {balancer_host}')
      balancer_status = get_balancer_status(balancer_host, balancer_connection)
      for pool in balancer_status.keys():
        pool_members = balancer_status[pool]['members']
        for member in pool_members.keys():
          # print(pool + ' :: ' + member + ' :: ' + str(pool_members[member]['addr']))
          if pool_members[member]['status.status-reason'] == 'Pool member has been marked down by a monitor' and pool_members[member]['monitor-status'] == 'down':
            node_state = float(enums.NodeBalancingState.OUT_OF_BALANCE)
          elif 'No successful responses received before deadline' in pool_members[member]['status.status-reason'] and pool_members[member]['monitor-status'] == 'down':
            node_state = float(enums.NodeBalancingState.OUT_OF_BALANCE)
          elif pool_members[member]['session-status'] == 'user-disabled': 
            if pool_members[member]['status.status-reason'] == 'Forced down':
              node_state = float(enums.NodeBalancingState.FORCED_DOWN)
            elif pool_members[member]['status.status-reason'] == 'Pool member is available, user disabled':
              node_state = float(enums.NodeBalancingState.STAND_BY)
          elif pool_members[member]['session-status'] == 'enabled' and pool_members[member]['status.status-reason'] == 'Pool member is available':
            node_state = float(enums.NodeBalancingState.ENABLED)
          else:
            node_state = float(enums.NodeBalancingState.OFFLINE)
          node_current_connections_gauge.labels(
            balancer = str(balancer_host),
            address = str(pool_members[member]['addr']), 
            node_name = str(pool_members[member]['node-name']),
            pool_name = str(pool_members[member]['pool-name'])
            ).set(float(pool_members[member]['serverside.cur-conns']))
          node_max_connections_gauge.labels(
            balancer = str(balancer_host),
            address = str(pool_members[member]['addr']), 
            node_name = str(pool_members[member]['node-name']),
            pool_name = str(pool_members[member]['pool-name'])
            ).set(float(pool_members[member]['serverside.max-conns']))
          node_bits_in_gauge.labels(
            balancer = str(balancer_host),
            address = str(pool_members[member]['addr']), 
            node_name = str(pool_members[member]['node-name']),
            pool_name = str(pool_members[member]['pool-name'])
            ).set(float(pool_members[member]['serverside.bits-in']))
          node_bits_out_gauge.labels(
            balancer = str(balancer_host),
            address = str(pool_members[member]['addr']), 
            node_name = str(pool_members[member]['node-name']),
            pool_name = str(pool_members[member]['pool-name'])
            ).set(float(pool_members[member]['serverside.bits-out']))
          node_balancing_state_gauge.labels(
            balancer = str(balancer_host),
            address = str(pool_members[member]['addr']), 
            node_name = str(pool_members[member]['node-name']),
            pool_name = str(pool_members[member]['pool-name'])
          ).set(node_state)
    time.sleep(t)

if __name__ == '__main__':
  # Start up the server to expose the metrics.
  start_http_server(int(settings.EXPORTER_PORT))
  logging.info(f'Started f5-exporter on port {settings.EXPORTER_PORT}')
  # Generate some requests.
  while True:
    process_request(int(settings.F5_REQUEST_INTERVAL))

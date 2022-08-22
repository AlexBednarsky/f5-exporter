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
  'Balancing state metric. 0 - Offline, 1 - User Disabled, 2 - Online', 
  settings.node_info_labels)



def prepare_json(data) -> str:
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

def replace_quantifier(match) -> str:
  # print(match.group(2))
  if match.group(2) == "K":
    quantifier = 1000
  if match.group(2) == "M":
    quantifier = 1000000
  if match.group(2) == "G":
    quantifier = 1000000000
  if match.group(2) == "T":
    quantifier = 1000000000000
  value = float(match.group(1))
  return str(int(value * quantifier))

def parse_numbers_in_json(data) -> str:
  data = re.sub(r'(\d+\.\d)(K|M|G|T)', replace_quantifier, data)
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
  # stdin, stdout, stderr = connection.exec_command('show ltm pool members field-fmt')
  stdin, stdout, stderr = connection.exec_command('cat f5-balancer-response.txt')
  data = stdout.read() + stderr.read()
  data_json = prepare_json(data)
  data_json = parse_numbers_in_json(data_json)
  connection.close()
  logging.debug(f'Connection with {host} successfully closed')
  return dict(json.loads(data_json))

def process_request(t) -> None:
    """A dummy function that takes some time."""
    for balancer in settings.F5_HOST:
      logging.debug(f'Iterating balancer list, current item {balancer}')
      balancer_status = get_balancer_status(balancer, balancer_connection)
      for pool in balancer_status.keys():
        pool_members = balancer_status[pool]['members']
        for member in pool_members.keys():
          # print(pool + ' :: ' + member + ' :: ' + str(pool_members[member]['addr']))
          if pool_members[member]['session-status'] == 'user-disabled':
            node_state = float(enums.NodeBalancingState.USER_DISABLED)
          elif pool_members[member]['session-status'] == 'enabled':
            node_state = float(enums.NodeBalancingState.ENABLED)
          else:
            node_state = float(enums.NodeBalancingState.OFFLINE)
          node_current_connections_gauge.labels(
            address = str(pool_members[member]['addr']), 
            node_name = str(pool_members[member]['node-name']),
            pool_name = str(pool_members[member]['pool-name'])
            ).set(float(pool_members[member]['serverside.cur-conns']))
          node_max_connections_gauge.labels(
            address = str(pool_members[member]['addr']), 
            node_name = str(pool_members[member]['node-name']),
            pool_name = str(pool_members[member]['pool-name'])
            ).set(float(pool_members[member]['serverside.max-conns']))
          node_bits_in_gauge.labels(
            address = str(pool_members[member]['addr']), 
            node_name = str(pool_members[member]['node-name']),
            pool_name = str(pool_members[member]['pool-name'])
            ).set(float(pool_members[member]['serverside.bits-in']))
          node_bits_out_gauge.labels(
            address = str(pool_members[member]['addr']), 
            node_name = str(pool_members[member]['node-name']),
            pool_name = str(pool_members[member]['pool-name'])
            ).set(float(pool_members[member]['serverside.bits-out']))
          node_balancing_state_gauge.labels(
            address = str(pool_members[member]['addr']), 
            node_name = str(pool_members[member]['node-name']),
            pool_name = str(pool_members[member]['pool-name'])
          ).set(node_state)
    time.sleep(t)

if __name__ == '__main__':
  # Start up the server to expose the metrics.
  start_http_server(settings.EXPORTER_PORT)
  logging.info(f'Started f5-exporter on port {settings.EXPORTER_PORT}')
  # Generate some requests.
  while True:
    process_request(settings.F5_REQUEST_INTERVAL)
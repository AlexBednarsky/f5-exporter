from asyncio.log import logger
import envparse
import json

try:
  F5_HOST: list = json.loads(
    envparse.env('F5_HOST', '["192.168.50.8"]')
  )
except json.decoder.JSONDecodeError:
  logger.fatal(f'Incorrect structure of F5_HOST variable, current value is: %s', envparse.env('F5_HOST'))
  exit()
F5_USER: str = str(envparse.env('F5_USER', 'user'))
F5_PASS: str = str(envparse.env('F5_PASS', 'password'))
F5_PORT: int = int(envparse.env('F5_PORT', 22))
F5_REQUEST_INTERVAL: int = int(envparse.env('F5_REQUEST_INTERVAL', 30))
LOGLEVEL: str = str(envparse.env('LOGLEVEL', 'ERROR'))
EXPORTER_PORT: int = int(envparse.env('EXPORTER_PORT', 9094))

node_info_labels: list = [
  'balancer',
  'address',
  'node_name',
  'pool_name',
]

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
F5_USER: str = envparse.env('F5_USER', 'user')
F5_PASS: str = envparse.env('F5_PASS', 'password')
F5_PORT: int = envparse.env('F5_PORT', 22)
F5_REQUEST_INTERVAL: int = envparse.env('F5_REQUEST_INTERVAL', 30)
LOGLEVEL: str = envparse.env('LOGLEVEL', 'ERROR')
EXPORTER_PORT: int = envparse.env('EXPORTER_PORT', 9093)
node_info_labels: list = [
  'address',
  'node_name',
  'pool_name'
]

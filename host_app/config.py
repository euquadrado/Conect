import os

RELAY_HOST = os.environ.get(
    'CONECT_RELAY_HOST',
    '127.0.0.1'
)

PORTS = [5938]

JPEG_QUALITY = int(os.environ.get('CONECT_JPEG_QUALITY', '72'))
FPS = int(os.environ.get('CONECT_FPS', '30'))
MONITOR_INDEX = int(os.environ.get('CONECT_MONITOR_INDEX', '1'))
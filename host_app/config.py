import os

RELAY_HOST = os.environ.get(
    'CONECT_RELAY_HOST',
    'ec2-15-228-9-137.sa-east-1.compute.amazonaws.com'
)

PORTS = [5938]

JPEG_QUALITY = int(os.environ.get('CONECT_JPEG_QUALITY', '72'))
FPS = int(os.environ.get('CONECT_FPS', '30'))
MONITOR_INDEX = int(os.environ.get('CONECT_MONITOR_INDEX', '1'))

def server_settings(role):
    from PySide6.QtCore import QSettings
    return QSettings(QSettings.IniFormat, QSettings.UserScope, 'Conect', role)


def load_server(role):
    return str(server_settings(role).value('relay_host', RELAY_HOST))


def save_server(role, address):
    import ipaddress
    import re
    address = address.strip()
    if not address:
        raise ValueError('Informe o IP ou o nome do servidor.')
    try:
        ipaddress.IPv4Address(address)
    except ValueError:
        if len(address) > 253 or not all(
            re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label)
            for label in address.split('.')
        ):
            raise ValueError('Use um IP ou domínio, sem https://, porta ou caminho.')
        if re.fullmatch(r'[0-9.]+', address):
            raise ValueError('Endereço IPv4 inválido.')
    settings = server_settings(role)
    settings.setValue('relay_host', address)
    settings.sync()
    if settings.status().value != 0:
        raise OSError('Não foi possível salvar o endereço neste computador.')
    return address

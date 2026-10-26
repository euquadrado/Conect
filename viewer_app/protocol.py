import json, socket, struct
HEADER = 5
TYPE_FRAME = b'F'; TYPE_MOUSE = b'M'; TYPE_KEY = b'K'; TYPE_INFO = b'I'; TYPE_CLOSE = b'C'
def configure_socket(sock):
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024*1024)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024*1024)
    except Exception: pass
    return sock
def send_packet(sock, packet_type, payload=b''):
    if isinstance(packet_type, str): packet_type = packet_type.encode('ascii')
    if isinstance(payload, str): payload = payload.encode('utf-8')
    sock.sendall(packet_type[:1] + struct.pack('!I', len(payload)) + payload)
def recv_exact(sock, size):
    data=b''
    while len(data)<size:
        chunk=sock.recv(size-len(data))
        if not chunk: return None
        data+=chunk
    return data
def recv_packet(sock):
    header=recv_exact(sock, HEADER)
    if not header: return None, None
    size=struct.unpack('!I', header[1:])[0]
    payload=recv_exact(sock, size) if size else b''
    if payload is None: return None, None
    return header[:1], payload
def send_json_line(sock, data):
    sock.sendall(json.dumps(data, separators=(',', ':')).encode('utf-8') + b'\n')
def recv_json_line(sock):
    buff=b''
    while not buff.endswith(b'\n'):
        chunk=sock.recv(1)
        if not chunk: raise ConnectionError('conexão encerrada')
        buff+=chunk
    return json.loads(buff.decode('utf-8'))
def json_bytes(data): return json.dumps(data, separators=(',', ':')).encode('utf-8')
def parse_json(payload): return json.loads(payload.decode('utf-8'))

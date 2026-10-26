import socket, threading, time
from protocol import recv_json_line, send_json_line, configure_socket
from config import PORTS
HOST='0.0.0.0'
hosts={}
lock=threading.Lock()
def close_socket(sock):
    try: sock.shutdown(socket.SHUT_RDWR)
    except Exception: pass
    try: sock.close()
    except Exception: pass
def pipe(src, dst, label):
    try:
        while True:
            data=src.recv(262144)
            if not data: break
            dst.sendall(data)
    except Exception: pass
    finally:
        close_socket(src); close_socket(dst)
        print('[RELAY] sessão encerrada:', label)
def handle_client(conn, addr):
    conn=configure_socket(conn)
    try:
        hello=recv_json_line(conn); role=hello.get('role')
        if role=='host':
            host_id=str(hello.get('host_id','')).strip(); password=str(hello.get('password','')).strip()
            if not(host_id.isdigit() and len(host_id)==9 and password.isdigit() and len(password)==4):
                send_json_line(conn, {'ok':False,'error':'ID precisa ter 9 dígitos e senha 4 dígitos'}); close_socket(conn); return
            with lock:
                old=hosts.get(host_id)
                if old: close_socket(old['conn'])
                hosts[host_id]={'password':password,'conn':conn,'addr':addr,'created':time.time()}
            send_json_line(conn, {'ok':True,'message':'host registrado'})
            print('[HOST]', host_id, 'online em', addr); return
        if role=='viewer':
            host_id=str(hello.get('host_id','')).strip(); password=str(hello.get('password','')).strip()
            with lock: host=hosts.pop(host_id, None)
            if not host or host.get('password') != password:
                send_json_line(conn, {'ok':False,'error':'host offline, ID inexistente ou senha incorreta'}); close_socket(conn)
                print('[VIEWER] falha para host', host_id, 'em', addr); return
            host_conn=host['conn']
            send_json_line(conn, {'ok':True,'message':'viewer conectado ao host'})
            send_json_line(host_conn, {'ok':True,'message':'viewer conectado'})
            print('[RELAY] viewer', addr, 'conectado ao host', host_id)
            threading.Thread(target=pipe,args=(conn,host_conn,'viewer->host'),daemon=True).start()
            threading.Thread(target=pipe,args=(host_conn,conn,'host->viewer'),daemon=True).start(); return
        send_json_line(conn, {'ok':False,'error':'role inválida'}); close_socket(conn)
    except Exception as exc:
        print('[ERRO]', addr, exc); close_socket(conn)
def listen(port):
    server=configure_socket(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, port)); server.listen(100)
    print(f'[SERVER] ouvindo em {HOST}:{port}')
    while True:
        conn, addr=server.accept()
        threading.Thread(target=handle_client,args=(conn,addr),daemon=True).start()
if __name__=='__main__':
    print('Conect AWS Relay iniciado')
    for port in PORTS: threading.Thread(target=listen,args=(port,),daemon=True).start()
    while True: time.sleep(3600)

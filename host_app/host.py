import ctypes


def enable_dpi_awareness():
    """Precisa rodar antes do MSS/Qt para evitar captura cortada em monitores com escala 125%, 150% etc."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# IMPORTANTE: chama antes de importar mss/pyautogui/Qt
# Isso corrige o caso do monitor 1920x1080 aparecer como 1536x864 e vir cortado.
enable_dpi_awareness()

import random
import socket
import sys
import threading
import time

import cv2
import mss
import numpy as np
import pyautogui
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QFrame

from protocol import (
    TYPE_FRAME, TYPE_MOUSE, TYPE_KEY, TYPE_INFO,
    recv_json_line, recv_packet, send_json_line,
    send_packet, parse_json, json_bytes, configure_socket
)
from config import RELAY_HOST as SERVER_HOST, PORTS, JPEG_QUALITY, FPS, MONITOR_INDEX

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0


def random_id():
    return str(random.randint(100000000, 999999999))


def random_password():
    return str(random.randint(1000, 9999))


def connect_server():
    last_error = None
    for port in PORTS:
        try:
            sock = configure_socket(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
            sock.settimeout(10)
            sock.connect((SERVER_HOST, port))
            sock.settimeout(None)
            return sock, port
        except Exception as exc:
            last_error = exc
    raise ConnectionError(last_error)


def monitor_valido(monitors, index):
    """
    No MSS:
    0 = todos os monitores
    1 = monitor principal
    2 = segundo monitor
    Aqui usamos apenas monitores individuais, então começa em 1.
    """
    try:
        index = int(index)
    except Exception:
        index = 1

    if index < 1:
        return 1

    if index >= len(monitors):
        return 1

    return index


class UiBus(QObject):
    status = Signal(str)


class HostWorker:
    def __init__(self, ui, host_id, password):
        self.ui = ui
        self.host_id = host_id
        self.password = password
        self.running = False
        self.sock = None

        self.monitor_index = int(MONITOR_INDEX)
        self.monitor_left = 0
        self.monitor_top = 0
        self.monitor_width = 1
        self.monitor_height = 1
        self.monitor_count = 1
        self.monitor_lock = threading.Lock()

    def start(self):
        self.running = True
        threading.Thread(target=self.run, daemon=True).start()

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass

    def run(self):
        while self.running:
            try:
                self.ui.status.emit(f'Conectando ao relay AWS {SERVER_HOST}...')
                self.sock, port = connect_server()

                send_json_line(
                    self.sock,
                    {
                        'role': 'host',
                        'host_id': self.host_id,
                        'password': self.password
                    }
                )

                answer = recv_json_line(self.sock)
                if not answer.get('ok'):
                    self.ui.status.emit(answer.get('error', 'erro ao registrar host'))
                    time.sleep(3)
                    continue

                self.ui.status.emit('Online na porta %s. Aguardando viewer...' % port)

                viewer = recv_json_line(self.sock)
                if not viewer.get('ok'):
                    self.ui.status.emit('Viewer não autorizado')
                    continue

                self.ui.status.emit('Viewer conectado. Transmitindo tela...')
                threading.Thread(target=self.control_loop, daemon=True).start()
                self.capture_loop()

            except Exception as exc:
                if self.running:
                    self.ui.status.emit(f'Conexão encerrada. Reconectando em 2s... {exc}')
                    time.sleep(2)

    def enviar_info_monitor(self, index, monitor, frame_width, frame_height):
        """
        Envia para o Viewer o tamanho REAL do frame capturado.
        Isso evita corte quando o Windows está com escala diferente em cada monitor.
        """
        self.monitor_left = int(monitor.get('left', 0))
        self.monitor_top = int(monitor.get('top', 0))
        self.monitor_width = max(1, int(frame_width))
        self.monitor_height = max(1, int(frame_height))

        send_packet(self.sock, TYPE_INFO, json_bytes({
            'action': 'monitor_info',
            'width': self.monitor_width,
            'height': self.monitor_height,
            'left': self.monitor_left,
            'top': self.monitor_top,
            'monitor_index': index,
            'monitor_count': self.monitor_count
        }))

        self.ui.status.emit(
            f'Monitor {index}/{self.monitor_count} selecionado: '
            f'{self.monitor_width}x{self.monitor_height}. Transmitindo tela...'
        )

    def capture_loop(self):
        with mss.mss() as sct:
            self.monitor_count = max(1, len(sct.monitors) - 1)

            print('\nMonitores detectados pelo MSS:')
            for i, monitor in enumerate(sct.monitors):
                print(f'{i} -> {monitor}')

            with self.monitor_lock:
                self.monitor_index = monitor_valido(sct.monitors, self.monitor_index)
                current_index = self.monitor_index

            monitor = sct.monitors[current_index]
            last_info = None

            delay = 1.0 / max(1, FPS)
            encode_params = [
                int(cv2.IMWRITE_JPEG_QUALITY), int(JPEG_QUALITY),
                int(cv2.IMWRITE_JPEG_OPTIMIZE), 1
            ]

            while self.running:
                started = time.time()

                with self.monitor_lock:
                    requested_index = monitor_valido(sct.monitors, self.monitor_index)

                if requested_index != current_index:
                    current_index = requested_index
                    monitor = sct.monitors[current_index]
                    last_info = None

                raw = np.array(sct.grab(monitor))
                frame = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
                frame_h, frame_w = frame.shape[:2]

                info = (
                    current_index,
                    int(monitor.get('left', 0)),
                    int(monitor.get('top', 0)),
                    int(frame_w),
                    int(frame_h),
                    int(self.monitor_count)
                )

                if info != last_info:
                    self.enviar_info_monitor(current_index, monitor, frame_w, frame_h)
                    last_info = info

                ok, encoded = cv2.imencode('.jpg', frame, encode_params)
                if ok:
                    send_packet(self.sock, TYPE_FRAME, encoded.tobytes())

                elapsed = time.time() - started
                if elapsed < delay:
                    time.sleep(delay - elapsed)

    def control_loop(self):
        while self.running:
            packet_type, payload = recv_packet(self.sock)
            if not packet_type:
                break

            try:
                data = parse_json(payload)

                if packet_type == TYPE_MOUSE:
                    self.handle_mouse(data)
                elif packet_type == TYPE_KEY:
                    self.handle_key(data)
                elif packet_type == TYPE_INFO:
                    self.handle_info(data)

            except Exception:
                pass

    def handle_info(self, data):
        action = data.get('action')

        if action == 'set_monitor':
            try:
                new_index = int(data.get('monitor_index', 1))
                with self.monitor_lock:
                    self.monitor_index = new_index
            except Exception:
                pass

    def handle_mouse(self, data):
        action = data.get('action')
        x = int(data.get('x', 0)) + int(self.monitor_left)
        y = int(data.get('y', 0)) + int(self.monitor_top)
        button = data.get('button', 'left')

        if action == 'move':
            pyautogui.moveTo(x, y, duration=0)
        elif action == 'down':
            pyautogui.moveTo(x, y, duration=0)
            pyautogui.mouseDown(button=button)
        elif action == 'up':
            pyautogui.moveTo(x, y, duration=0)
            pyautogui.mouseUp(button=button)
        elif action == 'scroll':
            pyautogui.moveTo(x, y, duration=0)
            pyautogui.scroll(int(data.get('delta', 0)) * 4)

    def handle_key(self, data):
        action = data.get('action')
        key = data.get('key')
        text = data.get('text', '')
        try:
            if action == 'text' and text:
                pyautogui.write(text, interval=0)
            elif action == 'press' and key:
                pyautogui.press(key)
            elif action == 'down' and key:
                pyautogui.keyDown(key)
            elif action == 'up' and key:
                pyautogui.keyUp(key)
        except Exception:
            pass


class HostWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.bus = UiBus()
        self.bus.status.connect(self.set_status)
        self.setWindowTitle('Conect Host')
        self.setMinimumSize(380, 460)
        self.build_ui()

    def build_ui(self):
        self.setStyleSheet('''
            QWidget { background: #f5f7fb; font-family: Segoe UI; color: #1f2937; }
            QLabel#title { font-size: 26px; font-weight: 800; color: #2563eb; }
            QLabel#sub { font-size: 13px; color: #6b7280; }
            QFrame#card { background: white; border-radius: 18px; border: 1px solid #e5e7eb; }
            QLineEdit { background: #f9fafb; border: 1px solid #d1d5db; border-radius: 10px; padding: 10px; font-size: 20px; font-weight: 700; }
            QPushButton { background: #2563eb; color: white; border-radius: 12px; padding: 11px; font-weight: 700; }
            QPushButton#stop { background: #ef4444; }
            QPushButton#copy { background: #0f172a; }
        ''')

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)

        title = QLabel('Conect')
        title.setObjectName('title')

        sub = QLabel('Compartilhe seu ID e senha apenas com quem você autoriza.')
        sub.setObjectName('sub')

        root.addWidget(title)
        root.addWidget(sub)

        card = QFrame()
        card.setObjectName('card')
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)

        card_layout.addWidget(QLabel('Seu ID'))
        self.id_edit = QLineEdit(random_id())
        self.id_edit.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.id_edit)

        card_layout.addWidget(QLabel('Senha de sessão'))
        self.pass_edit = QLineEdit(random_password())
        self.pass_edit.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.pass_edit)

        self.copy_btn = QPushButton('Copiar ID e senha')
        self.copy_btn.setObjectName('copy')
        self.copy_btn.clicked.connect(self.copy_credentials)
        card_layout.addWidget(self.copy_btn)

        buttons = QHBoxLayout()
        self.start_btn = QPushButton('Iniciar Host')
        self.stop_btn = QPushButton('Parar')
        self.stop_btn.setObjectName('stop')
        self.start_btn.clicked.connect(self.start_host)
        self.stop_btn.clicked.connect(self.stop_host)
        buttons.addWidget(self.start_btn)
        buttons.addWidget(self.stop_btn)
        card_layout.addLayout(buttons)

        root.addWidget(card)

        self.status = QLabel('Offline')
        self.status.setObjectName('sub')
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        root.addStretch()

    def copy_credentials(self):
        text = f'ID: {self.id_edit.text().strip()} | Senha: {self.pass_edit.text().strip()}'
        QGuiApplication.clipboard().setText(text)
        self.status.setText('ID e senha copiados.')

    def set_status(self, text):
        self.status.setText(text)

    def start_host(self):
        host_id = self.id_edit.text().strip()
        password = self.pass_edit.text().strip()

        if not (host_id.isdigit() and len(host_id) == 9 and password.isdigit() and len(password) == 4):
            self.status.setText('ID deve ter 9 dígitos e senha 4 dígitos.')
            return

        if self.worker:
            return

        self.worker = HostWorker(self.bus, host_id, password)
        self.worker.start()
        self.start_btn.setEnabled(False)

    def stop_host(self):
        if self.worker:
            self.worker.stop()
            self.worker = None

        self.start_btn.setEnabled(True)
        self.status.setText('Offline')


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = HostWindow()
    win.show()
    sys.exit(app.exec())

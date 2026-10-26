import ctypes


def enable_dpi_awareness():
    """Evita corte/escala errada no Windows quando há monitores com DPI diferente."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# Chama antes do Qt iniciar.
enable_dpi_awareness()

import socket
import sys
import threading

import cv2
import numpy as np
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QImage, QPixmap, QGuiApplication, QPainter
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame, QSizePolicy
)

from protocol import (
    TYPE_FRAME, TYPE_MOUSE, TYPE_KEY, TYPE_INFO,
    recv_json_line, recv_packet, send_json_line,
    send_packet, parse_json, json_bytes, configure_socket
)
from config import load_server, save_server, RELAY_HOST as SERVER_HOST, PORTS

QT_KEY_MAP = {
    Qt.Key_Return: 'enter', Qt.Key_Enter: 'enter', Qt.Key_Backspace: 'backspace', Qt.Key_Delete: 'delete',
    Qt.Key_Tab: 'tab', Qt.Key_Escape: 'esc', Qt.Key_Space: 'space', Qt.Key_Left: 'left', Qt.Key_Right: 'right',
    Qt.Key_Up: 'up', Qt.Key_Down: 'down', Qt.Key_Home: 'home', Qt.Key_End: 'end', Qt.Key_PageUp: 'pageup',
    Qt.Key_PageDown: 'pagedown', Qt.Key_Control: 'ctrl', Qt.Key_Shift: 'shift', Qt.Key_Alt: 'alt',
    Qt.Key_F1: 'f1', Qt.Key_F2: 'f2', Qt.Key_F3: 'f3', Qt.Key_F4: 'f4',
    Qt.Key_F5: 'f5', Qt.Key_F6: 'f6', Qt.Key_F7: 'f7', Qt.Key_F8: 'f8',
    Qt.Key_F9: 'f9', Qt.Key_F10: 'f10', Qt.Key_F11: 'f11', Qt.Key_F12: 'f12'
}


def qt_key_to_pyautogui(event):
    key = QT_KEY_MAP.get(event.key())
    if key:
        return key

    k = event.key()

    if Qt.Key_A <= k <= Qt.Key_Z:
        return chr(ord('a') + k - Qt.Key_A)

    if Qt.Key_0 <= k <= Qt.Key_9:
        return chr(ord('0') + k - Qt.Key_0)

    return None


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


class UiBus(QObject):
    status = Signal(str)
    frame = Signal(QImage)
    monitor_info = Signal(int, int, int, int)


class ScreenLabel(QLabel):
    def __init__(self, window):
        super().__init__()
        self.window = window

        self.setAlignment(Qt.AlignCenter)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(300, 200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet('background: #111827; border-radius: 14px;')

        self.remote_w = 1
        self.remote_h = 1

        self.draw_w = 1
        self.draw_h = 1
        self.draw_off_x = 0
        self.draw_off_y = 0

        self.original_pixmap = None

    def set_remote_size(self, w, h):
        self.remote_w = max(1, int(w))
        self.remote_h = max(1, int(h))
        self.update()

    def set_frame(self, image):
        self.original_pixmap = QPixmap.fromImage(image)

        # Segurança extra: se o Host ainda não mandou INFO, usa o tamanho real do frame.
        if self.remote_w <= 1 or self.remote_h <= 1:
            self.remote_w = max(1, image.width())
            self.remote_h = max(1, image.height())

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.black)

        if self.original_pixmap is None:
            return

        # Essa é a parte principal: caber dentro do espaço disponível SEM cortar.
        scaled = self.original_pixmap.scaled(
            self.width(),
            self.height(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.draw_w = max(1, scaled.width())
        self.draw_h = max(1, scaled.height())
        self.draw_off_x = (self.width() - self.draw_w) / 2
        self.draw_off_y = (self.height() - self.draw_h) / 2

        painter.drawPixmap(int(self.draw_off_x), int(self.draw_off_y), scaled)

    def map_pos(self, event):
        if self.original_pixmap is None:
            return None

        x_on_image = event.position().x() - self.draw_off_x
        y_on_image = event.position().y() - self.draw_off_y

        if x_on_image < 0 or y_on_image < 0:
            return None

        if x_on_image > self.draw_w or y_on_image > self.draw_h:
            return None

        x = x_on_image * (self.remote_w / self.draw_w)
        y = y_on_image * (self.remote_h / self.draw_h)

        x = max(0, min(self.remote_w - 1, int(x)))
        y = max(0, min(self.remote_h - 1, int(y)))

        return x, y

    def button_name(self, button):
        if button == Qt.RightButton:
            return 'right'
        if button == Qt.MiddleButton:
            return 'middle'
        return 'left'

    def mouseMoveEvent(self, event):
        pos = self.map_pos(event)
        if pos:
            self.window.send_mouse('move', pos[0], pos[1])

    def mousePressEvent(self, event):
        self.setFocus()
        pos = self.map_pos(event)
        if pos:
            self.window.send_mouse('down', pos[0], pos[1], self.button_name(event.button()))

    def mouseReleaseEvent(self, event):
        pos = self.map_pos(event)
        if pos:
            self.window.send_mouse('up', pos[0], pos[1], self.button_name(event.button()))

    def wheelEvent(self, event):
        pos = self.map_pos(event)
        if pos:
            delta = 1 if event.angleDelta().y() > 0 else -1
            self.window.send_mouse('scroll', pos[0], pos[1], delta=delta)

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return

        text = event.text()
        key = qt_key_to_pyautogui(event)
        has_modifier = bool(event.modifiers() & (Qt.ControlModifier | Qt.AltModifier))

        if text and text.isprintable() and not has_modifier:
            self.window.send_key('text', text=text)
        elif key:
            self.window.send_key('down', key=key)

    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            return

        key = qt_key_to_pyautogui(event)
        if key:
            self.window.send_key('up', key=key)


class ViewerWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.sock = None
        self.remote_w = 1
        self.remote_h = 1
        self.current_monitor = 1
        self.monitor_count = 1

        self.bus = UiBus()
        self.bus.status.connect(self.set_status)
        self.bus.frame.connect(self.show_frame)
        self.bus.monitor_info.connect(self.apply_monitor_info)

        self.setWindowTitle('Conect Viewer')
        self.setMinimumSize(980, 680)
        self.build_ui()

    def build_ui(self):
        # Mantém as cores originais dos botões.
        self.setStyleSheet('''
            QWidget { background: #f5f7fb; font-family: Segoe UI; color: #1f2937; }
            QLabel#title { font-size: 26px; font-weight: 800; color: #2563eb; }
            QLabel#sub { font-size: 13px; color: #6b7280; }
            QFrame#card { background: white; border-radius: 18px; border: 1px solid #e5e7eb; }
            QLineEdit { background: #f9fafb; border: 1px solid #d1d5db; border-radius: 10px; padding: 10px; font-size: 16px; }
            QPushButton { background: #2563eb; color: white; border-radius: 12px; padding: 11px; font-weight: 700; }
            QPushButton#monitor { background: #0f172a; }
            QPushButton#fullscreen { background: #16a34a; }
        ''')

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)

        header = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel('Conect Viewer')
        title.setObjectName('title')

        sub = QLabel('Digite o ID e a senha informados pelo Host para iniciar o suporte.')
        sub.setObjectName('sub')

        title_box.addWidget(title)
        title_box.addWidget(sub)
        header.addLayout(title_box)
        root.addLayout(header)

        root.addWidget(QLabel('Endereço do servidor'))
        server_row = QHBoxLayout()
        self.server_edit = QLineEdit(load_server('Viewer'))
        self.server_edit.setPlaceholderText('IP ou domínio do relay')
        self.server_edit.setStyleSheet('font-size: 13px; font-weight: 400;')
        self.server_save_btn = QPushButton('Salvar servidor')
        self.server_save_btn.clicked.connect(self.save_server_address)
        server_row.addWidget(self.server_edit, 1)
        server_row.addWidget(self.server_save_btn)
        root.addLayout(server_row)

        card = QFrame()
        card.setObjectName('card')
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)

        self.id_edit = QLineEdit()
        self.id_edit.setMaxLength(9)
        self.id_edit.setPlaceholderText('ID de 9 dígitos')

        self.pass_edit = QLineEdit()
        self.pass_edit.setMaxLength(4)
        self.pass_edit.setPlaceholderText('Senha')

        self.connect_btn = QPushButton('Conectar')
        self.connect_btn.clicked.connect(self.connect_viewer)

        self.monitor_btn = QPushButton('Monitor 1')
        self.monitor_btn.setObjectName('monitor')
        self.monitor_btn.clicked.connect(self.switch_monitor)
        self.monitor_btn.setEnabled(False)

        self.fullscreen_btn = QPushButton('Tela cheia')
        self.fullscreen_btn.setObjectName('fullscreen')
        self.fullscreen_btn.clicked.connect(self.toggle_fullscreen)

        card_layout.addWidget(self.id_edit)
        card_layout.addWidget(self.pass_edit)
        card_layout.addWidget(self.connect_btn)
        card_layout.addWidget(self.monitor_btn)
        card_layout.addWidget(self.fullscreen_btn)

        root.addWidget(card)

        self.screen = ScreenLabel(self)
        root.addWidget(self.screen, 1)

        self.status = QLabel('Desconectado')
        self.status.setObjectName('sub')
        root.addWidget(self.status)

    def save_server_address(self):
        global SERVER_HOST
        try:
            SERVER_HOST = save_server('Viewer', self.server_edit.text())
            self.server_edit.setText(SERVER_HOST)
            self.status.setText('Servidor salvo. Será usado na próxima conexão.')
            return True
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc))
            return False

    def set_status(self, text):
        self.status.setText(text)

    def apply_monitor_info(self, index, count, width, height):
        self.current_monitor = max(1, int(index))
        self.monitor_count = max(1, int(count))
        self.remote_w = max(1, int(width))
        self.remote_h = max(1, int(height))

        self.screen.set_remote_size(self.remote_w, self.remote_h)
        self.monitor_btn.setText(f'Monitor {self.current_monitor}')
        self.monitor_btn.setEnabled(self.monitor_count > 1)
        self.status.setText(
            f'Monitor {self.current_monitor}/{self.monitor_count} - '
            f'{self.remote_w}x{self.remote_h}. Recebendo tela...'
        )

    def connect_viewer(self):
        if not self.save_server_address():
            return
        host_id = self.id_edit.text().strip()
        password = self.pass_edit.text().strip()

        if not (host_id.isdigit() and len(host_id) == 9 and password.isdigit() and len(password) == 4):
            self.status.setText('Digite ID com 9 dígitos e senha com 4 dígitos.')
            return

        self.connect_btn.setEnabled(False)
        threading.Thread(target=self.worker, daemon=True).start()

    def worker(self):
        try:
            self.bus.status.emit(f'Conectando ao relay AWS {SERVER_HOST}...')
            self.sock, port = connect_server()

            send_json_line(
                self.sock,
                {
                    'role': 'viewer',
                    'host_id': self.id_edit.text().strip(),
                    'password': self.pass_edit.text().strip()
                }
            )

            answer = recv_json_line(self.sock)

            if not answer.get('ok'):
                self.bus.status.emit(answer.get('error', 'falha na conexão'))
                self.connect_btn.setEnabled(True)
                return

            self.bus.status.emit('Conectado na porta %s. Recebendo tela...' % port)
            self.receive_loop()

        except Exception as exc:
            self.bus.status.emit('Erro: %s' % exc)
            try:
                self.connect_btn.setEnabled(True)
            except Exception:
                pass

    def receive_loop(self):
        while True:
            packet_type, payload = recv_packet(self.sock)

            if not packet_type:
                self.bus.status.emit('Sessão encerrada')
                break

            if packet_type == TYPE_INFO:
                info = parse_json(payload)

                width = int(info.get('width', 1))
                height = int(info.get('height', 1))
                index = int(info.get('monitor_index', 1))
                count = int(info.get('monitor_count', 1))

                print(f'MONITOR RECEBIDO: {index}/{count} - {width}x{height}')
                self.bus.monitor_info.emit(index, count, width, height)

            elif packet_type == TYPE_FRAME:
                arr = np.frombuffer(payload, dtype=np.uint8)
                frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)

                if frame is None:
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape

                image = QImage(
                    rgb.data,
                    w,
                    h,
                    ch * w,
                    QImage.Format_RGB888
                ).copy()

                # Se por algum motivo o INFO vier errado, o frame real corrige a escala.
                if self.remote_w <= 1 or self.remote_h <= 1:
                    self.remote_w = w
                    self.remote_h = h
                    self.screen.set_remote_size(w, h)

                self.bus.frame.emit(image)

    def show_frame(self, image):
        self.screen.set_remote_size(self.remote_w, self.remote_h)
        self.screen.set_frame(image)

    def switch_monitor(self):
        if not self.sock:
            self.status.setText('Conecte primeiro antes de trocar o monitor.')
            return

        next_monitor = self.current_monitor + 1
        if next_monitor > self.monitor_count:
            next_monitor = 1

        self.request_monitor(next_monitor)

    def request_monitor(self, monitor_index):
        try:
            send_packet(self.sock, TYPE_INFO, json_bytes({
                'action': 'set_monitor',
                'monitor_index': int(monitor_index)
            }))
            self.status.setText(f'Solicitando monitor {monitor_index}...')
        except Exception as exc:
            self.status.setText(f'Erro ao trocar monitor: {exc}')

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_btn.setText('Tela cheia')
        else:
            self.showFullScreen()
            self.fullscreen_btn.setText('Sair da tela cheia')

    def send_mouse(self, action, x, y, button='left', delta=0):
        if not self.sock:
            return

        data = {
            'action': action,
            'x': x,
            'y': y,
            'button': button,
            'delta': delta
        }

        try:
            send_packet(self.sock, TYPE_MOUSE, json_bytes(data))
        except Exception:
            pass

    def send_key(self, action, key=None, text=''):
        if not self.sock:
            return

        data = {
            'action': action,
            'key': key,
            'text': text
        }

        try:
            send_packet(self.sock, TYPE_KEY, json_bytes(data))
        except Exception:
            pass


if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = ViewerWindow()
    import os
    if os.environ.get("CONECT_SELF_TEST_REPORT"):
        win.setAttribute(Qt.WA_DontShowOnScreen, True)
    win.show()
    if os.environ.get('CONECT_SELF_TEST_REPORT'):
        from pathlib import Path
        import json
        from PySide6.QtCore import qVersion
        app.processEvents()
        Path(os.environ['CONECT_SELF_TEST_REPORT']).write_text(
            json.dumps({'status': 'ok', 'qt': qVersion(), 'window': win.windowTitle(), 'platform': app.platformName(),
                        'server_field': win.server_edit.text(), 'visible': win.isVisible()}),
            encoding='utf-8')
        win.close()
        sys.exit(0)
    sys.exit(app.exec())

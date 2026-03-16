import socket
import threading
import time

from PySide6.QtCore import QObject, Qt, QSize, Signal, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class VideoReceiver(QObject):
    frame_received = Signal(bytes)
    status_changed = Signal(str)
    fps_updated = Signal(float)
    remote_resolution_changed = Signal(int, int)
    stream_resolution_changed = Signal(int, int)

    def __init__(self, host, port, password):
        super().__init__()
        self.host = host
        self.port = port
        self.password = password
        self.running = False
        self.sock = None
        self.last_frame_time = None

    def start(self):
        self.running = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self.running = False
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass

    def _recv_exact(self, sock, size):
        data = b""
        while len(data) < size and self.running:
            chunk = sock.recv(size - len(data))
            if not chunk:
                return None
            data += chunk
        return data

    def _run(self):
        try:
            self.status_changed.emit("Conectando vídeo...")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.host, self.port))

            self.sock.sendall(f"AUTH {self.password}".encode("utf-8"))
            auth_reply = self.sock.recv(1024).decode(errors="ignore").strip()

            if "AUTH_OK" not in auth_reply:
                self.status_changed.emit("Falha na autenticação do vídeo")
                return

            self.sock.settimeout(None)
            self.status_changed.emit("Vídeo conectado")

            while self.running:
                header = self._recv_exact(self.sock, 20)
                if not header:
                    break

                original_w = int.from_bytes(header[0:4], "big")
                original_h = int.from_bytes(header[4:8], "big")
                scaled_w = int.from_bytes(header[8:12], "big")
                scaled_h = int.from_bytes(header[12:16], "big")
                frame_len = int.from_bytes(header[16:20], "big")

                if frame_len <= 0:
                    continue

                frame_data = self._recv_exact(self.sock, frame_len)
                if not frame_data:
                    break

                self.remote_resolution_changed.emit(original_w, original_h)
                self.stream_resolution_changed.emit(scaled_w, scaled_h)

                now = time.time()
                if self.last_frame_time is not None:
                    delta = now - self.last_frame_time
                    if delta > 0:
                        self.fps_updated.emit(1.0 / delta)
                self.last_frame_time = now

                self.frame_received.emit(frame_data)

        except Exception as e:
            self.status_changed.emit(f"Erro no vídeo: {e}")
        finally:
            self.stop()
            self.status_changed.emit("Vídeo desconectado")


class ControlClient(QObject):
    status_changed = Signal(str)

    def __init__(self, host, port, password, history_callback=None):
        super().__init__()
        self.host = host
        self.port = port
        self.password = password
        self.history_callback = history_callback
        self.sock = None
        self.connected = False
        self.lock = threading.Lock()

    def log(self, text):
        if callable(self.history_callback):
            self.history_callback(text)

    def connect_control(self):
        try:
            self.status_changed.emit("Conectando controle...")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(8)
            self.sock.connect((self.host, self.port))

            self.sock.sendall(f"AUTH {self.password}".encode("utf-8"))
            auth_reply = self.sock.recv(1024).decode(errors="ignore").strip()

            if "AUTH_OK" not in auth_reply:
                self.status_changed.emit("Falha na autenticação do controle")
                self.log("Falha na autenticação do controle")
                return False

            self.sock.settimeout(None)
            self.connected = True
            self.status_changed.emit("Conectado")
            self.log(f"Controle conectado em {self.host}:{self.port}")
            return True

        except Exception as e:
            self.connected = False
            self.status_changed.emit(f"Erro controle: {e}")
            self.log(f"Erro ao conectar controle: {e}")
            return False

    def send_command(self, command):
        if not self.connected or not self.sock:
            return
        try:
            with self.lock:
                self.sock.sendall((command + "\n").encode("utf-8"))
        except Exception:
            self.connected = False

    def send_frame_info(self, original_w, original_h, scaled_w, scaled_h):
        self.send_command(f"FRAMEINFO {original_w} {original_h} {scaled_w} {scaled_h}")

    def previous_monitor(self):
        self.send_command("MONITOR_PREV")

    def next_monitor(self):
        self.send_command("MONITOR_NEXT")

    def mouse_click(self, x, y):
        self.send_command(f"MOUSE_CLICK {x} {y}")

    def mouse_down(self, x, y):
        self.send_command(f"MOUSE_DOWN {x} {y}")

    def mouse_up(self, x, y):
        self.send_command(f"MOUSE_UP {x} {y}")

    def mouse_drag(self, x, y):
        self.send_command(f"MOUSE_DRAG {x} {y}")

    def send_key(self, key_name):
        self.send_command(f"KEY {key_name}")

    def close(self):
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.connected = False


class RemoteScreenLabel(QLabel):
    def __init__(self, parent_session=None):
        super().__init__()
        self.parent_session = parent_session

    def mousePressEvent(self, event):
        if self.parent_session and event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            self.parent_session.handle_mouse_click(pos.x(), pos.y())
        super().mousePressEvent(event)


class RemoteSessionWindow(QWidget):
    def __init__(
        self,
        host,
        password,
        history_callback=None,
        machine_id="---",
        control_port=5000,
        video_port=6000,
        video_host=None,
        parent=None,
    ):
        super().__init__(parent)

        self.host = host
        self.video_host = video_host or host
        self.password = password
        self.history_callback = history_callback
        self.machine_id = machine_id
        self.control_port = control_port
        self.video_port = video_port

        self.current_pixmap = QPixmap()
        self.remote_screen_size = QSize(1536, 864)
        self.stream_size = QSize(960, 540)
        self.current_fps = 0.0

        self.last_original_w = 1536
        self.last_original_h = 864
        self.last_scaled_w = 960
        self.last_scaled_h = 540

        self.is_full_mode = False

        self.control_client = ControlClient(
            host=self.host,
            port=self.control_port,
            password=self.password,
            history_callback=self.history_callback,
        )

        self.video_receiver = VideoReceiver(
            host=self.video_host,
            port=self.video_port,
            password=self.password,
        )

        self.setup_ui()
        self.apply_styles()
        self.bind_signals()
        self.start_connections()

        QTimer.singleShot(150, self.adjust_video_viewport)

    def log(self, text):
        if callable(self.history_callback):
            self.history_callback(text)

    def setup_ui(self):
        self.setWindowTitle(f"Conect - Sessão Remota ({self.machine_id})")
        self.setMinimumSize(900, 540)
        self.showMaximized()

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        self.main_layout.setSpacing(4)

        self.top_frame = QFrame()
        self.top_frame.setObjectName("top_frame")
        self.top_layout = QHBoxLayout(self.top_frame)
        self.top_layout.setContentsMargins(8, 6, 8, 6)
        self.top_layout.setSpacing(6)

        self.machine_title_label = QLabel(f"Máquina {self.machine_id}")
        self.machine_title_label.setObjectName("machine_title_label")
        self.top_layout.addWidget(self.machine_title_label)

        self.top_layout.addStretch()

        self.btn_prev_monitor = self.create_tool_button("◀", "Monitor anterior")
        self.btn_next_monitor = self.create_tool_button("▶", "Próximo monitor")
        self.btn_fullscreen = self.create_tool_button("⛶", "Tela cheia")
        self.btn_restore = self.create_tool_button("↺", "Voltar")

        self.btn_prev_monitor.clicked.connect(self.request_previous_monitor)
        self.btn_next_monitor.clicked.connect(self.request_next_monitor)
        self.btn_fullscreen.clicked.connect(self.enter_full_mode)
        self.btn_restore.clicked.connect(self.exit_full_mode)

        self.status_label = self.create_badge("Status: Conectando")
        self.fps_label = self.create_badge("FPS: 0.0")
        self.monitor_label = self.create_badge("Monitor: 1536x864")
        self.stream_label = self.create_badge("Stream: 960x540")

        self.top_layout.addWidget(self.btn_prev_monitor)
        self.top_layout.addWidget(self.btn_next_monitor)
        self.top_layout.addWidget(self.btn_fullscreen)
        self.top_layout.addWidget(self.btn_restore)
        self.top_layout.addWidget(self.status_label)
        self.top_layout.addWidget(self.fps_label)
        self.top_layout.addWidget(self.monitor_label)
        self.top_layout.addWidget(self.stream_label)

        self.close_button = QPushButton("Encerrar")
        self.close_button.setObjectName("close_button")
        self.close_button.setFixedHeight(28)
        self.close_button.setMinimumWidth(82)
        self.close_button.clicked.connect(self.close)
        self.top_layout.addWidget(self.close_button)

        self.main_layout.addWidget(self.top_frame)

        self.video_frame = QFrame()
        self.video_frame.setObjectName("video_frame")

        self.video_layout = QVBoxLayout(self.video_frame)
        self.video_layout.setContentsMargins(0, 0, 0, 0)
        self.video_layout.setSpacing(0)

        self.video_center = QFrame()
        self.video_center.setObjectName("video_center")

        self.video_center_layout = QVBoxLayout(self.video_center)
        self.video_center_layout.setContentsMargins(0, 0, 0, 0)
        self.video_center_layout.setSpacing(0)

        self.screen_label = RemoteScreenLabel(self)
        self.screen_label.setText("Aguardando imagem remota...")
        self.screen_label.setObjectName("screen_label")
        self.screen_label.setAlignment(Qt.AlignCenter)
        self.screen_label.setMinimumSize(1, 1)
        self.screen_label.setMaximumSize(16777215, 16777215)
        self.screen_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.screen_label.setScaledContents(False)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addStretch()
        row.addWidget(self.screen_label)
        row.addStretch()

        self.video_center_layout.addStretch()
        self.video_center_layout.addLayout(row)
        self.video_center_layout.addStretch()

        self.video_layout.addWidget(self.video_center)
        self.main_layout.addWidget(self.video_frame, 1)

    def apply_styles(self):
        self.setStyleSheet("""
            QWidget {
                background: #f3f6fb;
                color: #16324f;
                font-size: 13px;
                font-family: Segoe UI, Arial;
            }

            QFrame#top_frame {
                background: #eef3f9;
                border: 1px solid #d6e0ea;
                border-radius: 12px;
            }

            QFrame#video_frame, QFrame#video_center {
                background: #000000;
                border: none;
                border-radius: 10px;
            }

            QLabel#machine_title_label {
                font-size: 18px;
                font-weight: 700;
                color: #173a63;
            }

            QLabel#screen_label {
                background: #000000;
                border: 1px solid #202020;
                border-radius: 8px;
                color: #d7dde5;
                font-size: 15px;
            }

            QLabel[badge="true"] {
                background: #edf4fb;
                border: 1px solid #c7d8ea;
                border-radius: 10px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
                color: #174067;
                min-height: 16px;
            }

            QPushButton#tool_btn {
                background: #eef3f8;
                border: 1px solid #c8d6e4;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 700;
                color: #123456;
            }

            QPushButton#tool_btn:hover {
                background: #e3edf7;
            }

            QPushButton#tool_btn:pressed {
                background: #d7e6f4;
            }

            QPushButton#close_button {
                background: #e8f0fb;
                border: 1px solid #c8d8eb;
                border-radius: 9px;
                padding: 0 12px;
                font-size: 11px;
                font-weight: 700;
                color: #18406a;
            }

            QPushButton#close_button:hover {
                background: #dfeaf8;
            }
        """)

    def create_badge(self, text):
        label = QLabel(text)
        label.setProperty("badge", True)
        label.setAlignment(Qt.AlignCenter)
        label.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        return label

    def create_tool_button(self, text, tooltip):
        btn = QPushButton(text)
        btn.setObjectName("tool_btn")
        btn.setToolTip(tooltip)
        btn.setFixedSize(34, 34)
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        return btn

    def bind_signals(self):
        self.control_client.status_changed.connect(self.on_status_changed)
        self.video_receiver.frame_received.connect(self.on_frame_received)
        self.video_receiver.status_changed.connect(self.on_video_status_changed)
        self.video_receiver.fps_updated.connect(self.on_fps_updated)
        self.video_receiver.remote_resolution_changed.connect(self.on_remote_resolution_changed)
        self.video_receiver.stream_resolution_changed.connect(self.on_stream_resolution_changed)

    def start_connections(self):
        ok = self.control_client.connect_control()
        if not ok:
            QMessageBox.warning(
                self,
                "Conexão",
                f"Não foi possível conectar no controle em {self.host}:{self.control_port}",
            )

        self.video_receiver.start()
        self.log(f"Sessão iniciada com {self.machine_id}")

    def get_remote_aspect_size(self):
        w = self.last_original_w if self.last_original_w > 0 else 1
        h = self.last_original_h if self.last_original_h > 0 else 1
        return w, h

    def adjust_video_viewport(self):
        remote_w, remote_h = self.get_remote_aspect_size()

        area_w = max(1, self.video_center.width() - 20)
        area_h = max(1, self.video_center.height() - 20)

        if area_w <= 1 or area_h <= 1 or remote_w <= 0 or remote_h <= 0:
            return

        scale = min(area_w / remote_w, area_h / remote_h)

        target_w = max(1, int(remote_w * scale))
        target_h = max(1, int(remote_h * scale))

        self.screen_label.setFixedSize(target_w, target_h)

        if not self.current_pixmap.isNull():
            scaled = self.current_pixmap.scaled(
                target_w,
                target_h,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.screen_label.setPixmap(scaled)

    def update_screen_pixmap(self, pixmap):
        self.current_pixmap = pixmap
        QTimer.singleShot(0, self.adjust_video_viewport)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.adjust_video_viewport)

    def closeEvent(self, event):
        try:
            self.video_receiver.stop()
        except Exception:
            pass

        try:
            self.control_client.close()
        except Exception:
            pass

        self.log(f"Sessão encerrada com {self.machine_id}")
        super().closeEvent(event)

    def enter_full_mode(self):
        self.is_full_mode = True
        self.showFullScreen()
        QTimer.singleShot(100, self.adjust_video_viewport)

    def exit_full_mode(self):
        self.is_full_mode = False
        self.showMaximized()
        QTimer.singleShot(100, self.adjust_video_viewport)

    def request_previous_monitor(self):
        self.control_client.previous_monitor()
        self.log("Solicitado monitor anterior")

    def request_next_monitor(self):
        self.control_client.next_monitor()
        self.log("Solicitado próximo monitor")

    def on_status_changed(self, text):
        self.status_label.setText(f"Status: {text}")

    def on_video_status_changed(self, text):
        if "Vídeo conectado" in text:
            self.status_label.setText("Status: Conectado")
        elif "Falha" in text or "Erro" in text:
            self.status_label.setText(f"Status: {text}")

    def on_fps_updated(self, fps):
        self.current_fps = float(fps)
        self.fps_label.setText(f"FPS: {self.current_fps:.1f}")

    def on_remote_resolution_changed(self, width, height):
        self.last_original_w = width
        self.last_original_h = height
        self.remote_screen_size = QSize(width, height)
        self.monitor_label.setText(f"Monitor: {width}x{height}")
        QTimer.singleShot(0, self.adjust_video_viewport)

    def on_stream_resolution_changed(self, width, height):
        self.last_scaled_w = width
        self.last_scaled_h = height
        self.stream_size = QSize(width, height)
        self.stream_label.setText(f"Stream: {width}x{height}")
        self.control_client.send_frame_info(
            self.last_original_w,
            self.last_original_h,
            self.last_scaled_w,
            self.last_scaled_h,
        )

    def on_frame_received(self, frame_data):
        image = QImage.fromData(frame_data)
        if image.isNull():
            return

        pixmap = QPixmap.fromImage(image)
        if pixmap.isNull():
            return

        self.update_screen_pixmap(pixmap)

    def handle_mouse_click(self, label_x, label_y):
        if self.current_pixmap.isNull():
            return

        current = self.screen_label.pixmap()
        if current is None:
            return

        label_w = self.screen_label.width()
        label_h = self.screen_label.height()
        pix_w = current.width()
        pix_h = current.height()

        if pix_w <= 0 or pix_h <= 0:
            return

        offset_x = (label_w - pix_w) // 2
        offset_y = (label_h - pix_h) // 2

        inner_x = label_x - offset_x
        inner_y = label_y - offset_y

        if inner_x < 0 or inner_y < 0 or inner_x > pix_w or inner_y > pix_h:
            return

        stream_x = int(inner_x * self.last_scaled_w / max(1, pix_w))
        stream_y = int(inner_y * self.last_scaled_h / max(1, pix_h))

        self.control_client.mouse_click(stream_x, stream_y)

    def keyPressEvent(self, event):
        key = event.key()

        key_map = {
            Qt.Key_Return: "enter",
            Qt.Key_Enter: "enter",
            Qt.Key_Backspace: "backspace",
            Qt.Key_Tab: "tab",
            Qt.Key_Escape: "esc",
            Qt.Key_Space: "space",
            Qt.Key_Up: "up",
            Qt.Key_Down: "down",
            Qt.Key_Left: "left",
            Qt.Key_Right: "right",
            Qt.Key_F1: "f1",
            Qt.Key_F2: "f2",
            Qt.Key_F3: "f3",
            Qt.Key_F4: "f4",
            Qt.Key_F5: "f5",
            Qt.Key_F6: "f6",
            Qt.Key_F7: "f7",
            Qt.Key_F8: "f8",
            Qt.Key_F9: "f9",
            Qt.Key_F10: "f10",
            Qt.Key_F11: "f11",
            Qt.Key_F12: "f12",
        }

        if key in key_map:
            self.control_client.send_key(key_map[key])
            return

        text = event.text()
        if text and text.isprintable():
            self.control_client.send_key(text)
            return

        super().keyPressEvent(event)
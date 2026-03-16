import datetime
import json
import os
import socket
import subprocess
import sys
import threading
import time

try:
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
except Exception:
    ctypes = None

import cv2
import mss
import numpy as np
import pyautogui
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.conect_utils import (
    DISCOVERY_PORT,
    generate_password,
    generate_persistent_machine_id,
    get_local_ip,
    load_json,
    save_json,
)

HOST = "0.0.0.0"
CONTROL_PORT = 5000
VIDEO_PORT = 6000

MAX_STREAM_WIDTH = 1280
MAX_STREAM_HEIGHT = 720
JPEG_QUALITY = 60
TARGET_FPS = 30
FRAME_TIME = 1.0 / TARGET_FPS

server_running = True
stream_paused = False

PASSWORD = ""
SERVER_MACHINE_ID = ""
SERVER_MACHINE_NAME = socket.gethostname()

selected_monitor_index = 1
monitor_lock = threading.Lock()
stream_lock = threading.Lock()


class ServerSignals(QObject):
    log = Signal(str)
    password = Signal(str)
    status = Signal(str)
    machine = Signal(str, str, str)


signals = ServerSignals()


def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def app_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def ensure_runtime_dirs():
    os.makedirs(os.path.join(app_base_dir(), "ui"), exist_ok=True)


def get_config_file():
    ensure_runtime_dirs()
    return os.path.join(app_base_dir(), "ui", "conect_local_config.json")


def load_or_create_server_identity():
    default = {
        "machine_id": generate_persistent_machine_id(),
        "machine_password": generate_password(),
        "machine_name": socket.gethostname(),
    }

    data = load_json(get_config_file(), default)

    if not data.get("machine_id"):
        data["machine_id"] = generate_persistent_machine_id()
    if not data.get("machine_password"):
        data["machine_password"] = generate_password()
    if not data.get("machine_name"):
        data["machine_name"] = socket.gethostname()

    save_json(get_config_file(), data)
    return data


def log(msg: str):
    agora = datetime.datetime.now().strftime("%H:%M:%S")
    signals.log.emit(f"[{agora}] {msg}")


def get_monitors():
    with mss.mss() as sct:
        monitors = []
        for idx, mon in enumerate(sct.monitors[1:], start=1):
            monitors.append({
                "left": int(mon["left"]),
                "top": int(mon["top"]),
                "width": int(mon["width"]),
                "height": int(mon["height"]),
                "right": int(mon["left"] + mon["width"]),
                "bottom": int(mon["top"] + mon["height"]),
                "device": f"MONITOR_{idx}",
                "is_primary": idx == 1,
            })
        return monitors


def get_selected_monitor():
    monitors = get_monitors()
    if not monitors:
        return None, 0, 0

    global selected_monitor_index
    with monitor_lock:
        if selected_monitor_index < 1:
            selected_monitor_index = 1
        if selected_monitor_index > len(monitors):
            selected_monitor_index = len(monitors)

        mon = monitors[selected_monitor_index - 1]
        return mon, selected_monitor_index, len(monitors)


def monitor_label_text():
    mon, idx, total = get_selected_monitor()
    if not mon:
        return "Nenhum monitor detectado"
    return (
        f"Monitor {idx}/{total} - "
        f"{mon['width']}x{mon['height']} "
        f"(left={mon['left']}, top={mon['top']})"
    )


def cycle_monitor(step: int):
    global selected_monitor_index
    monitors = get_monitors()
    if not monitors:
        return

    with monitor_lock:
        selected_monitor_index += step
        if selected_monitor_index < 1:
            selected_monitor_index = len(monitors)
        elif selected_monitor_index > len(monitors):
            selected_monitor_index = 1

    log(f"Monitor alterado para: {monitor_label_text()}")


def set_stream_paused(value: bool):
    global stream_paused
    with stream_lock:
        stream_paused = value


def is_stream_paused() -> bool:
    with stream_lock:
        return stream_paused


def resize_frame_keep_aspect(frame):
    h, w = frame.shape[:2]
    if w <= 0 or h <= 0:
        return frame

    scale = min(MAX_STREAM_WIDTH / w, MAX_STREAM_HEIGHT / h, 1.0)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))

    if new_w == w and new_h == h:
        return frame

    return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)


def autenticar(conn: socket.socket, tipo: str) -> bool:
    global PASSWORD
    try:
        data = conn.recv(1024).decode(errors="ignore").strip()

        if not data:
            conn.close()
            log(f"{tipo}: pacote vazio")
            return False

        if data.startswith("AUTH "):
            senha = data.split(" ", 1)[1].strip()
        else:
            senha = data.strip()

        if senha != PASSWORD:
            try:
                conn.sendall(b"AUTH_FAIL")
            except Exception:
                pass
            conn.close()
            log(f"{tipo}: senha incorreta")
            return False

        try:
            conn.sendall(b"AUTH_OK")
        except Exception:
            pass

        log(f"{tipo} autenticado com sucesso.")
        return True

    except Exception as e:
        log(f"Erro de autenticação: {e}")
        return False


def enviar_video(conn: socket.socket):
    try:
        with mss.mss() as sct:
            while server_running:
                start = time.perf_counter()

                if is_stream_paused():
                    time.sleep(FRAME_TIME)
                    continue

                monitor, _, _ = get_selected_monitor()
                if not monitor:
                    time.sleep(0.1)
                    continue

                capture_area = {
                    "left": int(monitor["left"]),
                    "top": int(monitor["top"]),
                    "width": int(monitor["width"]),
                    "height": int(monitor["height"]),
                }

                screenshot = sct.grab(capture_area)
                frame = np.asarray(screenshot, dtype=np.uint8)
                frame = frame[:, :, :3]

                original_h, original_w = frame.shape[:2]
                frame = resize_frame_keep_aspect(frame)

                ok, buffer = cv2.imencode(
                    ".jpg",
                    frame,
                    [
                        int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY,
                        int(cv2.IMWRITE_JPEG_OPTIMIZE), 0,
                    ],
                )

                if not ok:
                    elapsed = time.perf_counter() - start
                    sleep_time = FRAME_TIME - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    continue

                scaled_h, scaled_w = frame.shape[:2]
                data = buffer.tobytes()

                header = (
                    int(original_w).to_bytes(4, "big") +
                    int(original_h).to_bytes(4, "big") +
                    int(scaled_w).to_bytes(4, "big") +
                    int(scaled_h).to_bytes(4, "big") +
                    int(len(data)).to_bytes(4, "big")
                )

                conn.sendall(header + data)

                elapsed = time.perf_counter() - start
                sleep_time = FRAME_TIME - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

    except Exception as e:
        log(f"Erro vídeo: {e}")
    finally:
        try:
            conn.close()
        except OSError:
            pass
        log("Cliente de vídeo desconectado.")


def executar_tecla(tecla: str):
    try:
        especiais = {
            "enter": "enter",
            "backspace": "backspace",
            "tab": "tab",
            "esc": "esc",
            "space": "space",
            "up": "up",
            "down": "down",
            "left": "left",
            "right": "right",
        }

        tecla_lower = tecla.lower()

        if tecla_lower in especiais:
            pyautogui.press(especiais[tecla_lower])
            return

        if tecla_lower.startswith("f") and tecla_lower[1:].isdigit():
            pyautogui.press(tecla_lower)
            return

        combos = {
            "CTRL_C": ("ctrl", "c"),
            "CTRL_V": ("ctrl", "v"),
            "CTRL_X": ("ctrl", "x"),
            "CTRL_S": ("ctrl", "s"),
            "CTRL_Z": ("ctrl", "z"),
        }

        if tecla in combos:
            pyautogui.hotkey(*combos[tecla])
            return

        if tecla.startswith("SHIFT+"):
            pyautogui.hotkey("shift", tecla.split("+", 1)[1].lower())
            return

        if tecla.startswith("ALT+"):
            pyautogui.hotkey("alt", tecla.split("+", 1)[1].lower())
            return

        pyautogui.press(tecla_lower)

    except Exception:
        pass


def map_stream_to_monitor(x: int, y: int, original_w: int, original_h: int, scaled_w: int, scaled_h: int):
    monitor, _, _ = get_selected_monitor()
    if not monitor:
        return x, y

    if scaled_w <= 0 or scaled_h <= 0:
        return monitor["left"], monitor["top"]

    rel_x = x / scaled_w
    rel_y = y / scaled_h

    rel_x = max(0.0, min(rel_x, 1.0))
    rel_y = max(0.0, min(rel_y, 1.0))

    real_x = int(monitor["left"] + rel_x * original_w)
    real_y = int(monitor["top"] + rel_y * original_h)

    real_x = max(monitor["left"], min(real_x, monitor["left"] + original_w - 1))
    real_y = max(monitor["top"], min(real_y, monitor["top"] + original_h - 1))

    return real_x, real_y


def receber_comandos(conn: socket.socket):
    last_original_w = 1
    last_original_h = 1
    last_scaled_w = 1
    last_scaled_h = 1

    try:
        while server_running:
            pkg = conn.recv(4096)
            if not pkg:
                break

            mensagens = pkg.decode(errors="ignore").replace("\r", "").split("\n")

            for bruto in mensagens:
                msg = bruto.strip()
                if not msg:
                    continue

                if msg == "MONITOR_NEXT":
                    cycle_monitor(1)
                    continue

                if msg == "MONITOR_PREV":
                    cycle_monitor(-1)
                    continue

                if msg in ("STREAM_PAUSE", "PAUSE_STREAM"):
                    set_stream_paused(True)
                    log("Stream pausado pelo cliente.")
                    continue

                if msg in ("STREAM_RESUME", "RESUME_STREAM"):
                    set_stream_paused(False)
                    log("Stream retomado pelo cliente.")
                    continue

                if msg.startswith("FRAMEINFO "):
                    partes = msg.split()
                    if len(partes) == 5:
                        try:
                            last_original_w = int(partes[1])
                            last_original_h = int(partes[2])
                            last_scaled_w = int(partes[3])
                            last_scaled_h = int(partes[4])
                        except Exception:
                            pass
                    continue

                if msg.startswith("KEY "):
                    executar_tecla(msg.split(" ", 1)[1])
                    continue

                if msg.startswith("MOUSE_"):
                    partes = msg.split()
                    if len(partes) != 3:
                        log(f"Pacote mouse inválido: {msg}")
                        continue

                    acao, xs, ys = partes
                    try:
                        x = int(xs)
                        y = int(ys)
                    except ValueError:
                        log(f"Coordenadas inválidas: {msg}")
                        continue

                    real_x, real_y = map_stream_to_monitor(
                        x, y,
                        last_original_w, last_original_h,
                        last_scaled_w, last_scaled_h
                    )

                    if acao == "MOUSE_DOWN":
                        pyautogui.mouseDown(real_x, real_y)
                    elif acao == "MOUSE_DRAG":
                        pyautogui.moveTo(real_x, real_y)
                    elif acao == "MOUSE_UP":
                        pyautogui.mouseUp(real_x, real_y)
                    elif acao == "MOUSE_CLICK":
                        pyautogui.click(real_x, real_y)

    except Exception as e:
        log(f"Erro controle: {e}")
    finally:
        try:
            conn.close()
        except OSError:
            pass
        log("Cliente de controle desconectado.")


def iniciar_controle():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, CONTROL_PORT))
    s.listen(5)

    log(f"Controle ouvindo em {CONTROL_PORT}")

    while server_running:
        try:
            conn, addr = s.accept()
        except OSError:
            break

        log(f"Cliente (controle) conectado: {addr}")

        if not autenticar(conn, "CONTROLE"):
            continue

        threading.Thread(target=receber_comandos, args=(conn,), daemon=True).start()

    try:
        s.close()
    except Exception:
        pass


def iniciar_video():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, VIDEO_PORT))
    s.listen(5)

    log(f"Vídeo ouvindo em {VIDEO_PORT}")

    while server_running:
        try:
            conn, addr = s.accept()
        except OSError:
            break

        log(f"Cliente (vídeo) conectado: {addr}")

        if not autenticar(conn, "VÍDEO"):
            continue

        threading.Thread(target=enviar_video, args=(conn,), daemon=True).start()

    try:
        s.close()
    except Exception:
        pass


def discovery_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        sock.bind(("", DISCOVERY_PORT))
    except Exception as e:
        log(f"Discovery UDP não iniciou: {e}")
        return

    log(f"Discovery UDP ativo na porta {DISCOVERY_PORT}")

    while server_running:
        try:
            data, addr = sock.recvfrom(4096)
        except Exception:
            continue

        try:
            payload = json.loads(data.decode("utf-8", errors="ignore"))
        except Exception:
            continue

        if payload.get("type") != "CONECT_DISCOVERY_REQUEST":
            continue

        response = {
            "type": "CONECT_DISCOVERY",
            "machine_id": SERVER_MACHINE_ID,
            "machine_name": SERVER_MACHINE_NAME,
            "ip": get_local_ip(),
            "control_port": CONTROL_PORT,
            "video_port": VIDEO_PORT,
        }

        try:
            sock.sendto(json.dumps(response).encode("utf-8"), addr)
        except Exception:
            pass

    try:
        sock.close()
    except Exception:
        pass


def broadcast_presence():
    while server_running:
        try:
            local_ip = get_local_ip()
            payload = {
                "type": "CONECT_DISCOVERY",
                "machine_id": SERVER_MACHINE_ID,
                "machine_name": SERVER_MACHINE_NAME,
                "ip": local_ip,
                "control_port": CONTROL_PORT,
                "video_port": VIDEO_PORT,
            }

            data = json.dumps(payload).encode("utf-8")

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.sendto(data, ("255.255.255.255", DISCOVERY_PORT))
            sock.close()

            signals.machine.emit(SERVER_MACHINE_ID, local_ip, SERVER_MACHINE_NAME)
        except Exception as e:
            log(f"Falha ao anunciar na LAN: {e}")

        time.sleep(2)


def get_tailscale_ip():
    candidates = ["tailscale", r"C:\Program Files\Tailscale\tailscale.exe"]

    for binary in candidates:
        try:
            result = subprocess.run(
                [binary, "status", "--json"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                self_info = data.get("Self") or {}
                ips = self_info.get("TailscaleIPs") or []
                return ips[0] if ips else ""
        except Exception:
            continue

    return ""


class ServerWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        identity = load_or_create_server_identity()
        self.machine_id = identity["machine_id"]

        global PASSWORD, SERVER_MACHINE_ID, SERVER_MACHINE_NAME
        PASSWORD = identity["machine_password"]
        SERVER_MACHINE_ID = identity["machine_id"]
        SERVER_MACHINE_NAME = identity["machine_name"]

        self.setWindowTitle("Conect - Servidor")
        icon_path = resource_path(os.path.join("imagens", "pc_icon.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setStyleSheet("QWidget { background-color: #edf3f9; font-family: Segoe UI, Arial; }")

        screen = QGuiApplication.primaryScreen().availableGeometry()
        w = min(1000, max(860, screen.width() - 30))
        h = min(620, max(540, screen.height() - 30))
        self.resize(w, h)

        self.setup_ui()

        signals.log.connect(self.append_log)
        signals.password.connect(self.set_password)
        signals.status.connect(self.set_status)
        signals.machine.connect(self.on_machine_updated)

        self.set_password(PASSWORD)
        self.start_threads()

    def setup_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        main = QHBoxLayout(root)
        main.setContentsMargins(10, 10, 10, 10)
        main.setSpacing(10)

        left = QFrame()
        left.setStyleSheet("QFrame { background-color: white; border: 1px solid #d6e2f0; border-radius: 18px; }")

        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(10)

        title = QLabel("Servidor do Conect")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #123f6b;")

        subtitle = QLabel("Abra no PC do cliente. A troca de monitor é controlada apenas pelo viewer.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #5f7892; font-size: 12px;")

        info_row = QHBoxLayout()
        info_row.setSpacing(8)

        self.password_card = self.info_card("Senha", "----")
        self.id_card = self.info_card("ID da máquina", self.machine_id)
        self.ip_card = self.info_card("IP Local", get_local_ip())
        self.control_card = self.info_card("Porta Controle", str(CONTROL_PORT))
        self.video_card = self.info_card("Porta Vídeo", str(VIDEO_PORT))

        for card in [
            self.password_card,
            self.id_card,
            self.ip_card,
            self.control_card,
            self.video_card,
        ]:
            info_row.addWidget(card)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet(
            "QTextEdit { background-color: #f8fbfe; border: 1px solid #d1deec; "
            "border-radius: 14px; padding: 8px; font-size: 12px; color: #1f2d3a; }"
        )

        left_layout.addWidget(title)
        left_layout.addWidget(subtitle)
        left_layout.addLayout(info_row)
        left_layout.addWidget(self.log_box, 1)

        right = QFrame()
        right.setMinimumWidth(220)
        right.setMaximumWidth(250)
        right.setStyleSheet("QFrame { background-color: white; border: 1px solid #d6e2f0; border-radius: 18px; }")

        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(12)

        panel = QLabel("Ações")
        panel.setStyleSheet("font-size: 18px; font-weight: 700; color: #0f4c8a;")

        self.status_label = QLabel("Status: inicializando")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #1f2d3a; font-size: 14px; font-weight: 600;")

        copy_id_button = QPushButton("Copiar ID e senha")
        copy_id_button.setStyleSheet(self.primary_button_style())
        copy_id_button.clicked.connect(self.copy_machine_id)

        regen_button = QPushButton("Gerar nova senha")
        regen_button.setStyleSheet(self.primary_button_style())
        regen_button.clicked.connect(self.handle_regenerate_password)

        stop_button = QPushButton("Encerrar servidor")
        stop_button.setStyleSheet(self.secondary_button_style())
        stop_button.clicked.connect(self.handle_stop)

        right_layout.addWidget(panel)
        right_layout.addWidget(self.status_label)
        right_layout.addStretch()
        right_layout.addWidget(copy_id_button)
        right_layout.addWidget(regen_button)
        right_layout.addWidget(stop_button)

        main.addWidget(left, 1)
        main.addWidget(right)

    def info_card(self, label_text: str, value_text: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet("QFrame { background-color: #f6fbff; border: 1px solid #dbe7f3; border-radius: 16px; }")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        label = QLabel(label_text)
        label.setStyleSheet("font-size: 11px; color: #6e8298; font-weight: 600;")

        value = QLabel(value_text)
        value.setWordWrap(True)
        value.setStyleSheet("font-size: 15px; color: #123f6b; font-weight: 700;")
        value.setObjectName("value_label")

        layout.addWidget(label)
        layout.addWidget(value)

        return card

    def set_card_value(self, card: QFrame, value: str):
        label = card.findChild(QLabel, "value_label")
        if label:
            label.setText(value)

    def append_log(self, message: str):
        self.log_box.append(message)

    def set_password(self, password: str):
        self.set_card_value(self.password_card, password)
        self.set_status("Status: pronto para receber conexões")

    def set_status(self, text: str):
        self.status_label.setText(text)

    def on_machine_updated(self, machine_id: str, ip: str, machine_name: str):
        self.set_card_value(self.id_card, machine_id)
        self.set_card_value(self.ip_card, ip)

    def primary_button_style(self):
        return (
            "QPushButton { background-color: #1565c0; color: white; border: none; "
            "border-radius: 12px; padding: 12px; font-size: 14px; font-weight: 700; }"
            "QPushButton:hover { background-color: #0f56a7; }"
        )

    def secondary_button_style(self):
        return (
            "QPushButton { background-color: #eef4fb; color: #0f4c8a; border: 1px solid #c8d8ea; "
            "border-radius: 12px; padding: 12px; font-size: 14px; font-weight: 700; }"
            "QPushButton:hover { background-color: #e5eef8; }"
        )

    def start_threads(self):
        threading.Thread(target=iniciar_controle, daemon=True).start()
        threading.Thread(target=iniciar_video, daemon=True).start()
        threading.Thread(target=discovery_server, daemon=True).start()
        threading.Thread(target=broadcast_presence, daemon=True).start()

        log(f"ID fixo carregado: {self.machine_id}")
        log(f"Senha atual: {PASSWORD}")
        log(f"Broadcast LAN ativo na porta {DISCOVERY_PORT}")
        log(monitor_label_text())

    def copy_machine_id(self):
        password_label = self.password_card.findChild(QLabel, "value_label")
        password_text = password_label.text() if password_label else "----"
        tailscale_ip = get_tailscale_ip()

        texto = (
            f"ID: {self.machine_id}\n"
            f"Senha: {password_text}\n"
            f"IP Local: {get_local_ip()}\n"
            f"IP Tailscale: {tailscale_ip or 'não detectado'}"
        )
        QGuiApplication.clipboard().setText(texto)
        log("ID e senha copiados para a área de transferência.")

    def handle_regenerate_password(self):
        global PASSWORD

        PASSWORD = generate_password()
        config = load_json(get_config_file(), {})
        config["machine_id"] = self.machine_id
        config["machine_password"] = PASSWORD
        config["machine_name"] = SERVER_MACHINE_NAME
        save_json(get_config_file(), config)

        signals.password.emit(PASSWORD)
        log(f"Nova senha: {PASSWORD}")

    def handle_stop(self):
        global server_running
        server_running = False
        QMessageBox.information(self, "Servidor", "Fechando o servidor.")
        self.close()

    def closeEvent(self, event):
        global server_running
        server_running = False
        super().closeEvent(event)


def main():
    ensure_runtime_dirs()
    app = QApplication([])
    window = ServerWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
import json
import os
import socket
import subprocess
import time
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .conect_utils import (
    DISCOVERY_PORT,
    generate_password,
    generate_persistent_machine_id,
    get_local_ip,
    get_registry_entry,
    ip_to_machine_id,
    load_json,
    machine_id_to_ip,
    normalize_machine_id,
    resolve_machine_id_from_registry,
    save_json,
    save_machine_to_registry,
)

from .remote_session import RemoteSessionWindow


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "conect_local_config.json")
DEFAULT_CONTROL_PORT = 5000
DEFAULT_VIDEO_PORT = 6000


class DashboardWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.active_sessions: List[RemoteSessionWindow] = []
        self.discovered_devices: List[dict] = []

        self.identity = self.load_or_create_identity()
        self.machine_id = self.identity["machine_id"]
        self.machine_password = self.identity["machine_password"]
        self.machine_name = self.identity["machine_name"]

        self.local_ip = get_local_ip()

        self.setup_ui()
        self.refresh_identity_cards()

    def load_or_create_identity(self):
        default = {
            "machine_id": generate_persistent_machine_id(),
            "machine_password": generate_password(),
            "machine_name": socket.gethostname(),
        }
        data = load_json(CONFIG_FILE, default)

        if not data.get("machine_id"):
            data["machine_id"] = generate_persistent_machine_id()
        if not data.get("machine_password"):
            data["machine_password"] = generate_password()
        if not data.get("machine_name"):
            data["machine_name"] = socket.gethostname()

        save_json(CONFIG_FILE, data)
        return data

    def setup_ui(self):
        self.setWindowTitle("Conect - Dashboard")
        self.resize(1320, 780)
        self.setStyleSheet("QWidget { background-color: #eef4fa; font-family: Segoe UI, Arial; }")

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        sidebar = QFrame()
        sidebar.setFixedWidth(230)
        sidebar.setStyleSheet("QFrame { background-color: #0f4c8a; border-radius: 20px; }")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(18, 22, 18, 22)
        sidebar_layout.setSpacing(14)

        logo = QLabel("Conect")
        logo.setFont(QFont("Segoe UI", 24, QFont.Bold))
        logo.setStyleSheet("color: white;")

        logo_sub = QLabel("Acesso remoto")
        logo_sub.setStyleSheet("color: #cfe4fb; font-size: 12px;")

        sidebar_layout.addWidget(logo)
        sidebar_layout.addWidget(logo_sub)
        sidebar_layout.addSpacing(12)

        sidebar_layout.addWidget(self.sidebar_item("Conect", True))
        sidebar_layout.addWidget(self.sidebar_item("Usuário"))
        sidebar_layout.addWidget(self.sidebar_item("Máquina"))
        sidebar_layout.addWidget(self.sidebar_item("Painel Dispositivos"))
        sidebar_layout.addWidget(self.sidebar_item("Configurações"))
        sidebar_layout.addStretch()

        footer_info = QLabel(f"Máquina:\n{self.machine_name}\n\nID:\n{self.machine_id}")
        footer_info.setWordWrap(True)
        footer_info.setStyleSheet(
            "color: #d6e8f8; font-size: 11px; background-color: rgba(255,255,255,0.08); "
            "padding: 12px; border-radius: 12px;"
        )
        sidebar_layout.addWidget(footer_info)

        root.addWidget(sidebar)

        content = QVBoxLayout()
        content.setSpacing(12)

        top_bar = QFrame()
        top_bar.setStyleSheet(
            "QFrame { background-color: white; border: 1px solid #d7e3ef; border-radius: 18px; }"
        )
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(18, 14, 18, 14)

        title_box = QVBoxLayout()
        title = QLabel("Painel Principal")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        title.setStyleSheet("color: #123f6b;")

        subtitle = QLabel("Conexão por ID + senha com descoberta automática via LAN e Tailscale.")
        subtitle.setStyleSheet("color: #5f7892; font-size: 12px;")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        top_layout.addLayout(title_box)
        top_layout.addStretch()

        self.status_chip = QLabel("Online")
        self.status_chip.setStyleSheet(
            "background-color: #e7f5ec; color: #1f7a43; font-weight: 700; "
            "padding: 8px 14px; border-radius: 12px; font-size: 12px;"
        )
        top_layout.addWidget(self.status_chip)

        content.addWidget(top_bar)

        cards_grid = QGridLayout()
        cards_grid.setSpacing(12)

        self.id_card = self.info_card("ID da máquina", self.machine_id)
        self.password_card = self.info_card("Senha atual", self.machine_password)
        self.machine_card = self.info_card("Máquina", self.machine_name)
        self.ip_card = self.info_card("IP local", self.local_ip)

        cards_grid.addWidget(self.id_card, 0, 0)
        cards_grid.addWidget(self.password_card, 0, 1)
        cards_grid.addWidget(self.machine_card, 0, 2)
        cards_grid.addWidget(self.ip_card, 0, 3)

        cards_holder = QFrame()
        cards_holder.setStyleSheet("QFrame { background: transparent; }")
        cards_holder.setLayout(cards_grid)

        content.addWidget(cards_holder)

        middle_row = QHBoxLayout()
        middle_row.setSpacing(12)

        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        connect_card = QFrame()
        connect_card.setStyleSheet(self.card_style())
        connect_layout = QVBoxLayout(connect_card)
        connect_layout.setContentsMargins(18, 18, 18, 18)
        connect_layout.setSpacing(10)

        connect_title = QLabel("Conectar à máquina")
        connect_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #123f6b;")

        connect_desc = QLabel(
            "Digite o ID da máquina remota e a senha. Você também pode usar IP Tailscale ou nome .ts.net no campo de ID."
        )
        connect_desc.setWordWrap(True)
        connect_desc.setStyleSheet("color: #60768e; font-size: 12px;")

        self.remote_id_input = QLineEdit()
        self.remote_id_input.setPlaceholderText("ID remoto, IP Tailscale ou nome .ts.net")
        self.remote_id_input.setStyleSheet(self.input_style())

        self.remote_password_input = QLineEdit()
        self.remote_password_input.setPlaceholderText("Senha remota")
        self.remote_password_input.setEchoMode(QLineEdit.Password)
        self.remote_password_input.setStyleSheet(self.input_style())

        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        connect_button = QPushButton("Conectar")
        connect_button.setStyleSheet(self.primary_button_style())
        connect_button.clicked.connect(self.connect_remote)

        copy_button = QPushButton("Copiar ID")
        copy_button.setStyleSheet(self.secondary_button_style())
        copy_button.clicked.connect(self.copy_my_id)

        refresh_button = QPushButton("Atualizar LAN")
        refresh_button.setStyleSheet(self.secondary_button_style())
        refresh_button.clicked.connect(self.discover_lan_hosts)

        action_row.addWidget(connect_button)
        action_row.addWidget(copy_button)
        action_row.addWidget(refresh_button)

        connect_layout.addWidget(connect_title)
        connect_layout.addWidget(connect_desc)
        connect_layout.addWidget(self.remote_id_input)
        connect_layout.addWidget(self.remote_password_input)
        connect_layout.addLayout(action_row)

        left_col.addWidget(connect_card)

        devices_card = QFrame()
        devices_card.setStyleSheet(self.card_style())
        devices_layout = QVBoxLayout(devices_card)
        devices_layout.setContentsMargins(18, 18, 18, 18)
        devices_layout.setSpacing(10)

        devices_title = QLabel("Painel de Dispositivos")
        devices_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #123f6b;")

        devices_desc = QLabel("Duplo clique em um dispositivo para preencher o ID automaticamente.")
        devices_desc.setStyleSheet("color: #60768e; font-size: 12px;")

        self.devices_list = QListWidget()
        self.devices_list.setStyleSheet(self.list_style())
        self.devices_list.itemDoubleClicked.connect(self.fill_remote_from_list)

        devices_layout.addWidget(devices_title)
        devices_layout.addWidget(devices_desc)
        devices_layout.addWidget(self.devices_list)

        left_col.addWidget(devices_card, 1)

        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        user_card = QFrame()
        user_card.setStyleSheet(self.card_style())
        user_layout = QVBoxLayout(user_card)
        user_layout.setContentsMargins(18, 18, 18, 18)
        user_layout.setSpacing(10)

        user_title = QLabel("Usuário")
        user_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #123f6b;")

        user_info = QLabel(
            "Login padrão carregado.\n"
            "O painel usa descoberta automática e conexão autenticada por senha."
        )
        user_info.setWordWrap(True)
        user_info.setStyleSheet("color: #60768e; font-size: 12px;")

        user_layout.addWidget(user_title)
        user_layout.addWidget(user_info)

        machine_info_card = QFrame()
        machine_info_card.setStyleSheet(self.card_style())
        machine_layout = QVBoxLayout(machine_info_card)
        machine_layout.setContentsMargins(18, 18, 18, 18)
        machine_layout.setSpacing(10)

        machine_title = QLabel("Máquina")
        machine_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #123f6b;")

        self.machine_summary = QLabel("")
        self.machine_summary.setWordWrap(True)
        self.machine_summary.setStyleSheet("color: #60768e; font-size: 12px;")

        machine_layout.addWidget(machine_title)
        machine_layout.addWidget(self.machine_summary)

        config_card = QFrame()
        config_card.setStyleSheet(self.card_style())
        config_layout = QVBoxLayout(config_card)
        config_layout.setContentsMargins(18, 18, 18, 18)
        config_layout.setSpacing(10)

        config_title = QLabel("Configurações")
        config_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #123f6b;")

        regen_button = QPushButton("Gerar nova senha")
        regen_button.setStyleSheet(self.secondary_button_style())
        regen_button.clicked.connect(self.regenerate_password)

        config_layout.addWidget(config_title)
        config_layout.addWidget(regen_button)

        history_card = QFrame()
        history_card.setStyleSheet(self.card_style())
        history_layout = QVBoxLayout(history_card)
        history_layout.setContentsMargins(18, 18, 18, 18)
        history_layout.setSpacing(10)

        history_title = QLabel("Histórico")
        history_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #123f6b;")

        self.history_box = QTextEdit()
        self.history_box.setReadOnly(True)
        self.history_box.setStyleSheet(
            "QTextEdit { background-color: #f8fbfe; border: 1px solid #d1deec; "
            "border-radius: 14px; padding: 8px; font-size: 12px; color: #1f2d3a; }"
        )

        history_layout.addWidget(history_title)
        history_layout.addWidget(self.history_box)

        right_col.addWidget(user_card)
        right_col.addWidget(machine_info_card)
        right_col.addWidget(config_card)
        right_col.addWidget(history_card, 1)

        middle_row.addLayout(left_col, 3)
        middle_row.addLayout(right_col, 2)

        content.addLayout(middle_row, 1)

        root.addLayout(content, 1)

    def sidebar_item(self, text: str, active: bool = False):
        item = QLabel(text)
        if active:
            item.setStyleSheet(
                "background-color: rgba(255,255,255,0.18); color: white; font-size: 14px; "
                "font-weight: 700; padding: 12px 14px; border-radius: 12px;"
            )
        else:
            item.setStyleSheet("color: #d6e8f8; font-size: 14px; font-weight: 600; padding: 12px 14px;")
        return item

    def refresh_identity_cards(self):
        self.local_ip = get_local_ip()
        self.set_card_value(self.id_card, self.machine_id)
        self.set_card_value(self.password_card, self.machine_password)
        self.set_card_value(self.machine_card, self.machine_name)
        self.set_card_value(self.ip_card, self.local_ip)

        self.machine_summary.setText(
            f"Nome: {self.machine_name}\n"
            f"ID: {self.machine_id}\n"
            f"IP local: {self.local_ip}\n"
            f"Status: pronto para conexão"
        )

    def input_style(self):
        return (
            "QLineEdit { background-color: #f8fbfe; border: 1px solid #d1deec; border-radius: 12px; "
            "padding: 12px; font-size: 14px; color: #1f2d3a; }"
            "QLineEdit:focus { border: 2px solid #1565c0; background-color: white; }"
        )

    def card_style(self):
        return "QFrame { background-color: white; border: 1px solid #d6e2f0; border-radius: 18px; }"

    def primary_button_style(self):
        return (
            "QPushButton { background-color: #1565c0; color: white; border: none; border-radius: 12px; "
            "padding: 12px; font-size: 14px; font-weight: 700; }"
            "QPushButton:hover { background-color: #0f56a7; }"
        )

    def secondary_button_style(self):
        return (
            "QPushButton { background-color: #eef4fb; color: #0f4c8a; border: 1px solid #c8d8ea; "
            "border-radius: 12px; padding: 12px; font-size: 14px; font-weight: 700; }"
            "QPushButton:hover { background-color: #e5eef8; }"
        )

    def list_style(self):
        return (
            "QListWidget { background-color: #f8fbfe; border: 1px solid #d1deec; border-radius: 14px; padding: 8px; }"
            "QListWidget::item { padding: 10px; border-bottom: 1px solid #e8eff6; }"
            "QListWidget::item:selected { background-color: #dfeefe; color: #123f6b; border-radius: 10px; }"
        )

    def info_card(self, label_text: str, value_text: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet("QFrame { background-color: white; border: 1px solid #d6e2f0; border-radius: 16px; }")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        label = QLabel(label_text)
        label.setStyleSheet("font-size: 11px; color: #6e8298; font-weight: 600;")

        value = QLabel(value_text)
        value.setWordWrap(True)
        value.setStyleSheet("font-size: 14px; color: #123f6b; font-weight: 700;")
        value.setObjectName("value_label")

        layout.addWidget(label)
        layout.addWidget(value)
        return card

    def set_card_value(self, card: QFrame, value: str):
        label = card.findChild(QLabel, "value_label")
        if label:
            label.setText(value)

    def add_history(self, message: str):
        stamp = time.strftime("%H:%M:%S")
        self.history_box.append(f"[{stamp}] {message}")

    def regenerate_password(self):
        self.machine_password = generate_password()
        data = self.load_or_create_identity()
        data["machine_id"] = self.machine_id
        data["machine_password"] = self.machine_password
        data["machine_name"] = self.machine_name
        save_json(CONFIG_FILE, data)
        self.refresh_identity_cards()
        self.add_history(f"Nova senha gerada: {self.machine_password}")
        QMessageBox.information(self, "Senha", f"Nova senha gerada: {self.machine_password}")

    def copy_my_id(self):
        text = f"ID: {self.machine_id}\nSenha: {self.machine_password}"
        QGuiApplication.clipboard().setText(text)
        self.add_history("ID e senha copiados para a área de transferência")

    def discover_lan_hosts(self):
        self.devices_list.clear()
        self.discovered_devices = []
        self.add_history("Procurando dispositivos via LAN e Tailscale...")

        devices = {}

        for item in self.discover_by_udp():
            key = normalize_machine_id(item.get("machine_id", "")) or item.get("host", "")
            devices[key] = item

        for item in self.get_tailscale_devices():
            key = normalize_machine_id(item.get("machine_id", "")) or item.get("host", "")
            if key in devices:
                if item.get("host"):
                    devices[key]["host"] = item["host"]
                devices[key]["source"] = "LAN + Tailscale"
            else:
                devices[key] = item

        self.discovered_devices = list(devices.values())

        if not self.discovered_devices:
            self.devices_list.addItem("Nenhum dispositivo encontrado")
            self.add_history("Nenhum dispositivo encontrado")
            return

        for device in self.discovered_devices:
            self.add_device_to_list(device)
            if device.get("machine_id") and device.get("host"):
                save_machine_to_registry(
                    device["machine_id"],
                    device["host"],
                    device.get("machine_name", ""),
                    "",
                )

        self.add_history(f"{len(self.discovered_devices)} dispositivo(s) encontrado(s)")

    def discover_by_udp(self, timeout: float = 2.0) -> List[dict]:
        results: List[dict] = []
        seen = set()

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.3)

        try:
            sock.bind(("", 0))
        except OSError:
            pass

        probe = json.dumps({"type": "CONECT_DISCOVERY_REQUEST"}).encode("utf-8")

        try:
            sock.sendto(probe, ("255.255.255.255", DISCOVERY_PORT))
        except OSError:
            pass

        end = time.time() + timeout
        while time.time() < end:
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                payload = json.loads(data.decode("utf-8", errors="ignore"))
            except Exception:
                continue

            if payload.get("type") != "CONECT_DISCOVERY":
                continue

            machine_id = payload.get("machine_id") or ip_to_machine_id(addr[0])

            if normalize_machine_id(machine_id) == normalize_machine_id(self.machine_id):
                continue

            key = (normalize_machine_id(machine_id), addr[0])
            if key in seen:
                continue
            seen.add(key)

            results.append({
                "source": "LAN",
                "machine_id": machine_id,
                "machine_name": payload.get("machine_name", ""),
                "host": payload.get("ip") or addr[0],
                "display_name": payload.get("machine_name") or machine_id,
            })

        sock.close()
        return results

    def get_tailscale_binary(self) -> str:
        candidates = ["tailscale", r"C:\\Program Files\\Tailscale\\tailscale.exe"]

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
                    return binary
            except Exception:
                continue

        return ""

    def get_tailscale_status_json(self) -> dict:
        binary = self.get_tailscale_binary()
        if not binary:
            return {}

        try:
            result = subprocess.run(
                [binary, "status", "--json"],
                capture_output=True,
                text=True,
                timeout=6,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode != 0 or not result.stdout.strip():
                return {}
            return json.loads(result.stdout)
        except Exception:
            return {}

    def get_tailscale_devices(self) -> List[dict]:
        data = self.get_tailscale_status_json()
        peers = data.get("Peer") or {}
        results: List[dict] = []

        iterable = peers.values() if isinstance(peers, dict) else peers

        for peer in iterable:
            if not isinstance(peer, dict):
                continue

            ips = peer.get("TailscaleIPs") or []
            host = ips[0] if ips else ""
            dns_name = (peer.get("DNSName") or "").rstrip(".")
            machine_name = peer.get("HostName") or dns_name or host

            if not host and not dns_name:
                continue

            machine_id = peer.get("ConectMachineID") or host or dns_name

            results.append({
                "source": "Tailscale",
                "machine_id": machine_id,
                "machine_name": machine_name,
                "host": host or dns_name,
                "display_name": machine_name,
            })

        return results

    def add_device_to_list(self, device: dict):
        source = device.get("source", "Rede")
        mid = device.get("machine_id", "Sem ID")
        name = device.get("machine_name") or device.get("display_name") or "Sem nome"

        text = f"[{source}] {name} | ID: {mid}"
        item = QListWidgetItem(text)
        item.setData(Qt.UserRole, device)
        self.devices_list.addItem(item)

    def fill_remote_from_list(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole)
        if not isinstance(data, dict):
            return

        self.remote_id_input.setText(data.get("machine_id", ""))
        self.add_history(f"Dispositivo selecionado: {data.get('display_name') or data.get('machine_name')}")

    def resolve_target_host(self, raw_id: str) -> str:
        raw_id = raw_id.strip()
        normalized = normalize_machine_id(raw_id)

        if "." in raw_id or ":" in raw_id or raw_id.lower().endswith(".ts.net"):
            return raw_id

        for device in self.discovered_devices:
            if normalize_machine_id(device.get("machine_id", "")) == normalized:
                return device.get("host", "")

        entry = get_registry_entry(raw_id)
        if entry and entry.get("ip"):
            return entry.get("ip", "")

        ip_from_machine = machine_id_to_ip(raw_id)
        if ip_from_machine:
            return ip_from_machine

        reg_ip = resolve_machine_id_from_registry(raw_id)
        if reg_ip:
            return reg_ip

        return ""

    def connect_remote(self):
        raw_id = self.remote_id_input.text().strip()
        password = self.remote_password_input.text().strip()

        if not raw_id:
            QMessageBox.warning(self, "Conexão", "Informe o ID remoto.")
            return

        if not password:
            QMessageBox.warning(self, "Conexão", "Informe a senha remota.")
            return

        host = self.resolve_target_host(raw_id)
        if not host:
            QMessageBox.warning(
                self,
                "Conexão",
                "Não foi possível localizar a máquina pelo ID informado.\nClique em Atualizar LAN primeiro."
            )
            return

        session = RemoteSessionWindow(
            host=host,
            password=password,
            history_callback=self.add_history,
            machine_id=raw_id,
            control_port=DEFAULT_CONTROL_PORT,
            video_port=DEFAULT_VIDEO_PORT,
            video_host=host,
        )
        session.show()
        self.active_sessions.append(session)

        save_machine_to_registry(raw_id, host, raw_id, "")
        self.add_history(f"Abrindo sessão para {raw_id} em {host}:{DEFAULT_CONTROL_PORT}")
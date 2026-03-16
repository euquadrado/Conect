import json
import os
import random
import socket
import uuid
from typing import Optional


DISCOVERY_PORT = 5001


def get_base_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generate_password(length: int = 4) -> str:
    return "".join(random.choices("0123456789", k=length))


def ip_to_machine_id(ip: str) -> str:
    parts = ip.split(".")
    if len(parts) != 4:
        return ip
    try:
        nums = [f"{int(p):03d}" for p in parts]
    except ValueError:
        return ip
    return " ".join(nums)


def machine_id_to_ip(machine_id: str) -> Optional[str]:
    raw = "".join(ch for ch in machine_id if ch.isdigit())
    if len(raw) != 12:
        return None
    parts = [str(int(raw[i:i+3])) for i in range(0, 12, 3)]
    try:
        valid = all(0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return None
    return ".".join(parts) if valid else None


def normalize_machine_id(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def generate_persistent_machine_id() -> str:
    raw = str(uuid.uuid4().int)[-9:]
    raw = raw.zfill(9)
    return f"{raw[:3]} {raw[3:6]} {raw[6:]}"


def get_registry_file() -> str:
    return os.path.join(get_base_dir(), "lan_registry.json")


def load_registry() -> dict:
    return load_json(get_registry_file(), {})


def save_machine_to_registry(machine_id: str, ip: str, machine_name: str = "", password: str = "") -> None:
    registry = load_registry()
    registry[machine_id] = {
        "ip": ip,
        "machine_name": machine_name,
        "password": password,
    }
    save_json(get_registry_file(), registry)


def resolve_machine_id_from_registry(machine_id: str) -> Optional[str]:
    registry = load_registry()
    normalized = normalize_machine_id(machine_id)

    for saved_id, info in registry.items():
        if normalize_machine_id(saved_id) == normalized:
            if isinstance(info, dict):
                return info.get("ip")
            if isinstance(info, str):
                return info

    return None


def get_registry_entry(machine_id: str) -> Optional[dict]:
    registry = load_registry()
    normalized = normalize_machine_id(machine_id)

    for saved_id, info in registry.items():
        if normalize_machine_id(saved_id) == normalized:
            if isinstance(info, dict):
                return info
            return {"ip": info, "machine_name": "", "password": ""}

    return None
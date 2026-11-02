"""
Dialogue Engine - Network & System IP Utilities.
Работает исключительно на стандартной библиотеке Python (без сторонних зависимостей).
"""

from __future__ import annotations
import socket


def get_lan_ip() -> str:
    """
    Определяет локальный IP-адрес компьютера в локальной сети (Wi-Fi/LAN).
    Работает на стандартной библиотеке socket без внешних пакетов.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Подключение к внешнему шлюзу без отправки пакетов для определения рабочего сетевого интерфейса
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        pass

    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"

"""
Dialogue Engine - Standalone 24/7 Cowork & Web Server.
Запускает постоянный веб-сервер движка для совместной работы (коворка)
с компьютеров, телефонов и планшетов через браузер.
"""

from __future__ import annotations
import argparse
import asyncio
import logging
import os
import socket
import sys
import webbrowser

# Добавляем корень проекта в sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    import uvicorn
    HAS_UVICORN = True
except ImportError:
    HAS_UVICORN = False

from core.network import get_lan_ip
from cowork.session import CoworkSession
from cowork.server import create_cowork_app

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DialogueEngine.Server")


def print_banner(host: str, port: int, project_path: str, session: CoworkSession) -> None:
    lan_ip = get_lan_ip()
    local_url = f"http://localhost:{port}"
    network_url = f"http://{lan_ip}:{port}"

    print("\n" + "=" * 74)
    print("  🚀 DIALOGUE ENGINE - СЕРВЕР СОВМЕСТНОЙ РАБОТЫ (КОВОРК 24/7)")
    print("=" * 74)
    print(f"  💻 Вход с этого ПК (Браузер):   {local_url}")
    print(f"  📱 Вход с телефона / планшета:  {network_url}")
    print(f"  📂 Открытый проект:             {os.path.basename(project_path)}")
    print(f"  📊 Узлов в графе:               {len(session.project_data.nodes)}")
    print("=" * 74)

    # Генерация ASCII QR-кода в терминале для сканирования камерой телефона
    if HAS_QRCODE:
        try:
            print("\n  [QR-код для быстрого входа со смартфона или планшета]:")
            qr = qrcode.QRCode(box_size=1, border=1)
            qr.add_data(network_url)
            qr.make(fit=True)
            # Вывод псевдографикой в консоль
            qr.print_ascii(invert=True)
        except Exception:
            pass

    print("  • Сервер работает непрерывно. Изменения сохраняются автоматически.")
    print("  • Для остановки сервера нажмите Ctrl+C.")
    print("=" * 74 + "\n")


def main() -> None:
    if not HAS_UVICORN:
        print("\n" + "=" * 60)
        print(" [ОШИБКА] Пакет uvicorn не установлен!")
        print(" Для работы веб-сервера установите зависимости:")
        print("   pip install -r requirements.txt")
        print("=" * 60 + "\n")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Dialogue Engine 24/7 Cowork Server")
    parser.add_argument("--host", default="0.0.0.0", help="IP адрес для прослушивания (по умолчанию 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Порт сервера (по умолчанию 8000)")
    parser.add_argument("--project", default="violant.json", help="Файл проекта для загрузки/синхронизации")
    parser.add_argument("--no-open", action="store_true", help="Не открывать браузер автоматически")
    args = parser.parse_args()

    # Проверяем и разрешаем путь к проекту
    proj_path = args.project
    if not os.path.isabs(proj_path):
        proj_path = os.path.join(SCRIPT_DIR, proj_path)

    session = CoworkSession(project_path=proj_path)
    app = create_cowork_app(session=session)

    print_banner(args.host, args.port, proj_path, session)

    if not args.no_open:
        try:
            webbrowser.open(f"http://localhost:{args.port}")
        except Exception:
            pass

    # Запуск uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()

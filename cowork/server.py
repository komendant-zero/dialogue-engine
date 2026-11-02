"""
Dialogue Engine - 24/7 Cowork Web & WebSocket Server.
Запускает FastAPI сервер для совместной работы над проектом через веб-интерфейс
с компьютеров, телефонов и планшетов.
"""

from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
import io
import json
import logging
import os
import socket
import sys
from typing import Any, Dict, Optional

try:
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, JSONResponse, Response
    from fastapi.staticfiles import StaticFiles
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from core.models import ProjectData
from core.network import get_lan_ip
from core.serialization import ProjectSerializer
from cowork.session import CoworkSession

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

logger = logging.getLogger("DialogueEngine.Server")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)


def create_cowork_app(session: Optional[CoworkSession] = None) -> Any:
    """Создает и настраивает экземпляр FastAPI приложения."""
    if not HAS_FASTAPI:
        raise ImportError(
            "Для работы сервера совместной работы не установлен FastAPI!\n"
            "Установите зависимости командой: pip install -r requirements.txt"
        )
    if session is None:
        session = CoworkSession()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(session.start_autosave_loop(interval_sec=3.0))
        logger.info("Dialogue Engine Cowork Server started.")
        try:
            yield
        finally:
            task.cancel()
            session.save_to_disk()
            logger.info("Dialogue Engine Cowork Server saved project and stopped.")

    app = FastAPI(title="Dialogue Engine Cowork Server", version="2.2.0", lifespan=lifespan)

    # Разрешаем CORS для кросс-доменных подключений с любых девайсов
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.session = session

    # REST Endpoints
    @app.get("/api/status")
    async def get_status():
        lan_ip = get_lan_ip()
        return {
            "status": "online",
            "server": "Dialogue Engine 24/7 Server",
            "version": "2.2.0",
            "lan_ip": lan_ip,
            "project_name": session.project_data.metadata.title,
            "nodes_count": len(session.project_data.nodes),
            "connections_count": len(session.project_data.connections),
            "active_users": len(session.clients),
            "collaborators": list(session.clients.values())
        }

    @app.get("/api/project")
    async def get_project():
        return session.project_data.to_dict()

    @app.post("/api/project/save")
    async def save_project():
        path = session.save_to_disk()
        return {"status": "ok", "saved_file": path}

    @app.get("/api/qr")
    async def get_qr(port: int = 8000):
        """Генерирует PNG QR-код для моментального открытия на телефоне."""
        lan_ip = get_lan_ip()
        url = f"http://{lan_ip}:{port}"

        if HAS_QRCODE:
            qr = qrcode.QRCode(box_size=6, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#4a90e2", back_color="#1e1e1e")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return Response(content=buf.getvalue(), media_type="image/png")
        else:
            raise HTTPException(status_code=501, detail="QRCode library not installed")

    # WebSocket для коворка в реальном времени
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        client_id = None
        try:
            # Первое сообщение может содержать инфо о пользователе
            raw = await websocket.receive_text()
            init_info = {}
            try:
                init_info = json.loads(raw)
            except Exception:
                pass

            client_id = await session.register_client(websocket, init_info)

            # Основной цикл обработки сообщений
            while True:
                data = await websocket.receive_text()
                await session.handle_message(client_id, data)
        except WebSocketDisconnect:
            if client_id:
                await session.unregister_client(client_id)
        except Exception as e:
            logger.error(f"WebSocket error for client {client_id}: {e}")
            if client_id:
                await session.unregister_client(client_id)

    # Статические файлы веб-клиента
    index_file = os.path.join(STATIC_DIR, "index.html")

    @app.get("/", response_class=HTMLResponse)
    async def serve_index():
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                return f.read()
        return "<h1>Dialogue Engine Web Client Loading...</h1>"

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app

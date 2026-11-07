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
from cowork.session import CoworkSession, SessionManager

try:
    import qrcode
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

logger = logging.getLogger("DialogueEngine.Server")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)


def create_cowork_app(session: Optional[CoworkSession] = None, session_manager: Optional[SessionManager] = None) -> Any:
    """Создает и настраивает экземпляр FastAPI приложения с поддержкой множественных сессий."""
    if not HAS_FASTAPI:
        raise ImportError(
            "Для работы сервера совместной работы не установлен FastAPI!\n"
            "Установите зависимости командой: pip install -r requirements.txt"
        )
    if session_manager is None:
        default_path = session.project_path if session else None
        session_manager = SessionManager(default_project_path=default_path)

    default_session = session or session_manager.get_session("violant")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async def autosave_loop():
            while True:
                await asyncio.sleep(3.0)
                await session_manager.save_all()

        task = asyncio.create_task(autosave_loop())
        logger.info("Dialogue Engine Multi-Session Cowork Server started.")
        try:
            yield
        finally:
            task.cancel()
            await session_manager.save_all()
            logger.info("Dialogue Engine Cowork Server saved all sessions and stopped.")

    app = FastAPI(title="Dialogue Engine Cowork Server", version="2.3.0", lifespan=lifespan)

    # Разрешаем CORS для кросс-доменных подключений с любых девайсов
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.session_manager = session_manager
    app.state.session = default_session

    # Авторизация по паролю для публичного доступа
    SERVER_PASSWORD = os.getenv("COWORK_PASSWORD", "SPARTA1werXYZ")
    VALID_TOKENS = set()
    import hashlib
    MASTER_TOKEN = hashlib.sha256(SERVER_PASSWORD.encode()).hexdigest()[:32] if SERVER_PASSWORD else ""
    if MASTER_TOKEN:
        VALID_TOKENS.add(MASTER_TOKEN)

    # Определение и монтирование директории спрайтов
    sprites_candidates = [
        os.getenv("SPRITES_DIR", ""),
        os.path.join(os.path.dirname(os.path.abspath(session.project_path)), "sprite"),
        os.path.join(os.path.dirname(os.path.abspath(session.project_path)), "sprites"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sprite"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sprites"),
        "/app/data/sprite",
        r"D:\projects\Violant\game\sprite",
    ]
    SPRITES_DIR = None
    for cand in sprites_candidates:
        if cand and os.path.isdir(cand):
            SPRITES_DIR = os.path.abspath(cand)
            break

    if SPRITES_DIR and os.path.isdir(SPRITES_DIR):
        app.mount("/sprites", StaticFiles(directory=SPRITES_DIR), name="sprites")
        logger.info(f"Mounted /sprites static route from {SPRITES_DIR}")

    # REST Endpoints
    @app.post("/api/auth/login")
    async def auth_login(payload: Dict[str, Any]):
        pwd = payload.get("password", "")
        if not SERVER_PASSWORD or pwd == SERVER_PASSWORD:
            return {"status": "ok", "token": MASTER_TOKEN}
        raise HTTPException(status_code=401, detail="Неверный пароль")

    @app.get("/api/auth/check")
    async def auth_check(token: Optional[str] = None):
        if not SERVER_PASSWORD:
            return {"authenticated": True, "required": False}
        if token and (token in VALID_TOKENS or token == MASTER_TOKEN):
            return {"authenticated": True, "required": True}
        return {"authenticated": False, "required": True}

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

    @app.get("/api/sessions")
    async def get_sessions():
        """Возвращает список всех сессий/комнат на сервере."""
        return session_manager.list_sessions()

    @app.get("/api/session/{session_id}/project")
    async def get_session_project(session_id: str):
        target_sess = session_manager.get_session(session_id)
        return target_sess.project_data.to_dict()

    @app.get("/api/project")
    async def get_project(session: Optional[str] = None):
        target_sess = session_manager.get_session(session or "violant")
        return target_sess.project_data.to_dict()

    @app.post("/api/project/save")
    async def save_project(session: Optional[str] = None):
        target_sess = session_manager.get_session(session or "violant")
        path = target_sess.save_to_disk()
        return {"status": "ok", "saved_file": path, "session": session or "violant"}

    @app.get("/api/project/stats")
    async def get_project_stats():
        """Статистика сценария (плагин Word Counter)."""
        nodes = session.project_data.nodes
        total_words = 0
        total_chars = 0
        char_stats = {}
        for n in nodes:
            text = (n.content or "").strip()
            w = len(text.split()) if text else 0
            c = len(text)
            total_words += w
            total_chars += c
            speaker = (n.title or "Без имени").strip()
            if speaker not in char_stats:
                char_stats[speaker] = {"lines": 0, "words": 0, "chars": 0}
            char_stats[speaker]["lines"] += 1
            char_stats[speaker]["words"] += w
            char_stats[speaker]["chars"] += c
        return {
            "total_nodes": len(nodes),
            "total_connections": len(session.project_data.connections),
            "total_words": total_words,
            "total_chars": total_chars,
            "reading_time_min": max(1, (total_words + 159) // 160),
            "characters": char_stats
        }

    @app.get("/api/sprites")
    async def get_available_sprites():
        """Возвращает список всех найденных спрайтов персонажей и их эмоций/поз."""
        from core.sprites import IMAGE_EXTENSIONS
        sprites_list = []
        if SPRITES_DIR and os.path.isdir(SPRITES_DIR):
            for root, dirs, files in os.walk(SPRITES_DIR):
                for f in sorted(files):
                    ext = os.path.splitext(f)[1].lower()
                    if ext in IMAGE_EXTENSIONS:
                        rel = os.path.relpath(os.path.join(root, f), SPRITES_DIR).replace("\\", "/")
                        base = os.path.splitext(f)[0]
                        sprites_list.append({
                            "file": f,
                            "rel_path": rel,
                            "url": f"/sprites/{rel}",
                            "name": base
                        })
        return {
            "sprites_dir": SPRITES_DIR or "",
            "count": len(sprites_list),
            "sprites": sprites_list
        }

    @app.get("/api/sprites/resolve")
    async def resolve_sprite_endpoint(character: str, emotion: str = ""):
        """Автоматически находит наиболее подходящий файл спрайта для персонажа и эмоции."""
        from core.sprites import SpriteResolver
        if not SPRITES_DIR or not os.path.isdir(SPRITES_DIR):
            return {"found": False, "url": None}
        found_path = SpriteResolver.resolve_sprite(character, emotion, sprites_root=SPRITES_DIR)
        if found_path and os.path.exists(found_path):
            rel = os.path.relpath(found_path, SPRITES_DIR).replace("\\", "/")
            return {
                "found": True,
                "url": f"/sprites/{rel}",
                "file": os.path.basename(found_path),
                "path": found_path
            }
        return {"found": False, "url": None}

    @app.get("/api/characters")
    async def get_characters():
        """Возвращает список всех зарегистрированных персонажей проекта."""
        return [c.to_dict() for c in session.project_data.characters]

    @app.post("/api/characters")
    async def update_character(payload: Dict[str, Any]):
        """Создает или обновляет персонажа проекта."""
        from core.models import CharacterData
        cname = str(payload.get("name", "")).strip()
        if not cname:
            raise HTTPException(status_code=400, detail="Имя персонажа не может быть пустым")
        
        updated = False
        for i, ch in enumerate(session.project_data.characters):
            if ch.name.strip().lower() == cname.lower():
                session.project_data.characters[i] = CharacterData.from_dict(payload)
                updated = True
                break
        if not updated:
            session.project_data.characters.append(CharacterData.from_dict(payload))
        
        session.is_dirty = True
        await session.broadcast({
            "type": "characters_list_updated",
            "characters": [c.to_dict() for c in session.project_data.characters],
            "updated_character": payload
        })
        return {"status": "ok", "characters": [c.to_dict() for c in session.project_data.characters]}

    @app.post("/api/characters/apply_color")
    async def apply_character_color(payload: Dict[str, Any]):
        """Пакетно применяет цвет имени персонажа ко всем соответствующим репликам сценария."""
        cname = str(payload.get("name", "")).strip().lower()
        color = str(payload.get("color", "")).strip()
        header_color = payload.get("header_color")
        if not cname or not color:
            raise HTTPException(status_code=400, detail="Требуется имя и цвет")

        updated_nodes = []
        for n in session.project_data.nodes:
            title_raw = (n.title or "").strip()
            # Проверяем имя персонажа, убирая эмоцию в скобках, например "Ривер (радость)" -> "ривер"
            base_name = title_raw.split("(")[0].split("[")[0].strip().lower()
            if base_name == cname:
                n.custom_data = n.custom_data or {}
                n.custom_data["header_text_color"] = color
                if header_color:
                    n.custom_data["header_color"] = header_color
                updated_nodes.append(n.to_dict())

        session.is_dirty = True
        await session.broadcast({
            "type": "batch_nodes_updated",
            "nodes": updated_nodes
        })
        return {"status": "ok", "updated_count": len(updated_nodes), "nodes": updated_nodes}

    @app.get("/api/project/export/renpy")
    async def export_renpy():
        """Экспорт сценария в чистый Ren'Py script.rpy (плагин Ren'Py Exporter)."""
        nodes = session.project_data.nodes
        conns = session.project_data.connections
        lines = [
            f"# Generated by Dialogue Engine Studio 24/7",
            f"# Project: {session.project_data.metadata.title or 'Violant'}",
            "",
            "# --- Characters ---"
        ]
        char_set = set()
        for n in nodes:
            if n.title and not n.title.startswith("#") and n.node_type == "story":
                char_set.add(n.title.strip())

        char_var_map = {}
        for c in char_set:
            slug = "".join([ch.lower() if ch.isalnum() else "_" for ch in c]).strip("_") or "char"
            var_name = f"char_{slug}"
            char_var_map[c] = var_name
            lines.append(f'define {var_name} = Character("{c}")')

        lines.extend(["", "# --- Scenario Script ---"])
        for n in nodes:
            lines.append(f"\nlabel node_{n.id}:")
            if n.node_type == "story":
                var_name = char_var_map.get(n.title, "")
                clean_txt = (n.content or "").replace('"', '\\"')
                if var_name:
                    lines.append(f'    {var_name} "{clean_txt}"')
                else:
                    lines.append(f'    "{clean_txt}"')
            elif n.node_type == "choice":
                lines.append("    menu:")
                opts = [opt.strip() for opt in (n.content or "").split("\n") if opt.strip()]
                for idx, opt in enumerate(opts):
                    c_target = next((c for c in conns if str(c.from_node) == str(n.id) and int(c.out_idx) == idx), None)
                    lines.append(f'        "{opt}":')
                    if c_target:
                        lines.append(f"            jump node_{c_target.to_node}")
                    else:
                        lines.append("            pass")
                continue
            elif n.node_type == "music":
                clean_m = (n.content or "music.mp3").replace('"', '')
                lines.append(f'    play music "{clean_m}"')

            # Next jump
            next_c = next((c for c in conns if str(c.from_node) == str(n.id)), None)
            if next_c:
                lines.append(f"    jump node_{next_c.to_node}")
            else:
                lines.append("    return")

        script_content = "\n".join(lines)
        return Response(
            content=script_content,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="script.rpy"'}
        )

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

    # WebSocket для коворка в реальном времени с поддержкой отдельных комнат/сессий
    @app.websocket("/ws")
    @app.websocket("/ws/{session_id}")
    async def websocket_endpoint(websocket: WebSocket, session: Optional[str] = None, session_id: Optional[str] = None, token: Optional[str] = None):
        await websocket.accept()
        client_id = None
        target_sid = session_id or session or "violant"
        active_sess = session_manager.get_session(target_sid)
        try:
            raw = await websocket.receive_text()
            init_info = {}
            try:
                init_info = json.loads(raw)
            except Exception:
                pass

            if init_info.get("session"):
                target_sid = init_info["session"]
                active_sess = session_manager.get_session(target_sid)

            client_token = init_info.get("token") or token
            if SERVER_PASSWORD and client_token not in VALID_TOKENS and client_token != MASTER_TOKEN:
                await websocket.send_text(json.dumps({
                    "type": "auth_error",
                    "message": "Требуется авторизация (неверный пароль или токен)"
                }, ensure_ascii=False))
                await websocket.close(code=4403)
                return

            client_id = await active_sess.register_client(websocket, init_info)

            # Основной цикл обработки сообщений конкретной сессии
            while True:
                data = await websocket.receive_text()
                await active_sess.handle_message(client_id, data)
        except WebSocketDisconnect:
            if client_id:
                await active_sess.unregister_client(client_id)
        except Exception as e:
            logger.error(f"WebSocket error in session '{target_sid}' for client {client_id}: {e}")
            if client_id:
                await active_sess.unregister_client(client_id)

    # Статические файлы веб-клиента и поддержка прямых ссылок /s/{session_id}
    index_file = os.path.join(STATIC_DIR, "index.html")

    @app.get("/", response_class=HTMLResponse)
    @app.get("/app", response_class=HTMLResponse)
    @app.get("/s/{session_id}", response_class=HTMLResponse)
    async def serve_index(session_id: Optional[str] = None):
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                return f.read()
        return "<h1>Dialogue Engine Web Client Loading...</h1>"

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    return app

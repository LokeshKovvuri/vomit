import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("vomit")

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
PUBLIC_URL = os.getenv("PUBLIC_URL", "").rstrip("/")
TURN_URL = os.getenv("TURN_URL", "")
TURN_USER = os.getenv("TURN_USER", "")
TURN_PASS = os.getenv("TURN_PASS", "")

WEB_DIR = Path(__file__).parent.parent / "web"

app = FastAPI(title="vomit")


# ---------- Hub ----------
class Hub:
    def __init__(self) -> None:
        self.sessions: Dict[str, Dict[str, WebSocket]] = {}
        self.lock = asyncio.Lock()

    async def register(self, session_id: str, role: str, ws: WebSocket) -> None:
        async with self.lock:
            self.sessions.setdefault(session_id, {})[role] = ws
            log.info("register session=%s role=%s", session_id, role)

    async def unregister(self, session_id: str, role: str) -> None:
        async with self.lock:
            s = self.sessions.get(session_id)
            if not s:
                return
            s.pop(role, None)
            if not s:
                self.sessions.pop(session_id, None)
            log.info("unregister session=%s role=%s", session_id, role)

    async def relay(self, session_id: str, from_role: str, message: dict) -> None:
        async with self.lock:
            peers = self.sessions.get(session_id, {})
            targets = [ws for role, ws in peers.items() if role != from_role]
        if not targets:
            return
        payload = json.dumps(message)
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception as e:
                log.warning("send failed: %s", e)


hub = Hub()


# ---------- Config endpoint ----------
@app.get("/config")
async def config():
    ice = [{"urls": "stun:stun.l.google.com:19302"}]
    if TURN_URL:
        ice.append({
            "urls": TURN_URL,
            "username": TURN_USER,
            "credential": TURN_PASS,
        })
    return JSONResponse({"iceServers": ice, "publicUrl": PUBLIC_URL})


# ---------- Health check (Render uses this) ----------
@app.get("/healthz")
async def healthz():
    return {"ok": True}


# ---------- Static pages ----------
@app.get("/")
async def index():
    return FileResponse(WEB_DIR / "index.html")

@app.get("/agent.html")
async def agent_page():
    return FileResponse(WEB_DIR / "agent.html")

@app.get("/viewer.html")
async def viewer_page():
    return FileResponse(WEB_DIR / "viewer.html")


# ---------- WebSocket signaling ----------
@app.websocket("/ws")
async def ws_endpoint(
    ws: WebSocket,
    session: str = Query(...),
    role: str = Query(...),
):
    if role not in ("agent", "viewer"):
        await ws.close(code=1008, reason="invalid role")
        return

    await ws.accept()
    await hub.register(session, role, ws)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            await hub.relay(session, role, msg)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.exception("ws error: %s", e)
    finally:
        await hub.unregister(session, role)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT)
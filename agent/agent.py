"""
vomit native agent — screen share + input injection.

    python agent/agent.py --session myid --server https://your-app.onrender.com

Requires: aiortc, aiohttp, mss, pynput, numpy, av
Recommended: Python 3.12 venv for prebuilt wheels.
"""
import argparse
import asyncio
import fractions
import json
import logging
import os
import time
from typing import Optional

import numpy as np
import mss
from av import VideoFrame
from aiortc import (
    RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCIceCandidate
)
import aiohttp
from pynput.mouse import Controller as MouseController, Button
from pynput.keyboard import Controller as KeyboardController, Key

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    filename=os.path.join(os.path.expanduser("~"), "vomit-agent.log"),
    filemode="a",
)
log = logging.getLogger("vomit-agent")

SCREEN_SIZE = (1920, 1080)


class ScreenTrack(VideoStreamTrack):
    kind = "video"

    def __init__(self, monitor: int = 1, fps: int = 15):
        super().__init__()
        self.monitor = monitor
        self.fps = fps
        self.sct = mss.mss()
        self._last = 0.0

    async def recv(self) -> VideoFrame:
        now = time.time()
        wait = max(0, (1.0 / self.fps) - (now - self._last))
        if wait:
            await asyncio.sleep(wait)
        self._last = time.time()

        shot = self.sct.grab(self.sct.monitors[self.monitor])
        img = np.frombuffer(shot.rgb, dtype=np.uint8).reshape(shot.height, shot.width, 3)
        frame = VideoFrame.from_ndarray(img, format="rgb24")
        frame.pts = int(time.time() * 90000)
        frame.time_base = fractions.Fraction(1, 90000)
        return frame


mouse = MouseController()
keyboard = KeyboardController()
BUTTON_MAP = {0: Button.left, 1: Button.middle, 2: Button.right}


def inject(event: dict) -> None:
    t = event.get("type")
    try:
        if t == "mousemove":
            sw, sh = SCREEN_SIZE
            mouse.position = (int(event["x"] * sw), int(event["y"] * sh))
        elif t == "mousedown":
            mouse.press(BUTTON_MAP.get(event.get("button", 0), Button.left))
        elif t == "mouseup":
            mouse.release(BUTTON_MAP.get(event.get("button", 0), Button.left))
        elif t == "scroll":
            mouse.scroll(event.get("dx", 0) / 100, -event.get("dy", 0) / 100)
        elif t in ("keydown", "keyup"):
            k = map_key(event.get("key"), event.get("code"))
            if k is None:
                return
            if t == "keydown":
                keyboard.press(k)
            else:
                keyboard.release(k)
    except Exception as e:
        log.debug("inject error: %s", e)


def map_key(key: Optional[str], code: Optional[str]):
    if key and len(key) == 1:
        return key
    special = {
        "Enter": Key.enter, "Escape": Key.esc, "Backspace": Key.backspace,
        "Tab": Key.tab, " ": Key.space,
        "ArrowUp": Key.up, "ArrowDown": Key.down,
        "ArrowLeft": Key.left, "ArrowRight": Key.right,
        "Shift": Key.shift, "Control": Key.ctrl, "Alt": Key.alt,
        "Meta": Key.cmd,
    }
    return special.get(key)


async def run(session_id: str, server: str, monitor: int, fps: int):
    global SCREEN_SIZE
    with mss.mss() as sct:
        mon = sct.monitors[monitor]
        SCREEN_SIZE = (mon["width"], mon["height"])

    pc = RTCPeerConnection()
    pc.addTrack(ScreenTrack(monitor=monitor, fps=fps))

    @pc.on("datachannel")
    def on_dc(channel):
        log.info("datachannel open")

        @channel.on("message")
        def on_msg(message):
            try:
                inject(json.loads(message))
            except Exception as e:
                log.warning("inject: %s", e)

    @pc.on("connectionstatechange")
    async def on_state():
        log.info("pc state: %s", pc.connectionState)

    ws_proto = "wss" if server.startswith("https") else "ws"
    host = server.replace("https://", "").replace("http://", "").rstrip("/")
    ws_url = f"{ws_proto}://{host}/ws?session={session_id}&role=agent"

    log.info("connecting to %s", ws_url)

    async with aiohttp.ClientSession() as http:
        async with http.ws_connect(ws_url) as ws:
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            await ws.send_json({"type": "offer", "payload": {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type,
            }})

            @pc.on("icecandidate")
            async def on_ice(candidate):
                if candidate is None:
                    return
                await ws.send_json({"type": "ice", "payload": {
                    "foundation": candidate.foundation,
                    "component": candidate.component,
                    "protocol": candidate.protocol,
                    "priority": candidate.priority,
                    "ip": candidate.ip,
                    "port": candidate.port,
                    "type": candidate.type,
                }})

            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    continue
                data = json.loads(msg.data)
                if data["type"] == "answer":
                    desc = RTCSessionDescription(
                        sdp=data["payload"]["sdp"],
                        type=data["payload"]["type"],
                    )
                    await pc.setRemoteDescription(desc)
                    log.info("answer set")
                elif data["type"] == "ice":
                    c = data["payload"]
                    cand = RTCIceCandidate(
                        foundation=c.get("foundation", ""),
                        component=c.get("component", 1),
                        protocol=c.get("protocol", "udp"),
                        priority=c.get("priority", 0),
                        ip=c.get("ip", ""),
                        port=c.get("port", 0),
                        type=c.get("type", "host"),
                    )
                    try:
                        await pc.addIceCandidate(cand)
                    except Exception as e:
                        log.debug("add ice: %s", e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--server", default="http://localhost:8080")
    ap.add_argument("--monitor", type=int, default=1)
    ap.add_argument("--fps", type=int, default=15)
    args = ap.parse_args()

    try:
        asyncio.run(run(args.session, args.server, args.monitor, args.fps))
    except KeyboardInterrupt:
        log.info("bye")


if __name__ == "__main__":
    main()
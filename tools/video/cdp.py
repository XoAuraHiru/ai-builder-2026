"""A small Chrome DevTools Protocol client: launch headless Chrome, send commands, and receive events.

Commands resolve through futures keyed by id; events go to handlers registered by method name, so a screencast can
stream frames while scripted actions run.
"""
import asyncio
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from collections import defaultdict
from typing import Any, Awaitable, Callable

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


class Chrome:
    def __init__(self, port: int = 9711, width: int = 1440, height: int = 810):
        self.port, self.width, self.height = port, width, height
        self.profile = tempfile.mkdtemp(prefix="atrium-video-")
        self.proc: subprocess.Popen | None = None
        self.ws = None
        self._id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._handlers: dict[str, list[Callable[[dict], Awaitable[None] | None]]] = defaultdict(list)
        self._reader: asyncio.Task | None = None

    async def __aenter__(self) -> "Chrome":
        self.proc = subprocess.Popen(
            [CHROME, "--headless=new", f"--remote-debugging-port={self.port}", f"--user-data-dir={self.profile}",
             "--no-first-run", "--hide-scrollbars", "--mute-audio", "--force-color-profile=srgb",
             "--disable-features=Translate", f"--window-size={self.width},{self.height}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        page = None
        for _ in range(100):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json"))
                page = next(t for t in targets if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        if page is None:
            raise RuntimeError("Chrome did not start")
        self.ws = await websockets.connect(page["webSocketDebuggerUrl"], max_size=2 ** 28)
        self._reader = asyncio.create_task(self._read())
        return self

    async def __aexit__(self, *exc) -> None:
        if self._reader:
            self._reader.cancel()
        if self.ws:
            await self.ws.close()
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)  # a Chrome profile is tens of MB; never leave one behind

    async def _read(self) -> None:
        async for raw in self.ws:
            msg = json.loads(raw)
            if "id" in msg:
                fut = self._pending.pop(msg["id"], None)
                if fut and not fut.done():
                    if "error" in msg:
                        fut.set_exception(RuntimeError(f"{msg['error']}"))
                    else:
                        fut.set_result(msg.get("result", {}))
            else:
                for handler in self._handlers.get(msg.get("method", ""), []):
                    result = handler(msg.get("params", {}))
                    if asyncio.iscoroutine(result):
                        asyncio.create_task(result)

    def on(self, method: str, handler: Callable[[dict], Awaitable[None] | None]) -> None:
        self._handlers[method].append(handler)

    async def send(self, method: str, **params: Any) -> dict:
        self._id += 1
        fut = asyncio.get_running_loop().create_future()
        self._pending[self._id] = fut
        await self.ws.send(json.dumps({"id": self._id, "method": method, "params": params}))
        return await asyncio.wait_for(fut, timeout=120)

    async def js(self, expression: str) -> Any:
        r = await self.send("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True)
        if "exceptionDetails" in r:
            raise RuntimeError(f"page error: {r['exceptionDetails'].get('text')} in {expression[:120]}")
        return r.get("result", {}).get("value")

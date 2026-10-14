"""Record the real Atrium web app as video: Chrome's screencast streamed into ffmpeg at a constant frame rate.

The recorder keeps a clock of recorded time (frames written / fps). Scenes schedule actions on that clock, so they
line up with the voice-over. A wait can be cut: recording pauses while the page works (a Gemini call that takes
17 s), and on resume a small chip says how long it really took, so nothing is hidden. A cursor, captions and the
scene's label are drawn in the page itself, in Atrium's own fonts.
"""
import asyncio
import base64
import json
import math
from pathlib import Path

from cdp import Chrome

OVERLAY = r"""
(() => {
  if (window.__atr) return;
  const state = { x: 1100, y: 520 };
  const css = `
    #__atr { position: fixed; inset: 0; pointer-events: none; z-index: 2147483647; font-family: var(--font-sans), system-ui, sans-serif; }
    #__atr .cur { position: absolute; left: 0; top: 0; width: 26px; height: 26px; transform: translate(-3px,-2px); filter: drop-shadow(0 2px 3px rgba(28,27,23,.28)); }
    #__atr .ripple { position: absolute; width: 14px; height: 14px; margin: -7px 0 0 -7px; border-radius: 999px; border: 2px solid #3f8160; opacity: 0; }
    #__atr .ripple.go { animation: atr-rip .6s cubic-bezier(.22,1,.36,1) forwards; }
    @keyframes atr-rip { from { transform: scale(.6); opacity: .9 } to { transform: scale(3.4); opacity: 0 } }
    #__atr .cap { position: absolute; left: 50%; bottom: 26px; transform: translateX(-50%); max-width: 1020px; width: max-content;
      padding: 11px 20px 12px; border-radius: 14px; background: rgba(28,27,23,.86); color: #fff; font-size: 19px; line-height: 27px;
      font-weight: 500; letter-spacing: -.005em; text-align: center; opacity: 0; transition: opacity .25s ease; text-wrap: balance; }
    #__atr .cap.on { opacity: 1; }
    #__atr .lab { position: absolute; left: 124px; bottom: 96px; display: flex; align-items: center; gap: 10px; padding: 8px 16px 8px 8px;
      border-radius: 999px; background: #fff; box-shadow: 0 1px 2px rgba(28,27,23,.06), 0 12px 32px rgba(28,27,23,.14);
      font-size: 15px; font-weight: 600; color: #1c1b17; opacity: 0; transform: translateY(8px); transition: opacity .35s ease, transform .35s cubic-bezier(.22,1,.36,1); }
    #__atr .lab.on { opacity: 1; transform: none; }
    #__atr .lab .n { display: inline-flex; align-items: center; justify-content: center; height: 28px; min-width: 28px; padding: 0 9px;
      border-radius: 999px; background: #e0ede4; color: #1d4532; font-size: 13px; }
    #__atr .lab .s { color: #6f6c62; font-weight: 500; }
    #__atr .chip { position: absolute; left: 50%; top: 84px; transform: translate(-50%, -6px); padding: 7px 14px; border-radius: 999px;
      background: #f2f1fc; color: #4b44a6; font-size: 13px; font-weight: 600; box-shadow: 0 8px 24px rgba(28,27,23,.10);
      opacity: 0; transition: opacity .25s ease, transform .3s cubic-bezier(.22,1,.36,1); white-space: nowrap; }
    #__atr .chip.on { opacity: 1; transform: translate(-50%, 0); }
    nextjs-portal { display: none !important; }  /* the dev server's badge, on the local copy */
  `;
  function build() {
    if (document.getElementById('__atr')) return;
    const style = document.createElement('style'); style.textContent = css; document.head.appendChild(style);
    const root = document.createElement('div'); root.id = '__atr';
    root.innerHTML = `<div class="ripple"></div><div class="chip"></div><div class="lab"><span class="n"></span><span class="t"></span><span class="s"></span></div><div class="cap"></div>
      <svg class="cur" viewBox="0 0 24 24"><path d="M4 2.5l15.5 9.2-6.9 1.6 3.9 7.2-2.8 1.5-3.9-7.3-5.3 4.6z" fill="#fff" stroke="#1c1b17" stroke-width="1.4" stroke-linejoin="round"/></svg>`;
    document.body.appendChild(root);
    place();
  }
  const $ = (q) => document.querySelector('#__atr ' + q);
  function place() { const c = $('.cur'); if (c) c.style.left = state.x + 'px', c.style.top = state.y + 'px'; }
  const ease = (t) => 1 - Math.pow(1 - t, 3);
  window.__atr = {
    state,
    ready() { build(); return !!document.getElementById('__atr'); },
    move(x, y, ms) {
      build(); const x0 = state.x, y0 = state.y, t0 = performance.now();
      return new Promise((res) => {
        const step = (now) => { const k = Math.min(1, (now - t0) / ms), e = ease(k);
          state.x = x0 + (x - x0) * e; state.y = y0 + (y - y0) * e; place(); k < 1 ? requestAnimationFrame(step) : res(true); };
        requestAnimationFrame(step);
      });
    },
    ripple() { const r = $('.ripple'); if (!r) return; r.style.left = state.x + 'px'; r.style.top = state.y + 'px';
      r.classList.remove('go'); void r.offsetWidth; r.classList.add('go'); },
    caption(t) { build(); const c = $('.cap'); if (!c) return; if (t) { c.textContent = t; c.classList.add('on'); } else c.classList.remove('on'); },
    label(n, t, s) { build(); const l = $('.lab'); if (!l) return; if (!t) { l.classList.remove('on'); return; }
      $('.lab .n').textContent = n; $('.lab .t').textContent = t; $('.lab .s').textContent = s || ''; l.classList.add('on'); },
    chip(t) { build(); const c = $('.chip'); if (!c) return; if (t) { c.textContent = t; c.classList.add('on'); } else c.classList.remove('on'); },
    find(sel, text, nth, exact) {
      const visible = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
        return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && (!!sel || s.opacity !== '0'); };  // a named selector may be a transparent input over its boxes
      const label = (e) => (e.getAttribute('aria-label') || e.innerText || e.textContent || e.value || e.placeholder || '').replace(/\s+/g, ' ').trim();
      const match = (e) => !text || (exact ? label(e) === text : label(e).includes(text));
      let pool = sel ? [...document.querySelectorAll(sel)] : [...document.querySelectorAll('button,a,[role=button],[role=radio],input,textarea,select,summary')];
      let els = pool.filter((e) => visible(e) && match(e));
      if (!els.length && !sel) els = [...document.querySelectorAll('body *')].filter((e) => !e.closest('#__atr') && visible(e) && match(e));
      els.sort((a, b) => { const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect(); return ra.width * ra.height - rb.width * rb.height; });
      if (!sel && text) els.sort((a, b) => (a.closest('#__atr') ? 1 : 0) - (b.closest('#__atr') ? 1 : 0));
      const e = els[nth || 0]; if (!e) return null;
      const r = e.getBoundingClientRect();
      return { x: r.left + Math.min(r.width / 2, 160), y: r.top + r.height / 2, top: r.top, bottom: r.bottom, h: r.height, vh: innerHeight, sy: scrollY };
    },
    scrollTo(y, ms) {
      const y0 = scrollY, t0 = performance.now();
      return new Promise((res) => {
        const step = (now) => { const k = Math.min(1, (now - t0) / ms); scrollTo(0, y0 + (y - y0) * (0.5 - Math.cos(Math.PI * k) / 2));
          k < 1 ? requestAnimationFrame(step) : res(scrollY); };
        requestAnimationFrame(step);
      });
    },
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build); else build();
})();
"""


class Recorder:
    """Records one scene to `out` (H.264, no audio). Starts paused; `resume()` starts the clock."""

    def __init__(self, chrome: Chrome, out: Path, base: str, fps: int = 30, size: tuple[int, int] = (1920, 1080)):
        self.c, self.out, self.base, self.fps, self.size = chrome, out, base.rstrip("/"), fps, size
        self.frame: bytes | None = None
        self.frames = 0
        self.paused = True
        self.ffmpeg = None
        self.writer: asyncio.Task | None = None
        self.caption_text = ""
        self.label_args: tuple[str, str, str] | None = None
        self.cursor = (1100.0, 520.0)

    @property
    def clock(self) -> float:
        return self.frames / self.fps

    async def start(self) -> None:
        w, h = self.size
        self.ffmpeg = await asyncio.create_subprocess_exec(
            "ffmpeg", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(self.fps), "-c:v", "mjpeg",
            "-i", "-", "-vf", f"scale={w}:{h}:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "medium",
            "-crf", "18", "-r", str(self.fps), "-movflags", "+faststart", str(self.out), stdin=asyncio.subprocess.PIPE)
        await self.c.send("Page.enable")
        await self.c.send("Runtime.enable")
        await self.c.send("Page.addScriptToEvaluateOnNewDocument", source=OVERLAY)
        await self.c.send("Emulation.setDeviceMetricsOverride", width=self.c.width, height=self.c.height,
                          deviceScaleFactor=w / self.c.width, mobile=False)
        self.c.on("Page.screencastFrame", self._on_frame)
        await self.c.send("Page.startScreencast", format="jpeg", quality=92, maxWidth=w, maxHeight=h, everyNthFrame=1)
        self.writer = asyncio.create_task(self._write())

    async def _on_frame(self, params: dict) -> None:
        self.frame = base64.b64decode(params["data"])
        try:
            await self.c.send("Page.screencastFrameAck", sessionId=params["sessionId"])
        except Exception:
            pass

    async def _write(self) -> None:
        loop = asyncio.get_running_loop()
        tick = 1 / self.fps
        nxt = loop.time()
        while True:
            if self.paused or self.frame is None:
                await asyncio.sleep(tick)
                nxt = loop.time()
                continue
            self.ffmpeg.stdin.write(self.frame)
            await self.ffmpeg.stdin.drain()
            self.frames += 1
            nxt += tick
            await asyncio.sleep(max(0.0, nxt - loop.time()))

    async def stop(self) -> None:
        self.paused = True
        if self.writer:
            self.writer.cancel()
        await self.c.send("Page.stopScreencast")
        self.ffmpeg.stdin.close()
        await self.ffmpeg.wait()

    # -- the clock ---------------------------------------------------------------------------------------------

    def pause(self) -> None:
        self.paused = True

    async def resume(self, chip: str | None = None, chip_seconds: float = 2.6) -> None:
        await self.overlay_restore()
        if chip:
            await self.c.js(f"__atr.chip({json.dumps(chip)})")
        await asyncio.sleep(0.15)  # a fresh frame of the page as it is now
        self.paused = False
        if chip:
            asyncio.create_task(self._clear_chip_after(chip_seconds))

    async def _clear_chip_after(self, seconds: float) -> None:
        await self.until(self.clock + seconds)
        await self.c.js("__atr.chip('')")

    async def until(self, t: float) -> None:
        while self.clock < t:
            await asyncio.sleep(1 / self.fps)

    async def hold(self, seconds: float) -> None:
        await self.until(self.clock + seconds)

    # -- the overlay -------------------------------------------------------------------------------------------

    async def overlay_restore(self) -> None:
        for _ in range(40):
            if await self.c.js("!!(window.__atr && __atr.ready())"):
                break
            await asyncio.sleep(0.1)
        x, y = self.cursor
        await self.c.js(f"__atr.state.x={x}; __atr.state.y={y}; __atr.move({x},{y},1)")
        await self.c.js(f"__atr.caption({json.dumps(self.caption_text)})")
        if self.label_args:
            n, t, s = self.label_args
            await self.c.js(f"__atr.label({json.dumps(n)},{json.dumps(t)},{json.dumps(s)})")

    async def caption(self, text: str) -> None:
        self.caption_text = text
        await self.c.js(f"__atr.caption({json.dumps(text)})")

    async def label(self, number: str, title: str, sub: str = "") -> None:
        self.label_args = (number, title, sub) if title else None
        await self.c.js(f"__atr.label({json.dumps(number)},{json.dumps(title)},{json.dumps(sub)})")

    # -- the page ----------------------------------------------------------------------------------------------

    async def goto(self, path: str, ready: str | None = None, ready_sel: str | None = None, settle: float = 1.2) -> None:
        """Navigate while paused (no white flash is recorded), wait for the page to be ready, and stay paused."""
        was = self.paused
        self.paused = True
        url = path if "://" in path else f"{self.base}/{path.lstrip('/')}"
        await self.c.send("Page.navigate", url=url)
        await self.wait_for(text=ready, sel=ready_sel, timeout=60, record=False)
        await asyncio.sleep(settle)
        await self.overlay_restore()
        self.paused = was

    async def sign_in(self, email: str) -> None:
        self.paused = True
        await self.c.send("Page.navigate", url=f"{self.base}/login")
        await asyncio.sleep(2.5)
        device = f"video-{email.split('@')[0]}"
        await self.c.js(f"localStorage.setItem('atrium.devUser', {json.dumps(email)});"
                        f"localStorage.setItem('atrium-device.' + {json.dumps(email.lower())}, {json.dumps(device)})")

    async def find(self, text: str | None = None, sel: str | None = None, nth: int = 0, exact: bool = False):
        return await self.c.js(f"__atr.find({json.dumps(sel)}, {json.dumps(text)}, {nth}, {json.dumps(exact)})")

    async def wait_for(self, text: str | None = None, sel: str | None = None, timeout: float = 90, record: bool = True,
                       gone: bool = False) -> bool:
        """Wait until an element with this text (or selector) is there (or gone). With record=False the wait is cut."""
        if not text and not sel:
            return True
        was = self.paused
        if not record:
            self.paused = True
        loop = asyncio.get_running_loop()
        end = loop.time() + timeout
        ok = False
        while loop.time() < end:
            try:
                hit = await self.find(text=text, sel=sel)
            except Exception:
                hit = None
            if (hit is None) == gone:
                ok = True
                break
            await asyncio.sleep(0.25)
        if not record:
            self.paused = was
        if not ok:
            raise TimeoutError(f"waited {timeout}s for {text or sel}")
        return ok

    async def cut_wait(self, text: str | None = None, sel: str | None = None, timeout: float = 120,
                       chip: str | None = None, gone: bool = False) -> float:
        """Cut a long wait: pause, wait for the result, resume with a chip naming the real time. Returns seconds."""
        loop = asyncio.get_running_loop()
        started = loop.time()
        self.paused = True
        await self.wait_for(text=text, sel=sel, timeout=timeout, record=False, gone=gone)
        await asyncio.sleep(0.6)
        took = loop.time() - started
        await self.resume(chip=chip.format(s=round(took)) if chip else None)
        return took

    async def scroll_to(self, text: str | None = None, sel: str | None = None, at: float = 0.32, ms: int = 900) -> None:
        hit = await self.find(text=text, sel=sel)
        if not hit:
            raise RuntimeError(f"nothing to scroll to: {text or sel}")
        target = max(0, hit["sy"] + hit["top"] - hit["vh"] * at)
        await self.c.js(f"__atr.scrollTo({target}, {ms})")
        await asyncio.sleep(ms / 1000 + 0.05)

    async def scroll_by(self, dy: float, ms: int = 900) -> None:
        await self.c.js(f"__atr.scrollTo(scrollY + {dy}, {ms})")
        await asyncio.sleep(ms / 1000 + 0.05)

    async def move_to(self, text: str | None = None, sel: str | None = None, nth: int = 0, exact: bool = False,
                      dx: float = 0, dy: float = 0) -> dict:
        hit = await self.find(text=text, sel=sel, nth=nth, exact=exact)
        if not hit:
            raise RuntimeError(f"not on the page: {text or sel}")
        if hit["top"] < 70 or hit["bottom"] > hit["vh"] - 120:
            await self.scroll_to(text=text, sel=sel, at=0.42)
            hit = await self.find(text=text, sel=sel, nth=nth, exact=exact)
        x, y = hit["x"] + dx, hit["y"] + dy
        x0, y0 = self.cursor
        ms = int(min(1400, max(650, math.hypot(x - x0, y - y0) * 1.15)))  # an unhurried hand
        await self.c.js(f"__atr.move({x},{y},{ms})")
        await self.c.send("Input.dispatchMouseEvent", type="mouseMoved", x=x, y=y)
        self.cursor = (x, y)
        await asyncio.sleep(ms / 1000 + 0.05)
        return hit

    async def click(self, text: str | None = None, sel: str | None = None, nth: int = 0, exact: bool = False,
                    pause_after: float = 0.35) -> None:
        await self.move_to(text=text, sel=sel, nth=nth, exact=exact)
        await asyncio.sleep(0.18)
        x, y = self.cursor
        await self.c.js("__atr.ripple()")
        await self.c.send("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button="left", clickCount=1)
        await asyncio.sleep(0.07)
        await self.c.send("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button="left", clickCount=1)
        await asyncio.sleep(pause_after)

    async def select(self, sel: str, value: str) -> None:
        """Choose an option in a native select (whose open list headless Chrome does not draw): point at it, then
        set the value the way React listens for it."""
        await self.click(sel=sel, pause_after=0.25)
        await self.c.js(f"""(() => {{ const s = document.querySelector({json.dumps(sel)});
          const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
          set.call(s, {json.dumps(value)}); s.dispatchEvent(new Event('change', {{ bubbles: true }})); }})()""")
        await asyncio.sleep(0.4)

    async def select_all(self, sel: str) -> None:
        """Select a field's current value, so what is typed next replaces it."""
        await self.c.js(f"(() => {{ const i = document.querySelector({json.dumps(sel)}); i.focus(); i.select && i.select(); }})()")

    async def type(self, text: str, per_char: float = 0.045) -> None:
        for ch in text:
            await self.c.send("Input.insertText", text=ch)
            await asyncio.sleep(per_char)

from __future__ import annotations

from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import secrets
import socket
import threading
import time
from typing import Any
from urllib.parse import parse_qs


PORT = 8320


REMOTE_HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover,user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="OverheadLink">
<title>OverheadLink Remote</title>
<style>
:root{color-scheme:dark;--bg:#0a1016;--card:#111c25;--line:#263541;--text:#e8edf2;--muted:#91a2af;--amber:#f2a23a;--green:#74d990;--red:#ff7474}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding:env(safe-area-inset-top) 12px env(safe-area-inset-bottom)}
header{position:sticky;top:0;z-index:5;background:rgba(10,16,22,.94);backdrop-filter:blur(12px);padding:14px 4px 12px;border-bottom:1px solid var(--line)}
h1{font-size:22px;margin:0;color:var(--amber);letter-spacing:.05em}.status{font-size:13px;color:var(--muted);margin-top:6px}.ok{color:var(--green)}.bad{color:var(--red)}
.board{margin:16px 0}.board h2{font-size:15px;letter-spacing:.12em;color:#b9c5cf;margin:0 0 8px 4px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
.control{min-height:88px;border:1px solid var(--line);background:linear-gradient(180deg,#16232e,#101922);border-radius:13px;padding:12px;text-align:left;color:var(--text);font-size:14px;font-weight:650;position:relative;box-shadow:0 3px 12px rgba(0,0,0,.18)}
.control:active{transform:scale(.985);border-color:var(--amber)}.control .pin{display:block;color:var(--muted);font-size:11px;font-weight:500;margin-top:7px}.lamps{position:absolute;right:10px;top:10px;display:flex;gap:5px}.lamp{width:10px;height:10px;border-radius:50%;background:#26323a;border:1px solid #4c5961}.lamp.on{background:var(--amber);box-shadow:0 0 9px rgba(242,162,58,.8)}
footer{color:var(--muted);font-size:12px;padding:18px 4px 30px;text-align:center}@media(min-width:700px){.grid{grid-template-columns:repeat(4,minmax(0,1fr))}body{max-width:1000px;margin:auto}}
</style>
</head>
<body>
<header><h1>OVERHEADLINK</h1><div class="status" id="status">Connecting to cockpit PC…</div></header>
<main id="main"></main>
<footer>Local cockpit network only • Tap a control to operate the Fenix overhead</footer>
<script>
let rendering=false;
async function api(path,opts={}){const r=await fetch(path,{cache:'no-store',...opts});if(!r.ok){const t=await r.text();throw new Error(t||r.status)}return r.json()}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function tap(id,button){button.disabled=true;try{await api('/api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({assignment:id,event:'tap'})});if(navigator.vibrate)navigator.vibrate(20)}catch(e){alert('Control failed: '+e.message)}finally{setTimeout(()=>button.disabled=false,120)}}
function render(s){const status=document.getElementById('status');status.innerHTML=s.fenixReady?'<span class="ok">● Fenix connected</span> — '+esc(s.fenixDetail):'<span class="bad">● Fenix not ready</span> — '+esc(s.fenixDetail);let html='';for(const board of s.boards){if(!board.controls.length)continue;html+=`<section class="board"><h2>${esc(board.name)}</h2><div class="grid">`;for(const c of board.controls){html+=`<button class="control" onclick="tap('${esc(c.id)}',this)">${esc(c.control)}<span class="pin">${esc(c.pin)}</span><span class="lamps"><i class="lamp ${c.upper?'on':''}"></i><i class="lamp ${c.lower?'on':''}"></i></span></button>`}html+='</div></section>'}document.getElementById('main').innerHTML=html}
async function refresh(){if(rendering)return;rendering=true;try{render(await api('/api/state'))}catch(e){document.getElementById('status').innerHTML='<span class="bad">● Remote disconnected</span>'}finally{rendering=false}}
refresh();setInterval(refresh,900);
</script>
</body></html>'''


PAIR_HTML = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="apple-mobile-web-app-capable" content="yes"><title>Pair OverheadLink</title><style>body{margin:0;background:#0a1016;color:#eef3f6;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;display:grid;min-height:100vh;place-items:center;padding:24px}.box{width:min(420px,100%);background:#121e28;border:1px solid #2b3b47;border-radius:18px;padding:24px}h1{color:#f2a23a;letter-spacing:.06em}p{color:#9fb0bc;line-height:1.45}input{width:100%;font-size:30px;letter-spacing:.25em;text-align:center;padding:14px;border-radius:12px;border:1px solid #3a4a56;background:#081017;color:white;margin:12px 0}button{width:100%;padding:15px;border:0;border-radius:12px;background:#f2a23a;color:#12171b;font-size:16px;font-weight:750}</style></head><body><form class="box" method="post" action="/pair"><h1>OVERHEADLINK</h1><p>Enter the six-digit pairing code shown on the cockpit PC. This remote only accepts devices on your local network.</p><input name="code" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" required autofocus><button type="submit">PAIR iPHONE</button></form></body></html>'''


def _local_ipv4() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        address = sock.getsockname()[0]
        if address:
            return address
    except OSError:
        pass
    finally:
        sock.close()
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"


def _is_local_client(address: str) -> bool:
    try:
        value = ipaddress.ip_address(address)
        return value.is_private or value.is_loopback or value.is_link_local
    except ValueError:
        return False


def _mode_value(mode: object) -> str:
    return str(getattr(mode, "value", mode))


class RemotePanelServer:
    def __init__(self, app: Any, port: int = PORT):
        self.app = app
        self.port = port
        self.pairing_code = f"{secrets.randbelow(1_000_000):06d}"
        self._token = secrets.token_urlsafe(32)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.host_ip = _local_ipv4()

    @property
    def url(self) -> str:
        return f"http://{self.host_ip}:{self.port}/"

    def start(self) -> None:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "OverheadLinkRemote/0.3.7"

            def log_message(self, _format: str, *_args: object) -> None:
                return

            def _allowed(self) -> bool:
                return _is_local_client(self.client_address[0])

            def _paired(self) -> bool:
                cookie = SimpleCookie(self.headers.get("Cookie", ""))
                morsel = cookie.get("ohl_token")
                return morsel is not None and secrets.compare_digest(morsel.value, owner._token)

            def _send(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8", headers: dict[str, str] | None = None) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                if headers:
                    for key, value in headers.items():
                        self.send_header(key, value)
                self.end_headers()
                self.wfile.write(body)

            def _json(self, status: int, payload: object) -> None:
                self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

            def do_GET(self) -> None:
                if not self._allowed():
                    self._send(HTTPStatus.FORBIDDEN, b"Local network access only", "text/plain; charset=utf-8")
                    return
                path = self.path.split("?", 1)[0]
                if path == "/api/state":
                    if not self._paired():
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "pairing required"})
                        return
                    self._json(HTTPStatus.OK, owner.state_payload())
                    return
                if path == "/":
                    page = REMOTE_HTML if self._paired() else PAIR_HTML
                    self._send(HTTPStatus.OK, page.encode("utf-8"))
                    return
                self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")

            def do_POST(self) -> None:
                if not self._allowed():
                    self._send(HTTPStatus.FORBIDDEN, b"Local network access only", "text/plain; charset=utf-8")
                    return
                path = self.path.split("?", 1)[0]
                length = min(int(self.headers.get("Content-Length", "0") or 0), 8192)
                body = self.rfile.read(length)
                if path == "/pair":
                    fields = parse_qs(body.decode("utf-8", errors="replace"))
                    code = str(fields.get("code", [""])[0]).strip()
                    if not secrets.compare_digest(code, owner.pairing_code):
                        self._send(HTTPStatus.UNAUTHORIZED, PAIR_HTML.encode("utf-8"))
                        return
                    self._send(
                        HTTPStatus.SEE_OTHER,
                        b"",
                        headers={
                            "Location": "/",
                            "Set-Cookie": f"ohl_token={owner._token}; Path=/; HttpOnly; SameSite=Strict",
                        },
                    )
                    return
                if path == "/api/action":
                    if not self._paired():
                        self._json(HTTPStatus.UNAUTHORIZED, {"error": "pairing required"})
                        return
                    try:
                        request = json.loads(body.decode("utf-8"))
                        assignment_id = str(request.get("assignment", ""))
                        event = str(request.get("event", "tap"))
                        owner.execute_assignment(assignment_id, event)
                        self._json(HTTPStatus.OK, {"ok": True})
                    except Exception as error:
                        self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                    return
                self._send(HTTPStatus.NOT_FOUND, b"Not found", "text/plain; charset=utf-8")

        self._server = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, name="OverheadLink-Remote", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.shutdown()
            server.server_close()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def _assignment(self, assignment_id: str) -> Any:
        for board in self.app.profile.boards:
            for assignment in board.assignments:
                if assignment.id == assignment_id:
                    return assignment
        raise KeyError("Unknown overhead control")

    def execute_assignment(self, assignment_id: str, event: str = "tap") -> None:
        assignment = self._assignment(assignment_id)
        if not assignment.enabled or _mode_value(assignment.mode) != "digital_input":
            raise ValueError("That item is not an enabled overhead input")
        if not self.app.fenix.ready:
            raise RuntimeError("Fenix WASM bridge is not ready")
        if event not in {"tap", "press", "release"}:
            raise ValueError("Unsupported remote event")
        if event in {"tap", "press"}:
            if not assignment.sim.on_press:
                raise ValueError("No Fenix press action is assigned")
            self.app.fenix.execute(assignment.sim.on_press)
        if event == "tap" and assignment.sim.on_release:
            time.sleep(0.045)
            self.app.fenix.execute(assignment.sim.on_release)
        elif event == "release":
            if not assignment.sim.on_release:
                raise ValueError("No Fenix release action is assigned")
            self.app.fenix.execute(assignment.sim.on_release)

    def state_payload(self) -> dict[str, Any]:
        values = dict(self.app.feedback_values)
        boards: list[dict[str, Any]] = []
        for board in self.app.profile.boards:
            controls: list[dict[str, Any]] = []
            for assignment in board.assignments:
                if not assignment.enabled or _mode_value(assignment.mode) != "digital_input" or not assignment.sim.on_press:
                    continue
                base = assignment.id.rsplit(".", 1)[0]
                controls.append(
                    {
                        "id": assignment.id,
                        "control": assignment.control,
                        "pin": assignment.pin,
                        "upper": bool(values.get(base + ".upper", 0.0)),
                        "lower": bool(values.get(base + ".lower", 0.0)),
                    }
                )
            boards.append({"id": board.id, "name": board.name, "controls": controls})
        status = getattr(self.app.fenix, "status", None)
        return {
            "fenixReady": bool(self.app.fenix.ready),
            "fenixDetail": str(getattr(status, "detail", "Fenix status unavailable")),
            "boards": boards,
        }


def install_remote_tab(app: Any, server: RemotePanelServer) -> None:
    import tkinter as tk
    from tkinter import ttk

    tab = ttk.Frame(app.tabs, padding=18)
    app.tabs.add(tab, text="Remote")
    card = ttk.Frame(tab, style="Card.TFrame", padding=24)
    card.pack(fill="x")
    ttk.Label(card, text="iPhone / Device Remote", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
    ttk.Label(
        card,
        text="Use a phone or tablet on the same Wi-Fi/LAN as this cockpit PC. No cloud account is used.",
        style="Status.TLabel",
        wraplength=780,
    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(14, 16))
    ttk.Label(card, text="Remote address", style="Status.TLabel").grid(row=2, column=0, sticky="w", pady=4)
    url_var = tk.StringVar(value=server.url)
    ttk.Entry(card, textvariable=url_var, width=44, state="readonly").grid(row=2, column=1, sticky="ew", pady=4)
    ttk.Label(card, text="Pairing code", style="Status.TLabel").grid(row=3, column=0, sticky="w", pady=4)
    code = ttk.Label(card, text=server.pairing_code, style="Title.TLabel")
    code.grid(row=3, column=1, sticky="w", pady=4)

    def copy_url() -> None:
        app.clipboard_clear()
        app.clipboard_append(server.url)
        app.update_idletasks()

    ttk.Button(card, text="Copy Remote Address", command=copy_url).grid(row=4, column=0, sticky="w", pady=(18, 0))
    ttk.Label(
        card,
        text="On iPhone: open the address in Safari, enter the pairing code, then Share → Add to Home Screen for an app-like full-screen remote.",
        style="Status.TLabel",
        wraplength=780,
    ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(18, 0))
    card.columnconfigure(1, weight=1)

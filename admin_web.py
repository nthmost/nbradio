#!/usr/bin/env python3
"""KNOB - DJ Admin Panel

Admin interface for managing DJ credentials, protected by HTTP Basic Auth.
Same dark aesthetic as the nowplaying dashboard.
"""

import argparse
import base64
import hashlib
import html
import hmac
import json
import os
import secrets
import string
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

CREDS_FILE = "/etc/liquidsoap/dj_credentials"
ADMIN_CREDS_FILE = "/etc/liquidsoap/admin_credentials"
_file_lock = threading.Lock()


def _set_creds_file(path):
    global CREDS_FILE
    CREDS_FILE = path


def _set_admin_creds_file(path):
    global ADMIN_CREDS_FILE
    ADMIN_CREDS_FILE = path


def _read_admin_users():
    """Read admin credentials file. Returns dict of {username: password}."""
    admins = {}
    if not os.path.exists(ADMIN_CREDS_FILE):
        return admins
    with open(ADMIN_CREDS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":", 1)
            if len(parts) == 2:
                admins[parts[0]] = parts[1]
    return admins


def _check_auth(authorization_header):
    """Validate HTTP Basic Auth. Returns username if valid, None otherwise."""
    if not authorization_header:
        return None
    if not authorization_header.startswith("Basic "):
        return None
    try:
        decoded = base64.b64decode(authorization_header[6:]).decode("utf-8")
    except Exception:
        return None
    parts = decoded.split(":", 1)
    if len(parts) != 2:
        return None
    user, password = parts
    admins = _read_admin_users()
    if not admins:
        # No admin credentials file — deny all
        return None
    stored_pw = admins.get(user)
    if stored_pw is None:
        return None
    if hmac.compare_digest(stored_pw, password):
        return user
    return None


def _generate_password(length=16):
    """Generate a URL-safe random password."""
    return secrets.token_urlsafe(length)[:length]


def _read_djs():
    """Read DJ credentials file. Returns list of (username, password) tuples."""
    djs = []
    if not os.path.exists(CREDS_FILE):
        return djs
    with open(CREDS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":", 1)
            if len(parts) == 2:
                djs.append((parts[0], parts[1]))
    return djs


def _write_djs(djs):
    """Write DJ credentials file from list of (username, password) tuples."""
    lines = [
        "# KNOB DJ Credentials",
        "# Format: username:password",
        "# Managed by admin_web.py — do not edit while admin service is running.",
        "",
    ]
    for user, pw in djs:
        lines.append(f"{user}:{pw}")
    lines.append("")
    with open(CREDS_FILE, "w") as f:
        f.write("\n".join(lines))


def add_dj(username, password=None):
    """Add a DJ. Returns (username, password, error)."""
    username = username.strip()
    if not username:
        return None, None, "Username is required"
    if ":" in username:
        return None, None, "Username cannot contain ':'"
    if not password:
        password = _generate_password()
    password = password.strip()
    with _file_lock:
        djs = _read_djs()
        for u, _ in djs:
            if u == username:
                return None, None, f"DJ '{username}' already exists"
        djs.append((username, password))
        _write_djs(djs)
    return username, password, None


def remove_dj(username):
    """Remove a DJ. Returns error string or None."""
    with _file_lock:
        djs = _read_djs()
        new_djs = [(u, p) for u, p in djs if u != username]
        if len(new_djs) == len(djs):
            return f"DJ '{username}' not found"
        _write_djs(new_djs)
    return None


def reset_password(username):
    """Reset a DJ's password. Returns (new_password, error)."""
    new_pw = _generate_password()
    with _file_lock:
        djs = _read_djs()
        found = False
        for i, (u, p) in enumerate(djs):
            if u == username:
                djs[i] = (u, new_pw)
                found = True
                break
        if not found:
            return None, f"DJ '{username}' not found"
        _write_djs(djs)
    return new_pw, None


# --- HTML Template ------------------------------------------------------------

ADMIN_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KNOB Admin</title>
<style>
  :root {
    --bg: #0e0e12;
    --card: #16161d;
    --border: #2a2a35;
    --text: #e0e0e0;
    --dim: #7a7a8a;
    --accent: #6ec6ff;
    --green: #66d9a0;
    --yellow: #f0c674;
    --magenta: #c792ea;
    --red: #f07178;
    --cyan: #89ddff;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 2rem 1rem;
  }
  h1 {
    font-size: 1.1rem;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 0.5rem;
    text-align: center;
  }
  .subtitle {
    font-size: 0.75rem;
    color: var(--dim);
    letter-spacing: 0.15em;
    margin-bottom: 1.5rem;
    text-align: center;
  }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.25rem 1.5rem;
    width: 100%;
    max-width: 580px;
    margin-bottom: 1rem;
  }
  .card-title {
    font-size: 0.7rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--dim);
    margin-bottom: 0.75rem;
  }
  /* DJ table */
  .dj-table {
    width: 100%;
    border-collapse: collapse;
  }
  .dj-table th {
    font-size: 0.65rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--dim);
    text-align: left;
    padding: 0.4rem 0.5rem;
    border-bottom: 1px solid var(--border);
  }
  .dj-table td {
    padding: 0.5rem 0.5rem;
    border-bottom: 1px solid var(--border);
    font-size: 0.85rem;
    vertical-align: middle;
  }
  .dj-table tr:last-child td { border-bottom: none; }
  .dj-user { color: var(--cyan); font-weight: 600; }
  .dj-pass {
    color: var(--dim);
    font-family: inherit;
    font-size: 0.8rem;
    letter-spacing: 0.05em;
    cursor: pointer;
    position: relative;
  }
  .dj-pass .hidden-pw { filter: blur(4px); transition: filter 0.2s; }
  .dj-pass:hover .hidden-pw { filter: none; }
  .dj-pass .reveal-hint {
    font-size: 0.6rem;
    color: var(--dim);
    position: absolute;
    right: 0;
    top: -0.2rem;
    opacity: 0;
    transition: opacity 0.2s;
  }
  .dj-pass:hover .reveal-hint { opacity: 1; }
  .btn {
    display: inline-block;
    padding: 0.3rem 0.7rem;
    border-radius: 4px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text);
    font-family: inherit;
    font-size: 0.75rem;
    cursor: pointer;
    transition: all 0.15s;
    text-decoration: none;
  }
  .btn:hover { border-color: var(--accent); color: var(--accent); }
  .btn-danger { color: var(--red); border-color: #3a1a1a; }
  .btn-danger:hover { border-color: var(--red); background: #2a1010; }
  .btn-reset { color: var(--yellow); border-color: #3a3a1a; }
  .btn-reset:hover { border-color: var(--yellow); background: #2a2a10; }
  .btn-primary {
    background: var(--accent);
    color: var(--bg);
    border-color: var(--accent);
    font-weight: 600;
  }
  .btn-primary:hover { background: #8dd4ff; }
  .actions { display: flex; gap: 0.4rem; justify-content: flex-end; }
  /* Form */
  .form-row {
    display: flex;
    gap: 0.75rem;
    align-items: flex-end;
    flex-wrap: wrap;
  }
  .form-group {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    flex: 1;
    min-width: 120px;
  }
  .form-group label {
    font-size: 0.65rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--dim);
  }
  .form-group input {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.5rem 0.75rem;
    color: var(--text);
    font-family: inherit;
    font-size: 0.85rem;
    outline: none;
    transition: border-color 0.2s;
  }
  .form-group input:focus { border-color: var(--accent); }
  .form-group input::placeholder { color: #3a3a45; }
  .form-actions {
    display: flex;
    align-items: flex-end;
    padding-bottom: 1px;
  }
  /* Connection info */
  .info-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 0.35rem 0;
    border-bottom: 1px solid var(--border);
  }
  .info-row:last-child { border-bottom: none; }
  .info-label {
    font-size: 0.7rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--dim);
    flex-shrink: 0;
  }
  .info-value {
    text-align: right;
    font-size: 0.9rem;
    color: var(--green);
  }
  /* Flash messages */
  .flash {
    padding: 0.6rem 1rem;
    border-radius: 4px;
    font-size: 0.8rem;
    margin-bottom: 1rem;
    width: 100%;
    max-width: 580px;
    animation: flashIn 0.3s ease;
  }
  @keyframes flashIn { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; } }
  .flash-success { background: #1a3a2a; border: 1px solid #2a5a3a; color: var(--green); }
  .flash-error { background: #3a1a1a; border: 1px solid #5a2a2a; color: var(--red); }
  .flash-info { background: #1a2a3a; border: 1px solid #2a3a5a; color: var(--accent); }
  .flash code { background: #0e0e12; padding: 0.15rem 0.4rem; border-radius: 3px; }
  .no-djs {
    color: var(--dim);
    font-size: 0.85rem;
    text-align: center;
    padding: 1rem 0;
  }
  .footer {
    margin-top: 1rem;
    font-size: 0.7rem;
    color: var(--dim);
    text-align: center;
  }
  .footer a { color: var(--cyan); text-decoration: none; }
  .footer a:hover { text-decoration: underline; }
  @media (max-width: 600px) {
    body { padding: 1rem 0.5rem; }
    .card { padding: 1rem; }
    .form-row { flex-direction: column; }
  }
</style>
</head>
<body>

<h1>KNOB: DJ Admin</h1>
<div class="subtitle">Manage DJ credentials for Noisebridge Radio</div>

{{FLASH}}

<div class="card">
  <div class="card-title">Add New DJ</div>
  <form method="POST" action="./add">
    <div class="form-row">
      <div class="form-group">
        <label for="username">Username</label>
        <input type="text" id="username" name="username" placeholder="dj_handle" required
               pattern="[A-Za-z0-9_.\-]+" title="Letters, numbers, underscores, dots, hyphens">
      </div>
      <div class="form-group">
        <label for="password">Password <span style="color:#3a3a45">(blank = auto)</span></label>
        <input type="text" id="password" name="password" placeholder="auto-generated">
      </div>
      <div class="form-actions">
        <button type="submit" class="btn btn-primary">Add DJ</button>
      </div>
    </div>
  </form>
</div>

<div class="card">
  <div class="card-title">Registered DJs</div>
  {{DJ_TABLE}}
</div>

<div class="card">
  <div class="card-title">Connection Info (for DJs)</div>
  <div class="info-row">
    <span class="info-label">LAN Host</span>
    <span class="info-value">beyla.local:8005</span>
  </div>
  <div class="info-row">
    <span class="info-label">Remote Host</span>
    <span class="info-value">nbradio.nthmost.net:8005</span>
  </div>
  <div class="info-row">
    <span class="info-label">Mount</span>
    <span class="info-value">/live</span>
  </div>
  <div class="info-row">
    <span class="info-label">Protocol</span>
    <span class="info-value">Icecast / Shoutcast</span>
  </div>
</div>

<div class="footer">
  <a href="/">Back to Dashboard</a>
</div>

</body>
</html>"""


LOGIN_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KNOB Admin - Login</title>
<style>
  :root {
    --bg: #0e0e12; --card: #16161d; --border: #2a2a35;
    --text: #e0e0e0; --dim: #7a7a8a; --accent: #6ec6ff; --red: #f07178;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--bg); color: var(--text);
    font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', 'JetBrains Mono', monospace;
    min-height: 100vh; display: flex; flex-direction: column;
    align-items: center; justify-content: center; padding: 2rem 1rem;
  }
  h1 { font-size: 1.1rem; letter-spacing: 0.25em; text-transform: uppercase;
       color: var(--accent); margin-bottom: 0.5rem; }
  .subtitle { font-size: 0.75rem; color: var(--dim); letter-spacing: 0.15em;
              margin-bottom: 1.5rem; }
  .card { background: var(--card); border: 1px solid var(--border);
          border-radius: 8px; padding: 1.5rem; max-width: 380px; width: 100%; text-align: center; }
  .lock { font-size: 2rem; margin-bottom: 0.75rem; color: var(--dim); }
  .msg { font-size: 0.85rem; color: var(--dim); line-height: 1.6; }
</style>
</head>
<body>
<h1>KNOB: DJ Admin</h1>
<div class="subtitle">Authentication Required</div>
<div class="card">
  <div class="lock">&#128274;</div>
  <div class="msg">Enter your admin credentials to continue.</div>
</div>
</body>
</html>"""


def _render_login_page():
    return LOGIN_HTML.encode()


def _render_dj_table(djs):
    if not djs:
        return '<div class="no-djs">No DJs registered yet.</div>'
    rows = []
    for user, pw in djs:
        esc_user = html.escape(user)
        esc_pw = html.escape(pw)
        rows.append(f"""<tr>
  <td class="dj-user">{esc_user}</td>
  <td class="dj-pass"><span class="hidden-pw">{esc_pw}</span><span class="reveal-hint">hover</span></td>
  <td>
    <div class="actions">
      <form method="POST" action="./reset/{esc_user}" style="display:inline">
        <button type="submit" class="btn btn-reset"
                onclick="return confirm('Reset password for {esc_user}?')">Reset</button>
      </form>
      <form method="POST" action="./delete/{esc_user}" style="display:inline">
        <button type="submit" class="btn btn-danger"
                onclick="return confirm('Remove DJ {esc_user}?')">Remove</button>
      </form>
    </div>
  </td>
</tr>""")
    return f"""<table class="dj-table">
<tr><th>Username</th><th>Password</th><th></th></tr>
{"".join(rows)}
</table>"""


def _render_page(flash_html=""):
    djs = _read_djs()
    table = _render_dj_table(djs)
    page = ADMIN_HTML.replace("{{DJ_TABLE}}", table).replace("{{FLASH}}", flash_html)
    return page.encode()


def _flash(cls, message):
    return f'<div class="flash flash-{cls}">{message}</div>'


# --- HTTP Handler -------------------------------------------------------------

class AdminHandler(BaseHTTPRequestHandler):

    def _require_auth(self):
        """Check Basic Auth. Returns username if OK, sends 401 and returns None otherwise."""
        user = _check_auth(self.headers.get("Authorization"))
        if user:
            return user
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="KNOB Admin"')
        self.send_header("Content-Type", "text/html; charset=utf-8")
        body = _render_login_page()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return None

    def do_GET(self):
        if not self._require_auth():
            return
        path = self.path.split("?")[0].split("#")[0]
        if path in ("/", ""):
            payload = _render_page()
            self._respond(200, "text/html", payload)
        elif path == "/api/djs":
            djs = _read_djs()
            data = [{"username": u} for u, _ in djs]
            self._respond(200, "application/json", json.dumps(data).encode())
        else:
            self.send_error(404)

    def do_POST(self):
        if not self._require_auth():
            return
        path = self.path.split("?")[0].split("#")[0]
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length else ""
        params = parse_qs(body)

        if path == "/add":
            username = params.get("username", [""])[0]
            password = params.get("password", [""])[0] or None
            user, pw, err = add_dj(username, password)
            if err:
                flash = _flash("error", html.escape(err))
            else:
                flash = _flash("success",
                    f"Added DJ <code>{html.escape(user)}</code> "
                    f"with password <code>{html.escape(pw)}</code>")
            self._redirect_with_flash(flash)

        elif path.startswith("/delete/"):
            username = path[len("/delete/"):]
            err = remove_dj(username)
            if err:
                flash = _flash("error", html.escape(err))
            else:
                flash = _flash("success", f"Removed DJ <code>{html.escape(username)}</code>")
            self._redirect_with_flash(flash)

        elif path.startswith("/reset/"):
            username = path[len("/reset/"):]
            new_pw, err = reset_password(username)
            if err:
                flash = _flash("error", html.escape(err))
            else:
                flash = _flash("info",
                    f"New password for <code>{html.escape(username)}</code>: "
                    f"<code>{html.escape(new_pw)}</code>")
            self._redirect_with_flash(flash)

        else:
            self.send_error(404)

    def _redirect_with_flash(self, flash_html):
        """Render the page with a flash message (PRG-lite without session)."""
        payload = _render_page(flash_html)
        self._respond(200, "text/html", payload)

    def _respond(self, code, content_type, payload):
        self.send_response(code)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        pass


# --- Main ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="KNOB - DJ Admin Panel")
    parser.add_argument("--port", type=int, default=8081, help="HTTP port (default: 8081)")
    parser.add_argument("--bind", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--creds", default=CREDS_FILE, help="DJ credentials file path")
    parser.add_argument("--admin-creds", default=ADMIN_CREDS_FILE, help="Admin credentials file path")
    args = parser.parse_args()

    _set_creds_file(args.creds)
    _set_admin_creds_file(args.admin_creds)

    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((args.bind, args.port), AdminHandler)
    print(f"KNOB DJ Admin: http://{args.bind}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


if __name__ == "__main__":
    main()

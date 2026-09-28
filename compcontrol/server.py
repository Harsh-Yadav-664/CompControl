"""Authenticated local command UI. External binds are non-executing demo only."""
import hmac
import json
import platform
import secrets
import socket
import struct
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .broker import Broker, BrokerError, DemoExecutor
from .providers import ProviderConfig, ProviderError, TextProvider

WEB = Path(__file__).with_name('web')
MAX_BODY = 8192
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8')}


class AppServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 16

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def __init__(self, address, *, demo=False, provider=None):
        if address[0] != '127.0.0.1' and not demo:
            raise ValueError('Real desktop mode binds only to 127.0.0.1. Remote access is not implemented.')
        if not demo and struct.calcsize('P') != 8:
            raise ValueError('Use 64-bit Python for consistent Windows application paths.')
        if not demo and platform.system() != 'Windows':
            raise ValueError('Real desktop mode requires Windows. Use --demo on other systems.')
        if demo:
            executor = DemoExecutor()
            config = ProviderConfig()  # hard disabled, even when environment has secrets
        else:
            from .actions import WindowsExecutor
            executor = WindowsExecutor()
            config = provider or ProviderConfig.from_env()
        self.demo = demo
        self.token = secrets.token_urlsafe(32)
        self.broker = Broker(executor, demo=demo)
        self.provider = TextProvider(config)
        super().__init__(address, Handler)

    def allowed_host(self, host):
        if not host or any(c in host for c in '\r\n/@\\'):
            return False
        try:
            parsed = urlsplit('http://' + host)
            name, port = parsed.hostname, parsed.port
        except ValueError:
            return False
        if not self.demo:
            return name == '127.0.0.1' and port == self.server_port and host == f'127.0.0.1:{self.server_port}'
        # Demo has no provider or executor. Preview hosts are accepted only here.
        return ((name in {'127.0.0.1', 'localhost', '0.0.0.0'} and port == self.server_port)
                or (name is not None and name.endswith('.e2b.app') and port in {None, 443}))


class Handler(BaseHTTPRequestHandler):
    server_version = 'CompControl'
    sys_version = ''
    protocol_version = 'HTTP/1.0'

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_args):
        pass  # Do not log URL fragments, prompts, headers or request bodies.

    def reply(self, status, value, mime='application/json; charset=utf-8'):
        data = json.dumps(value, ensure_ascii=False).encode() if not isinstance(value, bytes) else value
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        # Only the inert demo may be embedded in Arena's preview.
        frame = '' if self.server.demo else " frame-ancestors 'none';"
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'self';" + frame)
        self.send_header('Permissions-Policy', 'microphone=(), camera=(), geolocation=()')
        if not self.server.demo:
            self.send_header('X-Frame-Options', 'DENY')
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def host_ok(self):
        hosts = self.headers.get_all('Host', [])
        if len(hosts) != 1 or not self.server.allowed_host(hosts[0]):
            self.reply(403, {'error': 'Host not allowed.'})
            return False
        return True

    def authorized(self, mutation=False):
        if not self.host_ok():
            return False
        host = self.headers['Host']
        origins = self.headers.get_all('Origin', [])
        valid_origins = {'http://' + host, 'https://' + host} if self.server.demo else {'http://' + host}
        if len(origins) > 1 or (origins and origins[0] not in valid_origins) or (mutation and not origins):
            self.reply(403, {'error': 'Same-origin request required.'})
            return False
        supplied = self.headers.get_all('Authorization', [])
        expected = 'Bearer ' + self.server.token
        if len(supplied) != 1 or not hmac.compare_digest(supplied[0].encode(), expected.encode()):
            self.reply(401, {'error': 'Session locked. Reopen the private launch URL from the terminal.'})
            return False
        return True

    def do_GET(self):
        if not self.host_ok():
            return
        if self.path in ASSETS:
            name, mime = ASSETS[self.path]
            try:
                content = (WEB / name).read_bytes()
                # PUBLIC demo-only bootstrap; never exposes the private local launch token.
                if self.path == '/' and self.server.demo:
                    content = content.replace(b'content="PRIVATE_SESSION"', ('content="' + self.server.token + '"').encode())
                self.reply(200, content, mime)
            except OSError:
                self.reply(500, {'error': 'UI assets missing. Reinstall CompControl.'})
        elif self.path == '/api/state':
            if self.authorized():
                self.reply(200, {**self.server.broker.state(), 'demo': self.server.demo,
                                'platform': platform.system(), 'provider': self.server.provider.config.public()})
        else:
            self.reply(404, {'error': 'Not found.'})

    def do_POST(self):
        if not self.authorized(mutation=True):
            return
        if self.headers.get_content_type() != 'application/json':
            self.reply(415, {'error': 'JSON required.'})
            return
        try:
            lengths = self.headers.get_all('Content-Length', [])
            if len(lengths) != 1 or self.headers.get('Transfer-Encoding'):
                raise ValueError('A single Content-Length is required.')
            size = int(lengths[0])
            if not 0 < size <= MAX_BODY:
                self.reply(413, {'error': 'Request is too large or empty.'})
                return
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError('Incomplete request.')
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError('JSON object required.')
            routes = {'/api/plan': {'text', 'browser'}, '/api/confirm': {'approval_id'},
                      '/api/cancel': {'approval_id'}, '/api/pause': {'paused'},
                      '/api/clear': set(), '/api/chat': {'text', 'persona', 'consent'}}
            if self.path not in routes:
                self.reply(404, {'error': 'Not found.'})
                return
            if set(data) - routes[self.path]:
                raise ValueError('Unexpected fields. Clients cannot supply executable actions.')
            if self.path == '/api/plan':
                value = self.server.broker.plan(data.get('text'), data.get('browser', 'default'))
            elif self.path in {'/api/confirm', '/api/cancel'}:
                approval_id = data.get('approval_id')
                if not isinstance(approval_id, str) or not 1 <= len(approval_id) <= 100:
                    raise ValueError('Approval identifier required.')
                method = self.server.broker.confirm if self.path.endswith('confirm') else self.server.broker.cancel
                value = method(approval_id)
            elif self.path == '/api/pause':
                if type(data.get('paused')) is not bool:
                    raise ValueError('Explicit boolean required.')
                value = self.server.broker.pause(data['paused'])
            elif self.path == '/api/clear':
                value = self.server.broker.clear()
            else:
                if data.get('consent') is not True:
                    raise ValueError('Explicit consent is required before sending text to the provider.')
                if data.get('persona', 'jarvis') not in {'jarvis', 'friday'}:
                    raise ValueError('Unknown persona.')
                value = {'answer': self.server.provider.answer(data.get('text'), data.get('persona', 'jarvis'))}
            self.reply(200, value)
        except BrokerError as exc:
            self.reply(exc.status, {'error': str(exc)})
        except ProviderError as exc:
            self.reply(422, {'error': str(exc)})
        except (ValueError, TypeError):
            self.reply(400, {'error': 'Invalid request. Check command length, characters and required fields.'})
        except (TimeoutError, OSError):
            self.reply(408, {'error': 'Request timed out.'})
        except Exception:
            self.reply(500, {'error': 'Internal error. No automatic retry was attempted.'})

    def do_OPTIONS(self):
        self.reply(403, {'error': 'Cross-origin API access is disabled.'})


def serve(host='127.0.0.1', port=8765, demo=False, open_browser=True):
    server = AppServer((host, port), demo=demo)
    url = f'http://127.0.0.1:{server.server_port}/#token={server.token}'
    print(f'CompControl — {"DEMO (no desktop access, no AI)" if demo else "Windows local mode"}', flush=True)
    print('Private launch URL (keep it on this device):\n' + url, flush=True)
    print('Ctrl+C stops the server. Reloading the local page locks it; reopen this URL.', flush=True)
    if open_browser and host == '127.0.0.1':
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped. Session approvals and token discarded.')
    finally:
        server.server_close()

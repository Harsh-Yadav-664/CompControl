"""Opt-in text and structured planning transport. No execution authority."""
import json
import os
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlsplit

LIMIT = 128 * 1024


class ProviderError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderError('Provider redirects are blocked. Use its direct API endpoint.')


@dataclass(frozen=True)
class ProviderConfig:
    kind: str = 'off'
    base_url: str = ''
    model: str = ''
    api_key: str = field(default='', repr=False)

    @classmethod
    def from_env(cls):
        kind = os.getenv('COMPCONTROL_PROVIDER', 'off').strip().lower()
        base = os.getenv('COMPCONTROL_BASE_URL', 'http://127.0.0.1:11434' if kind == 'ollama' else '').rstrip('/')
        cfg = cls(kind, base, os.getenv('COMPCONTROL_MODEL', '').strip(),
                  os.getenv('COMPCONTROL_API_KEY', ''))
        cfg.validate()
        return cfg

    def validate(self):
        if self.kind == 'off':
            return
        if self.kind not in {'ollama', 'openai'}:
            raise ProviderError('Provider must be off, ollama or openai.')
        if not self.model or len(self.model) > 100 or any(ord(c) < 32 for c in self.model):
            raise ProviderError('Set COMPCONTROL_MODEL to the exact installed/provider model name.')
        try:
            p = urlsplit(self.base_url)
            port = p.port
        except ValueError as exc:
            raise ProviderError('Invalid provider URL.') from exc
        if (not p.hostname or p.username or p.password or p.query or p.fragment
                or any(ord(c) < 33 for c in self.base_url) or len(self.base_url) > 500):
            raise ProviderError('Provider URL must have a plain host and no credentials, query or fragment.')
        if self.kind == 'ollama':
            if p.scheme != 'http' or p.hostname not in {'127.0.0.1', '::1'} or p.path not in {'', '/'}:
                raise ProviderError('Ollama must use a literal loopback HTTP address, for example http://127.0.0.1:11434.')
        elif p.scheme != 'https':
            raise ProviderError('OpenAI-compatible providers require HTTPS.')
        if port == 0 or any(ord(c) < 32 or ord(c) > 126 for c in self.api_key):
            raise ProviderError('Invalid provider port or API key format.')

    def public(self):
        p = urlsplit(self.base_url)
        return {'enabled': self.kind != 'off', 'kind': self.kind,
                'model': self.model, 'host': p.hostname or '',
                'cloud': self.kind == 'openai', 'key_configured': bool(self.api_key)}


class TextProvider:
    def __init__(self, config, transport=None):
        config.validate()
        self.config = config
        self._lock = threading.Lock()
        self.transport = transport or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect())

    def answer(self, prompt, persona='jarvis'):
        system = ('You are ' + ('Friday' if persona == 'friday' else 'Jarvis') +
                  ', a concise text-only assistant inside CompControl. You cannot execute tools, browse, '
                  'read files, see the screen or verify desktop state. Never claim that you performed '
                  'an action. Suggest supported commands as text if useful. Do not request secrets.')
        return self._request(prompt, system)

    def propose(self, prompt, browser='default'):
        from .ai_planner import SYSTEM, parse_proposal
        from .planner import clean
        raw = self._request(clean(prompt), SYSTEM, structured=True)
        plan = parse_proposal(raw, browser)
        # An inferred domain is not a grounded destination. Require an exact explicit
        # URL in the approved request; no model-authored download/install link.
        import re
        supplied = set(re.findall(r'https://[^\s]+', prompt))
        if any(a.kind == 'navigate' and a.target not in supplied for a in plan.actions):
            raise ProviderError('AI proposed a URL not explicitly present in your request. '
                                'Paste the exact HTTPS address or request a web search instead.')
        return plan

    def _request(self, prompt, system, structured=False):
        if self.config.kind == 'off':
            raise ProviderError('AI is off. Open AI settings to configure a model.')
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 2000:
            raise ProviderError('AI requests must contain 1–2000 characters.')
        if not self._lock.acquire(blocking=False):
            raise ProviderError('An AI request is already in progress. Wait for it to finish.')
        try:
            return self._complete(prompt, system, structured)
        finally:
            self._lock.release()

    def _complete(self, prompt, system, structured=False):
        cfg = self.config
        messages = [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}]
        if cfg.kind == 'ollama':
            url = cfg.base_url.rstrip('/') + '/api/chat'
            body = {'model': cfg.model, 'messages': messages, 'stream': False,
                    'keep_alive': '2m', 'options': {'num_predict': 512, 'num_ctx': 4096}}
        else:
            url = cfg.base_url.rstrip('/') + '/chat/completions'
            body = {'model': cfg.model, 'messages': messages, 'stream': False, 'max_tokens': 512}
        if structured and cfg.kind == 'ollama':
            body['format'] = 'json'
        # Only documented hosted adapters get vendor options; custom APIs stay generic.
        base = cfg.base_url.rstrip('/')
        if structured and base in {
                'https://api.groq.com/openai/v1',
                'https://generativelanguage.googleapis.com/v1beta/openai'}:
            body['response_format'] = {'type': 'json_object'}
        if base == 'https://api.groq.com/openai/v1' and cfg.model.startswith('openai/gpt-oss-'):
            body['reasoning_effort'] = 'low'
            body['max_tokens'] = 2048  # Include reasoning budget, not just final JSON.
        if base == 'https://generativelanguage.googleapis.com/v1beta/openai' and cfg.model == 'gemini-2.5-flash-lite':
            body['extra_body'] = {'google': {'thinking_config': {'thinking_budget': 0}}}

        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if cfg.kind == 'openai' and cfg.api_key:
            headers['Authorization'] = 'Bearer ' + cfg.api_key
        request = urllib.request.Request(url, json.dumps(body).encode(), headers, method='POST')
        try:
            with self.transport.open(request, timeout=30) as response:
                raw = response.read(LIMIT + 1)
                if len(raw) > LIMIT:
                    raise ProviderError('Provider response exceeded the size limit.')
                data = json.loads(raw)
                if cfg.kind != 'ollama' and data['choices'][0].get('finish_reason') == 'length':
                    raise ProviderError('The model hit its output limit. No proposal was accepted. '
                                        'Choose a non-reasoning text model or shorten the request.')
                answer = data['message']['content'] if cfg.kind == 'ollama' else data['choices'][0]['message']['content']
                if not isinstance(answer, str) or not answer.strip():
                    raise ValueError()
                if len(answer) > 12000:
                    raise ProviderError('AI output was too long; no proposal was accepted.')
                return answer
        except ProviderError:
            raise
        except urllib.error.HTTPError as exc:
            # Never include response bodies, headers, credentials or request object repr.
            hints = {
                401: 'API key rejected. Paste a valid key for the selected provider in AI settings.',
                403: 'This key/account cannot access the model. Check provider permissions and region eligibility.',
                404: 'Model or endpoint not found. Copy a currently available text model ID from the provider console.',
                429: 'Provider quota or rate limit reached. Check your free quota/reset time; no retry or paid fallback was made.',
            }
            raise ProviderError(f'Provider HTTP {exc.code}: ' + hints.get(exc.code,
                'Request failed. Check the model, endpoint and account settings. No automatic retry was made.')) from None
        except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError, RecursionError):
            raise ProviderError('AI request failed or timed out. Check the local service/endpoint and model. No action was taken.') from None

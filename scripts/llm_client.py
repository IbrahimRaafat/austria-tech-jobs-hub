"""Minimal LLM client for the resume tailor: local Ollama or cloud Gemini.

Standard library only (urllib), matching the rest of the scripts.

Configuration (environment variables, or a gitignored `.env` file in the repo root):
    OLLAMA_URL          base URL of the local Ollama server (default: http://127.0.0.1:11434)
    TAILOR_OLLAMA_MODEL local model for tailoring (default: $OLLAMA_MODEL or qwen2.5:7b)
    GEMINI_API_KEY      Google AI Studio key - required for cloud mode
    GEMINI_MODEL        Gemini model id (default: gemini-3.8-flash)
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_dotenv(path=None):
    """Loads KEY=VALUE lines from .env without overriding real environment variables."""
    path = path or os.path.join(REPO_ROOT, '.env')
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()


class LLMError(RuntimeError):
    def __init__(self, message, status=None, retry_after=None):
        super().__init__(message)
        self.status = status  # HTTP status code, 'timeout' or 'network'
        self.retry_after = retry_after  # seconds the server asked us to wait, if any


def _post_json(url, payload, headers=None, timeout=300):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', **(headers or {})},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        delay = re.search(r'"retryDelay":\s*"(\d+(?:\.\d+)?)s"', body) or re.search(r'^(\d+)$', e.headers.get('Retry-After') or '')
        raise LLMError(f"HTTP {e.code} from {url.split('?')[0]}: {body[:500]}", status=e.code,
                       retry_after=float(delay.group(1)) if delay else None) from e
    except urllib.error.URLError as e:
        raise LLMError(f"Could not reach {url.split('?')[0]}: {e.reason}", status='network') from e
    except TimeoutError as e:
        raise LLMError(f"Model did not answer within {timeout}s - it is too slow on this machine. "
                       "Try a smaller local model, raise TAILOR_TIMEOUT, or use cloud mode.", status='timeout') from e


def parse_json_response(text):
    """Parses a JSON object from model output, tolerating ```json fences and chatter."""
    text = text.strip()
    fenced = re.search(r'```(?:json)?\s*(.*?)```', text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find('{'), text.rfind('}')
        if start != -1 and end > start:
            return json.loads(text[start:end + 1])
        raise


class OllamaClient:
    name = 'local'

    def __init__(self, model=None, base_url=None):
        base = base_url or os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
        # OLLAMA_URL is also used by agent_classifier.py as the full /api/generate endpoint
        self.base_url = base.split('/api/')[0].rstrip('/')
        self.model = model or os.environ.get('TAILOR_OLLAMA_MODEL') or os.environ.get('OLLAMA_MODEL') or 'qwen2.5:7b'

    @property
    def label(self):
        return f"Ollama ({self.model})"

    def is_available(self):
        # Ollama is always local, so a short timeout is enough (a refused port can otherwise stall ~2s on Windows)
        try:
            urllib.request.urlopen(self.base_url, timeout=0.5)
            return True
        except Exception:
            return False

    @staticmethod
    def _context_size(text):
        needed = len(text) / 3.5 + 3000
        return min(32768, max(4096, int(-(-needed // 2048) * 2048)))

    def generate(self, system, prompt, json_mode=False, temperature=0.3):
        payload = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': prompt},
            ],
            'stream': False,
            # Resume + job posting exceed Ollama's small default context window, but a fixed large
            # window wastes RAM and slows CPU inference, so size it to the prompt (~3.5 chars/token)
            # plus room for a full resume in the answer.
            'options': {'temperature': temperature, 'num_ctx': self._context_size(system + prompt)},
        }
        if json_mode:
            payload['format'] = 'json'
        result = _post_json(f"{self.base_url}/api/chat", payload, timeout=int(os.environ.get('TAILOR_TIMEOUT', 1200)))
        if 'error' in result:
            raise LLMError(f"Ollama: {result['error']}")
        return result.get('message', {}).get('content', '')


class GeminiClient:
    name = 'cloud'
    API_BASE = 'https://generativelanguage.googleapis.com/v1beta/models'

    # Tried in order when the preferred model is overloaded (503/429), retired (404) or times out
    DEFAULT_FALLBACKS = 'gemini-3.7-flash,gemini-3.5-flash,gemini-flash-latest,gemini-2.5-flash'
    RETRYABLE = (404, 429, 500, 503, 'timeout', 'network')
    BACKOFF = (8, 20, 40)  # waits between attempts on the same model when overloaded/rate-limited
    MIN_INTERVAL = 4  # seconds between calls, to stay under free-tier requests-per-minute limits

    def __init__(self, model=None, api_key=None):
        self.model = model or os.environ.get('GEMINI_MODEL', 'gemini-3.8-flash')
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY', '')
        fallbacks = os.environ.get('GEMINI_FALLBACK_MODELS', self.DEFAULT_FALLBACKS)
        self.preferred = self.model
        self._last_call = 0.0
        self.fallbacks = [m.strip() for m in fallbacks.split(',') if m.strip()]

    @property
    def label(self):
        return f"Gemini ({self.model})"

    def is_available(self):
        return bool(self.api_key)

    def generate(self, system, prompt, json_mode=False, temperature=0.3):
        if not self.api_key:
            raise LLMError("GEMINI_API_KEY is not set (add it to your environment or .env)")
        generation_config = {'temperature': temperature}
        if json_mode:
            generation_config['responseMimeType'] = 'application/json'
        payload = {
            'systemInstruction': {'parts': [{'text': system}]},
            'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
            'generationConfig': generation_config,
        }
        result = self._post_with_fallback(payload)
        candidates = result.get('candidates') or []
        if not candidates:
            reason = result.get('promptFeedback', {}).get('blockReason', 'no candidates returned')
            raise LLMError(f"Gemini returned no output ({reason})")
        parts = candidates[0].get('content', {}).get('parts', [])
        return ''.join(p.get('text', '') for p in parts if not p.get('thought'))

    def _post_with_fallback(self, payload):
        errors = []
        # Last model that answered first, then the configured order, each model once
        candidates = list(dict.fromkeys([self.model, self.preferred, *self.fallbacks]))
        for model in candidates:
            for attempt in range(len(self.BACKOFF) + 1):
                time.sleep(max(0.0, self._last_call + self.MIN_INTERVAL - time.time()))
                self._last_call = time.time()
                try:
                    result = _post_json(f"{self.API_BASE}/{model}:generateContent", payload,
                                        headers={'x-goog-api-key': self.api_key},
                                        timeout=int(os.environ.get('GEMINI_TIMEOUT', 180)))
                    self.model = model  # stick with the model that answered for the rest of the run
                    return result
                except LLMError as e:
                    if e.status not in self.RETRYABLE:
                        raise
                    errors.append(f"{model}: {e.status}")
                    if e.status in (404, 'timeout') or attempt == len(self.BACKOFF):
                        break  # retrying the same model will not help / give up on it
                    time.sleep(min(60.0, e.retry_after or self.BACKOFF[attempt]))
        raise LLMError("All Gemini models are unavailable right now (" + ', '.join(errors) + "). Try again in a few minutes.")


PROVIDER_ALIASES = {'local': 'local', 'ollama': 'local', 'cloud': 'cloud', 'gemini': 'cloud'}


def get_client(provider='auto', model=None):
    """Returns a client for 'local'/'ollama', 'cloud'/'gemini', or 'auto'
    (local Ollama if it is running, otherwise Gemini if a key is configured)."""
    provider = (provider or 'auto').lower()
    if provider == 'auto':
        local = OllamaClient(model=model)
        if local.is_available():
            return local
        cloud = GeminiClient(model=model)
        if cloud.is_available():
            return cloud
        raise LLMError("No LLM available: start Ollama (`ollama serve`) or set GEMINI_API_KEY")
    if provider not in PROVIDER_ALIASES:
        raise LLMError(f"Unknown provider '{provider}' (use local, cloud or auto)")
    client = OllamaClient(model=model) if PROVIDER_ALIASES[provider] == 'local' else GeminiClient(model=model)
    if not client.is_available():
        hint = "start it with `ollama serve`" if client.name == 'local' else "set GEMINI_API_KEY"
        raise LLMError(f"{client.label} is not available - {hint}")
    return client


def provider_status():
    local, cloud = OllamaClient(), GeminiClient()
    return {
        'local': {'available': local.is_available(), 'label': local.label},
        'cloud': {'available': cloud.is_available(), 'label': cloud.label},
    }

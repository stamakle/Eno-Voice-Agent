from __future__ import annotations

import json
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError

from english_tech.observability.metrics import metrics_store


class JsonLlmClient:
    def __init__(self, *, provider: str, base_url: str, model: str, api_key: str, timeout_seconds: float) -> None:
        self.provider = provider.strip().lower()
        self.base_url = base_url.rstrip('/')
        self.model = model.strip()
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    @property
    def enabled(self) -> bool:
        return self.provider in {'ollama', 'openai_compat'} and bool(self.model)

    def generate_json(self, prompt: str, *, system_prompt: str = 'Return strict JSON only.') -> dict | None:
        if not self.enabled:
            return None
        try:
            if self.provider == 'ollama':
                raw = self._call_ollama(prompt)
            elif self.provider == 'openai_compat':
                raw = self._call_openai_compat(prompt, system_prompt=system_prompt)
            else:
                return None
        except (URLError, HTTPError, TimeoutError, ValueError):
            metrics_store.record_llm(surface='json', provider=self.provider or 'none', success=False)
            return None
        payload = self._extract_json(raw)
        metrics_store.record_llm(surface='json', provider=self.provider or 'none', success=payload is not None)
        return payload

    def _call_ollama(self, prompt: str) -> str:
        body = json.dumps({
            'model': self.model,
            'prompt': prompt,
            'stream': False,
            'format': 'json',
        }).encode('utf-8')
        req = urllib_request.Request(
            f'{self.base_url}/api/generate',
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib_request.urlopen(req, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode('utf-8'))
        return str(payload.get('response', '')).strip()

    def _call_openai_compat(self, prompt: str, *, system_prompt: str) -> str:
        body = json.dumps({
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': 0.2,
            'response_format': {'type': 'json_object'},
        }).encode('utf-8')
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        req = urllib_request.Request(
            f'{self.base_url}/v1/chat/completions',
            data=body,
            headers=headers,
            method='POST',
        )
        with urllib_request.urlopen(req, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode('utf-8'))
        choices = payload.get('choices', [])
        if not choices:
            return ''
        return str(choices[0].get('message', {}).get('content', '')).strip()

    def _extract_json(self, raw: str) -> dict | None:
        raw = raw.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find('{')
            end = raw.rfind('}')
            if start == -1 or end == -1 or end <= start:
                return None
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                return None

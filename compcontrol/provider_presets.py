"""Hosted API presets. No SDKs, model downloads, billing or credential storage."""
from dataclasses import dataclass

from .providers import ProviderConfig


@dataclass(frozen=True)
class Preset:
    kind: str
    base_url: str
    model: str
    note: str


PRESETS = {
    'Groq (cloud)': Preset('openai', 'https://api.groq.com/openai/v1', 'openai/gpt-oss-20b',
        'Runs on Groq, not your laptop. Check your account’s model access and free-tier limits.'),
    'Gemini (cloud)': Preset('openai', 'https://generativelanguage.googleapis.com/v1beta/openai',
        'gemini-2.5-flash-lite', 'Use a Google AI Studio API key. Free quota and data terms depend on model/account.'),
    'NVIDIA NIM (cloud)': Preset('openai', 'https://integrate.api.nvidia.com/v1',
        'meta/llama-3.3-70b-instruct', 'Hosted NVIDIA API: no GPU, Docker or local NIM install required. Check development access/quota.'),
    'Custom OpenAI-compatible': Preset('openai', '', '',
        'Enter the direct HTTPS API base URL and a text chat model. Pricing/access depend on your provider.'),
    'Off (local skills only)': Preset('off', '', '', 'App launching and YouTube/Spotify searches need no AI or API key.'),
    'Ollama (optional local model)': Preset('ollama', 'http://127.0.0.1:11434', '',
        'Only if you already run a local model. Not required for any cloud provider.'),
}


def preset_for(config):
    if config.kind == 'off':
        return 'Off (local skills only)'
    for label, preset in PRESETS.items():
        if preset.base_url and preset.kind == config.kind and preset.base_url == config.base_url.rstrip('/'):
            return label
    return 'Ollama (optional local model)' if config.kind == 'ollama' else 'Custom OpenAI-compatible'


def config_from_fields(label, base_url, model, api_key):
    preset = PRESETS[label]
    if preset.kind == 'off':
        return ProviderConfig()
    config = ProviderConfig(preset.kind, base_url.strip().rstrip('/') or preset.base_url,
                            model.strip(), api_key.strip())
    config.validate()
    return config

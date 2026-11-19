"""OpenRouter chat client with model fallback. Free-model IDs change often, so they are configurable."""
import os

import httpx

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODELS = [
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "openrouter/free",  # router that picks any currently-available free model
]


def models():
    env = os.environ.get("OPENROUTER_MODELS", "")
    lst = [m.strip() for m in env.split(",") if m.strip()]
    return lst or DEFAULT_MODELS


async def complete(messages, max_tokens=700, temperature=0.2):
    """Returns (text, model_used). Raises RuntimeError if no model could answer."""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.environ.get("APP_URL", "https://example.com"),
        "X-Title": "DarGlobal and Wasalt Assistant",
    }
    errors = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0)) as client:
        for model in models():
            try:
                r = await client.post(API_URL, headers=headers, json={
                    "model": model, "messages": messages,
                    "max_tokens": max_tokens, "temperature": temperature,
                })
                if r.status_code != 200:
                    errors.append(f"{model}: HTTP {r.status_code}")
                    continue
                data = r.json()
                text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                text = text.strip()
                if not text:
                    errors.append(f"{model}: empty reply")
                    continue
                return text, data.get("model") or model
            except (httpx.HTTPError, ValueError) as e:
                errors.append(f"{model}: {type(e).__name__}")
    raise RuntimeError("; ".join(errors) or "no models configured")

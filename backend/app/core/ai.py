"""Neutral LLM layer. Idea code calls generate_text / generate_json and never a vendor SDK directly.
Add a provider by writing a class with an async `text(prompt, system, model)` method and registering it.
Callers can pick the provider and model per call (`provider=`, `llm_model=`), e.g. a fast model for live turns
and a stronger one for grading. Blank means LLM_PROVIDER / GEMINI_MODEL."""
import json
import re

from app import config


class AIError(Exception):
    pass


class FakeProvider:
    """Works with no keys. Use for tests and as a demo fallback."""
    name = "fake"

    async def text(self, prompt: str, system: str | None = None, model: str | None = None) -> str:
        return json.dumps({"note": "fake AI provider; set LLM_PROVIDER and a key", "echo": prompt[:200]})


class GeminiProvider:
    """Calls Google's Gemini generateContent REST API. Needs GEMINI_API_KEY and GEMINI_MODEL in .env."""
    name = "gemini"

    async def text(self, prompt: str, system: str | None = None, model: str | None = None) -> str:
        import logging
        import httpx  # lazy import
        logging.getLogger("httpx").setLevel(logging.WARNING)  # never log URLs (the key is a query param)
        if not config.GEMINI_API_KEY:
            raise AIError("GEMINI_API_KEY is empty. Add it to .env and restart the server.")
        model = (model or config.GEMINI_MODEL).removeprefix("models/")
        if not model:
            raise AIError("GEMINI_MODEL is empty. Set it in .env to a model name from Google's current model list.")
        body: dict = {"contents": [{"parts": [{"text": prompt}]}]}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{config.GEMINI_BASE_URL}/models/{model}:generateContent",
                params={"key": config.GEMINI_API_KEY},
                json=body,
            )
        if resp.status_code != 200:
            raise AIError(f"Gemini error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise AIError(f"Gemini returned no answer (blocked or empty): {str(data.get('promptFeedback', data))[:300]}")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        if not text:
            raise AIError(f"Gemini returned an empty answer (finish reason: {candidates[0].get('finishReason')})")
        return text


PROVIDERS = {"fake": FakeProvider, "gemini": GeminiProvider}


def get_provider(name: str | None = None):
    name = name or config.LLM_PROVIDER
    if name not in PROVIDERS:
        raise AIError(f"unknown provider '{name}'. Options: {', '.join(PROVIDERS)}")
    return PROVIDERS[name]()


async def generate_text(prompt: str, system: str | None = None, *, llm_model: str | None = None,
                        provider: str | None = None) -> str:
    return await get_provider(provider).text(prompt, system, llm_model)


def _extract_json(raw: str) -> str:
    raw = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    return fenced.group(1).strip() if fenced else raw


async def generate_json(prompt: str, model=None, system: str | None = None, retries: int = 1, *,
                        llm_model: str | None = None, provider: str | None = None) -> dict:
    """Ask for JSON. If `model` (a Pydantic class) is given, validate against it.
    On invalid output, retry with the error appended, then raise AIError.
    `llm_model` / `provider` pick the LLM for this call (`model` is the Pydantic schema, kept for old callers)."""
    attempt_prompt = prompt
    last_error = None
    for _ in range(retries + 1):
        extra = {k: v for k, v in (("llm_model", llm_model), ("provider", provider)) if v}
        raw = await generate_text(attempt_prompt, system, **extra)  # no extras unless set: keeps test doubles working
        try:
            text = _extract_json(raw)
            if model is not None:
                return model.model_validate_json(text).model_dump()
            return json.loads(text)
        except ValueError as e:  # JSON decode errors and pydantic ValidationError
            last_error = e
            attempt_prompt = f"{prompt}\n\nYour previous reply was invalid ({e}). Reply with valid JSON only."
    raise AIError(f"invalid JSON after {retries + 1} attempts: {last_error}")
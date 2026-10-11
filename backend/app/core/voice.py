"""Neutral voice layer. Swap providers with VOICE_PROVIDER.
Providers implement `async def stream(text, voice_id)`, an async generator of raw audio bytes,
and `mint_token()`. `speak()` collects a whole clip."""
from typing import AsyncIterator

from app import config


class VoiceError(Exception):
    pass


class FakeVoice:
    name = "fake"

    async def stream(self, text: str, voice_id: str | None = None) -> AsyncIterator[bytes]:
        return
        yield  # makes this an async generator that yields nothing: no audio, no error

    async def mint_token(self) -> str | None:
        return None


class ElevenLabsVoice:
    """Streaming text to speech. POST /v1/text-to-speech/{voice_id}/stream, key in the xi-api-key header.
    Output is raw PCM (default pcm_16000: 16-bit mono little-endian). Verified by spikes/spike_tts.py."""
    name = "elevenlabs"
    BASE = "https://api.elevenlabs.io/v1"

    async def stream(self, text: str, voice_id: str | None = None) -> AsyncIterator[bytes]:
        import httpx  # lazy import
        voice_id = voice_id or config.ELEVENLABS_VOICE_ID
        if not config.ELEVENLABS_API_KEY:
            raise VoiceError("ELEVENLABS_API_KEY is empty. Add it to .env and restart the server.")
        if not voice_id:
            raise VoiceError("ELEVENLABS_VOICE_ID is empty. Set a voice your plan can use in .env.")
        body: dict = {"text": text}
        if config.ELEVENLABS_MODEL:
            body["model_id"] = config.ELEVENLABS_MODEL
        async with httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10)) as client:
            async with client.stream(
                "POST", f"{self.BASE}/text-to-speech/{voice_id}/stream",
                params={"output_format": config.ELEVENLABS_OUTPUT_FORMAT},
                headers={"xi-api-key": config.ELEVENLABS_API_KEY}, json=body,
            ) as resp:
                if resp.status_code != 200:
                    detail = (await resp.aread()).decode(errors="replace")[:200]
                    raise VoiceError(f"ElevenLabs error {resp.status_code}: {detail}")
                async for chunk in resp.aiter_bytes():
                    if chunk:
                        yield chunk

    async def mint_token(self) -> str | None:
        # The browser never talks to ElevenLabs directly: audio is relayed over our websocket,
        # so the API key never reaches the frontend.
        return None


PROVIDERS = {"fake": FakeVoice, "elevenlabs": ElevenLabsVoice}


def get_provider():
    if config.VOICE_PROVIDER not in PROVIDERS:
        raise ValueError(f"unknown VOICE_PROVIDER '{config.VOICE_PROVIDER}'. Options: {', '.join(PROVIDERS)}")
    return PROVIDERS[config.VOICE_PROVIDER]()


def stream(text: str, voice_id: str | None = None) -> AsyncIterator[bytes]:
    return get_provider().stream(text, voice_id)


async def speak(text: str, voice_id: str | None = None) -> bytes:
    return b"".join([chunk async for chunk in stream(text, voice_id)])


async def mint_token() -> str | None:
    return await get_provider().mint_token()

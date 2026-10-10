"""Neutral voice layer. Swap providers with VOICE_PROVIDER."""
from app import config


class FakeVoice:
    name = "fake"

    async def speak(self, text: str, voice_id: str | None = None) -> bytes:
        return b""

    async def mint_token(self) -> str | None:
        return None


class ElevenLabsVoice:
    name = "elevenlabs"

    async def speak(self, text: str, voice_id: str | None = None) -> bytes:
        # TODO: text-to-speech via ElevenLabs. Check their docs for the current endpoint.
        raise NotImplementedError

    async def mint_token(self) -> str | None:
        # TODO: if the browser talks to ElevenLabs directly, mint a short-lived token here
        # so config.ELEVENLABS_API_KEY never reaches the frontend. Check their docs for the mechanism.
        return None


PROVIDERS = {"fake": FakeVoice, "elevenlabs": ElevenLabsVoice}


def get_provider():
    if config.VOICE_PROVIDER not in PROVIDERS:
        raise ValueError(f"unknown VOICE_PROVIDER '{config.VOICE_PROVIDER}'. Options: {', '.join(PROVIDERS)}")
    return PROVIDERS[config.VOICE_PROVIDER]()


async def speak(text: str, voice_id: str | None = None) -> bytes:
    return await get_provider().speak(text, voice_id)


async def mint_token() -> str | None:
    return await get_provider().mint_token()

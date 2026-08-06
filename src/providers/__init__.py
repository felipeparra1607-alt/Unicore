from src.ai_config import AISettings
from src.providers.base import AIProvider
from src.providers.mock_provider import MockProvider
from src.providers.openai_provider import OpenAIProvider


def create_provider(
    settings: AISettings,
    requested_provider: str | None = None,
) -> AIProvider:
    """Crea el proveedor solicitado."""

    provider_name = (
        requested_provider.strip().casefold()
        if requested_provider
        else settings.provider
    )

    if provider_name == "mock":
        return MockProvider()

    if provider_name == "openai":
        return OpenAIProvider(settings)

    raise ValueError(
        f"Proveedor no compatible: {provider_name}"
    )


def available_providers() -> list[dict]:
    """Lista los proveedores implementados."""

    return [
        {
            "provider": "mock",
            "requires_api_key": False,
            "makes_external_request": False,
            "purpose": "Pruebas técnicas sin coste",
        },
        {
            "provider": "openai",
            "requires_api_key": True,
            "makes_external_request": True,
            "purpose": "Generación mediante API",
        },
    ]
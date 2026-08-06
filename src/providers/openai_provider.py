from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
)

from src.ai_config import AISettings
from src.providers.base import (
    AIProvider,
    GenerationRequest,
    GenerationResult,
)


class OpenAIProvider(AIProvider):
    """Proveedor generativo mediante la API de OpenAI."""

    provider_name = "openai"

    def __init__(
        self,
        settings: AISettings,
    ) -> None:
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY no está configurada"
            )

        self.settings = settings

        self.client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_seconds,
        )

    def generate(
        self,
        request: GenerationRequest,
    ) -> GenerationResult:
        """Genera una respuesta con OpenAI."""

        try:
            response = self.client.responses.create(
                model=self.settings.openai_model,
                instructions=request.system_message,
                input=request.user_message,
                max_output_tokens=(
                    request.maximum_output_tokens
                ),
                store=False,
            )

            output_text = (
                response.output_text.strip()
                if response.output_text
                else ""
            )

            usage = getattr(response, "usage", None)

            input_tokens = (
                getattr(usage, "input_tokens", None)
                if usage is not None
                else None
            )

            output_tokens = (
                getattr(usage, "output_tokens", None)
                if usage is not None
                else None
            )

            total_tokens = (
                getattr(usage, "total_tokens", None)
                if usage is not None
                else None
            )

            if not output_text:
                return GenerationResult(
                    ok=False,
                    provider=self.provider_name,
                    model=self.settings.openai_model,
                    response_id=getattr(
                        response,
                        "id",
                        None,
                    ),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    error="OpenAI no devolvió texto",
                )

            return GenerationResult(
                ok=True,
                provider=self.provider_name,
                model=self.settings.openai_model,
                text=output_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                response_id=getattr(
                    response,
                    "id",
                    None,
                ),
                metadata={
                    "api_called": True,
                    "stored_by_provider": False,
                },
            )

        except APITimeoutError as error:
            return GenerationResult(
                ok=False,
                provider=self.provider_name,
                model=self.settings.openai_model,
                error=(
                    "La llamada superó el tiempo máximo"
                ),
                technical_detail=str(error),
            )

        except APIConnectionError as error:
            return GenerationResult(
                ok=False,
                provider=self.provider_name,
                model=self.settings.openai_model,
                error=(
                    "No se pudo conectar con OpenAI"
                ),
                technical_detail=str(error),
            )

        except APIStatusError as error:
            return GenerationResult(
                ok=False,
                provider=self.provider_name,
                model=self.settings.openai_model,
                error="OpenAI devolvió un error de API",
                technical_detail=(
                    f"HTTP {error.status_code}: {error}"
                ),
                metadata={
                    "status_code": error.status_code,
                },
            )

        except Exception as error:
            return GenerationResult(
                ok=False,
                provider=self.provider_name,
                model=self.settings.openai_model,
                error=(
                    "Se produjo un error generando "
                    "la respuesta"
                ),
                technical_detail=str(error),
            )
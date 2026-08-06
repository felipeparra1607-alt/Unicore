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


def calculate_cost(
    token_count: int | None,
    price_per_million: float,
) -> float | None:
    """Calcula el coste aproximado en dólares."""

    if token_count is None:
        return None

    return round(
        token_count * price_per_million / 1_000_000,
        8,
    )


class OpenAIProvider(AIProvider):
    """Proveedor mediante OpenAI Responses API."""

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
        """Genera una respuesta mediante OpenAI."""

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

            response_status = getattr(
                response,
                "status",
                None,
            )

            incomplete_details = getattr(
                response,
                "incomplete_details",
                None,
            )

            incomplete_reason = (
                getattr(
                    incomplete_details,
                    "reason",
                    None,
                )
                if incomplete_details is not None
                else None
            )

            truncated = (
                response_status == "incomplete"
                and incomplete_reason
                == "max_output_tokens"
            )

            input_cost = calculate_cost(
                input_tokens,
                self.settings.openai_input_price_per_million,
            )

            output_cost = calculate_cost(
                output_tokens,
                self.settings.openai_output_price_per_million,
            )

            total_cost = (
                round(input_cost + output_cost, 8)
                if input_cost is not None
                and output_cost is not None
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
                    response_status=response_status,
                    incomplete_reason=incomplete_reason,
                    truncated=truncated,
                    estimated_input_cost_usd=input_cost,
                    estimated_output_cost_usd=output_cost,
                    estimated_total_cost_usd=total_cost,
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
                response_status=response_status,
                incomplete_reason=incomplete_reason,
                truncated=truncated,
                estimated_input_cost_usd=input_cost,
                estimated_output_cost_usd=output_cost,
                estimated_total_cost_usd=total_cost,
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
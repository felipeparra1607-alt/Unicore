import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def read_boolean_environment(
    variable_name: str,
    default: bool,
) -> bool:
    """Lee una variable de entorno booleana."""

    raw_value = os.getenv(variable_name)

    if raw_value is None:
        return default

    return raw_value.strip().casefold() in {
        "1",
        "true",
        "yes",
        "y",
        "sí",
        "si",
    }


def read_integer_environment(
    variable_name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    """Lee y valida una variable entera."""

    raw_value = os.getenv(variable_name)

    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        return default

    return max(minimum, min(maximum, value))


def read_float_environment(
    variable_name: str,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    """Lee y valida una variable decimal."""

    raw_value = os.getenv(variable_name)

    if raw_value is None:
        return default

    try:
        value = float(raw_value)
    except ValueError:
        return default

    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class AISettings:
    """Configuración común de proveedores generativos."""

    provider: str
    openai_api_key: str | None
    openai_model: str
    openai_timeout_seconds: int
    maximum_output_tokens: int
    fallback_to_extractive: bool

    openai_input_price_per_million: float
    openai_output_price_per_million: float


def get_ai_settings() -> AISettings:
    """Obtiene la configuración desde variables de entorno."""

    api_key = os.getenv(
        "OPENAI_API_KEY",
        "",
    ).strip()

    return AISettings(
        provider=os.getenv(
            "UNICORE_AI_PROVIDER",
            "mock",
        ).strip().casefold(),
        openai_api_key=api_key or None,
        openai_model=os.getenv(
            "OPENAI_MODEL",
            "gpt-5.6-luna",
        ).strip(),
        openai_timeout_seconds=read_integer_environment(
            variable_name="OPENAI_TIMEOUT_SECONDS",
            default=60,
            minimum=5,
            maximum=300,
        ),
        maximum_output_tokens=read_integer_environment(
            variable_name="UNICORE_MAX_OUTPUT_TOKENS",
            default=600,
            minimum=100,
            maximum=10000,
        ),
        fallback_to_extractive=read_boolean_environment(
            variable_name="UNICORE_FALLBACK_TO_EXTRACTIVE",
            default=True,
        ),
        openai_input_price_per_million=(
            read_float_environment(
                variable_name=(
                    "OPENAI_INPUT_PRICE_PER_MILLION"
                ),
                default=1.0,
                minimum=0.0,
                maximum=1000.0,
            )
        ),
        openai_output_price_per_million=(
            read_float_environment(
                variable_name=(
                    "OPENAI_OUTPUT_PRICE_PER_MILLION"
                ),
                default=6.0,
                minimum=0.0,
                maximum=1000.0,
            )
        ),
    )
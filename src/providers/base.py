from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GenerationRequest:
    """Petición común para cualquier proveedor de IA."""

    system_message: str
    user_message: str
    maximum_output_tokens: int


@dataclass
class GenerationResult:
    """Resultado normalizado de cualquier proveedor."""

    ok: bool
    provider: str
    model: str
    text: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    response_id: str | None = None

    response_status: str | None = None
    incomplete_reason: str | None = None
    truncated: bool = False

    estimated_input_cost_usd: float | None = None
    estimated_output_cost_usd: float | None = None
    estimated_total_cost_usd: float | None = None

    error: str | None = None
    technical_detail: str | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class AIProvider(ABC):
    """Contrato común de los proveedores de IA."""

    provider_name: str

    @abstractmethod
    def generate(
        self,
        request: GenerationRequest,
    ) -> GenerationResult:
        """Genera texto a partir de una petición."""
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
    """Resultado común devuelto por cualquier proveedor."""

    ok: bool
    provider: str
    model: str
    text: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    response_id: str | None = None
    error: str | None = None
    technical_detail: str | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


class AIProvider(ABC):
    """Contrato que deben respetar todos los proveedores."""

    provider_name: str

    @abstractmethod
    def generate(
        self,
        request: GenerationRequest,
    ) -> GenerationResult:
        """Genera una respuesta a partir de una petición."""
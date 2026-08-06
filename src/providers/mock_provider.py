import re

from src.providers.base import (
    AIProvider,
    GenerationRequest,
    GenerationResult,
)


class MockProvider(AIProvider):
    """
    Proveedor local de prueba.

    No utiliza claves, no llama a Internet y no consume dinero.
    """

    provider_name = "mock"

    def generate(
        self,
        request: GenerationRequest,
    ) -> GenerationResult:
        """Crea una respuesta simulada desde la primera fuente."""

        source_match = re.search(
            r"\[FUENTE 1\](.*?)(?:\n\n---|\Z)",
            request.user_message,
            flags=re.DOTALL,
        )

        if source_match:
            source_text = source_match.group(1).strip()

            content_parts = source_text.split(
                "\n\n",
                maxsplit=1,
            )

            evidence_text = (
                content_parts[1].strip()
                if len(content_parts) == 2
                else source_text
            )

            preview = evidence_text[:700].strip()

            text = (
                "Respuesta simulada del proveedor mock:\n\n"
                f"{preview} [FUENTE 1]\n\n"
                "Esta respuesta solo sirve para comprobar "
                "la integración. No se llamó a ninguna API."
            )
        else:
            text = (
                "No se encontró contexto suficiente para "
                "construir la respuesta simulada."
            )

        return GenerationResult(
            ok=True,
            provider=self.provider_name,
            model="mock-local-v1",
            text=text,
            metadata={
                "api_called": False,
                "estimated_cost": 0,
            },
        )
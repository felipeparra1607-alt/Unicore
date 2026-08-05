import re
from dataclasses import dataclass


@dataclass
class TextChunk:
    """Representa un fragmento generado a partir de un texto."""

    index: int
    content: str
    char_start: int
    char_end: int
    source_label: str | None = None


def normalize_text(text: str) -> str:
    """
    Limpia espacios innecesarios conservando los saltos importantes.
    """

    normalized_lines: list[str] = []

    for line in text.splitlines():
        clean_line = re.sub(r"[ \t]+", " ", line).strip()

        if clean_line:
            normalized_lines.append(clean_line)
        elif normalized_lines and normalized_lines[-1] != "":
            normalized_lines.append("")

    return "\n".join(normalized_lines).strip()


def find_best_cut(
    text: str,
    target_end: int,
    minimum_end: int,
) -> int:
    """
    Busca un punto natural para terminar el fragmento.

    Prioriza:
    1. Separación entre párrafos.
    2. Final de frase.
    3. Espacio entre palabras.
    """

    paragraph_cut = text.rfind(
        "\n\n",
        minimum_end,
        target_end,
    )

    if paragraph_cut != -1:
        return paragraph_cut + 2

    sentence_positions = [
        text.rfind(". ", minimum_end, target_end),
        text.rfind("? ", minimum_end, target_end),
        text.rfind("! ", minimum_end, target_end),
    ]

    sentence_cut = max(sentence_positions)

    if sentence_cut != -1:
        return sentence_cut + 2

    word_cut = text.rfind(
        " ",
        minimum_end,
        target_end,
    )

    if word_cut != -1:
        return word_cut + 1

    return target_end


def detect_source_label(content: str) -> str | None:
    """
    Detecta etiquetas generadas durante la extracción.

    Ejemplos:
    --- Página 2 ---
    --- Diapositiva 5 ---
    """

    matches = re.findall(
        r"---\s*(Página|Diapositiva)\s+(\d+)\s*---",
        content,
        flags=re.IGNORECASE,
    )

    if not matches:
        return None

    source_type, source_number = matches[-1]

    return f"{source_type.capitalize()} {source_number}"


def split_text_into_chunks(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[TextChunk]:
    """
    Divide un texto en fragmentos con solapamiento.

    El solapamiento permite conservar contexto entre fragmentos.
    """

    if chunk_size < 300 or chunk_size > 10000:
        raise ValueError(
            "chunk_size debe estar entre 300 y 10000"
        )

    if overlap < 0:
        raise ValueError(
            "overlap no puede ser negativo"
        )

    if overlap >= chunk_size:
        raise ValueError(
            "overlap debe ser menor que chunk_size"
        )

    normalized_text = normalize_text(text)

    if not normalized_text:
        return []

    chunks: list[TextChunk] = []
    text_length = len(normalized_text)
    start = 0
    chunk_index = 0

    while start < text_length:
        target_end = min(
            start + chunk_size,
            text_length,
        )

        if target_end < text_length:
            minimum_end = min(
                start + int(chunk_size * 0.6),
                target_end,
            )

            end = find_best_cut(
                normalized_text,
                target_end,
                minimum_end,
            )
        else:
            end = text_length

        content = normalized_text[start:end].strip()

        if content:
            real_start = normalized_text.find(
                content,
                start,
                end,
            )

            if real_start == -1:
                real_start = start

            real_end = real_start + len(content)

            chunks.append(
                TextChunk(
                    index=chunk_index,
                    content=content,
                    char_start=real_start,
                    char_end=real_end,
                    source_label=detect_source_label(content),
                )
            )

            chunk_index += 1

        if end >= text_length:
            break

        next_start = max(
            0,
            end - overlap,
        )

        if next_start <= start:
            next_start = end

        start = next_start

    return chunks
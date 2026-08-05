import re
from dataclasses import dataclass

import numpy as np

from src.embeddings import create_embeddings


@dataclass
class HybridChunk:
    index: int
    content: str
    char_start: int
    char_end: int
    source_label: str | None
    embedding: list[float]


@dataclass
class TextUnit:
    content: str
    char_start: int
    char_end: int
    source_label: str | None


SOURCE_PATTERN = re.compile(
    r"---\s*(Página|Diapositiva)\s+(\d+)\s*---",
    flags=re.IGNORECASE,
)

SENTENCE_PATTERN = re.compile(
    r"(?<=[.!?])\s+|\n{2,}"
)


def normalize_text(text: str) -> str:
    """Normaliza espacios sin eliminar la estructura principal."""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def detect_source_label(text: str) -> str | None:
    """Detecta la última página o diapositiva mencionada."""

    matches = SOURCE_PATTERN.findall(text)

    if not matches:
        return None

    source_type, source_number = matches[-1]

    return f"{source_type.capitalize()} {source_number}"


def split_into_units(text: str) -> list[TextUnit]:
    """
    Divide el documento en frases o pequeños bloques naturales.

    Mantiene las posiciones dentro del texto normalizado.
    """

    normalized = normalize_text(text)

    if not normalized:
        return []

    raw_units = SENTENCE_PATTERN.split(normalized)
    units: list[TextUnit] = []
    search_start = 0
    active_source_label: str | None = None

    for raw_unit in raw_units:
        content = raw_unit.strip()

        if not content:
            continue

        start = normalized.find(content, search_start)

        if start == -1:
            start = search_start

        end = start + len(content)
        detected_label = detect_source_label(content)

        if detected_label is not None:
            active_source_label = detected_label

        units.append(
            TextUnit(
                content=content,
                char_start=start,
                char_end=end,
                source_label=active_source_label,
            )
        )

        search_start = end

    return units


def semantic_similarity(
    first_embedding: list[float],
    second_embedding: list[float],
) -> float:
    """Calcula similitud entre dos unidades normalizadas."""

    first = np.asarray(first_embedding, dtype=float)
    second = np.asarray(second_embedding, dtype=float)

    return float(np.dot(first, second))


def group_units_semantically(
    units: list[TextUnit],
    unit_embeddings: list[list[float]],
    semantic_threshold: float,
    min_chunk_characters: int,
    max_chunk_characters: int,
) -> list[list[int]]:
    """
    Agrupa unidades respetando estructura, tamaño y cambios semánticos.
    """

    if not units:
        return []

    groups: list[list[int]] = []
    current_group: list[int] = [0]
    current_length = len(units[0].content)

    for index in range(1, len(units)):
        previous_unit = units[index - 1]
        current_unit = units[index]

        similarity = semantic_similarity(
            unit_embeddings[index - 1],
            unit_embeddings[index],
        )

        source_changed = (
            previous_unit.source_label is not None
            and current_unit.source_label is not None
            and previous_unit.source_label
            != current_unit.source_label
        )

        projected_length = (
            current_length
            + 2
            + len(current_unit.content)
        )

        maximum_reached = (
            projected_length > max_chunk_characters
        )

        semantic_break = (
            similarity < semantic_threshold
            and current_length >= min_chunk_characters
        )

        structural_break = (
            source_changed
            and current_length >= min_chunk_characters
        )

        if maximum_reached or semantic_break or structural_break:
            groups.append(current_group)
            current_group = [index]
            current_length = len(current_unit.content)
        else:
            current_group.append(index)
            current_length = projected_length

    if current_group:
        groups.append(current_group)

    return groups


def merge_small_groups(
    groups: list[list[int]],
    units: list[TextUnit],
    min_chunk_characters: int,
) -> list[list[int]]:
    """Evita fragmentos finales excesivamente pequeños."""

    if len(groups) < 2:
        return groups

    merged: list[list[int]] = []

    for group in groups:
        group_length = sum(
            len(units[index].content)
            for index in group
        )

        if (
            group_length < min_chunk_characters
            and merged
        ):
            merged[-1].extend(group)
        else:
            merged.append(group)

    return merged


def create_hybrid_semantic_chunks(
    text: str,
    semantic_threshold: float = 0.48,
    min_chunk_characters: int = 350,
    max_chunk_characters: int = 1800,
) -> list[HybridChunk]:
    """
    Crea chunks híbridos usando estructura y similitud semántica.
    """

    if semantic_threshold < 0 or semantic_threshold > 1:
        raise ValueError(
            "semantic_threshold debe estar entre 0 y 1"
        )

    if min_chunk_characters < 100:
        raise ValueError(
            "min_chunk_characters debe ser como mínimo 100"
        )

    if max_chunk_characters <= min_chunk_characters:
        raise ValueError(
            "max_chunk_characters debe ser mayor que el mínimo"
        )

    units = split_into_units(text)

    if not units:
        return []

    unit_embeddings = create_embeddings(
        [unit.content for unit in units]
    )

    groups = group_units_semantically(
        units=units,
        unit_embeddings=unit_embeddings,
        semantic_threshold=semantic_threshold,
        min_chunk_characters=min_chunk_characters,
        max_chunk_characters=max_chunk_characters,
    )

    groups = merge_small_groups(
        groups=groups,
        units=units,
        min_chunk_characters=min_chunk_characters,
    )

    chunk_texts: list[str] = []

    for group in groups:
        chunk_texts.append(
            "\n\n".join(
                units[index].content
                for index in group
            )
        )

    chunk_embeddings = create_embeddings(chunk_texts)
    chunks: list[HybridChunk] = []

    for chunk_index, group in enumerate(groups):
        first_unit = units[group[0]]
        last_unit = units[group[-1]]
        content = chunk_texts[chunk_index]

        source_labels = [
            units[index].source_label
            for index in group
            if units[index].source_label is not None
        ]

        source_label = (
            source_labels[0]
            if source_labels
            else None
        )

        chunks.append(
            HybridChunk(
                index=chunk_index,
                content=content,
                char_start=first_unit.char_start,
                char_end=last_unit.char_end,
                source_label=source_label,
                embedding=chunk_embeddings[chunk_index],
            )
        )

    return chunks
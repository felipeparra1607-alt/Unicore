import json
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer


DEFAULT_EMBEDDING_MODEL = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """
    Carga el modelo una sola vez y lo reutiliza.

    La primera ejecución puede tardar porque descarga el modelo.
    """

    return SentenceTransformer(DEFAULT_EMBEDDING_MODEL)


def create_embeddings(texts: list[str]) -> list[list[float]]:
    """Genera embeddings normalizados para varios textos."""

    if not texts:
        return []

    model = get_embedding_model()

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return embeddings.astype(float).tolist()


def create_embedding(text: str) -> list[float]:
    """Genera el embedding normalizado de un texto."""

    return list(_create_embedding_cached(text))


@lru_cache(maxsize=128)
def _create_embedding_cached(text: str) -> tuple[float, ...]:
    """Reutiliza embeddings de consultas idénticas dentro del proceso."""

    embeddings = create_embeddings([text])

    if not embeddings:
        return ()

    return tuple(embeddings[0])


def embedding_to_json(embedding: list[float]) -> str:
    """Convierte un embedding a texto JSON para SQLite."""

    return json.dumps(
        embedding,
        separators=(",", ":"),
    )


def embedding_from_json(value: str | None) -> list[float]:
    """Recupera un embedding almacenado en SQLite."""

    if not value:
        return []

    data = json.loads(value)

    return [
        float(number)
        for number in data
    ]


def cosine_similarity(
    first_embedding: list[float],
    second_embedding: list[float],
) -> float:
    """
    Calcula similitud coseno entre dos embeddings.

    Como los embeddings están normalizados, el producto escalar
    equivale a la similitud coseno.
    """

    if not first_embedding or not second_embedding:
        return 0.0

    first = np.asarray(first_embedding, dtype=float)
    second = np.asarray(second_embedding, dtype=float)

    if first.shape != second.shape:
        return 0.0

    return float(np.dot(first, second))

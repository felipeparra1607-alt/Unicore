from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, delete, func, select

from src.database.connection import DATABASE_PATH, engine


MATERIALS_DIRECTORY = DATABASE_PATH.parent / "materials"
BACKUPS_DIRECTORY = DATABASE_PATH.parent / "backups"


def backup_database(timestamp: datetime | None = None) -> Path:
    """Crea una copia consistente de la base antes de un reset."""

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"No existe la base de datos: {DATABASE_PATH}")

    BACKUPS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    suffix = (timestamp or datetime.now()).strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUPS_DIRECTORY / f"unicore-pre-real-use-{suffix}.db"

    with sqlite3.connect(DATABASE_PATH) as source, sqlite3.connect(backup_path) as target:
        source.backup(target)

    return backup_path


def _reflected_metadata() -> MetaData:
    metadata = MetaData()
    metadata.reflect(bind=engine)
    return metadata


def database_counts() -> dict[str, int]:
    """Devuelve el número de registros de cada tabla de usuario."""

    metadata = _reflected_metadata()
    with engine.connect() as connection:
        return {
            table.name: int(connection.scalar(select(func.count()).select_from(table)) or 0)
            for table in sorted(metadata.tables.values(), key=lambda item: item.name)
        }


def _managed_material_paths() -> list[Path]:
    metadata = _reflected_metadata()
    documents = metadata.tables.get("documents")
    if documents is None:
        return []

    root = MATERIALS_DIRECTORY.resolve()
    paths: list[Path] = []
    with engine.connect() as connection:
        for raw_path in connection.scalars(select(documents.c.file_path)):
            if not raw_path:
                continue
            candidate = Path(str(raw_path)).resolve()
            if candidate == root or root not in candidate.parents:
                continue
            paths.append(candidate)
    return paths


def reset_user_data() -> dict[str, Any]:
    """Elimina todo dato académico y de usuario conservando schema y configuración."""

    metadata = _reflected_metadata()
    before = database_counts()
    material_paths = _managed_material_paths()

    with engine.begin() as connection:
        for table in reversed(metadata.sorted_tables):
            connection.execute(delete(table))

    deleted_files: list[str] = []
    missing_files: list[str] = []
    MATERIALS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for path in material_paths:
        if path.exists() and path.is_file():
            path.unlink()
            deleted_files.append(str(path))
        else:
            missing_files.append(str(path))

    after = database_counts()
    non_empty = {name: count for name, count in after.items() if count}
    if non_empty:
        raise RuntimeError(f"El reset no quedó vacío: {non_empty}")

    return {
        "ok": True,
        "before": before,
        "after": after,
        "deleted_material_files": deleted_files,
        "missing_registered_files": missing_files,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepara UniCore para un usuario real desde cero.")
    parser.add_argument("--backup", action="store_true", help="Crea el backup obligatorio antes del reset.")
    args = parser.parse_args()

    backup_path = backup_database() if args.backup else None
    result = reset_user_data()
    if backup_path is not None:
        print(f"backup={backup_path}")
    print(f"deleted_rows={sum(result['before'].values())}")
    for table, count in result["after"].items():
        print(f"{table}={count}")


if __name__ == "__main__":
    main()

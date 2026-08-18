import os
import shutil
import uuid
from pathlib import Path


def resolve_storage_key(root: Path, key: str) -> Path:
    base = root.resolve()
    target = (base / key).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise ValueError("Storage key tidak valid.") from exc
    return target


def persist_original(source: Path, root: Path, dataset_id: uuid.UUID, suffix: str) -> str:
    key = f"originals/{dataset_id}{suffix.lower()}"
    target = resolve_storage_key(root, key)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return key


def delete_storage_key(root: Path, key: str | None) -> None:
    if key:
        resolve_storage_key(root, key).unlink(missing_ok=True)

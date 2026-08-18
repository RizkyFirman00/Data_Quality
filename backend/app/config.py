import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://data_quality:data_quality@localhost:5432/data_quality",
    )
    storage_root: Path = Path(os.getenv("STORAGE_ROOT", "storage"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "25"))
    max_dataset_rows: int = int(os.getenv("MAX_DATASET_ROWS", "100000"))
    max_dataset_columns: int = int(os.getenv("MAX_DATASET_COLUMNS", "1000"))
    max_dataset_cells: int = int(os.getenv("MAX_DATASET_CELLS", "2000000"))
    preview_rows: int = int(os.getenv("PREVIEW_ROWS", "50"))
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    )


settings = Settings()


def get_settings() -> Settings:
    return settings

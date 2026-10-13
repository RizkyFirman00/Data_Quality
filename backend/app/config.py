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
    master_reference_path: Path = Path(
        os.getenv(
            "MASTER_REFERENCE_PATH",
            str(Path(__file__).resolve().parents[1] / "reference" / "master.csv"),
        )
    )
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "25"))
    max_dataset_rows: int = int(os.getenv("MAX_DATASET_ROWS", "100000"))
    max_dataset_columns: int = int(os.getenv("MAX_DATASET_COLUMNS", "1000"))
    max_dataset_cells: int = int(os.getenv("MAX_DATASET_CELLS", "2000000"))
    max_findings: int = int(os.getenv("MAX_FINDINGS", "10000"))
    preview_rows: int = int(os.getenv("PREVIEW_ROWS", "50"))
    llm_base_url: str | None = os.getenv("LLM_BASE_URL")
    llm_api_key: str | None = os.getenv("LLM_API_KEY")
    llm_model: str | None = os.getenv("LLM_MODEL")
    llm_max_candidates: int = int(os.getenv("LLM_MAX_CANDIDATES", "50"))
    llm_max_columns: int = int(os.getenv("LLM_MAX_COLUMNS", "20"))
    llm_max_action_groups: int = int(os.getenv("LLM_MAX_ACTION_GROUPS", "20"))
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "10"))
    backoffice_api_base_url: str | None = os.getenv("BACKOFFICE_API_BASE_URL")
    backoffice_api_token: str | None = os.getenv("BACKOFFICE_API_TOKEN")
    backoffice_api_method: str = os.getenv("BACKOFFICE_API_METHOD", "GET")
    backoffice_start_param: str = os.getenv("BACKOFFICE_START_PARAM", "start")
    backoffice_length_param: str = os.getenv("BACKOFFICE_LENGTH_PARAM", "length")
    backoffice_data_path: str = os.getenv("BACKOFFICE_DATA_PATH", "data")
    backoffice_total_path: str = os.getenv("BACKOFFICE_TOTAL_PATH", "recordsFiltered")
    backoffice_page_size: int = int(os.getenv("BACKOFFICE_PAGE_SIZE", "100"))
    backoffice_timeout_seconds: float = float(os.getenv("BACKOFFICE_TIMEOUT_SECONDS", "10"))
    auth_cookie_name: str = os.getenv("AUTH_COOKIE_NAME", "dq_session")
    auth_cookie_secure: bool = os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
    auth_session_hours: int = int(os.getenv("AUTH_SESSION_HOURS", "8"))
    auth_max_failed_attempts: int = int(os.getenv("AUTH_MAX_FAILED_ATTEMPTS", "5"))
    auth_lock_minutes: int = int(os.getenv("AUTH_LOCK_MINUTES", "15"))
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    )


settings = Settings()


def get_settings() -> Settings:
    return settings

import time
from collections.abc import Mapping

import httpx

from .config import Settings
from .ingestion import DatasetParseError, ParsedColumn, ParsedDataset


def fetch_backoffice_dataset(config: Settings) -> ParsedDataset:
    """Fetch a configurable API without exposing its credentials to the browser."""
    if not config.backoffice_api_base_url:
        raise DatasetParseError("Backoffice API belum dikonfigurasi.")
    headers = {"authorization": f"Bearer {config.backoffice_api_token}"} if config.backoffice_api_token else {}
    records: list[dict[str, object]] = []
    total: int | None = None
    start = 0
    method = config.backoffice_api_method.upper()
    start_param = config.backoffice_start_param
    length_param = config.backoffice_length_param
    data_path = config.backoffice_data_path
    total_path = config.backoffice_total_path
    with httpx.Client(timeout=config.backoffice_timeout_seconds) as client:
        while total is None or len(records) < total:
            response: httpx.Response | None = None
            for attempt in range(2):
                try:
                    params = {start_param: start, length_param: config.backoffice_page_size}
                    if method == "POST":
                        response = client.post(
                            config.backoffice_api_base_url,
                            headers=headers,
                            json=params,
                        )
                    else:
                        response = client.get(
                            config.backoffice_api_base_url,
                            headers=headers,
                            params=params,
                        )
                    response.raise_for_status()
                    break
                except httpx.HTTPError as exc:
                    if attempt:
                        raise DatasetParseError("Backoffice API tidak dapat dihubungi.") from exc
                    time.sleep(0.2)
            if response is None:
                raise DatasetParseError("Backoffice API tidak dapat dihubungi.")
            try:
                payload = response.json()
                # Navigate to data array using data_path (e.g., "data" or "results.items")
                page = payload
                for key in data_path.split("."):
                    page = page[key]
                if not isinstance(page, list) or any(not isinstance(item, Mapping) for item in page):
                    raise TypeError
                # Navigate to total using total_path
                total_val = payload
                for key in total_path.split("."):
                    total_val = total_val.get(key)
                total = int(total_val) if total_val is not None else None
            except (TypeError, ValueError, KeyError, AttributeError):
                raise DatasetParseError("Respons Backoffice API tidak memiliki array data yang valid.") from None
            normalized = [dict(item) for item in page]
            records.extend(normalized)
            if not normalized:
                break
            start += len(normalized)
    if not records:
        raise DatasetParseError("Backoffice API tidak mengembalikan data.")
    names = list(dict.fromkeys(key for record in records for key in record))
    if len(names) > config.max_dataset_columns:
        raise DatasetParseError(f"Dataset melebihi batas {config.max_dataset_columns} kolom.")
    if len(records) > config.max_dataset_rows or len(records) * len(names) > config.max_dataset_cells:
        raise DatasetParseError("Dataset Backoffice melebihi batas yang diizinkan.")
    columns = [ParsedColumn(name, name, name) for name in names]
    return ParsedDataset(
        columns,
        [{name: record.get(name) for name in names} for record in records],
        list(range(1, len(records) + 1)),
    )

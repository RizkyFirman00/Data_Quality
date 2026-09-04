from pathlib import Path

import pytest
import httpx

from app.backoffice import fetch_backoffice_dataset
from app.config import Settings
from app.ingestion import ParsedColumn, ParsedDataset
from app.profiling import profile_dataset
from app.semantic import apply_semantic_roles, semantic_analysis


def test_semantic_is_safely_unavailable_without_llm_configuration() -> None:
    parsed = ParsedDataset(
        [ParsedColumn("wilayah", "wilayah", "wilayah")],
        [{"wilayah": "KOTA ADM. JAKRTA BARAT"}],
        [2],
    )

    result = semantic_analysis(parsed, profile_dataset(parsed), Settings(llm_base_url=None, llm_api_key=None, llm_model=None))

    assert result == type(result)([], False, {})


def test_semantic_uses_llm_for_bounded_free_text_typo(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass
        def __enter__(self): return self
        def __exit__(self, *_args: object) -> None: pass
        def post(self, _url: str, **kwargs: object) -> httpx.Response:
            calls.append(kwargs["json"])  # type: ignore[arg-type,index]
            if len(calls) == 1:
                content = '{"columns":[{"column":"event","role":"free_text","confidence":0.97,"reason":"Nama kegiatan."}]}'
            else:
                content = (
                    '{"classification": "typo", "recommendation": "Festival Jakarta", '
                    '"confidence": 0.94, "reason": "Ada huruf yang hilang."}'
                )
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": content
                            }
                        }
                    ]
                },
                request=httpx.Request("POST", _url),
            )

    monkeypatch.setattr("app.semantic.httpx.Client", Client)
    parsed = ParsedDataset(
        [ParsedColumn("event", "event", "event")],
        [
            {"event": "Festival Jakarta"},
            {"event": "Festival Jakarta"},
            {"event": "Festival Jakrta"},
        ],
        [2, 3, 4],
    )

    profile = profile_dataset(parsed)
    result = semantic_analysis(parsed, profile, Settings(llm_base_url="https://llm.test/v1", llm_api_key="secret", llm_model="model"))

    assert result.available is True
    assert len(calls) == 2
    assert result.roles == {"event": "free_text"}
    assert apply_semantic_roles(profile, result.roles).columns[0].candidate_role == "free_text"
    assert result.findings[0].row == 4
    assert result.findings[0].column == "event"
    assert result.findings[0].issue_type == "POTENTIAL_TYPO"
    assert result.findings[0].expected_value == "Festival Jakarta"
    assert result.findings[0].confidence == 0.94
    assert result.findings[0].detector == "free-text+llm-v2"


def test_semantic_uses_llm_for_semantic_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass
        def __enter__(self): return self
        def __exit__(self, *_args: object) -> None: pass
        def post(self, _url: str, **kwargs: object) -> httpx.Response:
            calls.append(kwargs["json"])  # type: ignore[arg-type,index]
            if len(calls) == 1:
                content = '{"columns":[{"column":"event","role":"free_text","confidence":0.96,"reason":"Judul kegiatan."}]}'
            else:
                content = (
                    '{"classification": "semantic_mismatch", "recommendation": "Festival Jakarta", '
                    '"confidence": 0.88, "reason": "Konteks event berbeda meski mirip."}'
                )
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": content
                            }
                        }
                    ]
                },
                request=httpx.Request("POST", _url),
            )

    monkeypatch.setattr("app.semantic.httpx.Client", Client)
    # Use same pattern as typo test but expect semantic_mismatch classification
    parsed = ParsedDataset(
        [ParsedColumn("event", "event", "event")],
        [
            {"event": "Festival Jakarta"},
            {"event": "Festival Jakarta"},
            {"event": "Festival Jakrta"},
        ],
        [2, 3, 4],
    )

    result = semantic_analysis(parsed, profile_dataset(parsed), Settings(llm_base_url="https://llm.test/v1", llm_api_key="secret", llm_model="model"))

    assert result.available is True
    assert len(calls) == 2
    assert result.findings[0].row == 4
    assert result.findings[0].column == "event"
    assert result.findings[0].issue_type == "SEMANTIC_MISMATCH"
    assert result.findings[0].expected_value == "Festival Jakarta"
    assert result.findings[0].confidence == 0.88


def test_semantic_skips_address_and_administrative_region(monkeypatch: pytest.MonkeyPatch) -> None:
    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass
        def __enter__(self): return self
        def __exit__(self, *_args: object) -> None: pass
        def post(self, _url: str, **_kwargs: object) -> httpx.Response:
            raise AssertionError("LLM should not be called for address or region columns")

    monkeypatch.setattr("app.semantic.httpx.Client", Client)
    parsed = ParsedDataset(
        [
            ParsedColumn("alamat", "alamat", "alamat"),
            ParsedColumn("wilayah", "wilayah", "wilayah"),
        ],
        [
            {"alamat": "Jalan Merdeka Barat Nomor 1", "wilayah": "KOTA ADM. JAKARTA BARAT"},
            {"alamat": "Jalan Merdeka Barat Nmor 1", "wilayah": "KOTA ADM. JAKRTA BARAT"},
        ],
        [2, 3],
    )

    result = semantic_analysis(parsed, profile_dataset(parsed), Settings(llm_base_url="https://llm.test/v1", llm_api_key="secret", llm_model="model"))

    assert result == type(result)([], True, {})


def test_semantic_role_classification_excludes_dynamic_address_from_typo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass
        def __enter__(self): return self
        def __exit__(self, *_args: object) -> None: pass
        def post(self, _url: str, **kwargs: object) -> httpx.Response:
            calls.append(kwargs["json"])  # type: ignore[arg-type,index]
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": (
                    '{"columns":[{"column":"domisili","role":"address",'
                    '"confidence":0.98,"reason":"Berisi alamat tempat tinggal."}]}'
                )}}]},
                request=httpx.Request("POST", _url),
            )

    monkeypatch.setattr("app.semantic.httpx.Client", Client)
    parsed = ParsedDataset(
        [ParsedColumn("domisili", "domisili", "domisili")],
        [
            {"domisili": "Jalan Merdeka Barat Nomor 1"},
            {"domisili": "Jalan Merdeka Barat Nomor 1"},
            {"domisili": "Jalan Merdeka Barat Nmor 1"},
        ],
        [2, 3, 4],
    )

    result = semantic_analysis(
        parsed,
        profile_dataset(parsed),
        Settings(llm_base_url="https://llm.test/v1", llm_api_key="secret", llm_model="model"),
    )

    assert len(calls) == 1
    role_prompt = calls[0]["messages"][1]["content"]  # type: ignore[index]
    assert "Jalan Merdeka Barat Nomor 1" in role_prompt
    assert result.available is True
    assert result.roles == {"domisili": "address"}
    assert result.findings == []


def test_backoffice_requires_server_side_configuration() -> None:
    with pytest.raises(ValueError, match="belum dikonfigurasi"):
        fetch_backoffice_dataset(Settings(backoffice_api_base_url=None))


def test_backoffice_error_message_is_safe_when_transport_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass
        def __enter__(self): return self
        def __exit__(self, *_args: object) -> None: pass
        def get(self, _url: str, **_kwargs: object) -> httpx.Response:
            raise httpx.HTTPError("secret-token response body")

    monkeypatch.setattr("app.backoffice.httpx.Client", Client)

    with pytest.raises(ValueError) as error:
        fetch_backoffice_dataset(Settings(backoffice_api_base_url="https://backoffice.test", backoffice_api_token="secret-token"))

    assert str(error.value) == "Backoffice API tidak dapat dihubungi."


def test_backoffice_fetches_all_datatables_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    class Client:
        def __init__(self, **_kwargs: object) -> None:
            pass
        def __enter__(self): return self
        def __exit__(self, *_args: object) -> None: pass
        def get(self, _url: str, **kwargs: object) -> httpx.Response:
            start = kwargs["params"]["start"]  # type: ignore[index]
            data = [{"nama": "ANI"}] if start == 0 else [{"nama": "BUDI"}]
            return httpx.Response(200, json={"recordsFiltered": 2, "data": data}, request=httpx.Request("GET", _url))

    monkeypatch.setattr("app.backoffice.httpx.Client", Client)

    parsed = fetch_backoffice_dataset(Settings(backoffice_api_base_url="https://backoffice.test", backoffice_page_size=1))

    assert parsed.records == [{"nama": "ANI"}, {"nama": "BUDI"}]

from app.config import Settings
from app.ingestion import ParsedColumn, ParsedDataset
from app.profiling import profile_dataset
from app.quality import planned_quality_checks
from app.semantic import semantic_analysis


def test_reporting_period_does_not_need_llm(monkeypatch):
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs):
            raise AssertionError("A known reporting period must not be sent to the LLM")

    monkeypatch.setattr("app.semantic.httpx.Client", Client)
    parsed = ParsedDataset([ParsedColumn("periode_data", "periode_data", "periode_data")], [{"periode_data": "2025-T1"}, {"periode_data": "2025-S1"}], [2, 3])
    profile = profile_dataset(parsed)
    assert "SEMANTIC_TYPO" not in planned_quality_checks(profile, semantic_enabled=True)
    result = semantic_analysis(parsed, profile, Settings(llm_base_url="https://llm.test/v1", llm_api_key="secret", llm_model="model"))
    assert result.findings == []
    assert result.roles == {}

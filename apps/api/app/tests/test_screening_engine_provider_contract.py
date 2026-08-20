from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.screening import (
    EngineProviderError,
    HiringScreeningEngineProvider,
    _classify_command_failure,
    _engine_environment,
)


def test_engine_environment_uses_stable_engine_contract_names():
    settings = SimpleNamespace(
        screening_chandra_base_url="http://127.0.0.1:18083",
        screening_chandra_api_key="not-consumed-by-stable-engine",
        screening_chandra_model="chandra-ocr-2-q8",
        screening_gemma_api_key="no-key",
        screening_gemma_model="/models/gemma.gguf",
        screening_gemma_resume_max_tokens=16384,
        screening_chandra_ocr_retry_max_tokens=8192,
        screening_pipeline_debug_raw_responses=False,
        screening_engine_timeout_seconds=900,
    )

    env = _engine_environment(settings, gemma_base_url="http://127.0.0.1:24181/v1")

    assert env["CHANDRA_BASE_URL"] == "http://127.0.0.1:18083"
    assert env["CHANDRA_MODEL"] == "chandra-ocr-2-q8"
    assert "CHANDRA_API_KEY" not in env
    assert env["GEMMA_BASE_URL"] == "http://127.0.0.1:24181/v1"
    assert env["GEMMA_API_KEY"] == "no-key"
    assert env["GEMMA_MODEL"] == "/models/gemma.gguf"
    assert env["GEMMA_RESUME_MAX_TOKENS"] == "16384"
    assert env["CHANDRA_OCR_RETRY_MAX_TOKENS"] == "8192"
    assert env["PIPELINE_DEBUG_RAW_RESPONSES"] == "false"


def test_gemma_fallback_retries_only_primary_gemma_unavailable(monkeypatch):
    calls: list[tuple[str, str]] = []
    provider = HiringScreeningEngineProvider()
    settings = SimpleNamespace(
        screening_engine_python="python3",
        screening_engine_timeout_seconds=900,
        screening_chandra_base_url="http://127.0.0.1:18083",
        screening_chandra_model="chandra-ocr-2-q8",
        screening_gemma_base_url="http://127.0.0.1:24181/v1",
        screening_gemma_fallback_base_url="http://127.0.0.1:24182/v1",
        screening_gemma_api_key="no-key",
        screening_gemma_model="/models/gemma.gguf",
        screening_gemma_resume_max_tokens=16384,
        screening_chandra_ocr_retry_max_tokens=8192,
        screening_pipeline_debug_raw_responses=False,
    )

    def fake_run_command(command, *, cwd, timeout, env, failure_code, model_endpoint_slot=None):
        calls.append((model_endpoint_slot or "", env["GEMMA_BASE_URL"]))
        if model_endpoint_slot == "primary":
            raise EngineProviderError("GEMMA_UNAVAILABLE", "primary transport failed", model_endpoint_slot="primary")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("app.services.screening._run_command", fake_run_command)

    slot = provider._structure_resume_with_gemma_fallback(
        settings=settings,
        engine_root=Path("/synthetic/engine"),
        ocr_dir=Path("/synthetic/ocr"),
        structured_resume_path=Path("/synthetic/resume.json"),
        candidate_id="candidate-1",
    )

    assert slot == "fallback"
    assert calls == [
        ("primary", "http://127.0.0.1:24181/v1"),
        ("fallback", "http://127.0.0.1:24182/v1"),
    ]


def test_gemma_fallback_does_not_retry_business_or_schema_failures(monkeypatch):
    provider = HiringScreeningEngineProvider()
    settings = SimpleNamespace(
        screening_engine_python="python3",
        screening_engine_timeout_seconds=900,
        screening_chandra_base_url="http://127.0.0.1:18083",
        screening_chandra_model="chandra-ocr-2-q8",
        screening_gemma_base_url="http://127.0.0.1:24181/v1",
        screening_gemma_fallback_base_url="http://127.0.0.1:24182/v1",
        screening_gemma_api_key="no-key",
        screening_gemma_model="/models/gemma.gguf",
        screening_gemma_resume_max_tokens=16384,
        screening_chandra_ocr_retry_max_tokens=8192,
        screening_pipeline_debug_raw_responses=False,
    )

    def fake_run_command(command, *, cwd, timeout, env, failure_code, model_endpoint_slot=None):
        raise EngineProviderError("ENGINE_OUTPUT_INVALID", "candidate profile schema invalid")

    monkeypatch.setattr("app.services.screening._run_command", fake_run_command)

    with pytest.raises(EngineProviderError) as error:
        provider._structure_resume_with_gemma_fallback(
            settings=settings,
            engine_root=Path("/synthetic/engine"),
            ocr_dir=Path("/synthetic/ocr"),
            structured_resume_path=Path("/synthetic/resume.json"),
            candidate_id="candidate-1",
        )

    assert error.value.failure_code == "ENGINE_OUTPUT_INVALID"


def test_gemma_command_failure_classification_only_marks_transport_as_unavailable():
    assert (
        _classify_command_failure(
            "GEMMA_UNAVAILABLE",
            "Connection refused while calling http://127.0.0.1:24181/v1",
        )
        == "GEMMA_UNAVAILABLE"
    )
    assert (
        _classify_command_failure(
            "GEMMA_UNAVAILABLE",
            "Structured resume validation failed: missing candidate profile fields",
        )
        == "ENGINE_EXECUTION_FAILED"
    )

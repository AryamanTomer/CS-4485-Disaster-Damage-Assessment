"""Tests for POST /chat: metadata JSON only (no CSV), OpenAI mocked."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _clear_chat_caches() -> None:
    import api.routers.chat as chat_mod

    chat_mod._load_tiles.cache_clear()


@pytest.fixture(autouse=True)
def reset_chat_cache():
    _clear_chat_caches()
    yield
    _clear_chat_caches()


def test_chat_source_has_no_read_csv_in_module():
    """Regression: chat must not load evaluation/results.csv."""
    import api.routers.chat as m

    src = Path(m.__file__).read_text(encoding="utf-8")
    assert "read_csv" not in src
    assert "results.csv" not in src


def test_chat_returns_503_when_metadata_file_missing(client: TestClient, monkeypatch, tmp_path: Path):
    missing = tmp_path / "does_not_exist.json"

    import api.routers.chat as chat_mod

    monkeypatch.setattr(chat_mod, "_metadata_path", lambda: missing)

    response = client.post("/chat", json={"message": "Hello"})
    assert response.status_code == 503
    assert "predictions_with_metadata" in response.json()["detail"]


def test_chat_returns_500_when_json_missing_columns(client: TestClient, monkeypatch, tmp_path: Path):
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(
        json.dumps({"tiles": [{"image_name": "x.png", "foo": 1}]}),
        encoding="utf-8",
    )

    import api.routers.chat as chat_mod

    monkeypatch.setattr(chat_mod, "_metadata_path", lambda: bad_path)

    response = client.post("/chat", json={"message": "Hello"})
    assert response.status_code == 500
    detail = response.json()["detail"].lower()
    assert "prediction" in detail or "ground_truth" in detail


def test_chat_never_calls_pandas_read_csv(client: TestClient, monkeypatch, tmp_path: Path):
    """Ensure /chat does not fall back to CSV via pandas."""
    good_path = tmp_path / "meta.json"
    good_path.write_text(
        json.dumps(
            {
                "tiles": [
                    {
                        "image_name": "t_000_post_disaster.png",
                        "prediction": "no-damage",
                        "ground_truth": "no-damage",
                    },
                    {
                        "image_name": "t_001_post_disaster.png",
                        "prediction": "destroyed",
                        "ground_truth": "destroyed",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    import api.routers.chat as chat_mod

    monkeypatch.setattr(chat_mod, "_metadata_path", lambda: good_path)

    read_csv_calls: list = []

    real_read_csv = pd.read_csv

    def spy_read_csv(*args, **kwargs):
        read_csv_calls.append((args, kwargs))
        return real_read_csv(*args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", spy_read_csv)

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="Stubbed assistant reply."))]

    with patch.object(chat_mod.client.chat.completions, "create", return_value=mock_resp):
        response = client.post("/chat", json={"message": "Summarize the dataset."})

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "Stubbed assistant reply."
    assert read_csv_calls == []


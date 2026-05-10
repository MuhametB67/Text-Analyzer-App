"""End-to-end smoke test for the Text Analyzer.

Submits a real job, polls until completion, and verifies the response shape.

Requires the app to be running locally (i.e. `docker compose up --build` in
another terminal). The base URL can be overridden with the BASE_URL env var.

Usage:
    pip install httpx pytest
    pytest tests/ -v
    # or, run directly:
    python tests/test_smoke.py
"""
import os
import sys
import time

import httpx
import pytest


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

SAMPLE_TEXT = (
    "I loved the new cafe downtown. The coffee was amazing and the staff were friendly. "
    "However the bathroom was terrible and the wifi was broken. "
    "Contact them at hello@cafe.com or visit https://cafe.example.com. "
    "Maria Gonzalez was our waiter. #GoodFood @cafe opened on March 15, 2024."
)

EXPECTED_RESULT_KEYS = {
    "basic_stats",
    "readability",
    "sentiment",
    "keywords",
    "entities",
}

POLL_INTERVAL_S = 0.4
POLL_TIMEOUT_S = 30.0


def test_health_endpoint():
    """The health endpoint should be reachable and return ok."""
    r = httpx.get(f"{BASE_URL}/api/health", timeout=5)
    assert r.status_code == 200, f"unexpected status: {r.status_code}"
    assert r.json() == {"status": "ok"}


def test_full_job_flow():
    """Submit a job, poll until done, and verify all 5 analyses came back."""
    
    r = httpx.post(
        f"{BASE_URL}/api/jobs",
        json={"text": SAMPLE_TEXT},
        timeout=10,
    )
    assert r.status_code == 200, f"submit failed: {r.status_code} {r.text}"
    body = r.json()
    assert "job_id" in body and "group_id" in body, f"missing ids in response: {body}"
    assert body["total_tasks"] == 5, f"expected 5 tasks, got {body['total_tasks']}"

    job_id = body["job_id"]
    group_id = body["group_id"]

    
    deadline = time.time() + POLL_TIMEOUT_S
    last = None
    while time.time() < deadline:
        r = httpx.get(
            f"{BASE_URL}/api/jobs/{job_id}",
            params={"group_id": group_id},
            timeout=5,
        )
        assert r.status_code == 200, f"poll failed: {r.status_code} {r.text}"
        last = r.json()
        if last.get("ready"):
            break
        time.sleep(POLL_INTERVAL_S)
    else:
        pytest.fail(f"job did not finish within {POLL_TIMEOUT_S}s, last status: {last}")

    
    assert last["successful"] is True, f"job failed: {last}"
    assert last["progress"]["completed"] == 5
    assert last["progress"]["total"] == 5

    result = last["result"]
    missing = EXPECTED_RESULT_KEYS - set(result.keys())
    assert not missing, f"missing analysis keys: {missing}"

    
    bs = result["basic_stats"]
    assert bs["words"] > 0
    assert bs["sentences"] > 0

    read = result["readability"]
    assert read["flesch_reading_ease"] is not None
    assert read["reading_level"]

    sent = result["sentiment"]
    assert sent["overall"] in {"positive", "negative", "neutral"}
    assert -1.0 <= sent["polarity"] <= 1.0
    assert isinstance(sent["per_sentence"], list) and sent["per_sentence"]

    kw = result["keywords"]
    assert isinstance(kw["top_keywords"], list) and kw["top_keywords"]

    ents = result["entities"]
    assert "hello@cafe.com" in ents["emails"], f"expected email not found: {ents['emails']}"
    assert any("cafe.example.com" in u for u in ents["urls"]), (
        f"expected URL not found: {ents['urls']}"
    )


if __name__ == "__main__":
    
    try:
        test_health_endpoint()
        print("[ok] /api/health")
        test_full_job_flow()
        print("[ok] full job flow (5/5 analyses returned)")
    except AssertionError as e:
        print(f"[fail] {e}")
        sys.exit(1)
    except httpx.HTTPError as e:
        print(f"[fail] could not reach {BASE_URL}: {e}")
        print("hint: is `docker compose up` running?")
        sys.exit(1)

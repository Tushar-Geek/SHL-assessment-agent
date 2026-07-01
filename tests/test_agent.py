from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_comparison() -> None:
    response = client.post(
        "/chat",
        json={"messages": [{"role": "user", "content": "Compare Verify Interactive - Numerical Reasoning and Occupational Personality Questionnaire OPQ"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["recommendations"]) == 2
    assert "Numerical" in body["reply"]
    assert "OPQ" in body["reply"]


def test_rejects_invalid_schema_extra_fields() -> None:
    response = client.post("/chat", json={"messages": [{"role": "user", "content": "Need Python"}], "extra": True})
    assert response.status_code == 422

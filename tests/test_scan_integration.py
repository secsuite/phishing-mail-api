import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.integration
def test_scan_email_with_real_model() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/v1/scan-email",
        json={
            "text": "Urgent notice: your account was suspended. Click here to verify password immediately."
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["is_phishing"], bool)
    assert 0 <= body["threat_score_out_of_100"] <= 100
    assert body["inference_time_ms"] >= 0

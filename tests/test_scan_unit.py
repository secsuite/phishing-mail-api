from fastapi.testclient import TestClient

from app.main import app
from app.routers.scan import get_classifier


class StubClassifier:
    def analyze(self, text: str):
        class Result:
            is_phishing = "urgent" in text.lower()
            threat_score = 91 if is_phishing else 4
            reasoning = "stubbed"
            inference_time_ms = 1.23

        return Result()


def test_scan_email_unit_with_override() -> None:
    app.dependency_overrides[get_classifier] = lambda: StubClassifier()

    client = TestClient(app)
    response = client.post(
        "/api/v1/scan-email",
        json={"text": "Urgent: verify your account password now"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_phishing"] is True
    assert body["threat_score_out_of_100"] == 91

    app.dependency_overrides.clear()

"""Email scanning endpoints."""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends

from app.schemas import EmailRequest, EmailResponse
from app.services.classifier import PhishingClassifier

router = APIRouter(tags=["Scanner"])


@lru_cache(maxsize=1)
def get_classifier() -> PhishingClassifier:
    from app.config import settings

    return PhishingClassifier(model_dir=settings.MODEL_DIR)


@router.post("/api/v1/scan-email", response_model=EmailResponse)
async def scan_email(
    request: EmailRequest,
    model: PhishingClassifier = Depends(get_classifier),  # noqa: B008
) -> EmailResponse:
    result = model.analyze(request.text)
    return EmailResponse(
        is_phishing=result.is_phishing,
        threat_score_out_of_100=result.threat_score,
        reasoning=result.reasoning,
        inference_time_ms=round(result.inference_time_ms, 2),
    )

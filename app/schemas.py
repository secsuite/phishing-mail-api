"""Request/response schemas."""

from pydantic import BaseModel, Field


class EmailRequest(BaseModel):
    text: str = Field(..., description="Email body text to analyze")


class EmailResponse(BaseModel):
    is_phishing: bool
    threat_score_out_of_100: int
    reasoning: str
    inference_time_ms: float

"""ONNX-backed phishing email classifier service."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer

from app.config import settings


@dataclass(frozen=True)
class AnalysisResult:
    is_phishing: bool
    confidence_score: float
    threat_score: int
    reasoning: str
    inference_time_ms: float


class PhishingClassifier:
    """Lazy-loading inference service for phishing mail classification."""

    def __init__(self, model_dir: str | None = None) -> None:
        self.model_dir = model_dir or settings.MODEL_DIR
        self._tokenizer = None
        self._session = None
        self._lock = Lock()

    def _ensure_pipeline(self) -> Any:
        if self._tokenizer is not None and self._session is not None:
            return self._tokenizer, self._session
        with self._lock:
            if self._tokenizer is not None and self._session is not None:
                return self._tokenizer, self._session
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_dir)
            self._session = ort.InferenceSession(
                f"{self.model_dir}/model.onnx",
                providers=["CPUExecutionProvider"],
            )
        return self._tokenizer, self._session

    @staticmethod
    def _clean_text(raw_text: str) -> str:
        text = re.sub(r"<[^>]+>", " ", str(raw_text))
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _reasoning(text: str, is_phishing: bool) -> str:
        risky_patterns = ["urgent", "verify", "password", "suspended", "click", "account"]
        lowered = text.lower()
        matches = [token for token in risky_patterns if token in lowered]
        if is_phishing and matches:
            return "Suspicious language patterns detected: " + ", ".join(matches[:4])
        if is_phishing:
            return "Model confidence indicates phishing-like characteristics."
        return "No strong phishing signal found in language patterns."

    def analyze(self, text: str) -> AnalysisResult:
        clean_text = self._clean_text(text)
        start = time.perf_counter()
        tokenizer, session = self._ensure_pipeline()
        encoded = tokenizer(
            clean_text,
            truncation=True,
            max_length=512,
            return_tensors="np",
        )
        ort_inputs = {
            input_meta.name: encoded[input_meta.name].astype(np.int64)
            for input_meta in session.get_inputs()
            if input_meta.name in encoded
        }
        logits = session.run(None, ort_inputs)[0][0]
        probs = np.exp(logits - np.max(logits))
        probs = probs / probs.sum()
        phishing_score = float(probs[1]) if len(probs) > 1 else float(probs[0])
        is_phishing = phishing_score >= settings.CLASSIFICATION_THRESHOLD
        elapsed_ms = (time.perf_counter() - start) * 1000
        threat_score = int(round(phishing_score * 100))

        return AnalysisResult(
            is_phishing=is_phishing,
            confidence_score=phishing_score,
            threat_score=threat_score,
            reasoning=self._reasoning(clean_text, is_phishing),
            inference_time_ms=elapsed_ms,
        )


classifier = PhishingClassifier()

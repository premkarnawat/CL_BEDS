"""
CL-BEDS RoBERTa Emotion Detection Model
Wraps HuggingFace transformers for NLP-based emotion inference.

Model: cardiffnlp/twitter-roberta-base-emotion
Labels: joy, optimism, anger, sadness  →  mapped to CL-BEDS emotion classes

CL-BEDS emotion mapping:
  joy / optimism → Neutral (low burnout signal)
  anger          → Stress
  sadness        → Fatigue
  (high probability combined score) → Cognitive_Overload
"""

import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy import to avoid slowing startup if transformers not installed
_pipeline = None
_LABEL_MAP = {
    "joy":       "Neutral",
    "optimism":  "Neutral",
    "anger":     "Stress",
    "sadness":   "Fatigue",
}
_OVERLOAD_THRESHOLD = 0.60   # combined neg-affect → Cognitive_Overload


class RoBERTaEmotionModel:
    """Singleton wrapper for the HuggingFace emotion pipeline."""

    def __init__(self):
        self._pipe = None
        self._available = False

    def load(self) -> None:
        """
        Attempt to load the transformers pipeline.
        Gracefully degrades if transformers / torch not available.
        """
        try:
            from transformers import pipeline  # type: ignore

            model_name = "cardiffnlp/twitter-roberta-base-emotion"
            self._pipe = pipeline(
                "text-classification",
                model=model_name,
                tokenizer=model_name,
                top_k=None,          # return all label scores
                device=-1,           # CPU
            )
            self._available = True
            logger.info("RoBERTa emotion model loaded successfully")
        except Exception as exc:
            logger.warning(
                "RoBERTa model could not be loaded (%s) – "
                "emotion detection will return 'Neutral'",
                exc,
            )
            self._available = False

    def predict(self, text: str) -> tuple[str, float]:
        """
        Predict the dominant emotion from a text snippet.

        Returns
        -------
        (emotion_label, confidence)  e.g. ("Stress", 0.82)
        """
        if not text or not text.strip():
            return "Neutral", 1.0

        if not self._available or self._pipe is None:
            return "Neutral", 1.0

        try:
            # Truncate input to 512 tokens proxy (128 words ~= safe limit)
            truncated = " ".join(text.split()[:128])
            results = self._pipe(truncated)[0]  # list of {label, score}

            # Sort by score descending
            results_sorted = sorted(results, key=lambda x: x["score"], reverse=True)
            top = results_sorted[0]

            # Check for cognitive overload: high combined negative affect
            neg_labels = {"anger", "sadness"}
            neg_score = sum(r["score"] for r in results if r["label"] in neg_labels)
            if neg_score >= _OVERLOAD_THRESHOLD:
                return "Cognitive_Overload", round(neg_score, 4)

            mapped = _LABEL_MAP.get(top["label"], "Neutral")
            return mapped, round(top["score"], 4)

        except Exception as exc:
            logger.error("RoBERTa inference error: %s", exc)
            return "Neutral", 1.0

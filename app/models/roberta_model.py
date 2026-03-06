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

MEMORY NOTE:
  RoBERTa is ~500 MB. On Render Nano (512 MB limit) it will OOM if loaded
  at startup. This module uses TRUE lazy loading — the model is only loaded
  on the first predict() call, not at import or load() time.
  If memory is insufficient, it degrades gracefully to returning "Neutral".
"""
import logging

logger = logging.getLogger(__name__)

_LABEL_MAP = {
    "joy":      "Neutral",
    "optimism": "Neutral",
    "anger":    "Stress",
    "sadness":  "Fatigue",
}
_OVERLOAD_THRESHOLD = 0.60


class RoBERTaEmotionModel:
    """Lazy-loading wrapper for the HuggingFace emotion pipeline."""

    def __init__(self):
        self._pipe = None
        self._available = False
        self._load_attempted = False  # only try once to avoid repeated OOM

    def load(self) -> None:
        """
        Called at startup — intentionally does NOTHING heavy.
        The actual model download happens on first predict() call.
        This prevents OOM on startup on low-memory servers (Render Nano).
        """
        logger.info(
            "RoBERTa model set to lazy-load mode — "
            "will load on first predict() call (saves ~500 MB at startup)"
        )
        self._available = False
        self._load_attempted = False

    def _try_load(self) -> None:
        """Internal: attempt to load the pipeline once."""
        if self._load_attempted:
            return
        self._load_attempted = True

        try:
            import os
            # Tell HuggingFace to cache models in a writable directory
            os.environ.setdefault("TRANSFORMERS_CACHE", "./ml_cache/transformers")
            os.environ.setdefault("HF_HOME", "./ml_cache/hf")

            from transformers import pipeline  # type: ignore

            model_name = "cardiffnlp/twitter-roberta-base-emotion"
            self._pipe = pipeline(
                "text-classification",
                model=model_name,
                tokenizer=model_name,
                top_k=None,   # return all label scores
                device=-1,    # CPU only
            )
            self._available = True
            logger.info("RoBERTa emotion model loaded successfully (lazy load)")

        except MemoryError:
            logger.warning(
                "RoBERTa model could not load — insufficient memory. "
                "Emotion detection will return 'Neutral'. "
                "Upgrade to a higher memory plan to enable this feature."
            )
            self._available = False

        except Exception as exc:
            logger.warning(
                "RoBERTa model could not be loaded (%s) — "
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
        Falls back to ("Neutral", 1.0) if model unavailable.
        """
        if not text or not text.strip():
            return "Neutral", 1.0

        # Lazy load on first real predict call
        if not self._load_attempted:
            self._try_load()

        if not self._available or self._pipe is None:
            return "Neutral", 1.0

        try:
            # Truncate to ~128 words as safe proxy for 512 token limit
            truncated = " ".join(text.split()[:128])
            results = self._pipe(truncated)[0]  # list of {label, score}

            results_sorted = sorted(
                results, key=lambda x: x["score"], reverse=True
            )
            top = results_sorted[0]

            # Check for cognitive overload: high combined negative affect
            neg_labels = {"anger", "sadness"}
            neg_score = sum(
                r["score"] for r in results if r["label"] in neg_labels
            )
            if neg_score >= _OVERLOAD_THRESHOLD:
                return "Cognitive_Overload", round(neg_score, 4)

            mapped = _LABEL_MAP.get(top["label"], "Neutral")
            return mapped, round(top["score"], 4)

        except Exception as exc:
            logger.error("RoBERTa inference error: %s", exc)
            return "Neutral", 1.0

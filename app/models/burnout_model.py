"""
CL-BEDS Burnout Fusion Model
PyTorch MLP that takes 5 multimodal features and outputs a burnout risk score.

Features (in order):
  0: CMES index
  1: HRV stress index
  2: Backspace ratio
  3: Mouse stiffness score
  4: NLP sentiment score

Output:
  risk_score  : float in [0, 1]   (higher = more at risk)
  confidence  : float in [0, 1]   (model certainty)
"""

import logging
import os
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

from app.config import settings

logger = logging.getLogger(__name__)

_INPUT_DIM = 5
_HIDDEN_DIMS = [32, 16]


class _BurnoutMLP(nn.Module):
    """
    Lightweight MLP for burnout risk scoring.
    Architecture: 5 → 32 → 16 → 2 (risk_score, confidence logit)
    """

    def __init__(self):
        super().__init__()
        dims = [_INPUT_DIM] + _HIDDEN_DIMS

        layers = []
        for in_d, out_d in zip(dims[:-1], dims[1:]):
            layers += [
                nn.Linear(in_d, out_d),
                nn.BatchNorm1d(out_d),
                nn.ReLU(),
                nn.Dropout(p=0.2),
            ]
        layers.append(nn.Linear(_HIDDEN_DIMS[-1], 2))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class BurnoutModel:
    """
    Wrapper around _BurnoutMLP providing load / predict / save helpers.
    If no saved weights exist, the model starts with random weights
    (suitable for demo; fine-tune with labelled data for production).
    """

    def __init__(self):
        self._model: _BurnoutMLP | None = None
        self._device = torch.device("cpu")

    def load(self) -> None:
        """Load model weights from disk or initialise fresh weights."""
        self._model = _BurnoutMLP().to(self._device)
        weight_path = Path(settings.BURNOUT_MODEL_PATH)

        if weight_path.exists():
            try:
                state = torch.load(weight_path, map_location=self._device)
                self._model.load_state_dict(state)
                logger.info("Burnout model weights loaded from %s", weight_path)
            except Exception as exc:
                logger.warning("Could not load weights (%s) – using random init", exc)
        else:
            logger.info(
                "No weights found at %s – using random initialisation "
                "(fine-tune before production use)",
                weight_path,
            )

        self._model.eval()

    def predict(self, features: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Run inference.

        Parameters
        ----------
        features : Tensor of shape (batch, 5)

        Returns
        -------
        (risk_score, confidence) – both scalars / batch tensors in [0, 1]
        """
        if self._model is None:
            raise RuntimeError("Model not loaded – call load() first")

        self._model.eval()
        with torch.no_grad():
            logits = self._model(features)          # (batch, 2)
            probs = torch.sigmoid(logits)            # (batch, 2)
            risk_score = probs[:, 0]                 # first output = risk
            confidence = probs[:, 1]                 # second output = confidence

        return risk_score.squeeze(), confidence.squeeze()

    def save(self, path: str | None = None) -> None:
        """Persist model weights."""
        if self._model is None:
            raise RuntimeError("Model not loaded")
        save_path = path or settings.BURNOUT_MODEL_PATH
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        torch.save(self._model.state_dict(), save_path)
        logger.info("Burnout model saved to %s", save_path)

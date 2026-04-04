"""
Adaptive image sizing helpers for packed technical-document images.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image

BUCKET_HEIGHTS = {
    "small": 96,
    "medium": 144,
    "large": 192,
}
BUCKET_ORDER = ("small", "medium", "large")
DEFAULT_BUCKET = "medium"


def bundled_model_path() -> Path | None:
    candidate = Path(__file__).resolve().parent / "model_data" / "adaptive_image_sizer.pt"
    if candidate.exists():
        return candidate
    return None


@dataclass(frozen=True)
class AdaptiveSizingDecision:
    bucket: str
    confidence: Optional[float] = None
    source: str = "fallback"

    @property
    def max_height(self) -> int:
        return BUCKET_HEIGHTS.get(self.bucket, BUCKET_HEIGHTS[DEFAULT_BUCKET])


class AdaptiveImageSizer:
    """
    Optional ML-backed image sizer.

    The class degrades safely to a static medium bucket when no model runtime is
    available or the checkpoint cannot be loaded.
    """

    def __init__(self, model_path: Optional[Path | str] = None):
        resolved_model_path = Path(model_path).expanduser() if model_path else None
        if resolved_model_path is None:
            resolved_model_path = bundled_model_path()
        self.model_path = resolved_model_path
        self._device = "cpu"
        self._model = None
        self._class_names = list(BUCKET_ORDER)
        self._input_size = 224
        self._decision_policy = {
            "demote_large_max_margin": 0.18,
            "demote_large_max_prob": 0.60,
            "demote_large_min_medium_prob": 0.30,
            "promote_large_min_prob": 0.45,
            "promote_large_margin": 0.01,
            "promote_small_min_prob": 0.40,
            "promote_small_margin": 0.02,
        }
        self._enabled = False
        self._load_error: Optional[str] = None
        if self.model_path:
            self._try_load_model()
        else:
            self._load_error = "missing_checkpoint"

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def predict(self, image: Image.Image) -> AdaptiveSizingDecision:
        if not self._enabled or self._model is None:
            return AdaptiveSizingDecision(bucket=DEFAULT_BUCKET, source="fallback")

        try:
            import torch
            from torchvision import transforms
        except Exception as exc:
            self._enabled = False
            self._load_error = f"missing_runtime:{type(exc).__name__}"
            return AdaptiveSizingDecision(bucket=DEFAULT_BUCKET, source="fallback")

        transform = transforms.Compose([
            transforms.Resize((self._input_size, self._input_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        tensor = transform(image.convert("RGB")).unsqueeze(0).to(self._device)

        with torch.no_grad():
            logits = self._model(tensor)
            probabilities = torch.softmax(logits, dim=1).squeeze(0)
            index = int(probabilities.argmax().item())
            confidence = float(probabilities[index].item())
            bucket = self._class_names[index] if index < len(self._class_names) else DEFAULT_BUCKET
            bucket, confidence = self._apply_decision_policy(probabilities, bucket, confidence)
        return AdaptiveSizingDecision(bucket=bucket, confidence=confidence, source="model")

    def _apply_decision_policy(self, probabilities, bucket: str, confidence: float) -> tuple[str, float]:
        if len(self._class_names) < 3:
            return bucket, confidence

        medium_index = self._class_names.index("medium")
        medium_probability = float(probabilities[medium_index].item())

        if bucket == "large" and "large" in self._class_names:
            large_index = self._class_names.index("large")
            large_probability = float(probabilities[large_index].item())
            if (
                large_probability <= float(self._decision_policy["demote_large_max_prob"])
                and medium_probability >= float(self._decision_policy["demote_large_min_medium_prob"])
                and (large_probability - medium_probability)
                <= float(self._decision_policy["demote_large_max_margin"])
            ):
                return "medium", medium_probability
            return bucket, confidence

        if bucket != "medium":
            return bucket, confidence

        if "large" in self._class_names:
            large_index = self._class_names.index("large")
            large_probability = float(probabilities[large_index].item())
            if (
                large_probability >= float(self._decision_policy["promote_large_min_prob"])
                and (medium_probability - large_probability)
                <= float(self._decision_policy["promote_large_margin"])
            ):
                return "large", large_probability

        if "small" in self._class_names:
            small_index = self._class_names.index("small")
            small_probability = float(probabilities[small_index].item())
            if (
                small_probability >= float(self._decision_policy["promote_small_min_prob"])
                and (medium_probability - small_probability)
                <= float(self._decision_policy["promote_small_margin"])
            ):
                return "small", small_probability

        return bucket, confidence

    def _try_load_model(self) -> None:
        if self.model_path is None or not self.model_path.exists():
            self._load_error = "missing_checkpoint"
            return

        try:
            import torch
        except Exception as exc:
            self._load_error = f"missing_torch:{type(exc).__name__}"
            return

        try:
            from torchvision import models
        except Exception as exc:
            self._load_error = f"missing_torchvision:{type(exc).__name__}"
            return

        try:
            checkpoint = torch.load(self.model_path, map_location="cpu")
            if torch.backends.mps.is_available():
                self._device = "mps"
            model = models.mobilenet_v3_small(weights=None)
            out_features = len(checkpoint.get("class_names", list(BUCKET_ORDER)))
            model.classifier[3] = torch.nn.Linear(model.classifier[3].in_features, out_features)
            model.load_state_dict(checkpoint["state_dict"])
            model.eval()
            model.to(self._device)
            self._model = model
            self._class_names = list(checkpoint.get("class_names", list(BUCKET_ORDER)))
            self._input_size = int(checkpoint.get("input_size", 224))
            policy = checkpoint.get("decision_policy")
            if isinstance(policy, dict):
                self._decision_policy.update(policy)
            self._enabled = True
        except Exception as exc:
            self._load_error = f"load_failed:{type(exc).__name__}"
            self._enabled = False

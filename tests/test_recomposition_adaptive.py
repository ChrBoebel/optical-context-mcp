from __future__ import annotations

from PIL import Image

from optical_mcp.adaptive_image_sizer import AdaptiveSizingDecision
from optical_mcp.recomposition import RecompositionEngine


class DummySizer:
    def __init__(self, buckets: list[str]) -> None:
        self._buckets = list(buckets)
        self._index = 0

    def predict(self, image: Image.Image) -> AdaptiveSizingDecision:
        bucket = self._buckets[self._index]
        self._index += 1
        return AdaptiveSizingDecision(bucket=bucket, confidence=0.99, source="test")


def make_image(width: int = 320, height: int = 200, color: str = "black") -> Image.Image:
    return Image.new("RGB", (width, height), color)


def test_small_preview_is_narrower_than_medium_preview():
    engine = RecompositionEngine()
    image = make_image()

    small = engine.render_bucket_preview(image, "small")
    medium = engine.render_bucket_preview(image, "medium")

    assert small.width < medium.width
    assert small.height <= medium.height


def test_large_and_medium_images_get_single_image_groups():
    engine = RecompositionEngine(adaptive_image_sizer=DummySizer(["large", "medium", "small", "small"]))

    groups = engine._group_images_for_compact_layout([make_image() for _ in range(4)])

    assert len(groups[0]) == 1
    assert groups[0][0].bucket == "large"
    assert len(groups[1]) == 1
    assert groups[1][0].bucket == "medium"
    assert len(groups[2]) == 2
    assert all(item.bucket == "small" for item in groups[2])

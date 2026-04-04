from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class PackedImageArtifact:
    index: int
    path: str
    width: int
    height: int
    size_bytes: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class CompressionJobManifest:
    job_id: str
    source_pdf: str
    output_dir: str
    created_at: str
    chars_per_image: int
    page_count: int
    extracted_image_count: int
    packed_image_count: int
    ocr_markdown_path: str
    packed_images: list[PackedImageArtifact]
    adaptive_sizing_enabled: bool = False
    adaptive_model_path: str | None = None
    adaptive_model_source: str | None = None
    adaptive_model_load_error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "source_pdf": self.source_pdf,
            "output_dir": self.output_dir,
            "created_at": self.created_at,
            "chars_per_image": self.chars_per_image,
            "page_count": self.page_count,
            "extracted_image_count": self.extracted_image_count,
            "packed_image_count": self.packed_image_count,
            "ocr_markdown_path": self.ocr_markdown_path,
            "packed_images": [image.to_dict() for image in self.packed_images],
            "adaptive_sizing_enabled": self.adaptive_sizing_enabled,
            "adaptive_model_path": self.adaptive_model_path,
            "adaptive_model_source": self.adaptive_model_source,
            "adaptive_model_load_error": self.adaptive_model_load_error,
        }

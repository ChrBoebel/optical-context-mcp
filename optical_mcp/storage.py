from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import uuid

from PIL import Image

from .models import CompressionJobManifest, PackedImageArtifact


class JobStore:
    """Persist compression jobs and their generated artifacts."""

    def __init__(self, jobs_root: Path):
        self.jobs_root = jobs_root
        self.jobs_root.mkdir(parents=True, exist_ok=True)

    def create_job_dir(self, source_pdf: Path) -> tuple[str, Path]:
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        stem = source_pdf.stem.lower().replace(" ", "-")
        safe_stem = "".join(ch for ch in stem if ch.isalnum() or ch in {"-", "_"})
        job_id = f"{timestamp}-{safe_stem[:32]}-{uuid.uuid4().hex[:8]}"
        job_dir = self.jobs_root / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        return job_id, job_dir

    def save_ocr_markdown(self, job_dir: Path, markdown: str) -> Path:
        markdown_path = job_dir / "ocr_markdown.md"
        markdown_path.write_text(markdown, encoding="utf-8")
        return markdown_path

    def save_packed_images(self, job_dir: Path, images: list[Image.Image]) -> list[PackedImageArtifact]:
        artifacts: list[PackedImageArtifact] = []
        for image_index, image in enumerate(images, start=1):
            image_path = job_dir / f"packed_{image_index:03d}.png"
            image.save(image_path, format="PNG")
            artifacts.append(
                PackedImageArtifact(
                    index=image_index,
                    path=str(image_path.resolve()),
                    width=image.width,
                    height=image.height,
                    size_bytes=image_path.stat().st_size,
                )
            )
        return artifacts

    def save_manifest(self, job_dir: Path, manifest: CompressionJobManifest) -> Path:
        manifest_path = job_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return manifest_path

    def load_manifest(self, job_id: str) -> CompressionJobManifest:
        manifest_path = self.jobs_root / job_id / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Unknown job_id: {job_id}")

        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return CompressionJobManifest(
            job_id=str(payload["job_id"]),
            source_pdf=str(payload["source_pdf"]),
            output_dir=str(payload["output_dir"]),
            created_at=str(payload["created_at"]),
            chars_per_image=int(payload["chars_per_image"]),
            page_count=int(payload["page_count"]),
            extracted_image_count=int(payload["extracted_image_count"]),
            packed_image_count=int(payload["packed_image_count"]),
            ocr_markdown_path=str(payload["ocr_markdown_path"]),
            packed_images=[
                PackedImageArtifact(
                    index=int(item["index"]),
                    path=str(item["path"]),
                    width=int(item["width"]),
                    height=int(item["height"]),
                    size_bytes=int(item["size_bytes"]),
                )
                for item in payload["packed_images"]
            ],
        )

    def get_image_bytes(self, job_id: str, image_index: int) -> bytes:
        manifest = self.load_manifest(job_id)
        for image in manifest.packed_images:
            if image.index == image_index:
                return Path(image.path).read_bytes()
        raise FileNotFoundError(f"Job {job_id} has no packed image {image_index}")

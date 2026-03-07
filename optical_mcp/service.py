from __future__ import annotations

from datetime import UTC, datetime
import os
from pathlib import Path

from dotenv import load_dotenv

from .mistral_client import MistralOCRClient
from .models import CompressionJobManifest
from .recomposition import RecompositionEngine
from .storage import JobStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class OpticalCompressionService:
    """Bridge the existing OCR/recomposition code into stored MCP-friendly jobs."""

    def __init__(
        self,
        job_store: JobStore,
        mistral_api_key: str | None = None,
    ):
        load_dotenv(PROJECT_ROOT / ".env")
        self.job_store = job_store
        self.mistral_api_key = mistral_api_key or os.getenv("MISTRAL_API_KEY")
        self._ocr_client: MistralOCRClient | None = None
        self.recomposition_engine = RecompositionEngine()

    @property
    def ocr_client(self) -> MistralOCRClient:
        if self._ocr_client is None:
            if not self.mistral_api_key:
                raise ValueError("MISTRAL_API_KEY is required for compress_pdf")
            self._ocr_client = MistralOCRClient(api_key=self.mistral_api_key)
        return self._ocr_client

    def compress_pdf(
        self,
        pdf_path: str | Path,
        chars_per_image: int = 12000,
    ) -> CompressionJobManifest:
        source_pdf = self._resolve_pdf_path(pdf_path)
        extraction = self.ocr_client.extract_pdf(source_pdf)

        pages_data: list[dict[str, object]] = []
        total_images = 0
        page_markdown_sections: list[str] = []

        for page_number, page in enumerate(extraction.pages, start=1):
            markdown = page.markdown if hasattr(page, "markdown") else ""
            images = list(page.images) if hasattr(page, "images") else []
            total_images += len(images)
            pages_data.append(
                {
                    "markdown": markdown,
                    "images": images,
                }
            )

            cleaned_markdown = str(markdown).strip()
            if cleaned_markdown:
                page_markdown_sections.append(f"## Page {page_number}\n\n{cleaned_markdown}")

        packed_images = self.recomposition_engine.pack_text_and_images_dense(
            pages_data=pages_data,
            target_height=1400,
            chars_per_image=chars_per_image,
        )

        job_id, job_dir = self.job_store.create_job_dir(source_pdf)
        ocr_markdown = "\n\n".join(page_markdown_sections)
        ocr_markdown_path = self.job_store.save_ocr_markdown(job_dir, ocr_markdown)
        packed_artifacts = self.job_store.save_packed_images(job_dir, packed_images)

        manifest = CompressionJobManifest(
            job_id=job_id,
            source_pdf=str(source_pdf),
            output_dir=str(job_dir.resolve()),
            created_at=datetime.now(tz=UTC).isoformat(),
            chars_per_image=chars_per_image,
            page_count=len(pages_data),
            extracted_image_count=total_images,
            packed_image_count=len(packed_artifacts),
            ocr_markdown_path=str(ocr_markdown_path.resolve()),
            packed_images=packed_artifacts,
        )
        self.job_store.save_manifest(job_dir, manifest)
        return manifest

    def get_manifest(self, job_id: str) -> CompressionJobManifest:
        return self.job_store.load_manifest(job_id)

    def get_image_bytes(self, job_id: str, image_index: int) -> bytes:
        return self.job_store.get_image_bytes(job_id, image_index)

    def _resolve_pdf_path(self, pdf_path: str | Path) -> Path:
        candidate = Path(pdf_path)
        if not candidate.is_absolute():
            candidate = (PROJECT_ROOT / candidate).resolve()
        else:
            candidate = candidate.resolve()

        if not candidate.exists():
            raise FileNotFoundError(f"PDF not found: {candidate}")
        if candidate.suffix.lower() != ".pdf":
            raise ValueError(f"Only PDF files are supported: {candidate}")
        return candidate

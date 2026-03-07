from __future__ import annotations

from pathlib import Path

from optical_mcp.models import CompressionJobManifest, PackedImageArtifact
from optical_mcp.storage import JobStore


def test_manifest_round_trip(tmp_path: Path):
    store = JobStore(tmp_path / "jobs")
    job_id, job_dir = store.create_job_dir(Path("example.pdf"))

    manifest = CompressionJobManifest(
        job_id=job_id,
        source_pdf="/tmp/example.pdf",
        output_dir=str(job_dir),
        created_at="2026-03-07T00:00:00+00:00",
        chars_per_image=12000,
        page_count=5,
        extracted_image_count=2,
        packed_image_count=1,
        ocr_markdown_path=str(job_dir / "ocr_markdown.md"),
        packed_images=[
            PackedImageArtifact(
                index=1,
                path=str(job_dir / "packed_001.png"),
                width=1024,
                height=1400,
                size_bytes=12345,
            )
        ],
    )

    store.save_manifest(job_dir, manifest)
    loaded = store.load_manifest(job_id)

    assert loaded.to_dict() == manifest.to_dict()

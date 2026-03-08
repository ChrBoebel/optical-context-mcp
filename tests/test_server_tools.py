from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
import pytest

from optical_mcp.models import CompressionJobManifest, PackedImageArtifact
from optical_mcp import server

def test_server_exposes_expected_tools():
    tools = asyncio.run(server.mcp.list_tools())
    tool_names = {tool.name for tool in tools}
    assert tool_names == {
        "compress_pdf",
        "get_job_manifest",
        "get_packed_images",
    }


def test_cli_help_exits_cleanly(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc_info:
        server.main(["--help"])

    assert exc_info.value.code == 0
    assert "optical-context-mcp" in capsys.readouterr().out


def test_compress_pdf_returns_no_more_than_30_inline_images(
    monkeypatch: pytest.MonkeyPatch,
):
    manifest = CompressionJobManifest(
        job_id="job-123",
        source_pdf="/tmp/example.pdf",
        output_dir="/tmp/optical-context-mcp/jobs/job-123",
        created_at="2026-03-08T00:00:00+00:00",
        chars_per_image=12000,
        page_count=80,
        extracted_image_count=10,
        packed_image_count=40,
        ocr_markdown_path="/tmp/optical-context-mcp/jobs/job-123/ocr_markdown.md",
        packed_images=[
            PackedImageArtifact(
                index=index,
                path=f"/tmp/optical-context-mcp/jobs/job-123/packed_{index:03d}.png",
                width=1000,
                height=1400,
                size_bytes=1234,
            )
            for index in range(1, 41)
        ],
    )

    class FakeService:
        def compress_pdf(self, pdf_path: str, chars_per_image: int) -> CompressionJobManifest:
            return manifest

        def get_image_bytes(self, job_id: str, image_index: int) -> bytes:
            return f"image-{image_index}".encode("ascii")

    monkeypatch.setattr(server, "_get_service", lambda: FakeService())

    result = server.compress_pdf("/tmp/example.pdf", inline_images=50)

    image_blocks = [block for block in result.content if block.type == "image"]
    assert len(image_blocks) == server.MAX_INLINE_IMAGES


def test_job_store_defaults_to_system_temp_directory():
    expected_root = (Path(tempfile.gettempdir()) / "optical-context-mcp" / "jobs").resolve()
    assert server.JOB_STORE.jobs_root == expected_root

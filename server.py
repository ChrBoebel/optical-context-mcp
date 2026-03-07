from __future__ import annotations

import base64
import json
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from mcp import types

from optical_mcp.service import PROJECT_ROOT, OpticalCompressionService
from optical_mcp.storage import JobStore

SERVER_ROOT = Path(__file__).resolve().parent
JOB_STORE = JobStore(SERVER_ROOT / "jobs")
SERVICE: OpticalCompressionService | None = None
mcp = FastMCP("Optical Context MCP")


def _get_service() -> OpticalCompressionService:
    global SERVICE
    if SERVICE is None:
        SERVICE = OpticalCompressionService(job_store=JOB_STORE)
    return SERVICE


def _manifest_summary(manifest: dict[str, object], inline_images: int) -> str:
    packed_count = int(manifest["packed_image_count"])
    page_count = int(manifest["page_count"])
    extracted_images = int(manifest["extracted_image_count"])
    summary_lines = [
        f"Compressed {page_count} PDF pages into {packed_count} packed images.",
        f"Job ID: {manifest['job_id']}",
        f"Source PDF: {manifest['source_pdf']}",
        f"Extracted images from OCR: {extracted_images}",
        f"Packed image preview returned inline: {min(packed_count, inline_images)}",
        f"Artifacts directory: {manifest['output_dir']}",
    ]
    if packed_count > inline_images:
        summary_lines.append(
            "Use get_packed_images to fetch the remaining packed PNGs in batches."
        )
    return "\n".join(summary_lines)


@mcp.tool(
    name="compress_pdf",
    description=(
        "Read a local PDF, run Mistral OCR, recompose it into dense packed PNG images, "
        "and create a retrievable compression job."
    ),
)
def compress_pdf(
    pdf_path: str,
    chars_per_image: int = 12000,
    inline_images: int = 3,
) -> ToolResult:
    """Compress a local PDF into dense packed images for downstream agent use."""
    if chars_per_image <= 0:
        raise ValueError("chars_per_image must be greater than 0")
    if inline_images < 0:
        raise ValueError("inline_images cannot be negative")

    service = _get_service()
    manifest = service.compress_pdf(pdf_path=pdf_path, chars_per_image=chars_per_image)
    manifest_payload = manifest.to_dict()

    content: list[types.ContentBlock] = [
        types.TextContent(
            type="text",
            text=_manifest_summary(manifest_payload, inline_images),
        )
    ]

    for image in manifest.packed_images[:inline_images]:
        content.append(
            types.ImageContent(
                type="image",
                data=base64.b64encode(
                    service.get_image_bytes(manifest.job_id, image.index)
                ).decode("ascii"),
                mimeType="image/png",
            )
        )

    return ToolResult(
        content=content,
        structured_content=manifest_payload,
    )


@mcp.tool(
    name="get_job_manifest",
    description="Load the saved manifest for a previously compressed PDF job.",
)
def get_job_manifest(job_id: str) -> ToolResult:
    """Return manifest metadata for a previously created compression job."""
    manifest = _get_service().get_manifest(job_id)
    manifest_payload = manifest.to_dict()
    return ToolResult(
        content=[
            types.TextContent(
                type="text",
                text=json.dumps(manifest_payload, ensure_ascii=False, indent=2),
            )
        ],
        structured_content=manifest_payload,
    )


@mcp.tool(
    name="get_packed_images",
    description=(
        "Return one or more previously generated packed PNG images for a stored job."
    ),
)
def get_packed_images(
    job_id: str,
    start_index: int = 1,
    limit: int = 3,
) -> ToolResult:
    """Fetch saved packed images in batches to keep MCP responses bounded."""
    if start_index <= 0:
        raise ValueError("start_index must be greater than 0")
    if limit <= 0:
        raise ValueError("limit must be greater than 0")

    service = _get_service()
    manifest = service.get_manifest(job_id)
    selected_images = [
        image
        for image in manifest.packed_images
        if image.index >= start_index
    ][:limit]

    if not selected_images:
        raise FileNotFoundError(
            f"No packed images available for job {job_id} at start_index={start_index}"
        )

    content: list[types.ContentBlock] = [
        types.TextContent(
            type="text",
            text=(
                f"Returning {len(selected_images)} packed images for job {job_id} "
                f"starting at index {start_index}."
            ),
        )
    ]
    returned_images: list[dict[str, object]] = []

    for image in selected_images:
        content.append(
            types.ImageContent(
                type="image",
                data=base64.b64encode(
                    service.get_image_bytes(job_id, image.index)
                ).decode("ascii"),
                mimeType="image/png",
            )
        )
        returned_images.append(image.to_dict())

    return ToolResult(
        content=content,
        structured_content={
            "job_id": job_id,
            "returned_images": returned_images,
            "remaining_images": max(
                manifest.packed_image_count - (selected_images[-1].index),
                0,
            ),
            "project_root": str(PROJECT_ROOT),
        },
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

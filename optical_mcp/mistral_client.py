"""
Mistral OCR client for document extraction.
"""

from __future__ import annotations

import base64
from pathlib import Path

from mistralai import Mistral


class MistralOCRClient:
    """Client for the Mistral OCR API."""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Mistral API key not provided")
        self.client = Mistral(api_key=api_key)
        self.model = "mistral-ocr-latest"

    def extract_pdf(self, pdf_path: Path | str):
        """Extract text and images from a PDF."""
        path = Path(pdf_path)
        with open(path, "rb") as handle:
            pdf_data = base64.b64encode(handle.read()).decode("utf-8")

        return self.client.ocr.process(
            model=self.model,
            document={
                "type": "document_url",
                "document_url": f"data:application/pdf;base64,{pdf_data}",
            },
            include_image_base64=True,
        )

    def extract_image(self, image_path: Path | str):
        """Extract text and elements from a single image."""
        path = Path(image_path)
        suffix = path.suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_map.get(suffix, "image/png")

        with open(path, "rb") as handle:
            image_data = base64.b64encode(handle.read()).decode("utf-8")

        return self.client.ocr.process(
            model=self.model,
            document={
                "type": "image_url",
                "image_url": f"data:{mime_type};base64,{image_data}",
            },
            include_image_base64=True,
        )

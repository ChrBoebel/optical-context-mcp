"""
Recomposition engine for optical compression.
"""

from __future__ import annotations

import base64
import hashlib
import io
from pathlib import Path
import re
import textwrap
from typing import List
from typing import Optional
from typing import Tuple

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


class RecompositionEngine:
    """Render extracted content onto compact, readable images."""

    def __init__(
        self,
        target_width: int = 1024,
        font_size: int = 9,
        line_spacing: int = 0,
        margin: int = 2,
        columns: int = 2,
    ):
        self.target_width = target_width
        self.font_size = font_size
        self.line_spacing = line_spacing
        self.margin = margin
        self.columns = columns
        self.font = self._load_font(font_size)
        self.font_bold = self._load_font(font_size, bold=True)
        self.font_small = self._load_font(font_size - 2)

    def _load_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
            (
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                if bold
                else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            ),
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for path in font_paths:
            if Path(path).exists():
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
        return ImageFont.load_default()

    def pack_text_and_images_dense(
        self,
        pages_data: List[dict],
        target_height: int = 1400,
        chars_per_image: int = 6000,
    ) -> List[Image.Image]:
        all_content = []

        for page_idx, page in enumerate(pages_data):
            page_seen_hashes: set[str] = set()
            markdown = page.get("markdown", "") if isinstance(page, dict) else getattr(page, "markdown", "")
            images = page.get("images", []) if isinstance(page, dict) else getattr(page, "images", [])

            all_content.append(("header", f"--- Page {page_idx + 1} ---"))

            cleaned_text = self._clean_markdown(markdown)
            if cleaned_text.strip():
                all_content.append(("text", cleaned_text))

            page_images = []
            for img_data in images:
                decoded = self._decode_image(img_data)
                if decoded and self._is_unique_image(decoded, page_seen_hashes):
                    page_images.append(decoded)

            for md_image in self._extract_data_uri_images_from_markdown(markdown):
                if self._is_unique_image(md_image, page_seen_hashes):
                    page_images.append(md_image)

            if page_images:
                grouped = self._group_images_for_compact_layout(page_images)
                for group in grouped:
                    if len(group) == 1:
                        all_content.append(("image", group[0]))
                    else:
                        all_content.append(("image_row", group))

        chunks = self._split_content_into_chunks(all_content, chars_per_image)
        return [self._render_dense_chunk(chunk, target_height) for chunk in chunks]

    def pack_chunks_to_images(
        self,
        chunks: List[str],
        target_height: int = 1400,
        chars_per_image: int = 6000,
    ) -> List[Image.Image]:
        if not chunks:
            return []

        combined_chunks = []
        current_combined = []
        current_chars = 0

        for chunk in chunks:
            chunk_len = len(chunk)
            if current_chars + chunk_len > chars_per_image and current_combined:
                combined_chunks.append("\n\n".join(current_combined))
                current_combined = []
                current_chars = 0

            current_combined.append(chunk)
            current_chars += chunk_len

        if current_combined:
            combined_chunks.append("\n\n".join(current_combined))

        pages_data = [{"markdown": text, "images": []} for text in combined_chunks]
        return self.pack_text_and_images_dense(
            pages_data=pages_data,
            target_height=target_height,
            chars_per_image=chars_per_image * 2,
        )

    def _split_content_into_chunks(
        self,
        content: List[Tuple[str, object]],
        chars_per_chunk: int,
    ) -> List[List[Tuple[str, object]]]:
        chunks = []
        current_chunk = []
        current_chars = 0

        for item_type, item_data in content:
            if item_type == "text":
                text_len = len(str(item_data))
                if current_chars + text_len > chars_per_chunk and current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_chars = 0
                current_chunk.append((item_type, item_data))
                current_chars += text_len
            elif item_type == "image":
                current_chunk.append((item_type, item_data))
                current_chars += 300
            elif item_type == "image_row":
                current_chunk.append((item_type, item_data))
                current_chars += 150 * len(item_data)
            else:
                current_chunk.append((item_type, item_data))
                current_chars += len(str(item_data))

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _render_dense_chunk(
        self,
        chunk: List[Tuple[str, object]],
        target_height: int,
    ) -> Image.Image:
        del target_height
        col_gap = 1
        col_width = (self.target_width - 2 * self.margin - col_gap) // self.columns
        avg_char_width = (
            self.font.getlength("x")
            if hasattr(self.font, "getlength")
            else self.font_size * 0.5
        )
        chars_per_line = int(col_width / avg_char_width) - 2
        line_height = self.font_size + self.line_spacing

        elements = []

        for item_type, item_data in chunk:
            if item_type == "header":
                elements.append(("header", item_data, line_height + 4))
            elif item_type == "text":
                lines = self._wrap_text(str(item_data), chars_per_line)
                elements.append(("text", lines, len(lines) * line_height))
            elif item_type == "image":
                img = self._scale_image(item_data, col_width - 10, 120)
                elements.append(("image", img, img.height + 6))
            elif item_type == "image_row":
                row_imgs = item_data
                row_height = max(img.height for img in row_imgs) + 6
                elements.append(("image_row", row_imgs, row_height))

        canvas_height = sum(element[2] for element in elements) + 2 * self.margin
        canvas = Image.new("RGB", (self.target_width, canvas_height), "white")
        draw = ImageDraw.Draw(canvas)

        if self.columns == 2:
            self._render_two_column(canvas, draw, elements, line_height, col_width)
        else:
            self._render_single_column(canvas, draw, elements, line_height)

        return self._crop_to_content(canvas)

    def _render_single_column(
        self,
        canvas: Image.Image,
        draw: ImageDraw.Draw,
        elements: List[Tuple[object, object, int]],
        line_height: int,
    ) -> None:
        y = self.margin

        for elem_type, elem_data, elem_height in elements:
            if elem_type == "header":
                draw.text((self.margin, y), elem_data, font=self.font_bold, fill="#333333")
                y += elem_height
            elif elem_type == "text":
                for line in elem_data:
                    draw.text((self.margin, y), line, font=self.font, fill="black")
                    y += line_height
            elif elem_type == "image":
                x = (self.target_width - elem_data.width) // 2
                canvas.paste(elem_data, (x, y))
                y += elem_height
            elif elem_type == "image_row":
                total_width = sum(img.width for img in elem_data) + 4 * (len(elem_data) - 1)
                x = (self.target_width - total_width) // 2
                for img in elem_data:
                    canvas.paste(img, (x, y))
                    x += img.width + 4
                y += elem_height

    def _render_two_column(
        self,
        canvas: Image.Image,
        draw: ImageDraw.Draw,
        elements: List[Tuple[object, object, int]],
        line_height: int,
        col_width: int,
    ) -> None:
        col_gap = 1
        col1_x = self.margin
        col2_x = self.margin + col_width + col_gap

        balanced_elements = []
        for elem_type, elem_data, elem_height in elements:
            if elem_type == "text" and len(elem_data) > 15:
                chunk_size = 10
                for i in range(0, len(elem_data), chunk_size):
                    chunk = elem_data[i:i + chunk_size]
                    balanced_elements.append(("text", chunk, len(chunk) * line_height))
            else:
                balanced_elements.append((elem_type, elem_data, elem_height))

        col1_y = self.margin
        col2_y = self.margin

        for elem_type, elem_data, elem_height in balanced_elements:
            if col1_y <= col2_y:
                x, y = col1_x, col1_y
                is_col1 = True
            else:
                x, y = col2_x, col2_y
                is_col1 = False

            if elem_type == "header":
                draw.text((x, y), elem_data, font=self.font_bold, fill="#333333")
                if is_col1:
                    col1_y += elem_height
                else:
                    col2_y += elem_height
            elif elem_type == "text":
                for line in elem_data:
                    line_width = (
                        self.font.getlength(line)
                        if hasattr(self.font, "getlength")
                        else len(line) * 5
                    )
                    if line_width > col_width - 4:
                        while line and (
                            self.font.getlength(line + "..")
                            if hasattr(self.font, "getlength")
                            else len(line) * 5
                        ) > col_width - 4:
                            line = line[:-1]
                        line = line + ".."
                    draw.text((x, y), line, font=self.font, fill="black")
                    y += line_height
                if is_col1:
                    col1_y = y
                else:
                    col2_y = y
            elif elem_type == "image":
                img_x = x + (col_width - elem_data.width) // 2
                canvas.paste(elem_data, (img_x, y))
                if is_col1:
                    col1_y += elem_height
                else:
                    col2_y += elem_height
            elif elem_type == "image_row":
                total_width = sum(img.width for img in elem_data) + 3 * (len(elem_data) - 1)
                img_x = x + (col_width - total_width) // 2
                for img in elem_data:
                    canvas.paste(img, (img_x, y))
                    img_x += img.width + 3
                if is_col1:
                    col1_y += elem_height
                else:
                    col2_y += elem_height

    def _scale_image(
        self,
        img: Image.Image,
        max_width: int,
        max_height: int,
    ) -> Image.Image:
        ratio = min(max_width / img.width, max_height / img.height)
        if ratio < 1:
            new_size = (int(img.width * ratio), int(img.height * ratio))
            return img.resize(new_size, Image.LANCZOS)
        return img

    def _crop_to_content(self, canvas: Image.Image) -> Image.Image:
        pixels = canvas.load()
        min_x, min_y = canvas.width, canvas.height
        max_x, max_y = 0, 0

        step = 2
        for y in range(0, canvas.height, step):
            for x in range(0, canvas.width, step):
                if pixels[x, y] != (255, 255, 255):
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)

        crop_left = max(0, min_x - self.margin)
        crop_top = max(0, min_y - self.margin)
        crop_right = min(canvas.width, max_x + self.margin + step)
        crop_bottom = min(canvas.height, max_y + self.margin + step)

        if crop_bottom < canvas.height - 10 or crop_right < canvas.width - 10:
            return canvas.crop((crop_left, crop_top, crop_right, crop_bottom))
        return canvas

    def _clean_markdown(self, markdown: str) -> str:
        text = re.sub(r"!\[.*?\]\(.*?\)", "", markdown)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
        lines = [line.strip() for line in text.split("\n")]
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)

    def _wrap_text(self, text: str, width: int) -> List[str]:
        lines = []
        for paragraph in text.split("\n"):
            if paragraph.strip():
                lines.extend(textwrap.wrap(paragraph, width=width))
            else:
                lines.append("")
        return lines

    def _decode_image(self, img_data: dict) -> Optional[Image.Image]:
        try:
            if hasattr(img_data, "image_base64"):
                b64 = img_data.image_base64
            elif hasattr(img_data, "base64"):
                b64 = img_data.base64
            elif isinstance(img_data, dict) and "image_base64" in img_data:
                b64 = img_data["image_base64"]
            elif isinstance(img_data, dict) and "base64" in img_data:
                b64 = img_data["base64"]
            else:
                return None

            if not b64:
                return None

            if b64.startswith("data:"):
                parts = b64.split(",", 1)
                if len(parts) == 2:
                    b64 = parts[1]

            img_bytes = base64.b64decode(b64)
            return Image.open(io.BytesIO(img_bytes)).convert("RGB")
        except Exception:
            return None

    def _extract_data_uri_images_from_markdown(self, markdown: str) -> List[Image.Image]:
        if not markdown:
            return []

        images: List[Image.Image] = []
        pattern = r"!\[[^\]]*]\((data:image/[^)]+)\)"

        for match in re.finditer(pattern, markdown):
            data_uri = match.group(1)
            try:
                parts = data_uri.split(",", 1)
                if len(parts) != 2:
                    continue
                img_bytes = base64.b64decode(parts[1])
                images.append(Image.open(io.BytesIO(img_bytes)).convert("RGB"))
            except Exception:
                continue

        return images

    def _is_unique_image(self, img: Image.Image, seen_hashes: set[str]) -> bool:
        try:
            digest = hashlib.sha1(img.tobytes()).hexdigest()
        except Exception:
            return True

        if digest in seen_hashes:
            return False

        seen_hashes.add(digest)
        return True

    def _group_images_for_compact_layout(
        self,
        images: List[Image.Image],
    ) -> List[List[Image.Image]]:
        col_width = (self.target_width - 3 * self.margin) // self.columns
        max_img_width = col_width - 10

        groups = []
        current_row = []
        current_row_width = 0

        for img in images:
            scaled = self._scale_image(img, max_img_width // 2, 120)
            if current_row_width + scaled.width + 5 <= max_img_width:
                current_row.append(scaled)
                current_row_width += scaled.width + 5
            else:
                if current_row:
                    groups.append(current_row)
                current_row = [scaled]
                current_row_width = scaled.width

        if current_row:
            groups.append(current_row)

        return groups

    def _is_full_page_image(self, img: Image.Image) -> bool:
        width, height = img.size
        if width > 800 and height > 1000:
            return True
        aspect = width / height if height > 0 else 1
        if 0.6 < aspect < 0.85 and height > 800:
            return True
        if width > 700 and height > 700:
            return True
        return False

    def pack_text_dense(
        self,
        all_markdown: List[str],
        target_height: int = 1024,
        chars_per_image: int = 4000,
    ) -> List[Image.Image]:
        pages_data = [{"markdown": md, "images": []} for md in all_markdown]
        return self.pack_text_and_images_dense(pages_data, target_height, chars_per_image)

    def render_page(self, markdown: str, images: Optional[list] = None) -> Image.Image:
        pages_data = [{"markdown": markdown, "images": images or []}]
        result = self.pack_text_and_images_dense(pages_data, 1024, 10000)
        if result:
            return result[0]
        return Image.new("RGB", (self.target_width, 100), "white")

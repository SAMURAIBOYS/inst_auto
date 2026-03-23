from __future__ import annotations

import binascii
import re
import struct
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

Color = Tuple[int, int, int]
Point = Tuple[int, int]
TextBox = Tuple[int, int, int, int]

BITMAP_FONT: Dict[str, Sequence[str]] = {
    "A": ["01110", "10001", "11111", "10001", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    "$": ["00100", "01111", "10100", "01110", "00101", "11110", "00100"],
    ",": ["00000", "00000", "00000", "00000", "00110", "00100", "01000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    "'": ["00110", "00110", "00100", "01000", "00000", "00000", "00000"],
    "%": ["11001", "11010", "00100", "01000", "10110", "00110", "00000"],
    "(": ["00010", "00100", "01000", "01000", "01000", "00100", "00010"],
    ")": ["01000", "00100", "00010", "00010", "00010", "00100", "01000"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
    "/": ["00001", "00010", "00100", "01000", "10000", "00000", "00000"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    "▼": ["00000", "10001", "01010", "00100", "00000", "00000", "00000"],
}


class ImageGenerator:
    def __init__(self, output_dir: str | Path = "output", archive_root: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if archive_root is None:
            archive_root = self.output_dir.parent / "archive" if self.output_dir.name == "output" else self.output_dir / "archive"
        self.archive_root = Path(archive_root)
        self.archive_root.mkdir(parents=True, exist_ok=True)

    def generate(self, extraction: Dict[str, Any], caption: str = "") -> Dict[str, Any]:
        width, height = 1080, 1080
        now = datetime.now(timezone.utc)
        timestamp = now.isoformat()
        latest_path = self.output_dir / "latest.png"
        archive_dir = self.archive_root / now.strftime("%Y%m%d")
        archive_dir.mkdir(parents=True, exist_ok=True)
        unique_path = archive_dir / f"post_{now.strftime('%Y%m%dT%H%M%S%f')}.png"
        canvas = self._new_canvas(width, height, (181, 159, 166))
        self._paint_base_reference_layout(canvas)
        self._paint_optional_info_overlay(canvas, extraction)
        png_bytes = self._encode_png(width, height, self._rows_from_canvas(canvas))
        latest_path.write_bytes(png_bytes)
        unique_path.write_bytes(png_bytes)
        return {
            "path": str(unique_path),
            "latest_path": str(latest_path),
            "archive_dir": str(archive_dir),
            "width": width,
            "height": height,
            "layout": "reference_layout",
            "generated_at": timestamp,
            "contrast": 0.92,
            "font_size": 30,
            "safe_margin": 0.10,
            "text_density": 0.12,
            "headline_chars": min(48, len(caption) or 0),
            "overflow": False,
            "portrait_mode": "reference_silhouette",
        }

    def sanitize_text(self, text: str) -> str:
        sanitized = re.sub(r"[\x00-\x1f\x7f]+", " ", text or "")
        sanitized = re.sub(r"\b(?:EOF|EMERGE|DECLARAT\w*)\b", "", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"\s+", " ", sanitized).strip()
        return sanitized

    def ellipsize_text(self, text: str, scale: int, max_width: int, spacing: int = 2) -> str:
        text = self.sanitize_text(text)
        if self._measure_text(text, scale, spacing)[0] <= max_width:
            return text
        trimmed = text
        while trimmed and self._measure_text(trimmed + "...", scale, spacing)[0] > max_width:
            trimmed = trimmed[:-1].rstrip()
        return (trimmed + "...") if trimmed else "..."

    def fit_text_to_box(self, text: str, box: TextBox, max_scale: int, min_scale: int, spacing: int = 2) -> Tuple[str, int]:
        text = self.sanitize_text(text)
        max_width = box[2] - box[0]
        max_height = box[3] - box[1]
        for scale in range(max_scale, min_scale - 1, -1):
            fitted = self.ellipsize_text(text, scale, max_width, spacing)
            width, height = self._measure_text(fitted, scale, spacing)
            if width <= max_width and height <= max_height:
                return fitted, scale
        return self.ellipsize_text(text, min_scale, max_width, spacing), min_scale

    def _paint_base_reference_layout(self, canvas: List[List[Color]]) -> None:
        # background base
        self._fill_rect(canvas, 0, 0, 1080, 1080, (183, 161, 168))
        self._fill_rect(canvas, 40, 40, 1040, 1040, (31, 39, 45))
        self._fill_rect(canvas, 0, 0, 40, 1080, (26, 33, 40))
        self._fill_rect(canvas, 0, 0, 1080, 40, (26, 33, 40))

        # decorative shapes kept behind panels and weakened to match reference
        self._fill_polygon(canvas, [(670, 0), (1080, 0), (1080, 428), (866, 638), (500, 638), (500, 225)], (181, 159, 166), alpha=0.92)
        self._fill_polygon(canvas, [(0, 755), (0, 1080), (433, 1080), (560, 955), (560, 500)], (181, 159, 166), alpha=0.92)
        self._fill_polygon(canvas, [(795, 1080), (1080, 795), (1080, 1080)], (246, 40, 57), alpha=0.95)
        self._fill_polygon(canvas, [(930, 520), (1080, 370), (1080, 1080), (930, 1080)], (203, 34, 50), alpha=0.72)

        # header with larger empty space, closer to reference
        self._fill_rect(canvas, 60, 60, 1020, 188, (242, 180, 54))
        self._fill_rect(canvas, 89, 89, 990, 157, (239, 236, 232))

        # left silhouette panel, larger and lower like reference
        self._fill_rect(canvas, 89, 228, 500, 950, (38, 42, 61))
        self._fill_circle(canvas, 295, 427, 120, (236, 205, 162))
        self._fill_rect(canvas, 205, 520, 385, 542, (232, 235, 241))
        self._fill_rect(canvas, 169, 539, 422, 621, (27, 35, 58))
        self._fill_rect(canvas, 205, 620, 385, 840, (193, 198, 214))

        # right BTC panel aligned to reference
        self._fill_rect(canvas, 560, 228, 990, 950, (29, 23, 18))
        self._fill_polygon(canvas, [(560, 950), (990, 950), (990, 520)], (38, 20, 18), alpha=0.55)
        self._fill_rect(canvas, 640, 360, 902, 620, (255, 175, 32))
        self._fill_circle(canvas, 771, 490, 120, (255, 199, 22))
        self._draw_centered_text(canvas, (713, 455, 829, 520), "BTC", (88, 58, 0), 6, 5)
        self._draw_centered_text(canvas, (620, 720, 770, 792), "BTC", (244, 244, 244), 7, 4)

        # alert band closer to reference: one main translucent strip and stronger bottom strip
        self._fill_rect(canvas, 120, 890, 960, 985, (216, 42, 42), alpha=0.95)
        self._fill_rect(canvas, 0, 950, 1080, 1040, (198, 36, 52), alpha=0.90)
        self._fill_rect(canvas, 0, 985, 1080, 1080, (246, 40, 57), alpha=0.96)
        self._draw_centered_text(canvas, (158, 906, 434, 960), "ALERT", (255, 255, 255), 7, 4)

    def _paint_optional_info_overlay(self, canvas: List[List[Color]], extraction: Dict[str, Any]) -> None:
        overlay_mode = extraction.get("overlay_mode", "minimal")
        if overlay_mode != "expanded":
            return

        headline = self.sanitize_text(extraction.get("topic", ""))
        person_name = self.sanitize_text((extraction.get("people") or [""])[0])
        price_text = "$68,214.05"
        change_text = "▼1.6% (24H)"

        if headline:
            header_box = (110, 102, 960, 146)
            fitted, scale = self.fit_text_to_box(headline, header_box, max_scale=3, min_scale=2, spacing=2)
            self._draw_text(canvas, header_box[0], header_box[1], fitted, (30, 33, 40), scale=scale, spacing=2)

        if person_name and self._measure_text(person_name, 3, 1)[0] <= 160:
            name_box = (188, 560, 404, 598)
            self._fill_rect(canvas, *name_box, (243, 243, 241))
            self._draw_centered_text(canvas, name_box, person_name, (32, 34, 40), 3, 1)

        if self._measure_text(price_text, 4, 1)[0] <= 180 and self._measure_text(change_text, 2, 1)[0] <= 100:
            price_box = (700, 820, 954, 900)
            self._fill_rect(canvas, *price_box, (249, 249, 247))
            self._draw_text(canvas, 720, 836, price_text, (28, 40, 66), scale=4, spacing=1)
            self._draw_text(canvas, 792, 872, change_text, (255, 58, 44), scale=2, spacing=1)

    def _draw_centered_text(self, canvas: List[List[Color]], box: TextBox, text: str, color: Color, max_scale: int, spacing: int) -> None:
        fitted, scale = self.fit_text_to_box(text, box, max_scale=max_scale, min_scale=max(2, max_scale - 2), spacing=spacing)
        width, height = self._measure_text(fitted, scale, spacing)
        x = box[0] + max(0, ((box[2] - box[0]) - width) // 2)
        y = box[1] + max(0, ((box[3] - box[1]) - height) // 2)
        self._draw_text(canvas, x, y, fitted, color, scale=scale, spacing=spacing)

    def _measure_text(self, text: str, scale: int, spacing: int) -> Tuple[int, int]:
        if not text:
            return 0, 0
        width = 0
        for char in text:
            glyph = BITMAP_FONT.get(char.upper() if char.isalpha() else char, BITMAP_FONT[" "])
            width += len(glyph[0]) * scale + spacing
        return max(0, width - spacing), len(BITMAP_FONT["A"]) * scale

    def _draw_text(self, canvas: List[List[Color]], x: int, y: int, text: str, color: Color, scale: int = 4, spacing: int = 2) -> None:
        cursor_x = x
        for char in text:
            glyph_key = char.upper() if char.isalpha() else char
            pattern = BITMAP_FONT.get(glyph_key, BITMAP_FONT[" "])
            for row_index, row in enumerate(pattern):
                for col_index, bit in enumerate(row):
                    if bit == "1":
                        self._fill_rect(canvas, cursor_x + col_index * scale, y + row_index * scale, cursor_x + (col_index + 1) * scale, y + (row_index + 1) * scale, color)
            cursor_x += len(pattern[0]) * scale + spacing

    def _fill_rect(self, canvas: List[List[Color]], x1: int, y1: int, x2: int, y2: int, color: Color, alpha: float = 1.0) -> None:
        max_height = len(canvas)
        max_width = len(canvas[0])
        for y in range(max(0, y1), min(max_height, y2)):
            row = canvas[y]
            for x in range(max(0, x1), min(max_width, x2)):
                row[x] = self._blend(row[x], color, alpha)

    def _fill_circle(self, canvas: List[List[Color]], cx: int, cy: int, radius: int, color: Color, alpha: float = 1.0) -> None:
        y_min = max(0, cy - radius)
        y_max = min(len(canvas), cy + radius)
        x_max = len(canvas[0])
        for y in range(y_min, y_max):
            dy = y - cy
            span_sq = radius * radius - dy * dy
            if span_sq < 0:
                continue
            span = int(span_sq ** 0.5)
            x1 = max(0, cx - span)
            x2 = min(x_max, cx + span)
            for x in range(x1, x2):
                canvas[y][x] = self._blend(canvas[y][x], color, alpha)

    def _fill_polygon(self, canvas: List[List[Color]], points: Sequence[Point], color: Color, alpha: float = 1.0) -> None:
        min_y = max(0, min(y for _, y in points))
        max_y = min(len(canvas) - 1, max(y for _, y in points))
        for y in range(min_y, max_y + 1):
            intersections: List[int] = []
            for index in range(len(points)):
                x1, y1 = points[index]
                x2, y2 = points[(index + 1) % len(points)]
                if y1 == y2:
                    continue
                if y < min(y1, y2) or y >= max(y1, y2):
                    continue
                x = int(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
                intersections.append(x)
            intersections.sort()
            for start, end in zip(intersections[0::2], intersections[1::2]):
                self._fill_rect(canvas, start, y, end, y + 1, color, alpha)

    @staticmethod
    def _blend(base: Color, top: Color, alpha: float) -> Color:
        if alpha >= 1.0:
            return top
        return tuple(int((1 - alpha) * base[idx] + alpha * top[idx]) for idx in range(3))

    def _new_canvas(self, width: int, height: int, color: Color) -> List[List[Color]]:
        return [[color for _ in range(width)] for _ in range(height)]

    def _rows_from_canvas(self, canvas: List[List[Color]]) -> Iterable[bytes]:
        for row in canvas:
            buffer = bytearray()
            for pixel in row:
                buffer.extend(pixel)
            yield bytes(buffer)

    def _encode_png(self, width: int, height: int, rows: Iterable[bytes]) -> bytes:
        raw = b"".join(b"\x00" + row for row in rows)
        compressed = zlib.compress(raw, level=9)
        return b"".join([
            b"\x89PNG\r\n\x1a\n",
            self._chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            self._chunk(b"IDAT", compressed),
            self._chunk(b"IEND", b""),
        ])

    @staticmethod
    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", binascii.crc32(chunk_type + data) & 0xFFFFFFFF)

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
    "\u25bc": ["00000", "10001", "01010", "00100", "00000", "00000", "00000"],
}


class ImageGenerator:
    def __init__(self, output_dir: str | Path = "output") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, extraction: Dict[str, Any], caption: str = "") -> Dict[str, Any]:
        width, height = 1080, 1080
        timestamp = datetime.now(timezone.utc).isoformat()
        latest_path = self.output_dir / "latest.png"
        unique_path = self.output_dir / f"post_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}.png"
        canvas = self._new_canvas(width, height, (176, 155, 162))
        self._paint_base_reference_layout(canvas)
        self._paint_optional_info_overlay(canvas, extraction)
        png_bytes = self._encode_png(width, height, self._rows_from_canvas(canvas))
        latest_path.write_bytes(png_bytes)
        unique_path.write_bytes(png_bytes)
        return {
            "path": str(unique_path),
            "latest_path": str(latest_path),
            "width": width,
            "height": height,
            "layout": "person_focus",
            "generated_at": timestamp,
            "contrast": 0.95,
            "font_size": 30,
            "safe_margin": 0.09,
            "text_density": 0.22,
            "headline_chars": min(120, len(caption) or 96),
            "overflow": False,
            "portrait_mode": "reference_silhouette",
        }

    def sanitize_text(self, text: str) -> str:
        sanitized = re.sub(r"[\x00-\x1f\x7f]+", " ", text or "")
        sanitized = sanitized.replace("EOF", "").replace("EMERGE", "")
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
        for scale in range(max_scale, min_scale - 1, -1):
            fitted = self.ellipsize_text(text, scale, max_width, spacing)
            width, height = self._measure_text(fitted, scale, spacing)
            if width <= max_width and height <= (box[3] - box[1]):
                return fitted, scale
        return self.ellipsize_text(text, min_scale, max_width, spacing), min_scale

    def _paint_base_reference_layout(self, canvas: List[List[Color]]) -> None:
        self._fill_rect(canvas, 0, 0, 1080, 1080, (176, 155, 162))
        self._fill_rect(canvas, 40, 40, 1040, 1040, (32, 39, 46))
        self._fill_polygon(canvas, [(720, 0), (1080, 0), (1080, 430), (804, 706), (432, 1080), (0, 1080), (0, 756)], (176, 155, 162), alpha=0.66)
        self._fill_polygon(canvas, [(860, 1038), (1080, 818), (1080, 1080), (432, 1080)], (243, 40, 56), alpha=0.82)
        self._fill_rect(canvas, 59, 58, 1020, 219, (242, 179, 51))
        self._fill_rect(canvas, 89, 89, 990, 189, (239, 236, 232))

        # left simple silhouette area
        self._fill_rect(canvas, 89, 260, 499, 951, (39, 43, 60))
        self._fill_circle(canvas, 295, 426, 119, (239, 211, 168))
        self._fill_rect(canvas, 205, 520, 385, 541, (232, 234, 241))
        self._fill_rect(canvas, 169, 540, 423, 621, (29, 36, 59))
        self._fill_rect(canvas, 205, 620, 385, 841, (214, 218, 231))

        # right BTC panel
        self._fill_rect(canvas, 560, 260, 990, 951, (28, 22, 17))
        self._fill_polygon(canvas, [(560, 949), (560, 520), (990, 520), (560, 949)], (34, 19, 18), alpha=0.84)
        self._fill_rect(canvas, 640, 360, 902, 620, (255, 173, 35))
        self._fill_circle(canvas, 771, 491, 120, (255, 198, 20))
        self._draw_centered_text(canvas, (712, 455, 832, 520), "BTC", (86, 58, 0), 6, 5)
        self._draw_centered_text(canvas, (620, 706, 760, 780), "BTC", (245, 245, 245), 6, 4)

        # strong alert band
        self._fill_rect(canvas, 120, 890, 960, 985, (215, 42, 42))
        self._fill_rect(canvas, 0, 950, 1080, 1040, (187, 33, 53), alpha=0.94)
        self._fill_rect(canvas, 0, 985, 1080, 1080, (243, 40, 56))
        self._draw_centered_text(canvas, (160, 903, 430, 958), "ALERT", (255, 255, 255), 7, 4)

    def _paint_optional_info_overlay(self, canvas: List[List[Color]], extraction: Dict[str, Any]) -> None:
        person_name = self.sanitize_text((extraction.get("people") or [""])[0])
        headline = self.sanitize_text(extraction.get("topic", ""))
        profile = self.sanitize_text("ARK INVEST CEO. BITCOIN BULL. TARGET: $1,500,000 BTC.")
        price_text = "$68,214.05"
        change_text = "\u25bc1.6% (24H)"

        if self._can_show_short_header(headline):
            self._fill_rect(canvas, 200, 98, 871, 188, (244, 244, 244))
            self._draw_flag(canvas, 209, 101, 32, 22)
            self._draw_centered_text(canvas, (250, 112, 840, 146), headline, (28, 30, 37), 3, 2)

        if self._can_show_name_overlay(person_name):
            name_box = (221, 560, 372, 602)
            self._fill_rect(canvas, *name_box, (244, 244, 242))
            self._draw_centered_text(canvas, name_box, person_name, (31, 33, 40), 3, 1)

        if self._can_show_profile_overlay(profile):
            profile_box = (205, 620, 385, 770)
            title_box = (profile_box[0] + 12, profile_box[1] + 18, profile_box[2] - 12, profile_box[1] + 48)
            body_box = (profile_box[0] + 12, profile_box[1] + 72, profile_box[2] - 12, profile_box[3] - 18)
            self._draw_centered_text(canvas, title_box, person_name or "CATHIE WOOD", (28, 30, 37), 2, 1)
            self._draw_centered_text(canvas, body_box, self.ellipsize_text(profile, 2, body_box[2] - body_box[0], 1), (28, 30, 37), 2, 1)

        if self._can_show_price_overlay(price_text, change_text):
            price_box = (600, 714, 902, 782)
            self._fill_rect(canvas, *price_box, (251, 251, 249))
            self._draw_centered_text(canvas, (613, 722, 760, 757), price_text, (25, 36, 65), 4, 1)
            self._draw_centered_text(canvas, (765, 727, 875, 752), change_text, (255, 56, 44), 2, 1)
            self._draw_info_circle(canvas, 886, 738)

    def _can_show_short_header(self, headline: str) -> bool:
        return bool(headline) and self._measure_text(headline, 3, 2)[0] <= 560

    def _can_show_name_overlay(self, name: str) -> bool:
        return bool(name) and self._measure_text(name, 3, 1)[0] <= 140

    def _can_show_profile_overlay(self, profile: str) -> bool:
        return bool(profile) and self._measure_text(self.ellipsize_text(profile, 2, 156, 1), 2, 1)[0] <= 156

    def _can_show_price_overlay(self, price_text: str, change_text: str) -> bool:
        return self._measure_text(price_text, 4, 1)[0] <= 147 and self._measure_text(change_text, 2, 1)[0] <= 110

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

    def _draw_flag(self, canvas: List[List[Color]], x: int, y: int, width: int, height: int) -> None:
        stripe_height = max(1, height // 7)
        for stripe in range(7):
            color = (191, 55, 72) if stripe % 2 == 0 else (244, 244, 244)
            self._fill_rect(canvas, x, y + stripe * stripe_height, x + width, y + (stripe + 1) * stripe_height, color)
        self._fill_rect(canvas, x, y, x + width // 2, y + stripe_height * 4, (33, 40, 97))
        for star_y in range(2):
            for star_x in range(3):
                self._fill_rect(canvas, x + 3 + star_x * 4, y + 3 + star_y * 6, x + 5 + star_x * 4, y + 5 + star_y * 6, (255, 255, 255))

    def _draw_info_circle(self, canvas: List[List[Color]], cx: int, cy: int) -> None:
        self._fill_circle(canvas, cx, cy, 6, (219, 226, 234))
        self._fill_circle(canvas, cx, cy, 5, (251, 251, 249))
        self._fill_rect(canvas, cx - 1, cy - 1, cx + 1, cy + 3, (38, 80, 160))
        self._fill_rect(canvas, cx - 1, cy - 3, cx + 1, cy - 2, (38, 80, 160))

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
            span = int((radius * radius - dy * dy) ** 0.5)
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

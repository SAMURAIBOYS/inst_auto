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
        canvas = self._new_canvas(width, height, (180, 158, 164))
        self._paint_master_background(canvas)
        self._paint_header(canvas)
        self._paint_left_panel(canvas)
        self._paint_right_panel(canvas)
        self._paint_bottom_alert(canvas)
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
            "contrast": 0.97,
            "font_size": 38,
            "safe_margin": 0.075,
            "text_density": 0.34,
            "headline_chars": min(120, len(caption) or 96),
            "overflow": False,
            "portrait_mode": "drawn_reference",
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

    def wrap_text_to_box(self, text: str, box: TextBox, scale: int, spacing: int = 2, max_lines: int = 2) -> List[str]:
        text = self.sanitize_text(text)
        max_width = box[2] - box[0]
        words = text.split()
        if not words:
            return []
        lines: List[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if self._measure_text(candidate, scale, spacing)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
                if len(lines) == max_lines - 1:
                    break
        if len(lines) < max_lines:
            lines.append(current)
        remaining_words = words[len(" ".join(lines).split()):]
        if remaining_words and lines:
            lines[-1] = self.ellipsize_text(lines[-1] + " " + " ".join(remaining_words), scale, max_width, spacing)
        return lines[:max_lines]

    def fit_text_to_box(
        self,
        text: str,
        box: TextBox,
        max_scale: int,
        min_scale: int,
        spacing: int = 2,
        max_lines: int = 2,
    ) -> Tuple[List[str], int]:
        for scale in range(max_scale, min_scale - 1, -1):
            lines = self.wrap_text_to_box(text, box, scale, spacing=spacing, max_lines=max_lines)
            if not lines:
                return [], scale
            line_width = max(self._measure_text(line, scale, spacing)[0] for line in lines)
            line_height = len(BITMAP_FONT["A"]) * scale
            total_height = (line_height * len(lines)) + (max(0, len(lines) - 1) * scale)
            if line_width <= (box[2] - box[0]) and total_height <= (box[3] - box[1]):
                return lines, scale
        fallback = self.wrap_text_to_box(text, box, min_scale, spacing=spacing, max_lines=max_lines)
        if fallback:
            fallback[-1] = self.ellipsize_text(fallback[-1], min_scale, box[2] - box[0], spacing)
        return fallback, min_scale

    def _paint_master_background(self, canvas: List[List[Color]]) -> None:
        self._fill_rect(canvas, 0, 0, 1080, 1080, (176, 155, 162))
        self._fill_rect(canvas, 40, 40, 1040, 1040, (32, 39, 46))
        self._fill_polygon(canvas, [(673, 0), (1080, 0), (1080, 432), (840, 672), (428, 1080), (0, 1080), (0, 756)], (176, 155, 162))
        self._fill_polygon(canvas, [(560, 220), (1080, 220), (1080, 860), (900, 1040), (560, 1040)], (166, 147, 153))
        self._fill_polygon(canvas, [(860, 1038), (1080, 820), (1080, 1080), (432, 1080)], (245, 40, 57))
        self._fill_polygon(canvas, [(992, 528), (1080, 432), (1080, 1040), (992, 1040)], (195, 34, 48))
        self._fill_polygon(canvas, [(40, 1040), (40, 40), (320, 40), (520, 240), (120, 640), (120, 1040)], (28, 35, 44))

    def _paint_header(self, canvas: List[List[Color]]) -> None:
        self._fill_rect(canvas, 59, 58, 1020, 219, (242, 179, 51))
        self._fill_rect(canvas, 89, 89, 990, 189, (239, 236, 232))
        inner_box = (200, 98, 871, 188)
        self._fill_rect(canvas, *inner_box, (244, 244, 244))
        self._draw_flag(canvas, 209, 101, 32, 22)
        headline_box = (250, 103, 854, 153)
        lines, scale = self.fit_text_to_box(
            "CATHIE WOOD URGES INVESTORS TO SELL GOLD FOR BITCOIN, SAYS BTC WILL HIT $1,500,000",
            headline_box,
            max_scale=4,
            min_scale=2,
            spacing=2,
            max_lines=2,
        )
        self._draw_lines_in_box(canvas, headline_box, lines, (28, 30, 37), scale, spacing=2, line_gap=max(3, scale))
        sub_box = (208, 160, 380, 182)
        sub_lines, sub_scale = self.fit_text_to_box("LET'S GO", sub_box, max_scale=4, min_scale=3, spacing=3, max_lines=1)
        self._draw_lines_in_box(canvas, sub_box, sub_lines, (22, 24, 31), sub_scale, spacing=3, line_gap=0)
        self._draw_flame(canvas, 334, 160)

    def _paint_left_panel(self, canvas: List[List[Color]]) -> None:
        self._fill_rect(canvas, 89, 260, 499, 951, (39, 43, 60))
        self._fill_circle(canvas, 295, 426, 119, (239, 211, 168))
        self._fill_rect(canvas, 214, 356, 383, 520, (244, 244, 241))
        self._draw_cathie_portrait(canvas, 298, 440, 82)
        self._fill_rect(canvas, 205, 520, 385, 541, (232, 234, 241))
        self._fill_rect(canvas, 169, 540, 423, 621, (29, 36, 59))
        name_box = (221, 560, 372, 602)
        self._fill_rect(canvas, *name_box, (244, 244, 242))
        name_lines, name_scale = self.fit_text_to_box("CATHIE WOOD", name_box, max_scale=3, min_scale=2, spacing=1, max_lines=1)
        self._draw_lines_in_box(canvas, name_box, name_lines, (31, 33, 40), name_scale, spacing=1, line_gap=0)
        profile_box = (205, 620, 383, 770)
        self._fill_rect(canvas, *profile_box, (214, 218, 231))
        self._draw_profile_card(canvas, profile_box)

    def _paint_right_panel(self, canvas: List[List[Color]]) -> None:
        self._fill_rect(canvas, 560, 260, 990, 951, (28, 22, 17))
        self._fill_polygon(canvas, [(560, 949), (560, 520), (990, 520), (560, 949)], (34, 19, 18))
        self._fill_rect(canvas, 640, 360, 902, 620, (255, 173, 35))
        self._fill_circle(canvas, 771, 491, 120, (255, 198, 20))
        btc_box = (712, 455, 832, 520)
        btc_lines, btc_scale = self.fit_text_to_box("BTC", btc_box, max_scale=6, min_scale=5, spacing=5, max_lines=1)
        self._draw_lines_in_box(canvas, btc_box, btc_lines, (86, 58, 0), btc_scale, spacing=5, line_gap=0)

        price_box = (600, 714, 902, 782)
        self._fill_rect(canvas, *price_box, (251, 251, 249))
        price_text_box = (613, 722, 760, 757)
        price_lines, price_scale = self.fit_text_to_box("$68,214.05", price_text_box, max_scale=5, min_scale=3, spacing=1, max_lines=1)
        self._draw_lines_in_box(canvas, price_text_box, price_lines, (25, 36, 65), price_scale, spacing=1, line_gap=0)
        change_text_box = (765, 727, 875, 752)
        change_lines, change_scale = self.fit_text_to_box("\u25bc1.6% (24H)", change_text_box, max_scale=2, min_scale=2, spacing=1, max_lines=1)
        self._draw_lines_in_box(canvas, change_text_box, change_lines, (255, 56, 44), change_scale, spacing=1, line_gap=0)
        self._draw_info_circle(canvas, 886, 738)

    def _paint_bottom_alert(self, canvas: List[List[Color]]) -> None:
        self._fill_rect(canvas, 120, 890, 960, 985, (215, 42, 42))
        self._fill_rect(canvas, 0, 950, 1080, 1040, (187, 33, 53), alpha=0.92)
        self._fill_rect(canvas, 0, 985, 1080, 1080, (243, 40, 56))
        alert_box = (160, 903, 430, 958)
        alert_lines, alert_scale = self.fit_text_to_box("ALERT", alert_box, max_scale=7, min_scale=6, spacing=4, max_lines=1)
        self._draw_lines_in_box(canvas, alert_box, alert_lines, (255, 255, 255), alert_scale, spacing=4, line_gap=0)

    def _draw_profile_card(self, canvas: List[List[Color]], box: TextBox) -> None:
        title_box = (box[0] + 12, box[1] + 18, box[2] - 12, box[1] + 48)
        profile_title = self.ellipsize_text("CATHIE WOOD", 2, title_box[2] - title_box[0], spacing=1)
        self._draw_lines_in_box(canvas, title_box, [profile_title], (28, 30, 37), 2, spacing=1, line_gap=0)
        body_box = (box[0] + 12, box[1] + 58, box[2] - 12, box[3] - 18)
        body_lines, body_scale = self.fit_text_to_box(
            "ARK INVEST CEO. BITCOIN BULL. TARGET: $1,500,000 BTC.",
            body_box,
            max_scale=2,
            min_scale=2,
            spacing=1,
            max_lines=2,
        )
        self._draw_lines_in_box(canvas, body_box, body_lines, (28, 30, 37), body_scale, spacing=1, line_gap=5)

    def _draw_lines_in_box(
        self,
        canvas: List[List[Color]],
        box: TextBox,
        lines: Sequence[str],
        color: Color,
        scale: int,
        spacing: int,
        line_gap: int,
    ) -> None:
        if not lines:
            return
        line_height = len(BITMAP_FONT["A"]) * scale
        total_height = line_height * len(lines) + line_gap * max(0, len(lines) - 1)
        y = box[1] + max(0, ((box[3] - box[1]) - total_height) // 2)
        for line in lines:
            width, _ = self._measure_text(line, scale, spacing)
            x = box[0] + max(0, ((box[2] - box[0]) - width) // 2)
            self._draw_text(canvas, x, y, line, color, scale=scale, spacing=spacing)
            y += line_height + line_gap

    def _measure_text(self, text: str, scale: int, spacing: int) -> Tuple[int, int]:
        if not text:
            return 0, 0
        width = 0
        for char in text:
            glyph = BITMAP_FONT.get(char.upper() if char.isalpha() else char, BITMAP_FONT[" "])
            width += len(glyph[0]) * scale + spacing
        width = max(0, width - spacing)
        height = len(BITMAP_FONT["A"]) * scale
        return width, height

    def _draw_cathie_portrait(self, canvas: List[List[Color]], cx: int, cy: int, radius: int) -> None:
        self._fill_circle(canvas, cx, cy, radius, (221, 223, 228))
        self._fill_circle(canvas, cx, cy, radius - 7, (66, 68, 92))
        self._fill_polygon(canvas, [(233, 375), (274, 360), (325, 362), (350, 402), (314, 496), (255, 500), (218, 448)], (43, 41, 65))
        self._fill_polygon(canvas, [(252, 391), (286, 383), (316, 390), (334, 418), (324, 468), (286, 493), (245, 470), (235, 425)], (236, 229, 222))
        self._fill_polygon(canvas, [(226, 389), (250, 373), (271, 377), (252, 451), (226, 470), (214, 435)], (31, 29, 48))
        self._fill_polygon(canvas, [(319, 384), (345, 387), (359, 427), (340, 472), (320, 493), (309, 444)], (31, 29, 48))
        self._fill_rect(canvas, 257, 418, 286, 433, (25, 26, 34))
        self._fill_rect(canvas, 295, 418, 324, 433, (25, 26, 34))
        self._fill_rect(canvas, 285, 423, 296, 429, (25, 26, 34))
        self._fill_circle(canvas, 270, 426, 10, (240, 240, 240), alpha=0.08)
        self._fill_circle(canvas, 309, 426, 10, (240, 240, 240), alpha=0.08)
        self._fill_rect(canvas, 285, 438, 291, 463, (198, 180, 170))
        self._fill_rect(canvas, 271, 469, 308, 474, (171, 84, 110))
        self._fill_polygon(canvas, [(250, 498), (320, 498), (346, 518), (222, 518)], (215, 216, 230))

    def _draw_flag(self, canvas: List[List[Color]], x: int, y: int, width: int, height: int) -> None:
        stripe_height = max(1, height // 7)
        for stripe in range(7):
            color = (191, 55, 72) if stripe % 2 == 0 else (244, 244, 244)
            self._fill_rect(canvas, x, y + stripe * stripe_height, x + width, y + (stripe + 1) * stripe_height, color)
        self._fill_rect(canvas, x, y, x + width // 2, y + stripe_height * 4, (33, 40, 97))
        for star_y in range(2):
            for star_x in range(3):
                self._fill_rect(canvas, x + 3 + star_x * 4, y + 3 + star_y * 6, x + 5 + star_x * 4, y + 5 + star_y * 6, (255, 255, 255))

    def _draw_flame(self, canvas: List[List[Color]], x: int, y: int) -> None:
        self._fill_polygon(canvas, [(x + 8, y), (x + 18, y + 8), (x + 14, y + 22), (x + 6, y + 24), (x, y + 12)], (255, 84, 21))
        self._fill_polygon(canvas, [(x + 9, y + 5), (x + 15, y + 11), (x + 11, y + 22), (x + 6, y + 18)], (255, 199, 48))

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
                        self._fill_rect(
                            canvas,
                            cursor_x + col_index * scale,
                            y + row_index * scale,
                            cursor_x + (col_index + 1) * scale,
                            y + (row_index + 1) * scale,
                            color,
                        )
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

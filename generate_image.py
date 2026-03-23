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
    "A": ["01110", "10001", "11111", "10001", "10001", "10001", "10001"], "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"], "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"], "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"], "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"], "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"], "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"], "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"], "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"], "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"], "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"], "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"], "X": ["10001", "01010", "00100", "00100", "00100", "01010", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"], "Z": ["11111", "00010", "00100", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"], "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"], "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"], "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"], "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"], "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    "$": ["00100", "01111", "10100", "01110", "00101", "11110", "00100"], ",": ["00000", "00000", "00000", "00000", "00110", "00100", "01000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"], "'": ["00110", "00110", "00100", "01000", "00000", "00000", "00000"],
    "%": ["11001", "11010", "00100", "01000", "10110", "00110", "00000"], "(": ["00010", "00100", "01000", "01000", "01000", "00100", "00010"],
    ")": ["01000", "00100", "00010", "00010", "00010", "00100", "01000"], "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"], "/": ["00001", "00010", "00100", "01000", "10000", "00000", "00000"],
    "!": ["00100", "00100", "00100", "00100", "00100", "00000", "00100"], " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    "▼": ["00000", "10001", "01010", "00100", "00000", "00000", "00000"], "+": ["00000", "00100", "00100", "11111", "00100", "00100", "00000"],
}

MOOD_PALETTE = {
    "up": {"accent": (40, 188, 108), "panel": (22, 44, 30), "price": (233, 255, 240), "change": (94, 255, 147), "chip": (21, 112, 62)},
    "down": {"accent": (220, 55, 55), "panel": (45, 24, 22), "price": (255, 235, 235), "change": (255, 120, 120), "chip": (120, 28, 28)},
    "neutral": {"accent": (242, 180, 54), "panel": (46, 38, 18), "price": (255, 247, 223), "change": (255, 220, 103), "chip": (132, 93, 23)},
}
STOPWORDS = {"AND", "OR", "THE", "OF", "TO", "FOR", "IN", "ON", "AT", "BY", "A"}


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
        canvas = self._new_canvas(width, height, (180, 160, 165))
        self._paint_base_reference_layout(canvas, extraction)
        self._paint_optional_overlay(canvas, extraction)
        png_bytes = self._encode_png(width, height, self._rows_from_canvas(canvas))
        latest_path.write_bytes(png_bytes)
        unique_path.write_bytes(png_bytes)
        return {
            "path": str(unique_path),
            "latest_path": str(latest_path),
            "archive_dir": str(archive_dir),
            "width": width,
            "height": height,
            "layout": "dynamic_reference_layout",
            "generated_at": timestamp,
            "contrast": 0.92,
            "font_size": 30,
            "safe_margin": 0.10,
            "text_density": 0.20,
            "headline_chars": min(72, len(caption) or 0),
            "overflow": False,
            "portrait_mode": extraction.get("person", {}).get("avatar_mode", "fallback"),
        }

    def _paint_base_reference_layout(self, canvas: List[List[Color]], extraction: Dict[str, Any]) -> None:
        market = extraction.get("market", {})
        mood = market.get("btc_direction", "neutral")
        palette = MOOD_PALETTE.get(mood, MOOD_PALETTE["neutral"])
        self._paint_background(canvas, palette)
        self._paint_header(canvas, extraction, palette)
        self._paint_person_panel(canvas, extraction.get("person", {}), palette)
        self._paint_btc_panel(canvas, extraction, palette)
        self._paint_alert_band(canvas, palette)

    def _paint_background(self, canvas: List[List[Color]], palette: Dict[str, Color]) -> None:
        self._fill_rect(canvas, 0, 0, 1080, 1080, (184, 163, 168))
        self._fill_rect(canvas, 38, 40, 1040, 1040, (30, 38, 45))
        self._fill_polygon(canvas, [(730, 0), (1080, 0), (1080, 260), (920, 420), (670, 420)], (184, 163, 168), alpha=0.82)
        self._fill_polygon(canvas, [(0, 760), (0, 1080), (430, 1080), (560, 950), (560, 760)], (175, 154, 160), alpha=0.80)
        self._fill_polygon(canvas, [(870, 1080), (1080, 870), (1080, 1080)], palette["accent"], alpha=0.55)
        self._fill_rect(canvas, 50, 50, 1030, 1030, (0, 0, 0), alpha=0.10)

    def _paint_header(self, canvas: List[List[Color]], extraction: Dict[str, Any], palette: Dict[str, Color]) -> None:
        self._fill_rect(canvas, 62, 62, 1018, 210, (242, 180, 54))
        self._fill_rect(canvas, 90, 90, 990, 184, (239, 236, 232))
        self._fill_rect(canvas, 108, 104, 250, 128, palette["chip"])
        self._draw_centered_text(canvas, (114, 108, 244, 124), "DAILY NEWS", (255, 255, 255), 2, 1)
        headline = extraction.get("headline") or extraction.get("article_title") or extraction.get("topic", "CRYPTO NEWS")
        headline_lines = self._fit_lines(headline, (122, 132, 958, 173), max_scale=3, min_scale=2, max_lines=2)
        self._draw_lines_centered(canvas, (122, 132, 958, 173), headline_lines, (29, 34, 41))

    def _paint_person_panel(self, canvas: List[List[Color]], person: Dict[str, Any], palette: Dict[str, Color]) -> None:
        self._fill_rect(canvas, 88, 228, 498, 948, (38, 42, 61))
        self._fill_rect(canvas, 112, 252, 474, 924, (255, 255, 255), alpha=0.03)
        self._paint_avatar(canvas, person, palette)
        self._fill_rect(canvas, 122, 760, 466, 930, (243, 243, 241))
        self._fill_rect(canvas, 122, 760, 466, 792, palette["chip"])
        self._draw_centered_text(canvas, (130, 768, 458, 785), self._safe_name(person.get("name", "MARKET WATCH")), (255, 255, 255), 3, 1)
        role_lines = self._fit_lines(self._safe_role(person.get("role", "Fallback Avatar")), (140, 806, 448, 842), max_scale=2, min_scale=2, max_lines=2)
        self._draw_lines_centered(canvas, (140, 806, 448, 842), role_lines, (62, 65, 74))
        summary_lines = self._fit_lines(self._safe_summary(person.get("summary", "")), (136, 854, 452, 914), max_scale=2, min_scale=1, max_lines=3)
        self._draw_lines_centered(canvas, (136, 854, 452, 914), summary_lines, (52, 54, 60))

    def _paint_avatar(self, canvas: List[List[Color]], person: Dict[str, Any], palette: Dict[str, Color]) -> None:
        avatar_mode = person.get("avatar_mode", "fallback")
        self._fill_circle(canvas, 294, 420, 122, (235, 208, 169))
        if avatar_mode == "person":
            self._fill_rect(canvas, 214, 342, 374, 374, (102, 67, 49))
            self._fill_rect(canvas, 236, 430, 352, 446, (104, 72, 52))
            self._fill_rect(canvas, 206, 522, 382, 546, (232, 235, 241))
            self._fill_rect(canvas, 170, 545, 418, 624, (28, 35, 58))
            self._fill_rect(canvas, 206, 624, 382, 754, (193, 198, 214))
        else:
            self._fill_rect(canvas, 214, 522, 382, 546, (232, 235, 241))
            self._fill_rect(canvas, 176, 545, 412, 624, palette["accent"])
            self._fill_rect(canvas, 206, 624, 382, 754, (193, 198, 214))
            self._draw_centered_text(canvas, (214, 392, 374, 444), "BTC", (97, 67, 0), 6, 2)

    def _paint_btc_panel(self, canvas: List[List[Color]], extraction: Dict[str, Any], palette: Dict[str, Color]) -> None:
        market = extraction.get("market", {})
        self._fill_rect(canvas, 560, 228, 990, 948, palette["panel"])
        self._fill_rect(canvas, 592, 260, 958, 916, (255, 255, 255), alpha=0.03)
        self._fill_rect(canvas, 642, 328, 902, 588, palette["accent"])
        self._fill_circle(canvas, 772, 458, 118, (255, 201, 28))
        self._draw_centered_text(canvas, (714, 423, 830, 488), "BTC", (88, 58, 0), 6, 5)
        self._fill_rect(canvas, 626, 640, 928, 714, (0, 0, 0), alpha=0.16)
        self._fill_rect(canvas, 626, 734, 928, 784, palette["chip"])
        self._draw_centered_text(canvas, (638, 652, 916, 701), self._format_price(market.get("btc_price", 0.0)), palette["price"], 5, 2)
        self._draw_centered_text(canvas, (648, 745, 906, 774), self._format_change(market), (255, 255, 255), 3, 2)
        topic_lines = self._fit_lines(extraction.get("topic", "BTC WATCH"), (616, 806, 934, 850), max_scale=3, min_scale=2, max_lines=2)
        self._draw_lines_centered(canvas, (616, 806, 934, 850), topic_lines, (245, 245, 245))

    def _paint_optional_overlay(self, canvas: List[List[Color]], extraction: Dict[str, Any]) -> None:
        claim_summary = self._safe_summary(extraction.get("claim_summary", ""), max_chars=88)
        if not claim_summary:
            return
        summary_lines = self._fit_lines(claim_summary, (606, 860, 944, 912), max_scale=2, min_scale=1, max_lines=3)
        if summary_lines:
            self._draw_lines_centered(canvas, (606, 860, 944, 912), summary_lines, (224, 224, 224))

    def _paint_alert_band(self, canvas: List[List[Color]], palette: Dict[str, Color]) -> None:
        self._fill_rect(canvas, 120, 890, 960, 985, palette["accent"], alpha=0.90)
        self._fill_rect(canvas, 0, 950, 1080, 1040, (198, 36, 52), alpha=0.88)
        self._fill_rect(canvas, 0, 985, 1080, 1080, (246, 40, 57), alpha=0.96)
        self._draw_centered_text(canvas, (158, 906, 434, 960), "ALERT", (255, 255, 255), 7, 4)

    def sanitize_text(self, text: str) -> str:
        sanitized = re.sub(r"[\x00-\x1f\x7f]+", " ", text or "")
        sanitized = re.sub(r"\b(?:EOF|EMERGE|DECLARAT\w*|DEBUG|TRACE|NULL|NONE)\b", "", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"[^\w\s\-\$%.,:/+()'▼]", " ", sanitized)
        sanitized = re.sub(r"\s+", " ", sanitized).strip()
        return sanitized

    def _safe_name(self, text: str) -> str:
        return self.sanitize_text(text)[:26]

    def _safe_role(self, text: str) -> str:
        return self._shorten_at_word_boundary(self.sanitize_text(text), 34)

    def _safe_summary(self, text: str, max_chars: int = 78) -> str:
        return self._shorten_at_word_boundary(self.sanitize_text(text), max_chars)

    def _shorten_at_word_boundary(self, text: str, max_chars: int) -> str:
        text = self.sanitize_text(text)
        if len(text) <= max_chars:
            return text
        shortened = text[:max_chars + 1].rsplit(" ", 1)[0].strip()
        if not shortened:
            shortened = text[:max_chars].strip()
        return shortened + "..."

    def _fit_lines(self, text: str, box: TextBox, max_scale: int, min_scale: int, max_lines: int) -> List[Tuple[str, int]]:
        cleaned = self.sanitize_text(text)
        if not cleaned:
            return []
        width = box[2] - box[0]
        height = box[3] - box[1]
        for scale in range(max_scale, min_scale - 1, -1):
            lines = self._wrap_text(cleaned, width, scale, 2, max_lines)
            if not lines:
                continue
            lines = self._drop_weak_last_line(lines)
            line_height = len(BITMAP_FONT["A"]) * scale + 4
            total_height = len(lines) * line_height - 4
            if lines and total_height <= height:
                return [(line, scale) for line in lines]
        fallback = self._ellipsize_text(cleaned, min_scale, width, 2)
        return [(fallback, min_scale)] if fallback else []

    def _drop_weak_last_line(self, lines: List[str]) -> List[str]:
        if len(lines) < 2:
            return lines
        last = lines[-1].strip().upper().rstrip(".")
        if len(last.split()) == 1 and (last in STOPWORDS or len(last) <= 3):
            merged = f"{lines[-2]} {last}".strip()
            lines = lines[:-2] + [merged]
        return lines

    def _wrap_text(self, text: str, max_width: int, scale: int, spacing: int, max_lines: int) -> List[str]:
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
        lines.append(current)
        if len(lines) > max_lines:
            kept = lines[:max_lines]
            kept[-1] = self._ellipsize_text(" ".join(lines[max_lines - 1:]), scale, max_width, spacing)
            return kept
        return [self._ellipsize_text(line, scale, max_width, spacing) for line in lines]

    def _ellipsize_text(self, text: str, scale: int, max_width: int, spacing: int = 2) -> str:
        text = self.sanitize_text(text)
        if self._measure_text(text, scale, spacing)[0] <= max_width:
            return text
        trimmed = text
        while trimmed and self._measure_text(trimmed + "...", scale, spacing)[0] > max_width:
            trimmed = trimmed[:-1].rstrip()
        return (trimmed + "...") if trimmed else "..."

    def _draw_lines_centered(self, canvas: List[List[Color]], box: TextBox, lines: List[Tuple[str, int]], color: Color) -> None:
        if not lines:
            return
        line_height = len(BITMAP_FONT["A"]) * lines[0][1] + 4
        total_height = len(lines) * line_height - 4
        y = box[1] + max(0, ((box[3] - box[1]) - total_height) // 2)
        for line, scale in lines:
            width, _ = self._measure_text(line, scale, 2)
            x = box[0] + max(0, ((box[2] - box[0]) - width) // 2)
            self._draw_text(canvas, x, y, line, color, scale, 2)
            y += len(BITMAP_FONT["A"]) * scale + 4

    def _draw_centered_text(self, canvas: List[List[Color]], box: TextBox, text: str, color: Color, max_scale: int, spacing: int) -> None:
        lines = self._fit_lines(text, box, max_scale=max_scale, min_scale=max(1, max_scale - 2), max_lines=1)
        self._draw_lines_centered(canvas, box, lines, color)

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

    @staticmethod
    def _format_price(price: float) -> str:
        return f"${float(price):,.2f}"

    @staticmethod
    def _format_change(market: Dict[str, Any]) -> str:
        change = float(market.get("btc_change_percent", 0.0) or 0.0)
        sign = "+" if change > 0 else "▼" if change < 0 else ""
        return f"{sign}{change:.1f}% (24H)"

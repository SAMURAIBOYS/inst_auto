from __future__ import annotations

import binascii
import html
import json
import re
import struct
import urllib.parse
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

Color = Tuple[int, int, int]
Point = Tuple[int, int]
TextBox = Tuple[int, int, int, int]
PixelGrid = List[List[Tuple[int, int, int, int]]]

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
    "X": ["10001", "01010", "00100", "00100", "00100", "01010", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00010", "00100", "00100", "01000", "10000", "11111"],
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
    "+": ["00000", "00100", "00100", "11111", "00100", "00100", "00000"],
    "?": ["01110", "10001", "00010", "00100", "00100", "00000", "00100"],
    # JP glyphs (8x8 stylized)
    "今": ["11111111", "00010000", "11111111", "00010000", "00111000", "01010100", "10010010", "00000000"],
    "日": ["11111110", "10000010", "10111010", "10101010", "10111010", "10000010", "11111110", "00000000"],
    "注": ["00100000", "11111110", "00100000", "00111100", "00100000", "00100000", "11111110", "00000000"],
    "目": ["11111110", "10000010", "11111110", "10000010", "11111110", "10000010", "11111110", "00000000"],
    "市": ["11111110", "00100000", "11111110", "00100000", "01111100", "00101000", "00101000", "00000000"],
    "場": ["10010000", "11111110", "10010000", "01111100", "01010100", "01111100", "01000100", "00000000"],
    "人": ["00010000", "00100000", "01000000", "10010000", "00010000", "00010000", "00010000", "00000000"],
    "物": ["01001000", "11111110", "01001000", "01111100", "01010000", "01111100", "01010010", "00000000"],
    "不": ["11111110", "00100000", "00111100", "00100000", "01010000", "10001000", "00000110", "00000000"],
    "明": ["11101110", "10101010", "11101110", "00111000", "01010100", "10010010", "11111110", "00000000"],
    "動": ["01001000", "11111110", "01001000", "01111100", "01010100", "11111110", "00101000", "00000000"],
    "向": ["11111110", "10000010", "10011010", "10011010", "10011010", "10000010", "11111110", "00000000"],
    "監": ["11111110", "10101010", "11111110", "00111000", "00101000", "11111110", "00111000", "00000000"],
    "視": ["01001000", "11111110", "01001000", "01111100", "01000100", "11111110", "00010000", "00000000"],
    "中": ["00100000", "11111110", "10111010", "10111010", "10111010", "11111110", "00100000", "00000000"],
    "速": ["01001000", "11111110", "01010000", "01111100", "01000100", "11101110", "00010000", "00000000"],
    "報": ["01001000", "11111110", "01001000", "01111100", "01010100", "11111110", "01010100", "00000000"],
    "意": ["11111110", "00100000", "11111110", "00000000", "11111110", "10010010", "01101100", "00000000"],

    "キ": ["11111110", "00100000", "11111110", "00100000", "00111100", "00100010", "01000010", "00000000"],
    "ョ": ["11111100", "00000100", "11111100", "00000100", "11111100", "00000000", "00000000", "00000000"],
    "ウ": ["01111100", "00010000", "00000000", "01111100", "00000100", "00000100", "01111000", "00000000"],
    "チ": ["11111110", "00100000", "00100000", "11111110", "00100000", "00100000", "00100000", "00000000"],
    "ュ": ["00000000", "00000000", "11111100", "00000100", "00111100", "01000100", "00111100", "00000000"],
    "モ": ["01111110", "00010000", "01111110", "00010000", "00010000", "10010000", "01100000", "00000000"],
    "ク": ["01111100", "00000100", "00001000", "00010000", "00100000", "01000010", "10000010", "00000000"],
    "ソ": ["10000010", "01000100", "00101000", "00010000", "00101000", "01000100", "10000010", "00000000"],
    "ホ": ["00100000", "00100000", "11111110", "00100000", "01111100", "10101010", "00100000", "00000000"],
    "イ": ["00010000", "00100000", "01000000", "00100000", "00100000", "00100000", "00100000", "00000000"],
    "シ": ["10000000", "01000000", "00100000", "00010000", "00001000", "00000100", "11111000", "00000000"],
    "ジ": ["10001000", "01000100", "00100010", "00010100", "00001000", "00000100", "11111000", "00000000"],
    "カ": ["00010000", "11111110", "00010010", "00010100", "00011000", "00110100", "11000010", "00000000"],
    "ン": ["10000000", "01000000", "00100000", "00010000", "00001000", "00000100", "11111000", "00000000"],
}

MOOD_PALETTE = {
    "up": {"accent": (40, 188, 108), "panel": (22, 44, 30), "price": (233, 255, 240), "change": (94, 255, 147), "chip": (21, 112, 62)},
    "down": {"accent": (220, 55, 55), "panel": (45, 24, 22), "price": (255, 235, 235), "change": (255, 120, 120), "chip": (120, 28, 28)},
    "neutral": {"accent": (242, 180, 54), "panel": (46, 38, 18), "price": (255, 247, 223), "change": (255, 220, 103), "chip": (132, 93, 23)},
}

STOPWORDS = {"AND", "OR", "THE", "OF", "TO", "FOR", "IN", "ON", "AT", "BY", "A", "AN", "WITH", "FROM", "AS", "IS", "ARE", "WILL", "ABOUT"}
BAD_TOKENS = {"EOF", "EMERGE", "DECLARAT", "DEBUG", "TRACE", "NULL", "NONE", "HREF", "HTTP", "HTTPS", "TARGET", "BLANK", "FONT", "COLOR", "OC"}
WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"


class ImageGenerator:
    def __init__(self, output_dir: str | Path = "output", archive_root: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if archive_root is None:
            archive_root = self.output_dir.parent / "archive" if self.output_dir.name == "output" else self.output_dir / "archive"
        self.archive_root = Path(archive_root)
        self.archive_root.mkdir(parents=True, exist_ok=True)
        self.avatar_cache_dir = self.archive_root / "avatar_cache"
        self.avatar_cache_dir.mkdir(parents=True, exist_ok=True)

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
            "text_density": 0.18,
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
        self._fill_polygon(canvas, [(740, 0), (1080, 0), (1080, 250), (930, 395), (705, 395)], (184, 163, 168), alpha=0.70)
        self._fill_polygon(canvas, [(0, 760), (0, 1080), (430, 1080), (560, 950), (560, 790)], (176, 155, 161), alpha=0.68)
        self._fill_polygon(canvas, [(900, 1080), (1080, 900), (1080, 1080)], palette["accent"], alpha=0.40)
        self._fill_rect(canvas, 50, 50, 1030, 1030, (0, 0, 0), alpha=0.08)

    def _paint_header(self, canvas: List[List[Color]], extraction: Dict[str, Any], palette: Dict[str, Color]) -> None:
        self._fill_rect(canvas, 62, 62, 1018, 220, (242, 180, 54))
        self._fill_rect(canvas, 90, 90, 990, 188, (239, 236, 232))
        self._fill_rect(canvas, 108, 104, 248, 130, palette["chip"])
        self._draw_centered_text(canvas, (116, 108, 240, 126), "キョウ チュウモク", (255, 255, 255), 2, 1)
        lines = self._fit_lines(self._display_headline(extraction), (122, 138, 958, 178), max_scale=3, min_scale=2, max_lines=2)
        self._draw_lines_centered(canvas, (122, 138, 958, 178), lines, (29, 34, 41))

    def _paint_person_panel(self, canvas: List[List[Color]], person: Dict[str, Any], palette: Dict[str, Color]) -> None:
        self._fill_rect(canvas, 88, 228, 498, 948, (38, 42, 61))
        self._fill_rect(canvas, 112, 252, 474, 924, (255, 255, 255), alpha=0.03)
        self._paint_avatar(canvas, person, palette)
        self._fill_rect(canvas, 122, 760, 466, 928, (243, 243, 241))
        self._fill_rect(canvas, 122, 760, 466, 794, palette["chip"])
        self._draw_centered_text(canvas, (130, 768, 458, 788), self._safe_name(person.get("name", "市場監視")), (255, 255, 255), 3, 1)
        role_lines = self._fit_lines(self._display_role(person), (140, 810, 448, 846), max_scale=2, min_scale=2, max_lines=2)
        self._draw_lines_centered(canvas, (140, 810, 448, 846), role_lines, (62, 65, 74))
        summary_lines = self._fit_lines(self._display_summary(person), (136, 858, 452, 910), max_scale=2, min_scale=1, max_lines=3)
        self._draw_lines_centered(canvas, (136, 858, 452, 910), summary_lines, (52, 54, 60))

    def _paint_avatar(self, canvas: List[List[Color]], person: Dict[str, Any], palette: Dict[str, Color]) -> None:
        photo = self._load_person_photo(person)
        if photo is not None:
            self._blit_photo_circle(canvas, photo, 204, 300, 180)
            self._fill_rect(canvas, 206, 522, 382, 546, (232, 235, 241))
            self._fill_rect(canvas, 170, 545, 418, 624, (28, 35, 58))
            self._fill_rect(canvas, 206, 624, 382, 754, (193, 198, 214))
            return
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
        self._fill_rect(canvas, 626, 736, 928, 788, palette["chip"])
        self._draw_centered_text(canvas, (638, 652, 916, 701), self._format_price(market.get("btc_price", 0.0)), palette["price"], 5, 2)
        self._draw_centered_text(canvas, (648, 747, 906, 778), self._format_change(market), (255, 255, 255), 3, 2)
        topic_lines = self._fit_lines(self._display_topic(extraction), (616, 812, 934, 846), max_scale=3, min_scale=2, max_lines=2)
        self._draw_lines_centered(canvas, (616, 812, 934, 846), topic_lines, (245, 245, 245))

    def _paint_optional_overlay(self, canvas: List[List[Color]], extraction: Dict[str, Any]) -> None:
        claim_summary = self._display_claim_summary(extraction.get("claim_summary", ""))
        if not claim_summary:
            return
        lines = self._fit_lines(claim_summary, (606, 864, 944, 902), max_scale=2, min_scale=1, max_lines=2)
        if lines:
            self._draw_lines_centered(canvas, (606, 864, 944, 902), lines, (224, 224, 224))

    def _paint_alert_band(self, canvas: List[List[Color]], palette: Dict[str, Color]) -> None:
        self._fill_rect(canvas, 0, 950, 1080, 1038, (198, 36, 52), alpha=0.90)
        self._fill_rect(canvas, 0, 988, 1080, 1080, (246, 40, 57), alpha=0.95)
        self._fill_rect(canvas, 0, 950, 1080, 976, palette["accent"], alpha=0.35)
        ticker = "カイ シグナル ソクホウ チュウモク カイ シグナル ソクホウ チュウモク"
        self._draw_ticker(canvas, (20, 958, 1060, 1028), ticker, (255, 255, 255), 3, 2, offset=42)

    def sanitize_text(self, text: str) -> str:
        raw = html.unescape(text or "")
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = re.sub(r"https?://\S+", " ", raw)
        raw = re.sub(r"www\.\S+", " ", raw)
        raw = re.sub(r"&[a-zA-Z0-9#]+;", " ", raw)
        raw = re.sub(r"[\x00-\x1f\x7f]+", " ", raw)
        raw = re.sub(r"\b(?:HREF|HTTP|HTTPS|TARGET|BLANK|FONT|COLOR|CLASS|STYLE|REL|IMG|SRC|OC)\b", " ", raw, flags=re.IGNORECASE)
        for token in BAD_TOKENS:
            raw = re.sub(rf"\b{re.escape(token)}\w*\b", " ", raw, flags=re.IGNORECASE)
        raw = raw.replace("—", "-").replace("–", "-")
        raw = re.sub(r"\s+", " ", raw).strip()
        return raw.upper()

    def _display_headline(self, extraction: Dict[str, Any]) -> str:
        headline_ja = extraction.get("headline_ja") or extraction.get("headline") or extraction.get("article_title") or ""
        if headline_ja:
            return self._shorten_at_word_boundary(self.sanitize_text(headline_ja), 44)
        person_name = self._safe_name(extraction.get("person", {}).get("name", ""))
        topic = self._display_topic(extraction)
        base = self._shorten_at_word_boundary(self.sanitize_text(extraction.get("article_title") or ""), 36)
        if person_name and person_name not in {"市場監視", "MARKET WATCH", "MARKET WATCH"}:
            return f"{person_name} {topic}"[:48]
        if base:
            return f"{base} {topic}"[:48]
        return topic[:48]

    def _display_role(self, person: Dict[str, Any]) -> str:
        role = person.get("role", "")
        if role:
            return self._shorten_at_word_boundary(self.sanitize_text(role), 24)
        if person.get("avatar_mode") == "person":
            return "チュウモク ジンブツ"
        return "シジョウ カイセツ"

    def _display_summary(self, person: Dict[str, Any]) -> str:
        summary = person.get("summary", "")
        if summary:
            return self._shorten_at_word_boundary(self.sanitize_text(summary), 32)
        if person.get("avatar_mode") == "person":
            name = self._safe_name(person.get("name", ""))
            return self._shorten_at_word_boundary(f"{name} BTC キョウキ", 28)
        return "BTC シジョウ カンシ"

    def _display_topic(self, extraction: Dict[str, Any]) -> str:
        topic = extraction.get("topic") or ""
        if topic:
            return self._shorten_at_word_boundary(self.sanitize_text(topic), 24)
        coins = extraction.get("coins") or []
        if coins:
            return f"{str(coins[0]).upper()} チュウモク"
        return "BTC チュウモク"

    def _display_claim_summary(self, text: str) -> str:
        cleaned = self._shorten_at_word_boundary(self.sanitize_text(text), 32)
        if not cleaned:
            return ""
        return f"BTC シジョウ {cleaned}"[:40]

    def _safe_name(self, text: str) -> str:
        text = (text or "").strip()
        return text[:26] if text else "シジョウ カンシ"

    def _shorten_at_word_boundary(self, text: str, max_chars: int) -> str:
        text = self.sanitize_text(text)
        if len(text) <= max_chars:
            return text
        shortened = text[: max_chars + 1].rsplit(" ", 1)[0].strip()
        if not shortened:
            shortened = text[:max_chars].strip()
        return shortened + "..."

    def _fit_lines(self, text: str, box: TextBox, max_scale: int, min_scale: int, max_lines: int) -> List[Tuple[str, int]]:
        cleaned = text.strip()
        if not cleaned:
            return []
        width = box[2] - box[0]
        height = box[3] - box[1]
        for scale in range(max_scale, min_scale - 1, -1):
            lines = self._wrap_text(cleaned, width, scale, 2, max_lines)
            if not lines:
                continue
            lines = self._drop_weak_last_line(lines)
            line_height = self._line_height(scale)
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
            return lines[:-2] + [merged]
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
        if self._measure_text(text, scale, spacing)[0] <= max_width:
            return text
        trimmed = text
        while trimmed and self._measure_text(trimmed + "...", scale, spacing)[0] > max_width:
            trimmed = trimmed[:-1].rstrip()
        return (trimmed + "...") if trimmed else "..."

    def _draw_lines_centered(self, canvas: List[List[Color]], box: TextBox, lines: List[Tuple[str, int]], color: Color) -> None:
        if not lines:
            return
        line_height = self._line_height(lines[0][1])
        total_height = len(lines) * line_height - 4
        y = box[1] + max(0, ((box[3] - box[1]) - total_height) // 2)
        for line, scale in lines:
            width, _ = self._measure_text(line, scale, 2)
            x = box[0] + max(0, ((box[2] - box[0]) - width) // 2)
            self._draw_text(canvas, x, y, line, color, scale, 2)
            y += self._line_height(scale)

    def _draw_ticker(self, canvas: List[List[Color]], box: TextBox, text: str, color: Color, scale: int, spacing: int, offset: int) -> None:
        phrase_width, _ = self._measure_text(text, scale, spacing)
        x = box[0] - offset
        while x < box[2]:
            self._draw_text(canvas, x, box[1], text, color, scale, spacing, clip_box=box)
            x += phrase_width + 36

    def _draw_centered_text(self, canvas: List[List[Color]], box: TextBox, text: str, color: Color, max_scale: int, spacing: int) -> None:
        lines = self._fit_lines(text, box, max_scale=max_scale, min_scale=max(1, max_scale - 2), max_lines=1)
        self._draw_lines_centered(canvas, box, lines, color)

    def _line_height(self, scale: int) -> int:
        return 8 * scale + 4

    def _measure_text(self, text: str, scale: int, spacing: int) -> Tuple[int, int]:
        if not text:
            return 0, 0
        width = 0
        max_height = 0
        for char in text:
            glyph = self._glyph_for(char)
            width += len(glyph[0]) * scale + spacing
            max_height = max(max_height, len(glyph) * scale)
        return max(0, width - spacing), max_height

    def _glyph_for(self, char: str) -> Sequence[str]:
        key = char.upper() if char.isalpha() and ord(char) < 128 else char
        return BITMAP_FONT.get(key, BITMAP_FONT["?"])

    def _draw_text(self, canvas: List[List[Color]], x: int, y: int, text: str, color: Color, scale: int = 4, spacing: int = 2, clip_box: TextBox | None = None) -> None:
        cursor_x = x
        for char in text:
            pattern = self._glyph_for(char)
            for row_index, row in enumerate(pattern):
                for col_index, bit in enumerate(row):
                    if bit == "1":
                        x1 = cursor_x + col_index * scale
                        y1 = y + row_index * scale
                        x2 = cursor_x + (col_index + 1) * scale
                        y2 = y + (row_index + 1) * scale
                        if clip_box and (x2 <= clip_box[0] or x1 >= clip_box[2] or y2 <= clip_box[1] or y1 >= clip_box[3]):
                            continue
                        self._fill_rect(canvas, x1, y1, x2, y2, color)
            cursor_x += len(pattern[0]) * scale + spacing

    def _load_person_photo(self, person: Dict[str, Any]) -> PixelGrid | None:
        if person.get("avatar_mode") != "person" or not person.get("name"):
            return None
        safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", person.get("name", ""))
        cached = self.avatar_cache_dir / f"{safe_name}.png"
        if cached.exists():
            try:
                return self._decode_png_rgba(cached.read_bytes())
            except Exception:
                cached.unlink(missing_ok=True)
        try:
            summary_url = WIKI_SUMMARY_URL.format(title=urllib.parse.quote(person["name"].replace(" ", "_")))
            with urllib.request.urlopen(summary_url, timeout=6) as response:
                payload = json.loads(response.read().decode("utf-8"))
            thumb = ((payload.get("thumbnail") or {}).get("source") or "")
            if not thumb.lower().endswith(".png"):
                return None
            with urllib.request.urlopen(thumb, timeout=6) as response:
                data = response.read()
            cached.write_bytes(data)
            return self._decode_png_rgba(data)
        except Exception:
            return None

    def _blit_photo_circle(self, canvas: List[List[Color]], photo: PixelGrid, x: int, y: int, size: int) -> None:
        small = self._resize_nearest_rgba(photo, 36, 36)
        pixelated = self._resize_nearest_rgba(small, size, size)
        radius = size // 2
        cx = x + radius
        cy = y + radius
        for py in range(size):
            for px in range(size):
                dx = px - radius
                dy = py - radius
                if dx * dx + dy * dy > radius * radius:
                    continue
                r, g, b, a = pixelated[py][px]
                if a == 0:
                    continue
                canvas[y + py][x + px] = self._blend(canvas[y + py][x + px], (r, g, b), a / 255.0)

    def _resize_nearest_rgba(self, src: PixelGrid, width: int, height: int) -> PixelGrid:
        src_h = len(src)
        src_w = len(src[0]) if src else 0
        if not src_w or not src_h:
            return [[(0, 0, 0, 0) for _ in range(width)] for _ in range(height)]
        out: PixelGrid = []
        for y in range(height):
            sy = min(src_h - 1, int(y * src_h / height))
            row = []
            for x in range(width):
                sx = min(src_w - 1, int(x * src_w / width))
                row.append(src[sy][sx])
            out.append(row)
        return out

    def _decode_png_rgba(self, data: bytes) -> PixelGrid:
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("not png")
        pos = 8
        width = height = 0
        bit_depth = color_type = interlace = 0
        idat = b""
        while pos < len(data):
            length = int.from_bytes(data[pos:pos + 4], "big")
            pos += 4
            chunk_type = data[pos:pos + 4]
            pos += 4
            chunk = data[pos:pos + length]
            pos += length + 4
            if chunk_type == b"IHDR":
                width = int.from_bytes(chunk[0:4], "big")
                height = int.from_bytes(chunk[4:8], "big")
                bit_depth = chunk[8]
                color_type = chunk[9]
                interlace = chunk[12]
            elif chunk_type == b"IDAT":
                idat += chunk
            elif chunk_type == b"IEND":
                break
        if bit_depth != 8 or interlace != 0 or color_type not in (2, 6):
            raise ValueError("unsupported png")
        channels = 4 if color_type == 6 else 3
        row_size = width * channels
        raw = zlib.decompress(idat)
        rows: List[bytes] = []
        prev = bytearray(row_size)
        idx = 0
        for _ in range(height):
            filter_type = raw[idx]
            idx += 1
            scan = bytearray(raw[idx:idx + row_size])
            idx += row_size
            self._unfilter_png_scanline(scan, prev, filter_type, channels)
            rows.append(bytes(scan))
            prev = scan
        image: PixelGrid = []
        for row in rows:
            pixels: List[Tuple[int, int, int, int]] = []
            for i in range(0, len(row), channels):
                if channels == 4:
                    pixels.append((row[i], row[i + 1], row[i + 2], row[i + 3]))
                else:
                    pixels.append((row[i], row[i + 1], row[i + 2], 255))
            image.append(pixels)
        return image

    def _unfilter_png_scanline(self, scan: bytearray, prev: bytearray, filter_type: int, bpp: int) -> None:
        if filter_type == 0:
            return
        for i in range(len(scan)):
            left = scan[i - bpp] if i >= bpp else 0
            up = prev[i] if prev else 0
            up_left = prev[i - bpp] if prev and i >= bpp else 0
            if filter_type == 1:
                scan[i] = (scan[i] + left) & 0xFF
            elif filter_type == 2:
                scan[i] = (scan[i] + up) & 0xFF
            elif filter_type == 3:
                scan[i] = (scan[i] + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                scan[i] = (scan[i] + self._paeth(left, up, up_left)) & 0xFF
            else:
                raise ValueError("unsupported filter")

    @staticmethod
    def _paeth(a: int, b: int, c: int) -> int:
        p = a + b - c
        pa = abs(p - a)
        pb = abs(p - b)
        pc = abs(p - c)
        if pa <= pb and pa <= pc:
            return a
        if pb <= pc:
            return b
        return c

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

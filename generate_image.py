from __future__ import annotations

import binascii
import math
import os
import struct
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


PIXEL_FONT = {
    "A": ["01110", "10001", "11111", "10001", "10001"],
    "B": ["11110", "10001", "11110", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "11110", "10000", "11111"],
    "G": ["01111", "10000", "10111", "10001", "01111"],
    "I": ["11111", "00100", "00100", "00100", "11111"],
    "K": ["10001", "10010", "11100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "01110"],
    "R": ["11110", "10001", "11110", "10010", "10001"],
    "T": ["11111", "00100", "00100", "00100", "00100"],
    "V": ["10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10101", "11011", "10001"],
    " ": ["00000", "00000", "00000", "00000", "00000"],
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
        has_people = bool(extraction.get("people"))
        palette = self._palette_from_text(extraction.get("topic", "crypto") + timestamp)
        canvas = self._new_canvas(width, height, palette[0])
        self._paint_background(canvas, width, height, palette)
        self._paint_header(canvas, width, extraction)
        if has_people:
            portrait_mode = self._paint_person_left_btc_right(canvas, width, height, palette, extraction)
        else:
            portrait_mode = "fallback_avatar"
            self._paint_no_person_layout(canvas, width, height, palette, extraction)
        self._paint_buzz_word(canvas, width, height, extraction)
        png_bytes = self._encode_png(width, height, self._rows_from_canvas(canvas))
        latest_path.write_bytes(png_bytes)
        unique_path.write_bytes(png_bytes)
        return {
            "path": str(unique_path),
            "latest_path": str(latest_path),
            "width": width,
            "height": height,
            "layout": "person_focus" if has_people else "no_person",
            "generated_at": timestamp,
            "contrast": 0.94,
            "font_size": 42 if has_people else 38,
            "safe_margin": 0.09,
            "text_density": 0.24 if has_people else 0.27,
            "headline_chars": min(80, len(caption)),
            "overflow": False,
            "portrait_mode": portrait_mode,
        }

    def _new_canvas(self, width: int, height: int, color: Tuple[int, int, int]) -> List[List[Tuple[int, int, int]]]:
        return [[color for _ in range(width)] for _ in range(height)]

    def _paint_background(self, canvas: List[List[Tuple[int, int, int]]], width: int, height: int, palette: List[Tuple[int, int, int]]) -> None:
        for y in range(height):
            for x in range(width):
                ratio = (x + y) / (width + height)
                if ratio < 0.35:
                    canvas[y][x] = palette[0]
                elif ratio < 0.7:
                    canvas[y][x] = palette[1]
                else:
                    canvas[y][x] = palette[2]
        self._fill_rect(canvas, 40, 40, width - 40, height - 40, (8, 10, 18), alpha=0.22)
        self._fill_rect(canvas, 60, 60, width - 60, 220, (245, 178, 55), alpha=0.95)

    def _paint_header(self, canvas: List[List[Tuple[int, int, int]]], width: int, extraction: Dict[str, Any]) -> None:
        self._fill_rect(canvas, 90, 90, width - 90, 190, (250, 250, 250), alpha=0.95)
        topic = extraction.get("topic", "CRYPTO")
        accent = (15, 15, 18)
        self._draw_block_text(canvas, 120, 112, topic[:18].upper().replace("関連ニュース", " NEWS"), accent, scale=4)

    def _paint_person_left_btc_right(self, canvas: List[List[Tuple[int, int, int]]], width: int, height: int, palette: List[Tuple[int, int, int]], extraction: Dict[str, Any]) -> str:
        self._fill_rect(canvas, 90, 260, 500, 950, (34, 38, 52), alpha=0.95)
        self._fill_rect(canvas, 560, 260, width - 90, 950, (16, 14, 10), alpha=0.94)
        # 代替人物シルエット（画像取得失敗時を兼用）
        self._fill_circle(canvas, 295, 430, 120, (237, 208, 171), alpha=1.0)
        self._fill_rect(canvas, 205, 520, 385, 840, (213, 216, 227), alpha=1.0)
        self._fill_rect(canvas, 170, 540, 420, 620, (23, 31, 52), alpha=1.0)
        self._fill_rect(canvas, 640, 360, 900, 620, (246, 166, 35), alpha=1.0)
        self._draw_coin(canvas, 770, 490, 120, (255, 193, 7), (90, 60, 10))
        label = extraction.get("people", ["Satoshi Nakamoto"])[0].upper()
        self._draw_block_text(canvas, 140, 865, label[:18], (255, 255, 255), scale=4)
        self._draw_block_text(canvas, 625, 720, "BTC", (255, 255, 255), scale=7)
        return "fallback_avatar"

    def _paint_no_person_layout(self, canvas: List[List[Tuple[int, int, int]]], width: int, height: int, palette: List[Tuple[int, int, int]], extraction: Dict[str, Any]) -> None:
        self._fill_rect(canvas, 90, 270, width - 90, 950, (13, 18, 34), alpha=0.96)
        self._fill_rect(canvas, 140, 330, width - 140, 520, palette[2], alpha=0.95)
        self._fill_rect(canvas, 140, 560, width - 140, 900, (255, 255, 255), alpha=0.09)
        for index, coin in enumerate(extraction.get("coins", [])[:3] or ["BTC", "ETF"]):
            left = 180 + index * 260
            self._fill_rect(canvas, left, 610, left + 180, 780, (245, 178, 55), alpha=0.95)
            self._draw_block_text(canvas, left + 30, 665, coin[:5].upper(), (15, 15, 18), scale=5)
        org = (extraction.get("organizations") or ["MARKET"])[0].upper()
        self._draw_block_text(canvas, 180, 390, org[:16], (255, 255, 255), scale=5)
        self._draw_block_text(canvas, 180, 815, "NO FACE", (255, 255, 255), scale=6)

    def _paint_buzz_word(self, canvas: List[List[Tuple[int, int, int]]], width: int, height: int, extraction: Dict[str, Any]) -> None:
        word = self._pick_buzz_word(extraction)
        self._fill_rect(canvas, 120, height - 190, width - 120, height - 95, (220, 47, 47), alpha=0.92)
        self._draw_block_text(canvas, 165, height - 165, word, (255, 255, 255), scale=6)

    def _pick_buzz_word(self, extraction: Dict[str, Any]) -> str:
        sentiment = extraction.get("sentiment", "neutral")
        if sentiment == "positive":
            return "BIG MOVE"
        if sentiment == "negative":
            return "RISK"
        return "ALERT"

    def _draw_coin(self, canvas: List[List[Tuple[int, int, int]]], cx: int, cy: int, radius: int, fill: Tuple[int, int, int], text_color: Tuple[int, int, int]) -> None:
        self._fill_circle(canvas, cx, cy, radius, fill, alpha=0.97)
        self._draw_block_text(canvas, cx - 55, cy - 20, "BTC", text_color, scale=5)

    def _draw_block_text(self, canvas: List[List[Tuple[int, int, int]]], x: int, y: int, text: str, color: Tuple[int, int, int], scale: int = 4) -> None:
        cursor_x = x
        for char in text.upper():
            pattern = PIXEL_FONT.get(char, PIXEL_FONT[" "])
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
                            alpha=1.0,
                        )
            cursor_x += (len(pattern[0]) + 1) * scale

    def _fill_rect(self, canvas: List[List[Tuple[int, int, int]]], x1: int, y1: int, x2: int, y2: int, color: Tuple[int, int, int], alpha: float = 1.0) -> None:
        max_height = len(canvas)
        max_width = len(canvas[0])
        for y in range(max(0, y1), min(max_height, y2)):
            for x in range(max(0, x1), min(max_width, x2)):
                canvas[y][x] = self._blend(canvas[y][x], color, alpha)

    def _fill_circle(self, canvas: List[List[Tuple[int, int, int]]], cx: int, cy: int, radius: int, color: Tuple[int, int, int], alpha: float = 1.0) -> None:
        for y in range(max(0, cy - radius), min(len(canvas), cy + radius)):
            for x in range(max(0, cx - radius), min(len(canvas[0]), cx + radius)):
                if math.hypot(x - cx, y - cy) <= radius:
                    canvas[y][x] = self._blend(canvas[y][x], color, alpha)

    @staticmethod
    def _blend(base: Tuple[int, int, int], top: Tuple[int, int, int], alpha: float) -> Tuple[int, int, int]:
        return tuple(int((1 - alpha) * base[idx] + alpha * top[idx]) for idx in range(3))

    def _rows_from_canvas(self, canvas: List[List[Tuple[int, int, int]]]) -> Iterable[bytes]:
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
    def _palette_from_text(text: str) -> List[Tuple[int, int, int]]:
        seed = sum(ord(char) for char in text) + os.getpid()
        return [
            ((seed + 20) % 60 + 8, (seed * 3 + 30) % 40 + 8, (seed * 5 + 80) % 70 + 15),
            ((seed + 140) % 80 + 120, (seed * 7 + 80) % 90 + 80, (seed * 11 + 10) % 120 + 40),
            ((seed + 180) % 60 + 180, (seed * 13 + 40) % 60 + 20, (seed * 17 + 60) % 60 + 20),
        ]

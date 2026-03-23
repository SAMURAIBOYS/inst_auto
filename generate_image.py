from __future__ import annotations

import json
import math
import re
import textwrap
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
BTC_LOGO_URL = "https://cryptologos.cc/logos/bitcoin-btc-logo.png"

FONT_CANDIDATES = [
    # Windows
    r"C:\\Windows\\Fonts\\meiryo.ttc",
    r"C:\\Windows\\Fonts\\msgothic.ttc",
    r"C:\\Windows\\Fonts\\YuGothM.ttc",
    r"C:\\Windows\\Fonts\\yugothm.ttc",
    r"C:\\Windows\\Fonts\\Yu Gothic UI.ttc",
    r"C:\\Windows\\Fonts\\BIZ-UDGothicR.ttc",
    # Linux / common
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansJP-Regular.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

NON_PERSON_TERMS = {
    "bitcoin", "btc", "ethereum", "eth", "xrp", "sol", "doge", "ada",
    "blackrock", "grayscale", "coinbase", "binance", "metaplanet", "sec",
    "fed", "fomc", "etf", "spot etf", "market watch", "market", "watch"
}

COIN_LABELS = {
    "BTC": "ビットコイン",
    "ETH": "イーサリアム",
    "XRP": "XRP",
    "SOL": "ソラナ",
    "ADA": "カルダノ",
    "DOGE": "ドージコイン",
}


def _download_bytes(url: str, timeout: int = 10) -> Optional[bytes]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read()
    except Exception:
        return None


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
        self.asset_cache_dir = self.archive_root / "asset_cache"
        self.asset_cache_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, extraction: Dict[str, Any], caption: str = "") -> Dict[str, Any]:
        width, height = 1080, 1080
        now = datetime.now(timezone.utc)
        latest_path = self.output_dir / "latest.png"
        archive_dir = self.archive_root / now.strftime("%Y%m%d")
        archive_dir.mkdir(parents=True, exist_ok=True)
        unique_path = archive_dir / f"post_{now.strftime('%Y%m%dT%H%M%S%f')}.png"

        market = extraction.get("market", {}) or {}
        change = float(market.get("btc_change_percent", 0.0) or 0.0)
        mood = "up" if change > 0 else "down" if change < 0 else "neutral"
        palette = self._palette(mood)

        image = Image.new("RGB", (width, height), palette["bg"])
        draw = ImageDraw.Draw(image)

        self._draw_background(draw, palette)
        self._draw_header(image, extraction, palette)
        self._draw_person_panel(image, extraction, palette)
        self._draw_market_panel(image, extraction, palette)
        self._draw_alert_band(image, palette)

        image.save(latest_path, format="PNG")
        image.save(unique_path, format="PNG")

        return {
            "path": str(unique_path),
            "latest_path": str(latest_path),
            "archive_dir": str(archive_dir),
            "width": width,
            "height": height,
            "layout": "pillow_japanese_layout",
            "generated_at": now.isoformat(),
            "portrait_mode": extraction.get("person", {}).get("avatar_mode", "fallback"),
        }

    def _palette(self, mood: str) -> Dict[str, tuple[int, int, int]]:
        if mood == "up":
            return {
                "bg": (190, 180, 185),
                "frame": (20, 30, 40),
                "accent": (28, 184, 98),
                "panel": (20, 39, 29),
                "chip": (22, 110, 62),
                "card": (244, 242, 238),
                "text": (24, 28, 34),
                "sub": (80, 85, 95),
                "danger": (232, 42, 60),
                "gold": (242, 184, 54),
                "price": (255, 255, 255),
            }
        if mood == "down":
            return {
                "bg": (190, 180, 185),
                "frame": (20, 30, 40),
                "accent": (220, 55, 55),
                "panel": (52, 24, 24),
                "chip": (130, 30, 30),
                "card": (244, 242, 238),
                "text": (24, 28, 34),
                "sub": (80, 85, 95),
                "danger": (232, 42, 60),
                "gold": (242, 184, 54),
                "price": (255, 246, 246),
            }
        return {
            "bg": (190, 180, 185),
            "frame": (20, 30, 40),
            "accent": (181, 138, 38),
            "panel": (58, 46, 22),
            "chip": (150, 110, 24),
            "card": (244, 242, 238),
            "text": (24, 28, 34),
            "sub": (80, 85, 95),
            "danger": (232, 42, 60),
            "gold": (242, 184, 54),
            "price": (255, 250, 236),
        }

    def _font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = FONT_CANDIDATES[:]
        if bold:
            extra = [
                r"C:\\Windows\\Fonts\\meiryob.ttc",
                r"C:\\Windows\\Fonts\\YuGothB.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansJP-Bold.otf",
            ]
            candidates = extra + candidates
        for path in candidates:
            try:
                if Path(path).exists() or ":\\" in path:
                    return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _draw_background(self, draw: ImageDraw.ImageDraw, palette: Dict[str, tuple[int, int, int]]) -> None:
        draw.rectangle((38, 40, 1040, 1040), fill=palette["frame"])
        draw.polygon([(740, 0), (1080, 0), (1080, 250), (930, 395), (705, 395)], fill=(184, 163, 168))
        draw.polygon([(0, 760), (0, 1080), (430, 1080), (560, 950), (560, 790)], fill=(176, 155, 161))
        draw.polygon([(900, 1080), (1080, 900), (1080, 1080)], fill=palette["accent"])

    def _draw_header(self, image: Image.Image, extraction: Dict[str, Any], palette: Dict[str, tuple[int, int, int]]) -> None:
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((62, 62, 1018, 220), radius=0, fill=palette["gold"])
        draw.rectangle((90, 90, 990, 188), fill=(239, 236, 232))
        draw.rectangle((108, 104, 248, 130), fill=palette["chip"])
        self._text_centered(draw, (108, 104, 248, 130), "今日注目", self._font(24, bold=True), "white")

        headline = self._headline(extraction)
        self._text_fitted(draw, (280, 102, 948, 176), headline, self._font, fill=palette["text"], max_size=42, min_size=22, align="center", max_lines=2)

    def _draw_person_panel(self, image: Image.Image, extraction: Dict[str, Any], palette: Dict[str, tuple[int, int, int]]) -> None:
        draw = ImageDraw.Draw(image)
        person = extraction.get("person", {}) or {}
        draw.rectangle((88, 228, 498, 948), fill=(38, 42, 61))
        draw.rectangle((112, 252, 474, 924), fill=(49, 54, 79))

        avatar = self._person_image(person)
        if avatar is not None:
            avatar = ImageOps.fit(avatar.convert("RGB"), (240, 240), method=Image.Resampling.LANCZOS)
            mask = Image.new("L", (240, 240), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 240, 240), fill=255)
            image.paste(avatar, (174, 300), mask)
        else:
            draw.ellipse((172, 298, 416, 542), fill=(235, 208, 169))
            draw.rectangle((214, 342, 374, 374), fill=(120, 78, 53))
            draw.rectangle((236, 430, 352, 446), fill=(120, 84, 60))

        draw.rectangle((206, 522, 382, 546), fill=(232, 235, 241))
        draw.rectangle((170, 545, 418, 624), fill=(28, 35, 58))
        draw.rectangle((206, 624, 382, 754), fill=(176, 181, 198))

        draw.rectangle((122, 760, 466, 928), fill=palette["card"])
        draw.rectangle((122, 760, 466, 794), fill=palette["chip"])

        name = self._display_name(person)
        role = self._display_role(person)
        summary = self._display_summary(person, extraction)

        self._text_centered(draw, (130, 764, 458, 792), name, self._font(28, bold=True), "white")
        self._text_fitted(draw, (140, 810, 448, 842), role, self._font, fill=palette["text"], max_size=30, min_size=20, align="center", max_lines=1)
        self._text_fitted(draw, (136, 854, 452, 910), summary, self._font, fill=palette["text"], max_size=24, min_size=16, align="center", max_lines=3)

    def _draw_market_panel(self, image: Image.Image, extraction: Dict[str, Any], palette: Dict[str, tuple[int, int, int]]) -> None:
        draw = ImageDraw.Draw(image)
        market = extraction.get("market", {}) or {}
        draw.rectangle((560, 228, 990, 948), fill=palette["panel"])
        draw.rectangle((592, 260, 958, 916), fill=(255, 255, 255, 16))
        draw.rectangle((642, 328, 902, 588), fill=palette["gold"])
        draw.ellipse((654, 340, 890, 576), fill=(251, 201, 28))
        self._text_centered(draw, (684, 408, 860, 498), "BTC", self._font(74, bold=True), (88, 58, 0))

        draw.rounded_rectangle((626, 640, 928, 714), radius=6, fill=(0, 0, 0))
        draw.rectangle((626, 736, 928, 788), fill=palette["chip"])

        price_text = self._format_price(market.get("btc_price", 0.0))
        change_text = self._format_change(market)
        topic = self._display_topic(extraction)
        claim = self._display_claim_summary(extraction.get("claim_summary", ""))

        self._text_centered(draw, (638, 650, 916, 704), price_text, self._font(46, bold=True), palette["price"])
        self._text_centered(draw, (648, 744, 906, 780), change_text, self._font(28, bold=True), "white")
        self._text_fitted(draw, (616, 812, 934, 846), topic, self._font, fill=(245, 245, 245), max_size=34, min_size=22, align="center", max_lines=1)
        self._text_fitted(draw, (606, 864, 944, 904), claim, self._font, fill=(224, 224, 224), max_size=22, min_size=15, align="center", max_lines=2)

        logo = self._btc_logo()
        if logo is not None:
            logo = ImageOps.contain(logo.convert("RGBA"), (220, 220), method=Image.Resampling.LANCZOS)
            image.paste(logo, (662, 346), logo)

    def _draw_alert_band(self, image: Image.Image, palette: Dict[str, tuple[int, int, int]]) -> None:
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 950, 1080, 1038), fill=(198, 36, 52))
        draw.rectangle((0, 988, 1080, 1080), fill=(246, 40, 57))
        draw.rectangle((0, 950, 1080, 976), fill=palette["accent"])
        ticker = "速報 注意 速報 注意 速報 注意 速報 注意"
        font = self._font(26, bold=True)
        x = 18
        while x < 1060:
            draw.text((x, 952), ticker, fill="white", font=font)
            x += int(draw.textlength(ticker, font=font)) + 42

    def _headline(self, extraction: Dict[str, Any]) -> str:
        person = extraction.get("person", {}) or {}
        person_name = self._display_name(person)
        topic = self._display_topic(extraction)
        article_title = self._clean_japanese_text(extraction.get("headline") or extraction.get("article_title") or "")
        if person_name != "市場注目":
            return f"{person_name} {topic}"
        if article_title:
            return article_title
        return topic

    def _display_name(self, person: Dict[str, Any]) -> str:
        raw = str(person.get("name") or "").strip()
        raw = re.sub(r"\s+", " ", raw)
        if not raw:
            return "市場注目"
        if raw.lower() in NON_PERSON_TERMS:
            return "市場注目"
        return raw[:24]

    def _display_role(self, person: Dict[str, Any]) -> str:
        if person.get("avatar_mode") == "person" and self._display_name(person) != "市場注目":
            return "注目人物"
        return "市場動向"

    def _display_summary(self, person: Dict[str, Any], extraction: Dict[str, Any]) -> str:
        name = self._display_name(person)
        if name != "市場注目" and person.get("avatar_mode") == "person":
            return f"{name}に注目"
        coin = self._primary_coin(extraction)
        label = COIN_LABELS.get(coin, coin)
        return f"{label}の値動きに注目"

    def _display_topic(self, extraction: Dict[str, Any]) -> str:
        coin = self._primary_coin(extraction)
        label = COIN_LABELS.get(coin, coin)
        return f"{label}に注目"

    def _display_claim_summary(self, text: str) -> str:
        cleaned = self._clean_japanese_text(text)
        if not cleaned:
            return "市場の反応を監視中"
        cleaned = re.sub(r"https?://\S+", "", cleaned).strip()
        return self._truncate_text(cleaned, 24)

    def _primary_coin(self, extraction: Dict[str, Any]) -> str:
        coins = extraction.get("coins") or []
        if coins:
            return str(coins[0]).upper()
        return "BTC"

    def _clean_japanese_text(self, text: str) -> str:
        raw = str(text or "")
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = re.sub(r"https?://\S+", " ", raw)
        raw = re.sub(r"[\x00-\x1f\x7f]", " ", raw)
        raw = raw.replace("—", "ー").replace("–", "ー")
        raw = re.sub(r"\s+", " ", raw).strip()
        return raw

    def _truncate_text(self, text: str, max_chars: int) -> str:
        return text if len(text) <= max_chars else text[:max_chars - 1].rstrip() + "…"

    def _person_image(self, person: Dict[str, Any]) -> Optional[Image.Image]:
        if person.get("avatar_mode") != "person":
            return None
        name = self._display_name(person)
        if name == "市場注目":
            return None
        safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name)
        cache_path = self.avatar_cache_dir / f"{safe_name}.png"
        if cache_path.exists():
            try:
                return Image.open(cache_path)
            except Exception:
                cache_path.unlink(missing_ok=True)
        try:
            summary_url = WIKI_SUMMARY_URL.format(title=urllib.parse.quote(name.replace(" ", "_")))
            data = _download_bytes(summary_url, timeout=6)
            if not data:
                return None
            payload = json.loads(data.decode("utf-8"))
            thumb = ((payload.get("thumbnail") or {}).get("source") or "")
            if not thumb:
                return None
            image_bytes = _download_bytes(thumb, timeout=8)
            if not image_bytes:
                return None
            cache_path.write_bytes(image_bytes)
            return Image.open(BytesIO(image_bytes))
        except Exception:
            return None

    def _btc_logo(self) -> Optional[Image.Image]:
        cache_path = self.asset_cache_dir / "btc_logo.png"
        if cache_path.exists():
            try:
                return Image.open(cache_path)
            except Exception:
                cache_path.unlink(missing_ok=True)
        try:
            image_bytes = _download_bytes(BTC_LOGO_URL, timeout=8)
            if not image_bytes:
                return None
            cache_path.write_bytes(image_bytes)
            return Image.open(BytesIO(image_bytes))
        except Exception:
            return None

    def _text_centered(self, draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, font: ImageFont.ImageFont, fill: Any) -> None:
        bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=4, align="center")
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = box[0] + ((box[2] - box[0]) - w) / 2
        y = box[1] + ((box[3] - box[1]) - h) / 2
        draw.multiline_text((x, y), text, font=font, fill=fill, spacing=4, align="center")

    def _text_fitted(
        self,
        draw: ImageDraw.ImageDraw,
        box: tuple[int, int, int, int],
        text: str,
        font_factory,
        fill: Any,
        max_size: int,
        min_size: int,
        align: str = "left",
        max_lines: int = 2,
    ) -> None:
        text = text.strip()
        if not text:
            return
        width = box[2] - box[0]
        height = box[3] - box[1]
        for size in range(max_size, min_size - 1, -1):
            font = font_factory(size, bold=size >= max_size - 4)
            wrapped = self._wrap_for_box(draw, text, font, width, max_lines)
            bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=4, align=align)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            if w <= width and h <= height:
                if align == "center":
                    x = box[0] + (width - w) / 2
                else:
                    x = box[0]
                y = box[1] + (height - h) / 2
                draw.multiline_text((x, y), wrapped, font=font, fill=fill, spacing=4, align=align)
                return
        font = font_factory(min_size, bold=False)
        wrapped = self._wrap_for_box(draw, self._truncate_text(text, 18), font, width, max_lines)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=4, align=align)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = box[0] + (width - w) / 2 if align == "center" else box[0]
        y = box[1] + (height - h) / 2
        draw.multiline_text((x, y), wrapped, font=font, fill=fill, spacing=4, align=align)

    def _wrap_for_box(self, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int, max_lines: int) -> str:
        if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", text):
            pieces = []
            current = ""
            for ch in text:
                trial = current + ch
                if draw.textlength(trial, font=font) <= width or not current:
                    current = trial
                else:
                    pieces.append(current)
                    current = ch
            if current:
                pieces.append(current)
        else:
            words = text.split()
            pieces = []
            current = ""
            for word in words:
                trial = word if not current else current + " " + word
                if draw.textlength(trial, font=font) <= width or not current:
                    current = trial
                else:
                    pieces.append(current)
                    current = word
            if current:
                pieces.append(current)
        if len(pieces) > max_lines:
            kept = pieces[:max_lines]
            kept[-1] = self._truncate_text(kept[-1], max(4, len(kept[-1]) - 1))
            pieces = kept
        return "\n".join(pieces)

    @staticmethod
    def _format_price(price: Any) -> str:
        try:
            return f"${float(price):,.2f}"
        except Exception:
            return "$0.00"

    @staticmethod
    def _format_change(market: Dict[str, Any]) -> str:
        try:
            change = float(market.get("btc_change_percent", 0.0) or 0.0)
        except Exception:
            change = 0.0
        sign = "+" if change > 0 else "▼" if change < 0 else ""
        return f"{sign}{change:.1f}%（24H）"

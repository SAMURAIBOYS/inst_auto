from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence, Tuple


STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "he", "in", "is", "it", "its", "of", "on", "that", "the", "to", "was",
    "were", "will", "with", "about", "into", "after", "before", "their", "them",
}


@dataclass
class ScoreBreakdown:
    person_accuracy: float
    summary_naturalness: float
    source_alignment: float
    image_readability: float
    layout_intact: int
    total_score: float
    diagnostics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "person_accuracy": self.person_accuracy,
            "summary_naturalness": self.summary_naturalness,
            "source_alignment": self.source_alignment,
            "image_readability": self.image_readability,
            "layout_intact": self.layout_intact,
            "total_score": self.total_score,
            "diagnostics": self.diagnostics,
        }


class ScoringEngine:
    """Heuristic evaluator for autonomous content iteration.

    The implementation is intentionally model-free so it can run unattended.
    Replace or augment these heuristics with external evaluators if needed.
    """

    def score(self, source: Dict[str, Any], candidate: Dict[str, Any]) -> ScoreBreakdown:
        extracted_people = candidate.get("people", [])
        expected_people = source.get("people", [])
        text = candidate.get("caption", "")
        summary = candidate.get("summary", "")
        image = candidate.get("image", {})

        person_accuracy, person_diag = self._score_person_accuracy(expected_people, extracted_people)
        naturalness, natural_diag = self._score_summary_naturalness(summary or text)
        alignment, align_diag = self._score_source_alignment(source, candidate)
        readability, readability_diag = self._score_image_readability(image)
        layout_intact, layout_diag = self._detect_layout_break(image)

        total_score = self._weighted_total(
            person_accuracy=person_accuracy,
            summary_naturalness=naturalness,
            source_alignment=alignment,
            image_readability=readability,
            layout_intact=layout_intact,
        )

        diagnostics = {
            "person": person_diag,
            "naturalness": natural_diag,
            "alignment": align_diag,
            "readability": readability_diag,
            "layout": layout_diag,
        }
        return ScoreBreakdown(
            person_accuracy=person_accuracy,
            summary_naturalness=naturalness,
            source_alignment=alignment,
            image_readability=readability,
            layout_intact=layout_intact,
            total_score=total_score,
            diagnostics=diagnostics,
        )

    def _score_person_accuracy(self, expected: Sequence[str], predicted: Sequence[str]) -> Tuple[float, Dict[str, Any]]:
        expected_norm = {self._normalize_name(name) for name in expected if name}
        predicted_norm = {self._normalize_name(name) for name in predicted if name}
        if not expected_norm and not predicted_norm:
            return 1.0, {"matched": [], "missing": [], "extra": []}
        if not expected_norm:
            return 0.0, {"matched": [], "missing": [], "extra": sorted(predicted_norm)}

        matches = expected_norm & predicted_norm
        precision = len(matches) / len(predicted_norm) if predicted_norm else 0.0
        recall = len(matches) / len(expected_norm)
        score = 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)
        return round(score, 4), {
            "matched": sorted(matches),
            "missing": sorted(expected_norm - predicted_norm),
            "extra": sorted(predicted_norm - expected_norm),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
        }

    def _score_summary_naturalness(self, text: str) -> Tuple[float, Dict[str, Any]]:
        tokens = self._tokens(text)
        if not tokens:
            return 0.0, {"reason": "empty_text"}
        sentence_count = max(1, len(re.findall(r"[.!?。！？]", text)) or 1)
        unique_ratio = len(set(tokens)) / len(tokens)
        avg_sentence_length = len(tokens) / sentence_count
        punctuation_balance = 1.0 if text.count("(") == text.count(")") else 0.6
        repeated_penalty = 0.0
        for idx in range(len(tokens) - 2):
            if tokens[idx] == tokens[idx + 1] == tokens[idx + 2]:
                repeated_penalty += 0.12
        sentence_length_score = max(0.0, 1 - abs(avg_sentence_length - 18) / 25)
        base = (0.4 * unique_ratio) + (0.4 * sentence_length_score) + (0.2 * punctuation_balance)
        score = max(0.0, min(1.0, base - repeated_penalty))
        return round(score, 4), {
            "token_count": len(tokens),
            "unique_ratio": round(unique_ratio, 4),
            "avg_sentence_length": round(avg_sentence_length, 4),
            "punctuation_balance": punctuation_balance,
            "repeated_penalty": round(repeated_penalty, 4),
        }

    def _score_source_alignment(self, source: Dict[str, Any], candidate: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        source_tokens = set(self._meaningful_tokens(" ".join([
            source.get("title", ""),
            source.get("summary", ""),
            " ".join(source.get("people", [])),
            " ".join(source.get("keywords", [])),
        ])))
        candidate_tokens = set(self._meaningful_tokens(" ".join([
            candidate.get("caption", ""),
            candidate.get("summary", ""),
            " ".join(candidate.get("people", [])),
        ])))
        if not source_tokens or not candidate_tokens:
            return 0.0, {"overlap": [], "source_size": len(source_tokens), "candidate_size": len(candidate_tokens)}
        overlap = source_tokens & candidate_tokens
        union = source_tokens | candidate_tokens
        jaccard = len(overlap) / len(union)
        coverage = len(overlap) / len(source_tokens)
        score = min(1.0, (0.45 * jaccard) + (0.55 * coverage))
        return round(score, 4), {
            "overlap": sorted(list(overlap))[:20],
            "source_size": len(source_tokens),
            "candidate_size": len(candidate_tokens),
            "jaccard": round(jaccard, 4),
            "coverage": round(coverage, 4),
        }

    def _score_image_readability(self, image: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
        width = max(1, int(image.get("width", 1)))
        height = max(1, int(image.get("height", 1)))
        font_size = max(1, int(image.get("font_size", 1)))
        contrast = float(image.get("contrast", 0.0))
        text_density = float(image.get("text_density", 0.0))
        headline_chars = int(image.get("headline_chars", 0))

        aspect_ratio = width / height
        aspect_score = max(0.0, 1 - abs(aspect_ratio - 1.0) / 1.5)
        font_score = max(0.0, min(1.0, font_size / 28))
        contrast_score = max(0.0, min(1.0, contrast))
        density_score = max(0.0, 1 - abs(text_density - 0.35) / 0.35)
        headline_score = max(0.0, 1 - max(0, headline_chars - 80) / 120)

        score = (0.2 * aspect_score) + (0.25 * font_score) + (0.25 * contrast_score) + (0.2 * density_score) + (0.1 * headline_score)
        return round(max(0.0, min(1.0, score)), 4), {
            "aspect_ratio": round(aspect_ratio, 4),
            "aspect_score": round(aspect_score, 4),
            "font_score": round(font_score, 4),
            "contrast_score": round(contrast_score, 4),
            "density_score": round(density_score, 4),
            "headline_score": round(headline_score, 4),
        }

    def _detect_layout_break(self, image: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        width = max(1, int(image.get("width", 1)))
        height = max(1, int(image.get("height", 1)))
        text_density = float(image.get("text_density", 0.0))
        overflow = bool(image.get("overflow", False))
        safe_margin = float(image.get("safe_margin", 0.0))
        too_small = width < 512 or height < 512
        broken = overflow or too_small or text_density > 0.7 or safe_margin < 0.03
        return (0 if broken else 1), {
            "overflow": overflow,
            "too_small": too_small,
            "text_density": text_density,
            "safe_margin": safe_margin,
        }

    @staticmethod
    def _weighted_total(**scores: float) -> float:
        total = (
            0.28 * scores["person_accuracy"]
            + 0.22 * scores["summary_naturalness"]
            + 0.25 * scores["source_alignment"]
            + 0.15 * scores["image_readability"]
            + 0.10 * scores["layout_intact"]
        )
        return round(total, 4)

    @staticmethod
    def _normalize_name(name: str) -> str:
        return re.sub(r"\s+", " ", name.strip().lower())

    @staticmethod
    def _tokens(text: str) -> List[str]:
        return re.findall(r"[A-Za-zÀ-ÿ0-9_'-]+", text.lower())

    def _meaningful_tokens(self, text: str) -> Iterable[str]:
        for token in self._tokens(text):
            if len(token) <= 2 or token in STOPWORDS:
                continue
            yield token

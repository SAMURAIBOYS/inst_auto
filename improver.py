from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Tuple


class ImprovementEngine:
    """Applies feedback-driven prompt and parameter changes without retraining models."""

    def improve(
        self,
        config: Dict[str, Any],
        score: Dict[str, Any],
        history: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[str]]:
        updated = deepcopy(config)
        changes: List[str] = []
        diagnostics = score.get("diagnostics", {})

        if score["total_score"] < updated["thresholds"]["retry_score"]:
            updated["prompt_template"] += "\n- Tighten factual grounding and avoid unsupported claims."
            changes.append("overall score below threshold -> tightened factual grounding prompt")

        if score["image_readability"] < updated["thresholds"]["image_readability"]:
            layout = updated["layout"]
            layout["font_size"] = min(layout["font_size"] + 4, 36)
            layout["contrast"] = min(layout["contrast"] + 0.15, 1.0)
            layout["text_density_target"] = max(layout["text_density_target"] - 0.05, 0.2)
            layout["safe_margin"] = min(layout["safe_margin"] + 0.02, 0.18)
            changes.append("image quality low -> boosted font size, contrast, and margins")

        if score["person_accuracy"] < updated["thresholds"]["person_accuracy"]:
            extraction = updated["extraction"]
            extraction["use_fallback"] = True
            extraction["capitalized_name_bias"] = min(extraction["capitalized_name_bias"] + 0.15, 1.0)
            updated["prompt_template"] += "\n- Explicitly mention every detected person by full name if present in source."
            changes.append("person extraction weak -> enabled fallback extractor and stronger person prompt")

        if score["layout_intact"] == 0:
            layout = updated["layout"]
            layout["canvas_width"] = max(layout["canvas_width"], 1080)
            layout["canvas_height"] = max(layout["canvas_height"], 1080)
            layout["text_density_target"] = max(0.18, layout["text_density_target"] - 0.08)
            layout["safe_margin"] = min(layout["safe_margin"] + 0.04, 0.2)
            changes.append("layout break detected -> enlarged canvas and reduced density")

        if score["source_alignment"] < updated["thresholds"]["source_alignment"]:
            keywords = diagnostics.get("alignment", {}).get("overlap", [])
            if keywords:
                updated["prompt_template"] += "\n- Preserve core source terms: " + ", ".join(keywords[:6])
            else:
                updated["prompt_template"] += "\n- Re-anchor summary on title, people, and source keywords."
            changes.append("source alignment low -> injected anchor keywords into prompt")

        if not changes and history:
            updated["prompt_template"] += "\n- Keep current strategy but make phrasing more concise and visually balanced."
            changes.append("no critical issue -> applied mild prompt refinement")

        updated["meta"] = {
            "improvement_count": updated.get("meta", {}).get("improvement_count", 0) + 1,
            "last_changes": changes,
        }
        return updated, changes

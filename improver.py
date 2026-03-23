from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


class ImprovementEngine:
    def __init__(self, best_result_path: str | Path) -> None:
        self.best_result_path = Path(best_result_path)

    def improve(self, extraction: Dict[str, Any], score: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        improved = json.loads(json.dumps(extraction, ensure_ascii=False))
        changes: List[str] = []
        diagnostics = score.get("diagnostics", {})
        previous_best = self._load_previous_best()

        if score.get("change_score", 0.0) < 0.35:
            improved["image_hint"] += " 短期変動が弱いので『ALERT』訴求を強める。"
            changes.append("change_score low -> buzz word strengthened")

        if score.get("topic_score", 0.0) < 0.45 and previous_best.get("extraction", {}).get("coins"):
            previous_coins = previous_best["extraction"].get("coins", [])[:1]
            for coin in previous_coins:
                if coin not in improved.get("coins", []):
                    improved.setdefault("coins", []).append(coin)
                    changes.append(f"topic_score low -> reused prior high-performing coin context: {coin}")

        previous_people = previous_best.get("extraction", {}).get("people", [])
        if score.get("people_score", 0.0) < 0.7 and improved.get("people") and previous_people:
            lead = previous_people[0]
            if lead not in improved.get("people", []):
                improved.setdefault("people", []).append(lead)
                changes.append(f"people_score low -> appended prior corroborating person: {lead}")
        elif score.get("people_score", 0.0) < 0.7 and not improved.get("people"):
            improved["image_hint"] += " 人物不在のため、人物画像は使わず市場レイアウトを維持する。"
            changes.append("people_score low -> preserved no-person layout to avoid false face selection")

        if diagnostics.get("topic", {}).get("coin_count", 0) >= 2:
            improved["image_hint"] += " 複数コイン比較を視覚で出す。"
            changes.append("multi-coin topic -> highlight comparison cards")

        if not changes:
            improved["image_hint"] += " 現状の勝ち筋を維持しつつ余白を増やす。"
            changes.append("stable score -> minor visual polish")
        return improved, changes

    def _load_previous_best(self) -> Dict[str, Any]:
        if not self.best_result_path.exists():
            return {}
        try:
            with self.best_result_path.open("r", encoding="utf-8") as fp:
                payload = json.load(fp)
            result = payload.get("result", payload)
            if isinstance(result, dict):
                return result
        except Exception:  # noqa: BLE001
            return {}
        return {}

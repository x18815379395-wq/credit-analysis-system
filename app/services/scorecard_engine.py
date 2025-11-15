from __future__ import annotations

from typing import Any, Dict


class ScorecardEngine:
    """Rule-based engine that maps metrics/profile data into a five-dimension score."""

    DIMENSION_CAPS = {
        "industry": 20,
        "character": 20,
        "business": 20,
        "financial": 20,
        "collateral": 20,
    }

    def compute(self, metrics: Dict[str, Any], profile: Dict[str, Any], collateral: Dict[str, Any]) -> Dict[str, Any]:
        dimension_scores = {
            "industry": self._industry_score(profile.get("industry", {})),
            "character": self._character_score(profile.get("company", {}).get("governance", {})),
            "business": self._business_score(profile.get("company", {}).get("business_model", {})),
            "financial": self._financial_score(metrics),
            "collateral": self._collateral_score(collateral, profile.get("company", {}).get("collateral", {})),
        }
        total_score = int(sum(dimension_scores.values()))
        return {
            "dimension_scores": dimension_scores,
            "total_score": total_score,
            "risk_level": self._risk_level(total_score),
        }

    def _industry_score(self, industry: Dict[str, Any]) -> float:
        base = 15.0
        lifecycle = industry.get("lifecycle", "mature")
        risk_level = industry.get("risk_level", "medium")
        if lifecycle == "growth":
            base += 2
        elif lifecycle == "decline":
            base -= 3
        if risk_level == "low":
            base += 3
        elif risk_level == "high":
            base -= 3
        return self._clamp(base, "industry")

    def _character_score(self, governance: Dict[str, Any]) -> float:
        base = 16.0
        if governance.get("negative_records"):
            base -= 5
        experience = governance.get("experience_years") or 0
        if experience >= 10:
            base += 2
        elif experience < 3:
            base -= 1
        transparency = governance.get("transparency", "medium")
        if transparency == "high":
            base += 2
        elif transparency == "low":
            base -= 2
        return self._clamp(base, "character")

    def _business_score(self, business: Dict[str, Any]) -> float:
        base = 15.0
        concentration = business.get("customer_concentration", "medium")
        if concentration == "high":
            base -= 4
        elif concentration == "low":
            base += 2
        payment_terms = business.get("payment_terms", "standard")
        if payment_terms == "long":
            base -= 2
        supply_chain_risk = business.get("supply_chain_risk", "medium")
        if supply_chain_risk == "low":
            base += 1
        elif supply_chain_risk == "high":
            base -= 2
        return self._clamp(base, "business")

    def _financial_score(self, metrics: Dict[str, Any]) -> float:
        base = 15.0
        latest = metrics.get("latest_year", {})
        averages = metrics.get("averages", {})

        leverage = averages.get("asset_liability_ratio") or latest.get("asset_liability_ratio")
        margin = averages.get("gross_margin") or latest.get("gross_margin")
        cash_conversion = averages.get("cash_conversion_cycle")
        ocf_vs_profit = averages.get("ocf_vs_profit")

        if leverage is not None:
            if leverage < 0.6:
                base += 3
            elif leverage > 0.8:
                base -= 4
        if margin is not None:
            if margin >= 0.35:
                base += 2
            elif margin < 0.15:
                base -= 3
        if cash_conversion and cash_conversion > 120:
            base -= 2
        if ocf_vs_profit is not None and ocf_vs_profit < 0.8:
            base -= 2
        interest_coverage = averages.get("interest_coverage") or latest.get("interest_coverage")
        if interest_coverage is not None and interest_coverage < 2:
            base -= 2
        return self._clamp(base, "financial")

    def _collateral_score(self, collateral: Dict[str, Any], profile_collateral: Dict[str, Any]) -> float:
        base = 12.0
        has_collateral = collateral.get("has_collateral") or profile_collateral.get("type") is not None
        if has_collateral:
            liquidity = profile_collateral.get("liquidity") or collateral.get("liquidity", "medium")
            coverage = collateral.get("coverage_ratio")
            base = 16.0
            if liquidity == "high":
                base += 2
            if coverage and coverage >= 1.1:
                base += 2
        else:
            base -= 2
        return self._clamp(base, "collateral")

    def _clamp(self, value: float, dimension: str) -> float:
        cap = self.DIMENSION_CAPS[dimension]
        return max(0.0, min(float(cap), round(value, 2)))

    @staticmethod
    def _risk_level(total_score: int) -> str:
        if total_score >= 85:
            return "A"
        if total_score >= 70:
            return "B"
        if total_score >= 55:
            return "C"
        return "D"

from __future__ import annotations

from statistics import mean
from typing import Any, Dict, List, Optional


class FinancialMetricsService:
    """Calculate profitability, leverage, efficiency, and cash flow indicators."""

    def compute(self, statements: List[Dict[str, Any]]) -> Dict[str, Any]:
        ordered = sorted(statements, key=lambda item: item["year"])
        per_year: List[Dict[str, Any]] = []

        for statement in ordered:
            income = statement.get("income_statement", {})
            balance = statement.get("balance_sheet", {})
            cashflow = statement.get("cashflow_statement", {})

            revenue = self._value(income, "revenue", "operating_income")
            cogs = self._value(income, "cost_of_goods_sold", "cogs")
            gross_profit = self._value(income, "gross_profit")
            net_income = self._value(income, "net_income", "profit")
            ebit = self._value(income, "ebit", "operating_profit")
            interest_expense = self._value(income, "interest_expense")

            total_assets = self._value(balance, "total_assets")
            total_liabilities = self._value(balance, "total_liabilities")
            equity = self._value(balance, "total_equity")
            interest_bearing_debt = self._value(balance, "interest_bearing_debt", "short_term_debt", "long_term_debt")

            receivables = self._value(balance, "accounts_receivable")
            inventory = self._value(balance, "inventory")
            payables = self._value(balance, "accounts_payable")

            ocf = self._value(cashflow, "operating_cash_flow")

            entry = {
                "year": statement["year"],
                "revenue": revenue,
                "net_income": net_income,
                "gross_margin": self._ratio(gross_profit, revenue),
                "net_margin": self._ratio(net_income, revenue),
                "asset_liability_ratio": self._ratio(total_liabilities, total_assets),
                "debt_to_equity": self._ratio(total_liabilities, equity),
                "interest_coverage": self._ratio(ebit, interest_expense) if interest_expense else None,
                "operating_cash_flow": ocf,
                "ocf_vs_profit": self._ratio(ocf, net_income),
                "turnover_days": {
                    "dso": self._turnover_days(receivables, revenue),
                    "dio": self._turnover_days(inventory, cogs),
                    "dpo": self._turnover_days(payables, cogs),
                },
            }
            entry["cash_conversion_cycle"] = self._cash_conversion_cycle(entry["turnover_days"])
            entry["interest_bearing_debt"] = interest_bearing_debt
            per_year.append(entry)

        return {
            "years": per_year,
            "averages": self._averages(per_year),
            "growth": self._growth(per_year),
            "latest_year": per_year[-1] if per_year else {},
        }

    @staticmethod
    def _value(source: Dict[str, Any], *candidates: str) -> Optional[float]:
        for key in candidates:
            if key in source and source[key] not in (None, "", {}):
                try:
                    return float(source[key])
                except (TypeError, ValueError):
                    continue
        return None

    @staticmethod
    def _ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
        if numerator is None or denominator in (None, 0):
            return None
        return round(numerator / denominator, 4)

    @staticmethod
    def _turnover_days(balance_value: Optional[float], flow_value: Optional[float]) -> Optional[float]:
        if balance_value is None or flow_value in (None, 0):
            return None
        return round((balance_value / flow_value) * 365, 2)

    @staticmethod
    def _cash_conversion_cycle(turnover: Dict[str, Optional[float]]) -> Optional[float]:
        dso = turnover.get("dso") or 0
        dio = turnover.get("dio") or 0
        dpo = turnover.get("dpo") or 0
        if not any(turnover.values()):
            return None
        return round(dso + dio - dpo, 2)

    @staticmethod
    def _growth(per_year: List[Dict[str, Any]]) -> Dict[str, Any]:
        if len(per_year) < 2:
            return {}
        growth: Dict[str, Any] = {}
        for prev, curr in zip(per_year, per_year[1:]):
            growth[curr["year"]] = {
                "revenue_growth": FinancialMetricsService._ratio(
                    (curr.get("revenue") or 0) - (prev.get("revenue") or 0),
                    prev.get("revenue"),
                ),
                "net_income_growth": FinancialMetricsService._ratio(
                    (curr.get("net_income") or 0) - (prev.get("net_income") or 0),
                    prev.get("net_income"),
                ),
            }
        return growth

    @staticmethod
    def _averages(per_year: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
        def avg(field: str) -> Optional[float]:
            values = [entry.get(field) for entry in per_year if entry.get(field) is not None]
            return round(mean(values), 4) if values else None

        return {
            "gross_margin": avg("gross_margin"),
            "net_margin": avg("net_margin"),
            "asset_liability_ratio": avg("asset_liability_ratio"),
            "interest_coverage": avg("interest_coverage"),
            "cash_conversion_cycle": avg("cash_conversion_cycle"),
            "ocf_vs_profit": avg("ocf_vs_profit"),
        }

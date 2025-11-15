from __future__ import annotations

from typing import Any, Dict


class ReportGenerator:
    """Render Markdown + lightweight HTML reports."""

    def render(
        self,
        *,
        customer: Dict[str, Any],
        web_profile: Dict[str, Any],
        metrics: Dict[str, Any],
        scores: Dict[str, Any],
        industry_text: str,
        financial_text: str,
        risk_summary: str,
    ) -> Dict[str, str]:
        markdown = self._build_markdown(
            customer=customer,
            web_profile=web_profile,
            metrics=metrics,
            scores=scores,
            industry_text=industry_text,
            financial_text=financial_text,
            risk_summary=risk_summary,
        )
        html = self._markdown_to_html(markdown)
        return {"markdown": markdown, "html": html}

    def _build_markdown(self, **sections: Dict[str, Any]) -> str:
        customer = sections["customer"]
        scores = sections["scores"]
        metrics = sections["metrics"]
        latest = metrics.get("latest_year", {})
        dimension_lines = "\n".join(
            f"- {name.title()}: {value:.1f} pts" for name, value in scores.get("dimension_scores", {}).items()
        )

        return (
            "# Credit Analysis Report\n\n"
            "## Customer Overview\n"
            f"- Name: {customer.get('name')}\n"
            f"- Region: {customer.get('region') or 'N/A'}\n"
            f"- Industry Code: {customer.get('industry_code') or 'N/A'}\n"
            f"- Requested By: {customer.get('requested_by') or 'Not provided'}\n\n"
            "## Industry & Environment\n"
            f"{sections['industry_text']}\n\n"
            "## Financial Highlights\n"
            f"{sections['financial_text']}\n\n"
            "### Latest Ratios\n"
            f"- Revenue: {latest.get('revenue', 'n/a')}\n"
            f"- Net Margin: {latest.get('net_margin', 'n/a')}\n"
            f"- Leverage: {latest.get('asset_liability_ratio', 'n/a')}\n"
            f"- Cash Conversion Cycle: {latest.get('cash_conversion_cycle', 'n/a')}\n\n"
            "## Scores & Risk Summary\n"
            f"- Total Score: {scores.get('total_score')}\n"
            f"- Risk Level: {scores.get('risk_level')}\n"
            f"{dimension_lines}\n\n"
            f"{sections['risk_summary']}\n"
        )

    def _markdown_to_html(self, markdown: str) -> str:
        html_lines = []
        for line in markdown.splitlines():
            stripped = line.strip()
            if stripped.startswith("### "):
                html_lines.append(f"<h3>{stripped[4:]}</h3>")
            elif stripped.startswith("## "):
                html_lines.append(f"<h2>{stripped[3:]}</h2>")
            elif stripped.startswith("# "):
                html_lines.append(f"<h1>{stripped[2:]}</h1>")
            elif stripped.startswith("- "):
                html_lines.append(f"<p>{stripped}</p>")
            elif stripped:
                html_lines.append(f"<p>{stripped}</p>")
        return "\n".join(html_lines)

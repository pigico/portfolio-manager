"""AI Reasoning Engine — Claude qualitative analysis layer.

Calls Claude API for qualitative override of quantitative scores.
Rules:
- Max override: ±20 points
- Every override MUST be logged with rationale
- Auto-disable after 5 consecutive bad overrides for 7 days
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from loguru import logger


class ReasoningEngine:
    """Call Claude API for qualitative analysis of market events.

    Triggered by: earnings releases, Fed statements, regulatory news,
    black swan events, or significant score changes.
    """

    MAX_OVERRIDE = 20.0

    def __init__(self, anthropic_api_key: str = "", model: str = "claude-sonnet-4-20250514") -> None:
        self._api_key = anthropic_api_key
        self._model = model
        self._client = None

    def _get_client(self):
        """Lazy-init the Anthropic client."""
        if self._client is not None:
            return self._client
        if not self._api_key:
            logger.warning("Anthropic API key not set — AI reasoning disabled.")
            return None
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key)
            return self._client
        except ImportError:
            logger.warning("anthropic package not installed — AI reasoning disabled.")
            return None

    def analyze_event(
        self,
        event_type: str,
        event_summary: str,
        affected_assets: list[str],
        current_scores: dict[str, float],
        current_regime: str = "",
        portfolio_summary: str = "",
    ) -> dict[str, Any]:
        """Analyze a qualitative event and suggest score overrides.

        Args:
            event_type: One of 'earnings', 'fed_statement', 'regulatory', 'black_swan', 'other'.
            event_summary: Brief description of the event.
            affected_assets: List of tickers potentially affected.
            current_scores: Dict of asset -> current composite score.
            current_regime: Current macro regime.
            portfolio_summary: Brief portfolio state description.

        Returns:
            Dict with analysis, impact_assessment, override suggestions.
        """
        client = self._get_client()
        if client is None:
            return self._no_override_result(affected_assets, "AI reasoning unavailable.")

        prompt = self._build_prompt(
            event_type, event_summary, affected_assets,
            current_scores, current_regime, portfolio_summary,
        )

        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            return self._parse_response(text, affected_assets)
        except Exception as e:
            logger.error(f"AI reasoning API call failed: {e}")
            return self._no_override_result(affected_assets, f"API error: {e}")

    def _build_prompt(
        self,
        event_type: str,
        event_summary: str,
        affected_assets: list[str],
        current_scores: dict[str, float],
        current_regime: str,
        portfolio_summary: str,
    ) -> str:
        scores_text = "\n".join(f"  {a}: {s:.1f}/100" for a, s in current_scores.items())

        return f"""You are an expert portfolio analyst. Analyze this market event and suggest
score adjustments for affected assets.

EVENT TYPE: {event_type}
EVENT: {event_summary}
CURRENT MACRO REGIME: {current_regime}
AFFECTED ASSETS: {', '.join(affected_assets)}

CURRENT COMPOSITE SCORES:
{scores_text}

PORTFOLIO: {portfolio_summary}

Respond in JSON format:
{{
  "analysis": "Brief qualitative analysis of the event",
  "impact_assessment": {{
    "TICKER": {{
      "impact": "positive/negative/neutral",
      "override_suggestion": <integer from -20 to +20, 0 means no change>,
      "rationale": "Why this override"
    }}
  }},
  "confidence": "HIGH/MEDIUM/LOW",
  "time_horizon": "short/medium/long"
}}

Rules:
- Override must be between -20 and +20 (inclusive)
- Use 0 if the event doesn't materially change the outlook
- Be conservative — only suggest overrides for clear, material impacts
- Provide specific rationale for each non-zero override"""

    def _parse_response(self, text: str, affected_assets: list[str]) -> dict:
        """Parse Claude's response into structured override data."""
        try:
            # Try to extract JSON from response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
            else:
                return self._no_override_result(affected_assets, "Could not parse AI response.")

            # Validate and clamp overrides
            impacts = data.get("impact_assessment", {})
            for asset in impacts:
                override = impacts[asset].get("override_suggestion", 0)
                impacts[asset]["override_suggestion"] = max(
                    -self.MAX_OVERRIDE, min(self.MAX_OVERRIDE, int(override))
                )

            return {
                "analysis": data.get("analysis", ""),
                "impact_assessment": impacts,
                "confidence": data.get("confidence", "MEDIUM"),
                "time_horizon": data.get("time_horizon", "medium"),
                "timestamp": datetime.now(tz=UTC).isoformat(),
                "success": True,
            }
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse AI response: {e}")
            return self._no_override_result(affected_assets, f"Parse error: {e}")

    def _no_override_result(self, assets: list[str], reason: str) -> dict:
        return {
            "analysis": reason,
            "impact_assessment": {
                a: {"impact": "neutral", "override_suggestion": 0, "rationale": reason}
                for a in assets
            },
            "confidence": "LOW",
            "time_horizon": "medium",
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "success": False,
        }

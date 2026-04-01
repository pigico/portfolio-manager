# Fed Statement Analysis Prompt Template

Analyze the following Fed communication:

**Type:** {STATEMENT_TYPE} (rate decision / minutes / speech)
**Key Points:** {SUMMARY}
**Rate Decision:** {RATE_ACTION} (hold / cut / hike by {BPS}bps)
**Dot Plot Signal:** {DOT_PLOT}

Current regime: {REGIME}
Portfolio exposure: {EXPOSURE}%
Affected assets: {AFFECTED_ASSETS}

Evaluate:
1. Is this hawkish, dovish, or neutral relative to market expectations?
2. What does this mean for each asset class (stocks, crypto, commodities)?
3. Does this change the macro regime classification?
4. What is the likely market reaction in the next 1-4 weeks?

Suggest overrides per affected asset (-20 to +20).

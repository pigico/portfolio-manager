# Earnings Analysis Prompt Template

Analyze the following earnings report for {TICKER}:

**Reported:** EPS {ACTUAL_EPS} vs Expected {EXPECTED_EPS} ({SURPRISE_PCT}% surprise)
**Revenue:** {ACTUAL_REV} vs Expected {EXPECTED_REV}
**Guidance:** {GUIDANCE_SUMMARY}

Current composite score: {CURRENT_SCORE}/100
Current regime: {REGIME}

Evaluate:
1. Was the surprise meaningful or noise?
2. Does guidance change the medium-term outlook?
3. Are there hidden risks in the report (margin compression, customer concentration)?
4. How does this interact with the current macro regime?

Suggest override (-20 to +20) with rationale.

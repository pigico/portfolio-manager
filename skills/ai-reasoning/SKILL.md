# AI Reasoning — Claude Qualitative Override Layer

Uses Claude API for qualitative analysis that quantitative models miss.

## Scripts
- `reasoning_engine.py` — Calls Claude API with structured prompts
- `news_interpreter.py` — Fed statements, earnings, regulatory changes
- `override_manager.py` — Logs all overrides with rationale

## Trigger Events
- Earnings release
- Fed statement / rate decision
- Regulatory news
- Black swan event
- Significant score change

## Rules (IMMUTABLE)
- Max override: **±20 points** on composite score
- Score cannot exit 0-100 range
- Every override MUST be logged with timestamp, context, rationale
- Auto-disable after 5 bad overrides for 7 days

## Prompt Templates (in references/prompt_templates/)
- `earnings_analysis.md`
- `fed_statement.md`
- `regulatory_change.md`
- `black_swan.md`

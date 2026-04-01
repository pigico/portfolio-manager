# Portfolio Manager — Claude Code Orchestrator

## Decision Pipeline (ORDINE RIGOROSO)

0. **risk-guard** → Il sistema è operativo? Kill switch ok? Circuit breaker ok?
1. **market-posture** → Quanto capitale impegnare? → exposure_ceiling (0-100%)
2. **macro-regime-detector** → Quale quadrante Dalio? → asset_class_weights
3. **composite-scorer** → Score 0-100 per ogni asset → decision per asset
4. **ai-reasoning** → Claude override qualitativo → ±20 punti (loggato)
5. **divergence check** → Cross-platform divergence → amplifica segnale
6. **risk-guard validation** → Pre-trade checks su ogni operazione suggerita
7. **paper-trader** → Esegui trade simulato
8. **telegram-bot** → Alert con rationale

## Skills Directory

Each skill under `skills/` is an independent module with its own:
- `SKILL.md` — instructions for Claude on how to use the skill
- `scripts/` — Python implementation
- `references/` — documentation, parameter guides, templates

## Regole Immutabili

- NESSUN trade bypassa il RiskGuard. Mai. Nemmeno in paper mode.
- Kill switch a -40% drawdown richiede reset MANUALE.
- Circuit breaker: 3 loss consecutivi → pausa 1h. Non disattivabile.
- AI Override max ±20 punti, DEVE essere loggato con rationale.
- Position size max 20%, asset class max 60%, cash reserve min 5%.

## Config Files

- `config/settings.py` — API keys from .env, global config
- `config/portfolio_config.yaml` — Portfolio definition, weights, constraints
- `config/risk_config.yaml` — Risk parameters (IMMUTABLE defaults)
- `config/alert_config.yaml` — Alert rules and channels

## Development Standards

- Python 3.11+
- Type hints everywhere
- Logging with loguru (no print())
- Graceful error handling (never crash on API failure)
- Retry logic for all API calls
- Unit tests with mock data

# Exnova Ultra-Smart Bot v3.0

Bot de trading automático para Exnova/IQ Option con dashboard en consola, estrategias mejoradas y gestión de riesgo avanzada.

## Correr el bot

- Workflow `Bot Exnova: Trading` — arranca el bot en modo práctica (consola)
- Para correrlo manualmente: `cd bot && python3 main.py`

## Credenciales requeridas (ya configuradas en Secrets)

- `EXNOVA_EMAIL` — email de la cuenta Exnova
- `EXNOVA_PASSWORD` — contraseña de la cuenta Exnova

## Donde vive el código

```
bot/
  main.py                    — punto de entrada, dashboard Rich en consola
  config.py                  — configuración centralizada
  engine/
    signal_engine.py         — motor principal de señales v3.0
  core/
    advanced_risk_manager.py — Kelly Criterion + drawdown protection
    unified_scoring_engine.py — scoring 0-100 ponderado
  strategies/
    technical.py             — indicadores técnicos (RSI, MACD, BB, EMA)
    smart_reversal.py        — estrategia de reversión en S/R
    multi_timeframe.py       — análisis multi-timeframe (H1/M30/M15/M5/M1)
  data/
    market_data.py           — conexión y datos de Exnova
  exnovaapi/                 — API wrapper de Exnova (copiado del repo original)
```

## Mejoras aplicadas vs el repo original

- Motor de señales unificado con 11 filtros en cascada
- Análisis de patrones de velas (Hammer, Engulfing, Pin Bar, Morning/Evening Star, Shooting Star)
- Filtro de volatilidad ATR (evita mercados erráticos o muertos)
- Confirmación multi-timeframe estricta (M1+M5+M15 deben alinearse)
- Kelly Criterion con Quarter-Kelly para position sizing conservador
- Cooldown automático tras pérdidas consecutivas
- Dashboard Rich en consola: balance, PnL, win rate, historial, señales, riesgo
- Expiración adaptativa según alineación MTF (1-3 minutos)

## Activos configurados (OTC — disponibles 24/7)

EURUSD-OTC, GBPUSD-OTC, AUDUSD-OTC, EURJPY-OTC

## Parámetros de riesgo

- Confianza mínima para operar: 68%
- Max drawdown diario: 10%
- Max pérdidas consecutivas antes de parar: 4
- Max operaciones/hora: 6
- Cooldown tras pérdida: 2 minutos

## User preferences

- Dashboard en consola, sin web UI
- Modo práctica de Exnova (demo, sin dinero real)
- Estrategias conservadoras con alta selectividad

## Gotchas

- Siempre correr en `bot/` directory: `cd bot && python3 main.py`
- Si hay error de conexión, verificar credenciales en Secrets
- Los activos OTC tienen payout ligeramente menor pero están disponibles 24/7 incluyendo fines de semana

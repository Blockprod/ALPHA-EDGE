---
type: operational_protocol
projet: ALPHAEDGE
broker: Interactive Brokers (IB Gateway)
edge_status: CONDITIONNEL (6.8/10)
validation_stage: GATE BEFORE FULL CAPITAL
derniere_revision: 2026-04-02
creation: 2026-04-02
---

# ALPHAEDGE — Paper Validation Protocol
## Gate Before Full Capital Deployment

**Context:** Strategic audit verdict = CONDITIONNEL (6.8/10)
- Win rate IC95 [42.05%, 50.17%] includes 50% (edge not statistically proven at 95% threshold)
- N=579 trades backtest sufficient in size, but confidence insufficient
- **Gate:** Must validate 5 NYSE sessions with live market data before full capital authorization

---

## 1 · VALIDATION PHASE REQUIREMENTS

### 1.1 Conditions de Démarrage

| Criterion | Value | Source |
|-----------|-------|--------|
| Backtest baseline | PF=1.454, Sharpe=3.06, MaxDD=7.70% | reports/ALPHAEDGE_backtest_results.csv (N=579) |
| IC95 WR range | [42.05%, 50.17%] | Audit strategic BLOC 1 |
| Audit verdict | CONDITIONNEL | audit_strategic_alphaedge.md |
| Status before validation | ⏳ BLOCKED | Paper trading NOT authorized |
| Status after validation | ✅ APPROVED | Paper trading authorized if thresholds pass |

### 1.2 Duration & Scope

**Duration:** 5 consecutive NYSE trading sessions (minimum)
- Sessions = calendar days when NYSE open 09:30–16:00 EST (15:30–16:30 CET / 14:30–15:30 CEST)
- NO holidays
- Can span 1–2 weeks depending on market schedule

**Scope:** Paper (simulated) trading via IB Gateway papertrading account
- **NOT** real capital at risk
- Real market data (live fills from IBKR)
- Real slippage & spread (not modeled)
- All risk constraints active (daily loss limit, position sizing, etc.)

**Pairs:** All configured pairs active
- EURUSD, GBPUSD, USDJPY (per config.yaml)

**Capital:** Simulate realistic lot sizes
- Use paper account $100K starting equity
- risk_pct = 0.67% (per config.yaml:39)
- Lot sizing follows production formula

---

## 2 · LOGGING FORMAT & METRICS

### 2.1 Trade-by-Trade Log

Create file: `reports/ALPHAEDGE_VALIDATION_SESSION_[DATE].csv`

**Columns (required):**

```csv
session_date,pair,direction,entry_price,exit_price,entry_time_utc,exit_time_utc,pnl_pips,pnl_usd,outcome,observed_wr,observed_pf,vs_backtest_wr,vs_backtest_pf,spread_cost_pips,slippage_cost_pips,notes
2026-04-08,EURUSD,LONG,1.0950,1.0980,15:35,16:18,+30,+300,WIN,50.00%,1.50,-3.94%,+3.06%,1.2,0.8,"Healthy momentum signal"
2026-04-08,GBPUSD,SHORT,1.2850,1.2830,-20,-200,LOSS,43.75%,1.42,-6.25%,-2.38%,1.4,1.0,"Carry conflict on GBPUSD"
...
```

**Metrics per session:**

```
── Session Log: ALPHAEDGE_VALIDATION_SESSION_2026-04-08.csv ────────────────
Date             : 2026-04-08 (NYSE open)
Trades executed  : N_session = 12
Win rate (obs)   : WR_obs = 50.00% (6 wins / 12 trades)
WR vs backtest   : Δ WR = +3.94% (backtest WR = 46.11%)
Profit Factor    : PF_obs = 1.52
PF vs backtest   : Δ PF = +4.66% (backtest PF = 1.454)
Daily P&L        : $2,845 USD (3.48 pips/trade avg)
Max drawdown     : -$890 USD (0.89% equity)
Slippage avg     : 0.92 pips/trade (vs backtest model 0.68)
Status           : ✅ PASS (within tolerance bands)
───────────────────────────────────────────────────────────────
```

### 2.2 Comparaison Backtest ↔ Live

**Compute after each session:**

```python
# Pseudo-code logging
session_metrics = {
    "N": 12,
    "WR_backtest": 0.4611,
    "WR_observed": 0.5000,
    "WR_delta_pct": ((0.5000 - 0.4611) / 0.4611) * 100,  # +3.94%
    "PF_backtest": 1.454,
    "PF_observed": 1.52,
    "PF_delta_pct": ((1.52 - 1.454) / 1.454) * 100,  # +4.66%
    "Sharpe_observed": 2.95,
    "MaxDD_pct": 0.89,
}
```

---

## 3 · PASSING THRESHOLDS

### 3.1 Per-Session Acceptance Criteria

| Metric | Threshold | Reason |
|--------|-----------|--------|
| **Win Rate** | WR_obs ≥ 40% | Conservative vs backtest baseline (46.11%) |
| **Profit Factor** | PF_obs ≥ 1.30 | Conservative vs backtest baseline (1.454) |
| **Max Drawdown** | MaxDD_session ≤ 10% | Safety margin vs backtest 7.70% |
| **Trade Count** | N_session ≥ 5 | Ensure sufficient sample size per session |
| **Signal Frequency** | ≥ 2 trades/pair across 5 sessions | Validation across all configured pairs |

### 3.2 Session Status

**✅ PASS Session:** All metrics within thresholds
**⚠️ WARN Session:** 1 metric slightly outside (e.g., 38% < WR < 40%)
**❌ FAIL Session:** 2+ metrics outside thresholds → **Pause & Investigate**

### 3.3 Aggregated 5-Session Validation

**After completion of all 5 sessions, compute aggregate:**

```python
N_total = sum(N_i for i in range(5))  # Total trades across 5 sessions
WR_5session = sum(wins) / N_total
PF_5session = sum(gross_wins) / sum(gross_losses)
Sharpe_5session = annualized daily Sharpe from cumulative daily PnL
MaxDD_5session = maximum observed equity drawdown across all 5 sessions
```

**5-Session Pass Criteria (final gate):**

| Metric | Threshold | Status |
|--------|-----------|--------|
| **Win Rate Aggregate** | WR_5 ≥ 42% | Must not degrade >4% from backtest 46.11% |
| **Profit Factor Aggregate** | PF_5 ≥ 1.40 | Must not degrade >4% from backtest 1.454 |
| **Max Drawdown** | MaxDD_5 ≤ 10% | Safety margin (backtest 7.70%) |
| **Sharpe Aggregate** | Sharpe_5 ≥ 2.50 | Conservative vs backtest 3.06 |
| **All Sessions ≥ WARN** | 0 FAIL sessions | No hard stops detected |
| **Signal Coverage** | All pairs ≥ 2 trades | Validate multi-pair harmony |

---

## 4 · FAILURE MODES & RECOVERY

### 4.1 Session-Level Failures

**❌ Scenario A: Single FAIL session (e.g., WR=30%, PF=1.1)**

Action:
1. Log detailed notes (filter cascade analysis, news events, technical issues)
2. Do NOT pause validation phase
3. Continue to next session, monitor for systematic bias
4. If 2+ FAIL sessions observed → escalate to Stage 2 analysis

**❌ Scenario B: Persistent slippage divergence (observed > 2× backtest model)**

Action:
1. Extract fill-by-fill costs from IBKR API
2. Compare vs `compute_variable_slippage()` backtest model
3. Update `cost_slippage_multipliers` in config.yaml (C-04 framework)
4. Re-run backtest with calibrated multipliers
5. Resume validation with new baseline

### 4.2 5-Session Aggregate Failure

**❌ Overall FAIL: WR_5 < 42% OR PF_5 < 1.40 OR MaxDD_5 > 10%**

Action:
1. **Do NOT proceed to full capital**
2. Escalate to secondary audit:
   - Is backtest→live divergence systematic?
   - Does live data quality differ from backtest assumptions?
   - Are Carry or Momentum parameters miscalibrated?
3. Options:
   - **Option A:** Continue additional 5 sessions with unchanged config (gather more data)
   - **Option B:** Apply parameter adjustments (C-ST-03 Bayesian sweep) + restart validation
   - **Option C:** Pause and investigate root cause (credential issue, data feed problem, etc.)

### 4.3 Systematic Issues Detected

**⚠️ Example: "Consecutive rejections on GBPUSD LONG for 3 sessions in a row"**

Action:
1. Extract `rejection_log.csv` from backtest (if available post C-ST-07)
2. Cross-reference with live session logs
3. Diagnose: Is ADX threshold too high? Is Carry gate over-restrictive?
4. If systematic → apply pair-level override (GBPUSD gate per C-ST-06)
5. Resume validation with documented deviation

---

## 5 · AUTHORIZATION GATE (Final)

### 5.1 GO Paper Trading (Full Size)

**Condition:** 5-session aggregate PASS

```
✅ GATE OPEN: Paper Trading Full Size Authorized

Evidence:
- 5 NYSE sessions completed (2026-04-08 to 2026-04-15)
- WR_5 = 45.2% (within tolerance -4% vs backtest)
- PF_5 = 1.43 (within tolerance -1.6% vs backtest)
- MaxDD_5 = 8.5% (within safety margin)
- All 0 FAIL sessions
- Signal coverage: EURUSD=12, GBPUSD=14, USDJPY=11 (all > 2)

Approved by: [auditor name + timestamp]
Next gate: Monthly P&L review (if live capital > $50K)
```

### 5.2 CONDITIONAL Pass (Review Required)

**Condition:** 5-session aggregate PASS, but 1+ WARN sessions OR edge close to threshold

```
⚠️ CONDITIONAL PASS: Paper Trading Authorized With Monitoring

Evidence:
- 5 NYSE sessions completed (2026-04-08 to 2026-04-15)
- WR_5 = 42.8% (at lower boundary -3.3% vs backtest)
- PF_5 = 1.41 (within tolerance -3.0% vs backtest)
- Session 2: WARN level (WR=38%, but still traded)
- Systematic finding: Slippage +30% vs model (cost calibration updating)

Conditions:
1. Continue daily logs during first 10 live trades (full capital)
2. If degradation > 5% from validation WR → pause and investigate
3. Monthly reviews required (vs quarterly for PASS)

Approved by: [auditor name + timestamp]
Next gate: 2026-05-02 (30-day review)
```

### 5.3 FAIL Pass (Halt & Investigate)

**Condition:** 5-session aggregate FAIL

```
❌ GATE CLOSED: Paper Trading Not Authorized

Evidence:
- 5 NYSE sessions completed (2026-04-08 to 2026-04-15)
- WR_5 = 38.5% (-7.6% vs backtest, below -4% threshold)
- PF_5 = 1.24 (-14.7% vs backtest, below -4% threshold)
- 2 FAIL sessions detected (Session 1, Session 4)
- Systematic issue: ADX signal appears over-restrictive in live NYSE open regime

Reason: Edge validation insufficient, backtest→live divergence exceeds tolerance

Required Actions (before retry):
1. Analyze filter underperformance (C-ST-05 detailed rejection logs)
2. Consider parameter sweep (C-ST-03) + restart validation
3. Or: Accept risk and escalate to human decision (require executive sign-off)
4. Timeline: 2 weeks to resolve or archive

Decision: [RETRY / ESCALATE / ARCHIVE]
```

---

## 6 · DOCUMENTATION & AUDIT TRAIL

### 6.1 Files Generated

```
reports/
  ├─ ALPHAEDGE_VALIDATION_SESSION_2026-04-08.csv
  ├─ ALPHAEDGE_VALIDATION_SESSION_2026-04-09.csv
  ├─ ALPHAEDGE_VALIDATION_SESSION_2026-04-10.csv
  ├─ ALPHAEDGE_VALIDATION_SESSION_2026-04-13.csv
  ├─ ALPHAEDGE_VALIDATION_SESSION_2026-04-14.csv
  └─ ALPHAEDGE_VALIDATION_AGGREGATE_2026-04-02_to_2026-04-14.md

docs/
  └─ ALPHAEDGE_PAPER_VALIDATION_PROTOCOL.md (this file)
```

### 6.2 Checklist: Validation Complete

- [ ] All 5 sessions executed (dates logged)
- [ ] Trade CSV created for each session (15 cols min)
- [ ] Per-session metrics computed (WR, PF, MaxDD, Sharpe)
- [ ] 5-session aggregate metrics computed
- [ ] Aggregate status: PASS / CONDITIONAL / FAIL determined
- [ ] Failure modes documented (if any)
- [ ] Gate decision recorded (GO / RETRY / HALT)
- [ ] Backtest comparison analysis completed
- [ ] Slippage calibration reviewed (cost multipliers)
- [ ] Signal coverage verified (all pairs ≥2 trades)
- [ ] Manual sign-off by risk manager or authorized personnel
- [ ] Configuration locked (no changes during validation unless documented)

### 6.3 Lessons Learned (Post-Validation)

After validation completes, document in `tasks/lessons.md`:
- What diverged between backtest & live (signal frequency? fills?)
- Which filters triggered most rejections in live?
- Cost calibration accuracy (slippage multiplier effectiveness)
- Psychological challenges (drawdown tolerance, streak length)
- Recommended follow-up audits (STRAT-03 PF tuning, etc.)

---

## 7 · ACTIVATION & TIMELINE

### 7.1 Config Flag (Optional)

Add to `config.yaml` for explicit tracking:

```yaml
# Validation Phase Control
validation_phase:
  enabled: true
  start_date: 2026-04-08
  required_sessions: 5
  target_completion: 2026-04-15
  status: "IN_PROGRESS"  # or "PASS", "CONDITIONAL", "FAIL"
  approved_by: null  # set after review
```

### 7.2 Timeline (Example)

```
2026-04-02  ← Audit CONDITIONNEL verdict issued
2026-04-08  ← Validation phase STARTS (5 sessions initiated)
2026-04-09  ← Session 1 complete, metrics logged
2026-04-10  ← Session 2 complete
2026-04-13  ← Session 3 complete (skip Fri 2026-04-12 volatility)
2026-04-14  ← Session 4 complete
2026-04-15  ← Session 5 complete
2026-04-16  ← Aggregate analysis + GO/CONDITIONAL/FAIL decision
2026-04-17 ← Full capital authorization (if PASS) OR escalation (if FAIL)
```

---

## 8 · SUCCESS CRITERIA (EDGE PROOF GATE)

✅ **Validation Phase PASSES if:**
1. All 5 sessions executed without critical IB Gateway errors
2. 5-session WR_aggregate ≥ 42% (within -4% tolerance vs backtest 46.11%)
3. 5-session PF_aggregate ≥ 1.40 (within -4% tolerance vs backtest 1.454)
4. Max observed drawdown ≤ 10% (safety margin vs backtest 7.70%)
5. Zero FAIL sessions (all sessions ≥ WARN or PASS)
6. Signal coverage: all pairs ≥ 2 trades across 5 sessions
7. No systematic drift (e.g., slippage model ≤ 2× actual)

✅ **Paper Trading Authorization Granted** → Proceed to full capital (if risk committee approves)

---

**Document Version:** 1.0
**Last Updated:** 2026-04-02
**Next Review:** Post-validation (2026-04-16)

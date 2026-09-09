![[_nav.md]]

::: row {.right}
Session |1|{.primary}   Tracker |connected|{.success}   Calibration |fresh|{.success}
:::

## 3 · Results

[[← Back to Tasks](./tasks.md)]

> **Design note:** reached by clicking **Analyze** on a completed task card in Tasks (`tasks.md`) — also a persistent top-level tab like Setup/Tasks, so it's reachable directly too. Always shows the **most recent run** for whichever task was last analyzed (re-runs stay on disk in their own `_run1`/`_run2`/... session folders, but only the latest is shown here in this phase — no run-picker yet). Modeled closely on `resources/images/diki-ui-3.png`'s table structure, restyled into this project's own WTMH Clinical Teal theme.

---

### Static Click — 32 trials

Computed alongside the raw `trials.csv`/`gaze_stream.csv`/`events.jsonl` and written to `session_metrics.json` in this run's session folder.

---

#### Data quality

| Metric | Value |
|---|---|
| Valid samples | 92% |
| On-screen samples | — |
| Effective rate | — |
| Calibration error (raw) | 8.4 px |
| Longest gap | — |

#### Fixation

| Metric | Value |
|---|---|
| Mean duration | 0.34 s |
| Median duration | 0.29 s |
| Rate | 18.2 /min |

#### Saccade

| Metric | Value |
|---|---|
| Mean amplitude | — |
| Mean direction | — |
| Latency (to first fixation) | — |

#### Selection

| Metric | Value |
|---|---|
| Hit rate | 78% |
| Median RT | — |
| Mean attempts | — |
| Mean revisits | — |
| Trials needing re-attempt | — |

> **"—" means not yet computed by this codebase** (see the metrics-category gap report in `docs/specs/SPEC-result-logic.md`) — not a rendering bug. Rows already backed by real data today: Valid samples, Calibration error, Fixation mean/median duration, Fixation rate, Hit rate.
> **Alternate state (not shown above):** if Valid samples fell below an 80% floor, a warning banner would appear directly under the Data quality table — `::: alert warning` — "! valid share 62% below the 80% floor" (wording/threshold matches the reference image; exact floor value TBD at implementation time).

---

#### Session Log

::: card

```
Session started: 2026-09-09_P001_click_static_run1
Connected to Gazepoint Control.
Calibration measured — 5 points, mean error 8.4px, valid.
Running Static Click (32 trials) at 1920x1080.
Setting changed: dwell.threshold_ms 800 -> 700
Wrote 32 trials -> sessions/2026-09-09_P001_click_static_run1/trials.csv
```

:::

> **Data source:** this panel is `session.log`, already written verbatim by `SessionRecorder` every run today — no new capture needed, only a UI panel to display it.

---

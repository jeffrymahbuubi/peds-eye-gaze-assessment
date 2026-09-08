![[_nav.md]]

::: row {.right}
Session |1|{.primary}   Tracker |connected|{.success}   Calibration |fresh|{.success}
:::

## 2 · Tasks

[[← Back to Setup / recalibrate](./setup.md)]

> Run in any order, re-run freely — each run gets its own session folder (`_run1`, `_run2`, ...), so a re-run never overwrites a prior attempt.

---

::: card

### Static Click

One still target on an empty field — baseline look-and-select.

|Pending|{.warning}

[Run]* [Settings]{.outline} [Analyze]{state:disabled}

:::

::: card

### Grid Click (3x3)

One cell of a visible 3x3 board lights up — selection among candidates.

|Pending|{.warning}

[Run]* [Settings]{.outline} [Analyze]{state:disabled}

:::

::: card

### Follow & Click

The target travels; select it while it moves — smooth pursuit.

|Pending|{.warning}

[Run]* [Settings]{.outline} [Analyze]{state:disabled}

:::

::: card

### Scanning Search

Find the cued shape in a 2D field of distractors — visual search.

|Complete|{.success}

[Run]{.outline} [Settings]{.outline} [Analyze]*

:::

> **Design note (illustrative only):** Scanning Search is shown Complete above just to demonstrate the status/button-state change after a run — in a fresh session all four tasks start Pending. Clicking **Run** embeds the task canvas + operator sidebar into this same window in place of this page's content (no new window, no subprocess); it returns here with status updated to Complete when the task ends.

---

## Modals & Dialogs

> Not visible on page load.

::: modal

## Task Settings — Static Click

Trial Count
[10___________________________]{type:number}

Target Radius (px)
[60___________________________]{type:number}

Timeout (ms)
[4000_________________________]{type:number}

[Save]* [Cancel]

:::

# SPEC-gaze-cursor-redesign — Gaze Cursor Behaviour & Appearance

**Status: DONE — implemented, live-validated against the real GP3 HD with a real subject, committed as `fa55f8c` and pushed to `origin/main`.** The reported corner jump (§2) is fixed and **user-confirmed live**: deliberate blinking no longer moves the cursor. Two design decisions were revised after that session (§10): the ring's colours were re-chosen by measurement after the first attempt blended into the forest theme, and the off-canvas fade was **removed entirely** in favour of freezing the cursor in place, at the user's request, for parity with Gazepoint Control — so §4.2 is superseded and `_OFF_CANVAS_FADE_NORM` no longer exists. **One thing is implemented but not visually signed off: how the new ring reads against the red target (§10.3).** Tests: 161 collected, 160 passed, 1 pre-existing unrelated failure, +13 new.

**Created:** 2026-09-11
**Last updated:** 2026-09-11 (live session + revisions)

## Scope note

Follow-on from `SPEC-gui-audit-2026-09-10.md` §6, which made the gaze cursor share hit-testing's corrected coordinate conversion and added an edge clamp so the cursor could never silently vanish off-canvas. That work shipped in `364cc54` and did what it set out to do. This SPEC covers a **separate** defect in the same feature, reported by the user after living with the result, plus an appearance request.

All findings below come from reading the current working copy of `dev/peds-eye-gaze-assessment/` at commit `85bf3bd`, cross-referenced against the verified OpenGaze corpus at `docs/gazepoints/` and the reference screenshots at `resources/images/gaze-cursor-from-calib/`. **No code was changed to produce this diagnosis.**

## 1. Reported symptom, and the correction to it

**Reported (user, 2026-09-11):** "when the eyes is not gaze to the circle it will goes back to left corner on the screen (correct me i'm wrong)... this behavior is quite distracting." Request: make the cursor behave and look like Gazepoint Control's own marker, per `resources/images/gaze-cursor-from-calib/`.

**The symptom is real and accurately described. The stated trigger is not correct**, and the distinction matters because it changes the fix entirely:

- The cursor does **not** jump to the corner because gaze moved off a circle. Gaze direction has nothing to do with it.
- It jumps because the tracker **lost the eyes** — a blink, the face leaving the camera's view, or head movement out of range. The app then renders a zeroed coordinate, which lands in the top-left corner.

The two correlate in practice, which is why the inference was natural: a child looking away from a target is also the moment they are most likely to blink or shift their head. But a child can stare fixedly at a non-centre circle indefinitely without ever triggering it, and can trigger it while looking directly *at* a circle by blinking.

**Why this is not the §6 clamp misbehaving.** The clamp pulls an off-canvas position to the *nearest* edge. Genuine off-canvas gaze to the right clamps right, above clamps top, and so on. A consistent, repeatable jump to one specific corner is not what a nearest-edge clamp produces — it is what a single fixed coordinate produces. That fixed coordinate is `(0.0, 0.0)`.

## 2. Root cause — an invalid sample's coordinates are rendered as if they were a position

Traced end to end through the current source; every step below was read, not inferred.

**Step 1 — the client zeroes the coordinates of an unusable sample.** `rec_to_sample` (`src/inputs/gazepoint_client.py:222-248`) picks the best point of gaze when `BPOGV` is set, otherwise falls back to the fixation POG with `valid = FPOGV` (lines 229-239). It then constructs the sample:

```python
x=x if x is not None else 0.0,
y=y if y is not None else 0.0,
valid=bool(valid and x is not None and y is not None),
```

(lines 246-248). When the device sends no usable coordinate — or sends one the parser cannot read — `x` and `y` become **`0.0`**, and `valid` becomes `False`. The zero is a placeholder standing in for "no value", but it is indistinguishable downstream from a real reading of the screen's top-left corner.

**Step 2 — `EyeInput.poll` passes those placeholder coordinates through untouched.** `src/inputs/eye_input.py:176-201` handles three distinct invalid cases, and treats one of them differently from the other two:

| Case | Line | Returned pointer |
|---|---|---|
| Source reports the link is down | 186-188 | `(0.5, 0.5)`, `valid=False` — neutral centre |
| No sample has ever arrived | 190-192 | `(0.5, 0.5)`, `valid=False` — neutral centre |
| **Sample present but `valid=False`** | **194-199** | **`(sample.x, sample.y)` — raw, i.e. `(0.0, 0.0)`** |

The third branch resets the smoother, with a comment explaining that an invalid point must not smear the running average — which is correct and deliberate. But it then returns the invalid sample's own coordinates. The two neighbouring branches already demonstrate that the codebase knows an invalid pointer needs a substituted position; this branch is the one that was missed.

**Step 3 — the render path faithfully draws it in the corner.** `BaseTask.pointer_to_canvas_px` (`src/tasks/base_task.py:172-187`) converts `(0.0, 0.0)`:

- With gaze geometry known (live device): `norm_to_px(0, 0, gaze_w, gaze_h)` is `(0, 0)`, minus the canvas's on-screen offset gives `(-offset_x, -offset_y)` — negative on both axes whenever the canvas is inset within the monitor, which it always is (§6 of the GUI-audit SPEC measured a real `744×845` canvas inside a `1024×897` window).
- With no geometry (headless replay): `norm_to_px(0, 0, screen_w, screen_h)` is `(0, 0)`.

Either way the position is at or left-of and above the canvas origin. `_clamp_to_canvas` (`src/ui/canvas.py:30-49`) then pulls it to `(14, 14)` — one cursor radius in from the top-left — and `_draw_cursor` (`src/ui/canvas.py:342-353`) paints it at `alpha=70`, the dim treatment, since `cursor_valid` is `False`.

**The code predicts the exact reported symptom**, including which corner. That correspondence is the confirmation; no live reproduction is needed to establish the mechanism.

**Step 4 — how often this fires is easy to underestimate.** The verified corpus (`docs/gazepoints/synthesis/data-fields-reference.md:56-65`) records that `FPOGV` is true only when an eye is detected **and** a fixation is detected, and is false during blinks, when no face is in view, **and during saccades**. Whenever the `BPOGV` branch is unavailable and the code falls back to `FPOGV`, every saccade is a candidate dropout. A child performing a scanning or grid task saccades constantly by design.

**Interaction with §6's clamp.** The clamp did not cause this and is not itself wrong, but it changed how the bug presents: before `364cc54`, a zeroed coordinate was drawn outside the widget rect and silently clipped away by Qt, so a dropout looked like a brief disappearance. After the clamp, the same zeroed coordinate is dragged into view and parked in the corner — more visible, and therefore more distracting, even though the underlying defect is unchanged and older than the clamp.

## 3. Reference behaviour — what Gazepoint Control actually does

All four screenshots in `resources/images/gaze-cursor-from-calib/` are the same screen: Gazepoint Control's **calibration-results overlay**, reached with `'M' to view marker tracking` (visible in the on-screen legend). Observed characteristics:

- **A small hollow ring**, roughly 8-10px across with a thin stroke, in saturated green — not a filled disc. Being hollow, it does not occlude whatever sits under it.
- **Several recent samples drawn at once**, connected by thin line segments — a short comet-trail showing where gaze has just been. `Screenshot 2026-09-10 171829.png` shows a wide scattered trail; `173242.png` shows a tight cluster during a steady fixation. The trail length is what makes jitter and saccade direction legible at a glance.
- **Drawn wherever it lands, never clamped.** `173255.png` shows the marker in the empty gap *between* the bottom-row circles, not inside any target. Their overlay is fullscreen, so "off-canvas" does not exist as a state for them — which is precisely why they need no clamp and we do.
- **On a dropped sample, nothing is drawn.** No marker parks anywhere.

**Design tension worth stating plainly rather than assuming away:** that overlay is an **operator diagnostic**, shown to the person running the calibration. Our cursor is on screen in front of a **child performing a clinical task**. The trail is informative for an operator and is additional moving visual noise for a child who is supposed to be attending to a target. This is the reason §4's appearance decision adopts the ring but not the trail.

## 4. Design decisions (locked in with the user, 2026-09-11)

Four decisions taken via `AskUserQuestion`. Recorded here with their trade-offs, including the ones the user accepted rather than avoided.

### 4.1 — Tracking dropout: freeze at the last valid position, stay dim

**Decision:** when a sample is invalid, the cursor holds the **last valid position** and is drawn dim. It does not move, does not jump, and does not disappear, for as long as the dropout lasts.

**Why this over the alternatives.** Hiding immediately (Gazepoint Control's own behaviour) makes every blink a flicker off and back on, which is its own form of distraction. Freeze-then-fade-then-hide was offered as the recommendation; the user chose the simpler, more stable rule instead.

**Accepted trade-off, explicitly:** a long dropout leaves a stale dot resting at a position nobody is looking at any more. The dim treatment is the only signal distinguishing it from a live reading. This is a deliberate choice of visual stability over strict honesty, and should not be quietly "improved" into a fade later without asking — if it turns out to mislead an operator in practice, that is a new finding to raise, not a silent revision.

### 4.2 — Genuine off-canvas gaze: clamp to the edge, fade with distance

> **SUPERSEDED 2026-09-11 by §10.2** — implemented as described, then removed at the user's request after live testing, in favour of freezing the cursor in place. The threshold this section calls for no longer exists in the source. Retained here because §4.5 and §6 refer to it, and because why it was dropped is worth keeping.

**Decision:** when gaze is **valid** but lands outside the canvas, keep the §6 edge clamp, and additionally fade the dot as real gaze travels further off-canvas, hiding it entirely past a threshold distance.

**Why.** The current behaviour parks a dim dot at the edge for as long as the child looks away — the flat, always-on version of the same distraction. Fading by distance keeps "glanced just past the edge" visible (which is what §6's clamp was for) while letting "looking right away from the screen" resolve to nothing on screen.

**Preserved from §6:** the reason the clamp exists at all is that "looking away" and "tracking died" must not look identical. Under this design they still do not, because §4.1 gives tracking loss its own distinct behaviour (a frozen dot in place, never at the edge).

### 4.3 — Appearance: small hollow ring, no trail

**Decision:** adopt Gazepoint Control's ring shape and smaller size — a thin-stroked hollow ring around 10px across — and **do not** adopt the sample trail.

**Why.** The hollow ring stops the cursor occluding the target underneath it, which matters most at exactly the moment the child is on target and the dwell ring is filling. The trail is rejected for the audience reason in §3: it is an operator diagnostic being shown to a child mid-task.

**Constraint to respect during implementation:** the dwell progress ring (`_draw_progress_ring`, `src/ui/canvas.py:~334-340`, an 8px-wide arc) and the hit-feedback particles are existing visual language the child already knows. A smaller hollow gaze ring must remain visually distinct from the dwell arc at a glance, not read as a second, smaller progress indicator.

### 4.4 — Measure before tuning: a live dropout diagnostic first

**Decision:** before finalising any timing or distance constants, run a live diagnostic against the real GP3 HD recording what the device actually reports during deliberate blinks and look-aways.

**Why.** This is the discipline that paid off in `SPEC-gui-audit-2026-09-10.md` §7/§9: a plausible hypothesis about point counts was retracted only because real timing data existed, and that same data exposed a far more serious bug. The §4.2 fade threshold in particular is a constant that should be set from measured dropout frequency and off-canvas excursion distance, not guessed. Note that the §4.1 fix itself does **not** depend on the diagnostic's outcome — rendering an invalid sample's coordinates is wrong regardless of what the device sends — so the diagnostic gates the *tuning*, not the *correctness*.

### 4.5 — Resolving the overlap between 4.1 and 4.2

The two rules meet when **tracking is lost while gaze was already off-canvas**. §4.1 says never hide on dropout; §4.2 says hide when far off-canvas. Resolution: **freeze holds the last rendered state, including its faded alpha level.** If the cursor had already faded to invisible because gaze was far off-canvas, a dropout at that moment leaves it invisible rather than resurrecting a dot at the edge. "Freeze" means freeze what was on screen, not recompute a position.

## 5. Implementation plan — all built; §5.2 later removed by §10.2

*(Section numbering jumps from 7 to 10: §10 is cited by name from `src/ui/canvas.py`'s comments, so it is not renumbered.)*

Ordered as recommended: the correctness fix first, standalone and independently verifiable, before any appearance change.

**5.1 — Fix the dropout passthrough (`src/inputs/eye_input.py`).** Give `poll`'s invalid-sample branch (lines 194-199) a remembered last-valid position to return instead of `sample.x/sample.y`. `EyeInput` already tracks `self._last_valid`, which is read at line 191 for the no-sample case — the same field can serve here, so this is plausibly a small change rather than new state. When no valid sample has ever been seen, fall back to the neutral `(0.5, 0.5)` the two sibling branches already use, so the cursor never starts life in a corner either. The smoother reset at line 198 stays exactly as it is — it is correct and unrelated.

**Tests:** `tests/test_eye_input.py`. A direct reproduction-and-fix proof, not a smoke test, matching the standard this project held itself to in `SPEC-gui-audit-2026-09-10.md` §9: feed a valid sample at a known non-origin position, then an invalid sample carrying `(0.0, 0.0)`, and assert the returned pointer stays at the first position rather than moving to the origin. Verify the test genuinely fails without the fix before considering it done — §9 records a draft test that passed with its own fix disabled and had to be rewritten.

**5.2 — Off-canvas distance fade (`src/ui/canvas.py`).** `_clamp_to_canvas` (lines 30-49) already computes and returns whether it clamped; extend it to also report **how far** the unclamped position was from the canvas, and have `_draw_cursor` scale alpha down by that distance, reaching zero past a threshold. Keep the clamped-vs-valid alpha distinction that exists today (lines 344-350). The threshold constant is the one §4.4's diagnostic should inform.

**Testing note:** `src/ui/canvas.py` imports PySide6 at module load and its own docstring states it is never imported by the headless pipeline or tests — this project's established convention (see `tests/test_theme_sounds.py`'s docstring, and §6 of the GUI-audit SPEC, which deliberately left the clamp un-unit-tested) is to validate UI-layer rendering live via qt-mcp rather than by unit test. The *distance calculation* could reasonably be extracted to a pure helper and unit-tested even though the drawing cannot; worth deciding at implementation time.

**5.3 — Ring appearance (`src/ui/canvas.py`).** `_draw_cursor` (lines 342-353) currently fills an ellipse of radius `_CURSOR_RADIUS_PX = 14.0` (line 27) with `cursor_color`. Change to a stroked, unfilled ellipse at roughly a 5px radius. Two knock-on checks before calling it done:

- `_clamp_to_canvas` insets by `_CURSOR_RADIUS_PX` specifically so a clamped dot draws whole (lines 41-48); a smaller radius must keep that inset consistent, and the inset now also needs to account for stroke width so the ring is not half-clipped.
- Verify contrast on both themes at the smaller size against a real screenshot, not by reasoning about hex values: `forest` is a **light** theme (`background: "#e8f5e9"`, `cursor_color: "#1b5e20"` — dark on light) while `space` uses `cursor_color: "#ffeb3b"`. A thin ring has far less ink than a filled disc, so a size that reads clearly as a disc may not as a ring.

**5.4 — Live validation.** Real GP3 HD with a real subject, via qt-mcp, per this project's established practice. Specifically confirm: a deliberate blink no longer moves the cursor at all; a deliberate look-away fades it out rather than parking it at the edge; the ring is clearly visible and clearly distinct from the dwell arc while on target. Note the known operational gotchas before starting — `SetupPage.can_continue()` silently requires **Sex** to be set or every Run button no-ops, and the qt-mcp probe has previously entered a bad state mid-session and needed a restart (both recorded in `SPEC-gui-audit-2026-09-10.md`'s round-3 log).

## 6. The dropout diagnostic (§4.4) — what to capture

Purpose: establish how often dropouts actually occur during a real task, how long they last, and how far off-canvas real gaze travels, so §4.2's fade threshold is set from data.

**Precedent to follow:** `calibration_timing_log_path()` and `_append_timing_record` in `src/engine/calibration.py`, added in `SPEC-gui-audit-2026-09-10.md` round 3 — a JSONL record per event under `sessions/_diagnostics/`, shared across runs, with every `OSError` swallowed by design so a diagnostic can never break a session a child is sitting through. That diagnostic is still in place and is what made the §9 fix independently checkable a day later; this one should be built the same way and left in place for the same reason.

**Worth recording per dropout:** wall-clock timestamp, duration, the raw `BPOGV`/`FPOGV` flags and the raw `BPOGX`/`BPOGY`/`FPOGX`/`FPOGY` values that accompanied it, and the last valid canvas-normalised position before it. Separately, for valid-but-off-canvas samples, the normalised distance outside the canvas.

**The specific question to settle first:** whether the device sends literal zeros during a dropout or whether our own parser's `None → 0.0` fallback (`gazepoint_client.py:246-247`) is manufacturing them. Both produce the identical corner jump and both are fixed by §5.1, so this does not block the fix — but if the device is in fact *holding* the last fixation coordinates rather than zeroing them, that is useful durable device knowledge of the kind §3 of the GUI-audit SPEC's round-3 findings captured, and it would mean dropouts are currently less visually disruptive than the zero case predicts.

**ANSWERED 2026-09-11 by the real-device drill, and the answer is neither option cleanly: the device does both.** At dropout start it reports `BPOGV=0, FPOGV=0`, with `FPOGX`/`FPOGY` **literally `0.00000` in 8 of 31 captured cases** and a real stale coordinate in the rest. The zeros are device-sent, not manufactured by our fallback. Because `rec_to_sample` falls back to the FPOG branch whenever `BPOGV` is unset, those 8 are precisely the frames that jumped to the corner — which is what made the symptom intermittent rather than constant. Separately: `BPOGX`/`BPOGY` are **not** zeroed during a dropout, carrying uncalibrated garbage instead (e.g. `-0.42802`, `2.15309`), so they must never be used without checking `BPOGV` first. See the Log.

## 7. Open questions and risks

*Refreshed 2026-09-11 after the live session — several original entries are now resolved and are marked as such rather than deleted, so the reasoning stays traceable.*

- **RESOLVED — the fade threshold no longer exists.** §10.2 removed the fade entirely at the user's request; `_OFF_CANVAS_FADE_NORM` is deleted, so there is no constant left to tune and §4.4's tuning question is moot. (The diagnostic that would have informed it is still worth keeping for its dropout data.)
- **PARTLY RESOLVED — ring legibility.** Size was confirmed fine by the user against the real device. Contrast was fixed by measurement (§10.1, +73%). **Still unverified: how the white core reads against the red target** — see §10.3.
- **§4.1's stale-dot trade-off is accepted, not solved.** Recorded in full in §4.1 so a future session does not "fix" a deliberate decision. §10.2 widened it: off-canvas gaze now freezes too, so a stale ring can mean either "looking away" or "tracking lost".
- **Whether the trail should ever be available to the operator** is not decided. §4.3 rejects it for the child-facing canvas; it is not ruled out as a future operator-panel diagnostic view, and is not in scope here.
- **RESOLVED — dropout frequency is now measured, not inferred.** Across three real sessions: median dropout 52–98ms, longest 6.4s. Literal-zero `FPOGX` (the corner-jump case) occurred at 8/31, 6/361 and 4/24 across the three — **the rate varies substantially between sessions and does not track calibration quality**, contrary to a correlation suggested mid-session and retracted here. Two of those samples are small.

## 10. Revisions after the live subject session (2026-09-11)

The subject-facing pass §5.4 called for was run against the real GP3 HD with the user as subject. It confirmed one thing outright, and produced two changes.

### 10.1 — §5.1 confirmed live; the ring's colour was wrong

**Confirmed by the user:** through deliberate blinking, the cursor **stayed put — no corner jump.** That is §2's bug closed on real hardware with a real subject, which is what §5.1 existed to achieve.

**Reported problem:** the ring blended into the forest theme and was hard to notice. Size was judged fine ("similar to the one in Gazepoint Control"), so this was purely contrast.

**Root cause of my own design error, worth recording because it is a general trap:** I copied Gazepoint Control's ring *colour logic* along with its shape. Their saturated green works because their backdrop is near-black — the transferable principle is **maximum contrast against the background, not the hue**. Forest is a *light* theme (`background: #e8f5e9`) whose `cursor_color` is `#1b5e20`, the same hue family, and that same colour also draws the grid cell outlines the cursor sits among.

**Decision (`AskUserQuestion`): a two-tone halo ring**, theme-independent, no theme-file changes.

**Which two tones was settled by measurement, not taste, and the measurement reversed my assumption.** Four variants were rendered against the real forest scene (grid outlines included, cursor placed over one) and scored by total colour deviation from the background in a 40×40 box:

| Variant | Score | vs. current |
|---|---|---|
| A — current, no halo (dark-green core) | 30832 | — |
| B — **white** halo + theme core | 32205 | **+4%** |
| C — **dark** halo + white core | **53363** | **+73%** |
| D — white halo, thicker strokes | 48765 | +58% |

I had assumed B. It is nearly useless: white fringe on a near-white background adds almost no ink. On a light backdrop the **dark** fringe is what carries legibility, and on a dark backdrop the white core does — which is why C is the genuinely theme-independent answer rather than just the highest-scoring one. D gets partway there by thickness alone, which the user had already ruled out by saying the size was right.

**Implemented:** `_CURSOR_HALO_COLOR = "#102010"` at 5px under `_CURSOR_CORE_COLOR = "#ffffff"` at 2px, same radius, halo drawn first so its extra width survives as a fringe on both sides of the core. `_clamp_to_canvas`'s inset now uses `max(core, halo)` stroke width.

### 10.2 — The off-canvas fade is removed; the cursor freezes instead

**User decision, reversing §4.2:** "I want to drop this Look-away behavior, since this is not appear in the gazepoint control. When I look away in the control, the cursor just stop."

This is a correction worth honouring rather than arguing: §4.2's fade was an invention of this SPEC, not a property of the reference implementation it was supposed to be matching.

**Implemented:** new `TaskCanvas._cursor_draw_position()`. When gaze is valid but outside the canvas, the cursor is drawn at `_last_on_canvas_xy` — the last position gaze was genuinely inside the canvas — and dimmed. It does not track to the edge and does not fade. `_OFF_CANVAS_FADE_NORM` is **deleted**, so §4.4's whole tuning question is now moot: there is no constant left to tune. Before the first on-canvas reading of a run there is nothing to freeze at, and nothing is drawn.

**Two consequences, both deliberate and both accepted by the user when choosing this option:**

1. **"Looking away" and "tracking lost" are now visually identical** — both a dimmed, frozen ring. This is precisely the ambiguity the §6 clamp of `SPEC-gui-audit-2026-09-10.md` was introduced to remove, so it is a knowing reversal of that decision, on the grounds that Gazepoint Control does not distinguish them either.
2. **The edge clamp is now a safety net, not a mechanism.** Off-canvas positions no longer reach it; it only keeps a ring sitting exactly on the boundary from being half-clipped.

**Hit-testing is untouched.** `BaseTask` still receives the true, unfrozen, possibly out-of-range position, so a frozen cursor can never cause a selection the child did not make. Freezing is the renderer's decision alone — the same separation §6 of the GUI-audit SPEC established for the clamp.

### 10.3 — What is NOT confirmed

The user moved to commit without giving a verdict on the revised ring's appearance. So: the ring is **implemented and measured, but not visually signed off.** Specifically unverified — **how the white core reads against the red target**, the one backdrop the measurements did not cover and the moment the cursor matters most. A future session should not treat §10.1 as visually validated.

## Log

- **2026-09-11** — Cursor feedback brought via `/sparc:orchestrator`; **diagnosis and design only, no code changed** (`git status` clean, `main` level with `origin/main` at `85bf3bd`). Reference screenshots at `resources/images/gaze-cursor-from-calib/` read directly (all four are Gazepoint Control's `'M'` marker-tracking view of the calibration-results overlay, characterised in §3); they were viewed, not copied into the repo. Root cause of the reported corner jump traced end to end through current source and confirmed to be a **tracking-dropout defect predating and independent of `364cc54`'s clamp** (§2) — the user's reported symptom is accurate but its stated trigger (gaze leaving a circle) is not, and §1 records the correction. Key evidence: `eye_input.py:194-199` returns an invalid sample's raw `(0.0, 0.0)` coordinates while its two sibling branches (lines 186-188, 190-192) both substitute a neutral centre for the same class of condition; `gazepoint_client.py:246-248` is where those zeros originate. Four design decisions locked in via `AskUserQuestion` (§4): freeze-and-dim on dropout (the user chose this over the recommended fade-then-hide, and §4.1 records the accepted stale-dot trade-off), distance-fade off-canvas, hollow ring without the sample trail, and measure-before-tuning. The overlap between the first two decisions was surfaced and resolved explicitly in §4.5 rather than left to implementation. Implementation plan (§5) and diagnostic spec (§6) written but **not built — awaiting user review of this SPEC before any code is written**, per the user's explicit instruction this session.

- **2026-09-11, later — user reviewed the SPEC and approved implementation. §5.1, §5.2, §5.3 and §6 implemented; §5.4 partially done (real-device drill passed, subject-facing visual pass still outstanding).** Order followed the plan: correctness fix first, standalone, before any appearance change.

  **§5.1 (dropout freeze) IMPLEMENTED.** `EyeInput` (`src/inputs/eye_input.py`) gained `_last_pointer_xy`, holding the position last handed to the caller; `poll`'s invalid-sample branch now returns that instead of the sample's own coordinates, falling back to the neutral `(0.5, 0.5)` its two sibling branches already use when nothing valid has been seen yet. The smoother reset on that branch is untouched — it was already correct. **One refinement over what §5 specified:** the SPEC suggested reusing the existing `_last_valid` field, but `_last_valid` holds the *raw* sample while the renderer was given the *smoothed* pointer; returning the raw one would twitch the cursor at the exact instant tracking is lost, which is the opposite of §4.1's intent. A separate field holding the smoothed value is what satisfies §4.5's "freeze what was on screen". The disconnect branch additionally clears the held position, for the same reason it already clears the running average.

  **Tests: 4 new in `tests/test_eye_input.py`**, and **all four were verified to genuinely fail with the fix reverted** — the §9 discipline, applied deliberately rather than assumed. The failure output of the reverted run reads `assert (0.0, 0.0) == (0.5, 0.5)`, i.e. the corner jump reproduced in a test. Coverage: the core reproduction (dropout holds position rather than reporting `(0.0, 0.0)`), the smoothed-not-raw distinction, the never-seen-a-valid-sample fallback, and the disconnect clearing the held position.

  **§6 (dropout diagnostic) IMPLEMENTED**, mirroring `calibration.py`'s timing-log precedent: new `src/engine/gaze_diagnostics.py` with `gaze_dropout_log_path()` and a `GazeDropoutLog` observer writing one JSONL record per *run* (not per frame — a 150 Hz tracker would otherwise bury the signal), every `OSError` swallowed. Records dropout runs (duration, frames, the raw POG attributes captured at the run's first frame, the frozen position) and off-canvas runs (duration, frames, **`max_distance_norm`** — the number §4.2's threshold is meant to be read from). Wired into `AssessmentApp._tick`, live-device only (a replay fixture's dropouts are the fixture's, not the tracker's, and would pollute the aggregate), and flushed in `_shutdown` so a dropout that never recovered is still recorded. To capture the raw attributes without touching the recording schema, `GazepointClient` gained `last_raw_pog()` — a diagnostic-only snapshot of the six POG keys from the most recent REC. **9 new tests** in `tests/test_gaze_diagnostics.py` (pure logic, no Qt or device dependency, so unlike the canvas it is directly coverable).

  **§5.2 / §5.3 (fade + ring) IMPLEMENTED.** `_CURSOR_RADIUS_PX` 14.0 → 5.0 with a new `_CURSOR_STROKE_PX = 2.0`; `_draw_cursor` now strokes a hollow ring instead of filling a disc, and scales alpha down by how far off-canvas real gaze is, returning without drawing once it reaches zero. Alphas raised 200/70 → 235/110 because a ring lays down far less ink than the disc it replaces. `_clamp_to_canvas`'s inset is now `radius + stroke/2`, not radius alone — a stroke straddles the path it is drawn on, so the old inset would have left the ring's outer half clipped. **A shared-helper decision worth recording:** the off-canvas distance is computed by a single `outside_distance()` now living in `src/inputs/base.py` alongside the other geometry helpers, used by *both* the canvas fade and the diagnostic, so the number the renderer acts on cannot drift from the number the threshold is tuned against — the same class of drift that caused §6 of `SPEC-gui-audit-2026-09-10.md` in the first place. It was briefly placed in `gaze_diagnostics.py` and moved, to avoid a `ui → engine` import and a cross-module private.

  **Canvas verified by rendered-pixel measurement, not by "it didn't crash".** `src/ui/canvas.py` is not pytest-covered by this project's convention (it imports PySide6 at module load; see its own docstring and `tests/test_theme_sounds.py`), so an offscreen render was measured instead: total colour deviation from the background across all four cursor states. On-canvas valid = 31124 ink units; dropout-frozen = 14526 (47%, the dim treatment); off-canvas fading in a clean linear ramp 14526 → 11520 → 8555 → 5782 → 2900 → 576 → **0 at the `0.25` threshold** and beyond. That is the fade doing what §4.2 specifies, demonstrated rather than asserted.

  **§5.4, real-device drill — PASSED, and it answered §6's open question.** Run as a standalone script (this project's established drill technique) rather than the full app, deliberately: `configs/default.yaml` has `calibration.enabled: true`, so a CLI launch would have popped a real calibration window on the real device, and the drill needed none — this is `feedback-check-disruptive-paths-before-live-launch` applied. Connected to the real GP3 HD (`GP3HD · 150 Hz · USB3 · SN 23309153`, `SCREEN_SIZE` 1920×1080) and streamed for 15s: **642 valid frames, 186 invalid, and zero invalid pointers reported at the origin.** Before the fix all 186 would have been at `(0.0, 0.0)`. 32 dropout runs and 23 off-canvas runs were recorded by the new diagnostic, 31 of 32 capturing raw POG attributes.

  **§6's question is settled, and the answer is more specific than either option it offered.** The zeros are **device-sent, not manufactured by our `None → 0.0` fallback** — but only some of the time. At dropout start the device consistently reports `BPOGV=0, FPOGV=0`, and `FPOGX`/`FPOGY` is *literally* `0.00000` in **8 of 31** captured cases while carrying a real stale coordinate in the rest. Since `rec_to_sample` falls back to the FPOG branch whenever `BPOGV` is unset, those 8 are exactly the frames that produced a corner jump. **This explains the symptom's intermittent character** — roughly a quarter of dropouts jumped to the corner and the rest froze more or less in place by accident — which no amount of source reading would have predicted. Also worth keeping: `BPOGX`/`BPOGY` are *not* zeroed during a dropout; they carry uncalibrated garbage (values like `-0.42802`, `2.15309`), which is why they must never be trusted without checking `BPOGV`.

  **Measured dropout durations:** min 17ms, median 52ms, max 445ms. A 52ms freeze is imperceptible, which supports §4.1's freeze-in-place choice; the 445ms tail is the case where the rejected fade-then-hide option would have differed most.

  **§4.2's threshold is deliberately NOT being finalised from this drill's data, and `0.25` remains marked PROVISIONAL in the source.** The drill's tracker was uncalibrated with no controlled subject, so its off-canvas distances (median 0.164, p90 1.153, 9 of 23 runs beyond 0.25) describe garbage readings rather than a real child glancing off the canvas. Tuning the threshold against them would be exactly the guess §4.4 exists to prevent. The number should come from a calibrated session's `max_distance_norm` records.

  **Files changed:** `src/inputs/eye_input.py`, `src/inputs/base.py`, `src/inputs/gazepoint_client.py`, `src/ui/canvas.py`, `src/app.py`, new `src/engine/gaze_diagnostics.py`, new `tests/test_gaze_diagnostics.py`, `tests/test_eye_input.py`, and this SPEC. **Full pytest suite: 161 collected, 160 passed, 1 pre-existing unrelated failure** (`test_config_merges_task_over_default`, the long-known local `target_fps` skip-worktree drift), **+13 new tests, no regressions.** **Nothing committed yet.** The scratch drill script was kept out of the repo (written to the session scratchpad, not `tools/`) and its JSONL output with it, so `sessions/_diagnostics/` still holds only the calibration timing log; `git status` shows only the intended source changes.

  **Still open:** (1) §5.4's subject-facing pass — a calibrated session with a real person deliberately blinking and looking away, to confirm visually that the cursor holds position through a blink, fades out rather than parking at the edge, and that the smaller hollow ring is legible on both themes and not mistakable for the dwell arc (§5.3's explicit unverified risk). (2) §4.2's threshold, pending that session's data.

- **2026-09-11, later still — §5.4's subject-facing pass RUN against the real GP3 HD with the user as subject. §5.1 confirmed live; two design revisions followed (§10).** Two dashboard sessions were driven via qt-mcp on `127.0.0.1:4242` against the real device, window maximised first (per `feedback-qt-mcp-maximize-before-validating`). Pre-flight checked `configs/local_state.json` first — `127.0.0.1`/`4242`, clean — which is the stale-port class of bug that caused the 2026-09-09 calibration crash.

  **§5.1 CONFIRMED LIVE BY THE USER:** through deliberate blinking, the cursor **stayed put, no corner jump.** This is the reported bug closed on real hardware with a real subject, not just in tests.

  **Both calibrations were genuine runs, incidentally re-confirming §9 of `SPEC-gui-audit-2026-09-10.md`:** session 1 logged `elapsed_s: 10.328`, `per_point_captured: true`, `mean_error_px: 69.67`; session 2 `mean_error_px: 27` — distinct values, each its own result rather than a retained one.

  **§10.1 — ring colour re-chosen by measurement after the user reported it blending into the forest theme** (size judged fine, "similar to the one in Gazepoint Control"). My own error is recorded in §10.1: I copied Gazepoint Control's colour logic along with its shape, but their saturated green works because their backdrop is near-black. Four variants were rendered against the real forest scene and scored; **the measurement reversed my assumption** — the white halo I expected to work scored +4%, while a dark halo with a white core scored **+73%**, because on a light background it is the dark fringe that carries legibility. Implemented as `#102010` 5px halo under a `#ffffff` 2px core, theme-independent.

  **§10.2 — the off-canvas fade was REMOVED at the user's request**, reversing §4.2: "this is not appear in the gazepoint control. When I look away in the control, the cursor just stop." Correct objection — the fade was this SPEC's invention, not a property of the reference implementation. Replaced by `TaskCanvas._cursor_draw_position()`, which freezes the cursor at `_last_on_canvas_xy` when gaze leaves the canvas. `_OFF_CANVAS_FADE_NORM` deleted, which makes §4.4's tuning question moot — **there is no constant left to tune**, despite the live data that had been collected for it. Two accepted consequences: "looking away" and "tracking lost" are now visually identical (a knowing reversal of the §6 clamp's rationale in the GUI-audit SPEC), and the clamp is demoted to a safety net. **Hit-testing is untouched** — `BaseTask` still sees the true unfrozen position, so freezing can never cause a selection the child did not make.

  **Canvas verified by rendered-pixel measurement** (it is not pytest-covered by convention): fresh canvas with off-canvas gaze draws nothing (ink 0, correct — nothing to freeze at yet); on-canvas 53128; off-canvas frozen-dim 32864; dropout-dim 32864; full strength restored on re-entry, frozen position held correctly.

  **Diagnostic data from the live sessions, now the real basis for §7's claims:** 758 records total. Dropouts median 52–98ms, longest 6.4s. Literal-zero `FPOGX` at 8/31, 6/361 and 4/24 across three sessions — **a mid-session claim that this rate tracked calibration quality is retracted**; it varies by session and does not, and two samples are small.

  **NOT confirmed (§10.3):** the user moved to commit without giving a verdict on the revised ring's appearance, so it is implemented and measured but **not visually signed off** — specifically how the white core reads against the red target, the one backdrop the measurements did not cover.

  **Files changed this round:** `src/ui/canvas.py` only (plus this SPEC). Full suite re-run after the revisions: **161 collected, 160 passed, 1 pre-existing unrelated failure, no regressions.**

- **2026-09-11, later still — `/spec-memory-audit` pass, then committed as `fa55f8c` and pushed to `origin/main`.** Audit verified every symbol this SPEC names against current source (`_last_pointer_xy`, `_cursor_draw_position`, `_last_on_canvas_xy`, `_CURSOR_HALO_COLOR`/`_CURSOR_CORE_COLOR`, `outside_distance` in `src/inputs/base.py`) and confirmed `_OFF_CANVAS_FADE_NORM` is genuinely absent; re-ran the suite (161/160/1, matching); checked log chronology (three entries, correctly ordered); confirmed both wikilinks in the memory file resolve. **Fixed during the audit:** §4.2 marked SUPERSEDED rather than rewritten, §5's heading which still read "not yet built", §7's risk list which still described the deleted fade threshold as an open question, the status header, and the memory index line which still said DESIGN ONLY. A section-numbering gap (7 → 10) is deliberate and noted in §5: `src/ui/canvas.py` cites "S10" by name, so renumbering would silently break those references.

  **Cleanup:** the three QA session directories this task created (`CURSOR01` ×2, `CURSOR02`) were deleted; the user's own `TESTING` session dirs were deliberately left alone. `sessions/` is gitignored, so none of it was ever committable. Scratch scripts (the real-device drill, the ring-variant renderer) stayed in the session scratchpad and never entered the repo. `sessions/_diagnostics/gaze_dropouts.jsonl` is kept deliberately, for the same reason the calibration timing log was: it is what makes these findings checkable by a later session that was not here.

# PHASE 2B — Bayesian Knowledge Tracing

**Status:** reference implementation written and tested (`backend/ntgen/bkt.py`,
`backend/ntgen/fit_bkt.py`). Both run. Numbers below are real output, not projections.

**Replaces:** the 3-consecutive-correct mastery rule as the *mechanic*. The streak stays
as a UI element only.

**Insert:** between Phase 2 (graph engine) and Phase 3 (diagnostic). Phase 3 is rewritten
to use BKT.

> **As built (2026-08-22):** this spec was implemented with deliberate deviations.
> Read the **"As-built deltas"** appendix at the bottom before trusting any detail here —
> in particular §6 (resolved: option 1) and §5 (the diagnostic needed a calibration step
> the reference design lacks).

---

## 1. What it is, in one paragraph

Standard BKT models one skill as a two-state hidden Markov model — the student either has
mastered it or hasn't, and we never observe which. Four parameters per node: `p_init`
(mastered before practice), `p_learn` (chance an attempt teaches it), `p_slip` (wrong
despite mastery), `p_guess` (right without mastery). After each answer, Bayes gives the
posterior, then a transition step accounts for learning. We run one chain per node and add
a propagation step along prerequisite edges.

Reference: Corbett & Anderson (1995). A judge can look it up, which is the point.

---

## 2. Why this and not something else

**It is real ML, honestly described.** SymPy is symbolic computation — deterministic
algebra. Calling it ML in the pitch would be a claim a judge could catch. BKT is an HMM
with fitted parameters. Parameter estimation via gradient descent is genuine model fitting.

**It is visible.** Mastery becomes a continuous value per node, so the graph shows
continuous colour rather than three discrete states. Evidence propagates along edges, so
**one answer visibly moves several nodes at once.**

**It uses the graph rather than sitting beside it.** The propagation step is only possible
because the curriculum has prerequisite edges. A bolted-on feature would not have that
property.

---

## 3. The math

### 3.1 Posterior (Bayes on the observation)

Correct answer:

```
P(M | correct) = P(M)(1 − slip) / [ P(M)(1 − slip) + (1 − P(M))·guess ]
```

Wrong answer:

```
P(M | wrong) = P(M)·slip / [ P(M)·slip + (1 − P(M))(1 − guess) ]
```

### 3.2 Transition (the student may have learned)

```
P(M) ← P(M) + (1 − P(M))·learn
```

Mastery is absorbing in standard BKT — no forgetting.

### 3.3 Predicted correctness (used for fitting)

```
P(correct) = P(M)(1 − slip) + (1 − P(M))·guess
```

---

## 4. Prerequisite propagation — OURS, AND A HEURISTIC

**Say this honestly if asked.** Exact Bayesian inference over a joint distribution on 34
correlated nodes is expensive and needs data we do not have. This is an approximation with
a monotonicity constraint. "It's a documented heuristic" is a far better answer to a judge
than pretending it's exact inference.

**Assumption:** mastery is monotone along prerequisite edges. A student who can do CRT can
almost certainly do the Euclidean algorithm underneath it.

**Backward pass** (reverse topological order — evidence flows down to prerequisites):

```
P(prereq) ← max( P(prereq), BACKWARD_STRENGTH × P(node) )
```

**Forward pass** (topological order — a weak prerequisite caps its dependents):

```
P(node) ← min( P(node), FORWARD_CAP + min over prereqs of P(prereq) )
```

Constants as tested: `BACKWARD_STRENGTH = 0.85`, `FORWARD_CAP = 0.25`,
`MASTERY_THRESHOLD = 0.95`. These are tunable — they were chosen to look right on
synthetic students, not fitted.

---

## 5. TESTED FINDING — a design bug worth knowing about

The first version of `most_informative()` picked the next diagnostic question **from the
frontier**. That silently destroyed the entire feature.

Reason: early on, the frontier is just the graph's roots. Roots have no prerequisites. So
every answer moved **exactly one node** and no evidence ever propagated. Measured output:

```
Q1: divisibility    wrong     1 nodes moved
Q2: divisibility    correct   1 nodes moved
Q3: divisibility    correct   1 nodes moved
```

The fix: the diagnostic must be allowed to probe **deep** nodes. It is a binary search,
not a walk from the roots. Selection score:

```
uncertainty = 1 − 2·|P(M) − 0.5|        (peaks at P = 0.5)
reach       = 1 + number of ancestors
score       = uncertainty × sqrt(reach)
```

After the fix, same synthetic student:

```
Q2: gcd_lcm            correct   3 nodes moved
Q4: digit_rules        correct   3 nodes moved
Q6: order              wrong     9 nodes moved
```

**Practice mode is different and must still serve from `frontier()`** — students should
never be handed a problem whose prerequisites they lack. Only the *diagnostic* probes deep.

---

## 6. KNOWN ISSUE — flag before demo day

In the tested run, `order` was answered **wrong** and its probability went **up**
(+0.145 → 0.26).

This is correct standard-BKT behaviour, not a bug: the transition step assumes an attempt
may teach the skill, so it always increases P(M). When P(M) is low, that increase
outweighs the small posterior drop from a wrong answer.

It is also a well-known criticism of BKT — and on screen it looks broken. A student gets a
question wrong and watches the node get *brighter*.

Options, in order of preference:

1. **Apply the transition step only on correct answers.** Simple, visually coherent,
   defensible ("we model learning as occurring on successful practice"). Deviates from
   textbook BKT — say so.
2. Lower `p_learn` for tier 1 nodes so the effect is invisible. Hides the symptom, does
   not fix it.
3. Keep textbook behaviour and explain it. Honest, but the demo looks wrong.

**Recommend option 1.** Decide before building the frontend, since the animation depends
on it. *(Resolved 2026-08-22: option 1 — see as-built delta 1.)*

---

## 7. Cold start

There is no student data. Two approaches, both implemented in `fit_bkt.py`:

**Literature priors.** Start at slip ≈ 0.1, guess ≈ 0.2, learn ≈ 0.3, init ≈ 0.15. Refit
from usage as it accumulates.

**Synthetic students** — this is the better demo. Generate students with *known* mastery,
simulate their answers through the slip/guess model, fit parameters, and show recovery.
Measured on 200 synthetic students × 10 attempts:

| param | true | fitted | error |
|---|---|---|---|
| p_init | 0.200 | 0.143 | 0.057 |
| p_learn | 0.300 | 0.262 | 0.038 |
| p_slip | 0.090 | 0.103 | 0.013 |
| p_guess | 0.210 | 0.238 | 0.028 |

Slip and guess recover well; `p_init` is the weakest, which is expected — it is only
weakly identified from short sequences.

**This means the ML story does not depend on recruiting users in time.** Real student data
improves it; it is not required for it to work.

**Identifiability guard — do not remove.** If `slip + guess ≥ 1` the model degenerates and
a wrong answer becomes evidence *for* mastery. `NodeParams.clamp()` bounds slip ≤ 0.30 and
guess ≤ 0.40. This is a documented BKT failure mode.

---

## 8. Frontend requirements

`observe(node, correct)` returns `{node_id: delta}` for every node that moved. **The
frontend animates exactly these.**

- Node fill colour interpolates on P(M), continuous — not three buckets
- Nodes that moved pulse simultaneously, sized by |delta|
- On the diagnostic, show the count: "1 answer → 9 nodes updated." This is the sentence
  that sells the feature
- Keep the streak pips as a secondary UI element; they no longer drive mastery
- Mastery threshold P ≥ 0.95

---

## 9. Changes to existing docs

**`PROJECT.md` §5.3** — mastery rule becomes `P(mastered) ≥ 0.95` via BKT. The 3-streak
rule is demoted to UI. Keep the reset-to-zero decision and the "unparseable is not an
attempt" rule; both still apply.

**`PROJECT.md` §2** — add a rejected-alternatives note: binary mastery was replaced
because it discards information (a near-miss and a wild guess counted identically) and
because it cannot propagate evidence across prerequisite edges.

**`CLAUDE_CODE_HANDOFF.md` §2 Phase 3** — the diagnostic is now BKT-driven. Question
selection is `most_informative()`, not a hand-written binary search. Target 4–6 questions.

**Cut order (§4)** — BKT sits above the streak rule: if it is not working by day 5, revert
to the 3-streak mechanic and cut it. The graph view and symbolic verification remain
untouchable.

---

## 10. Build order

1. Read `bkt.py` and run `fit_bkt.py`. Confirm the numbers above reproduce.
2. Decide the §6 transition question. Implement it.
3. Wire `KnowledgeState` into the graph engine, replacing binary mastery.
4. Rewrite the Phase 3 diagnostic around `most_informative()`.
5. Tune `BACKWARD_STRENGTH` / `FORWARD_CAP` against synthetic students until the
   propagation looks right on screen.
6. Only then build the animation.

**Budget: ~5 days.** If it slips past that, fall back to the streak rule. The project
survives without BKT; it does not survive a broken graph view.

---

## Appendix — As-built deltas (2026-08-22)

What the shipped implementation does differently from this reference spec, and why. Every
delta is deliberate; the four mechanic decisions were made by the project owner.

1. **Transition on correct only** (§6 resolved as option 1). `observe(node, wrong)` is the
   Bayes posterior alone — a wrong answer strictly lowers P(M). Documented deviation from
   Corbett & Anderson; the code says so where it happens.

2. **Reveal counts as wrong evidence.** The app has a surrender mechanic (student gives up,
   streak wipes, worked solution shown, problem retired) that postdates this spec. A reveal
   applies the wrong-answer posterior (no learning transition — mastery must be earned by
   answering, not by reading) and propagates like any observation.

3. **`most_informative()` pool is authored nodes only, minus already-classified ones.**
   The app can only serve problems for tier 0/1 ("authored") nodes, so the probe pool is
   restricted to them — the §5 "probe deep" intent survives because deep authored nodes
   (`order`: 14 ancestors, `crt`: 11) dominate the reach term. The pool also excludes
   nodes the running diagnostic has already classified known/unknown by inference
   (without this pruning a weak student is served the six deepest nodes and the search
   never walks down). Question 1 is anchored at `congruence` for determinism. Propagation
   still updates tier 2/3 probabilities for display. The uncertainty term is `p(1−p)`
   (same peak at 0.5 as the spec's tent function, smoother shoulders).

4. **Sticky unlock, honest colour.** Once a node's prerequisites cross 0.95 it joins a
   grow-only per-student `unlocked` set and never re-locks, so no rug-pulls mid-session.
   Its fill colour, however, always shows the *current* P — a mastered node can honestly
   fade below threshold after wrong answers or a collapsed prerequisite, and re-mastering
   costs at most 3 corrects (see delta 6).

5. **The diagnostic calibrates at finish — required, not optional.** Backward propagation
   maxes out at `0.85 × P ≤ 0.85 < 0.95`, so with one observation per node NOTHING can
   cross the mastery threshold during a 6-question diagnostic: every student would finish
   with frontier = the root. The reference design is internally inconsistent here. As
   built, the diagnostic runs live BKT observations (for the deltas and the "N skills
   updated" moments) alongside the proven set-based bisection, and `result()` calibrates
   final priors from the sets: tested-correct → max(p, 0.96); inferred-known →
   max(p, 0.95); tested-wrong → keep the observed posterior; inferred-unknown →
   min(p, 0.40). No propagate runs after calibration (it would let capped dependents
   back-lift a tested-wrong node). Tested beats inferred, exactly as before.

6. **Forward-cap deadlock: analysed, no guard needed.** Considered guard — skip the
   forward cap for nodes with attempts > 0 — **rejected**. Inside every propagate the
   backward pass runs first, lifting a practiced node's prerequisites to ≥ 0.85·X before
   the cap applies, and 0.25 + 0.85·X > X always, so a directly practiced node can never
   be blocked from mastery. Corollary (checked by the selftest gate): from ANY prior,
   3 consecutive corrects reach ≥ 0.95 with the shipped parameters — the familiar
   "3 in a row" pace is preserved as a theorem, not a coincidence. Cold start masters in
   exactly 3; a diagnostic-lifted prior (≥ 0.28) masters in 2.

7. **Per-tier parameters, uniform pacing.** slip 0.10 / guess 0.20 / learn 0.30
   everywhere (the reference's per-tier slip/guess profiles broke the 3-corrects bound —
   tier 0's guess 0.22 lands at 0.948 after 3 from a collapsed prior); only `p_init`
   varies by tier (tier 0: 0.20, tiers 1–3: 0.10).

8. **Known propagation quirk — the dependents floor.** The backward pass takes
   `max(P(prereq), 0.85·P(dependent))` over ALL dependents, including ones whose P is
   still just its prior. So a node with many dependents has a soft floor of
   0.85 × (highest dependent P) that direct negative evidence cannot push through:
   getting `divisibility` wrong drops it to ~0.17, not ~0.03, because `primes` and
   `bases` still sit at their 0.20 priors. This is the monotonicity constraint working
   as designed ("a prerequisite is never much less known than what's built on it"), it
   never blocks mastery (3 corrects still cross 0.95 from the floor), and wrong answers
   still strictly lower P — but on root-ish nodes the drop is damped, and a second
   reveal in a row may visibly move almost nothing. Documented rather than "fixed":
   filtering the lift to evidence-bearing dependents would break the invariant that
   propagation is a pure function of the current P vector.

9. **`fit_bkt.py` is offline-only.** It is the judge-facing parameter-recovery demo
   (`python3 backend/ntgen/fit_bkt.py`), never imported by the app or the gates — the
   numeric-gradient fit is far too slow for the selftest. Its Part-2 walkthrough now
   reflects delta 1, so §6's "wrong answer went up" output no longer reproduces (that is
   the point).

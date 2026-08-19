# VoltHacks — Python Pipeline Build Plan (Phases 0–3)

## Status

| Phase | State |
|---|---|
| 0 — restructure + fix `safe_eval` | ✅ done |
| 1a — generalise the gate, 10 easy nodes | ✅ done |
| 1b — 5 special-case nodes (string / sentinel / condition checkers) | ✅ done |
| 1c — variants, distractors, hand-authored `pigeonhole_nt` | ✅ done |
| **Phase 1 total** | **45 generated templates + 5 hand-authored, all 22 tier 0–1 nodes, gate green** |
| 2 — `graph.py` | ✅ done — found 2 real bugs in the DAG file (see below) |
| 3 — `diagnostic.py` | ✅ done — 6-question bisection, `tested` vs `inferred` tagged |
| **Python layer** | **complete; `selftest.py` gates graph + diagnostic + every problem** |
| 4 — web app | 🟨 stack decided 2026-08-19: Flask + vanilla JS, name-only login |
| 4 CP-A — API + leak test | ✅ done — 8 routes, tri-state grading, `web/leaktest.py` green |
| 4 CP-B — frontend (graph view, diagnostic, practice UI) | 🟨 built 2026-08-19 — awaiting eyeball pass in the browser |
| 4 CP-C — deploy (PythonAnywhere; Render+disk fallback) | ⬜ target Aug 24–25, students ~Aug 26 |
| 5 — LLM authoring | ⬜ deliberately last |

Bugs the Phase 2 validator caught in `number-theory-dag.json` (both fixed 2026-08-19):
- `meta.node_count` said 34; the file has **35** (tier 2 has 10 nodes, not 9).
  PROJECT.md §3.2's table was stale too — §3.5 already enumerated ten. Doc updated;
  **the Google Doc still needs the same edit by hand.**
- `meta.demo_path` was **not walkable** — it reached `mod_exp` before `bases`,
  `mod_inverse` before `bezout`, `linear_congruence` before `linear_diophantine`.
  Following it literally lights a node up while its parent is still grey, in the exact
  screen §5.2 calls the money shot. Repaired to 19 nodes; `validate()` now enforces it.

2026-08-19 — mastery-rule decisions recorded + phase 4 checkpoint A:
- **PROJECT.md §5.3 is now a decision block** (threshold 3, reset-to-zero, unparseable
  submissions don't count as attempts, pips UI, "3 in a row" never "perfect"); §8 Q4
  closed, §4.3 cross-references it.
- **Tri-state grading**: `Problem.grade()` returns correct / wrong / **unparseable** —
  what `normalise()` can't read is a formatting slip, never an attempt, and never resets
  a streak. `check()` delegates; the gate tests all three outcomes per template.
- **`web/`**: Flask API (8 routes) over the untouched engine. Answers never leave the
  server — one serializer, and `web/leaktest.py` proves it (key allowlist + forbidden
  keys + answer-value scan over full simulated sessions). Per-student JSON + `events.jsonl`
  under `data/` ($NTGEN_DATA_DIR). Input guard blocks sympify DoS (`9^9^9^9`,
  `factorial(10**9)`), thresholds verified against the whole answer corpus.
- Standing gate is now: `python3 ntgen/selftest.py && python3 web/leaktest.py`.

2026-08-19 — prompt readability pass (user: "the average student will not be able to
read this"):
- **31 of 50 problems reworded** — plain-words question first, technical term kept as a
  labeled aside, every congruence stated as "leaves the same remainder", format hints show
  concrete numbers (new derived display values nm1/pm1/pm2; `answer_format` and `hint` are
  now interpolated with params in `Problem.__init__`). Gate gained a leftover-brace check.
- Proof sheet with before/after for all 50: https://claude.ai/code/artifact/9521d75f-1274-467f-94d0-4998a776b88c

Things built that were not in the original plan, and why:
- **`also_accept`** — Wilson's theorem answer is *−1*; the canonical stored value is *p−1*.
  Both are correct, so the exact checker accepts a list of values.
- **Degeneracy check in the gate** — a template whose sampler collapses to one case
  passes every other check while being useless. Fails unless the template declares
  `constant_answer_by_design` (as the "this congruence has no solutions" drill does).
- **`distractor_expr`** — machine-computable predicted wrong value, alongside the prose
  `distractor_note`. The gate rejects a distractor that always equals the right answer,
  since it could never identify a mistake. Phase 5 consumes these for targeted hints.
- **`why` field required on every hand-authored problem** — the one file with a stored
  answer key gets no SymPy verification, so each entry carries its full argument *and*
  a tightness check. The gate fails any entry missing it.

## Context

VoltHacks entry: a number theory mastery platform. The subject is modeled as a 34-node
prerequisite DAG (`ntgen/number-theory-dag.json`); a ~6-question diagnostic locates each
student's knowledge frontier; unlimited practice problems are generated at that frontier with
answers computed by SymPy — never by an LLM. That "the LLM never produces an answer" rule is
the project's core reliability claim and its pitch differentiator, and it is non-negotiable
per `CLAUDE_CODE_HANDOFF.md` §0.2.

**Where we stand (Aug 14 — day ~9 of 31):** Week 1 was the risk week — prove that
parameterized templates + SymPy verification produce clean problems. That bet has essentially
paid off: `verify.py`, `generator.py`, `selftest.py`, `demo.py` exist and 5 of 6 templates
pass 300 trials each. The task now is the rest of the Python layer, before any web work:

- **Phase 1** — template library for all 22 tier 0–1 nodes (6 covered, 15 to generate, 1 hand-authored)
- **Phase 2** — graph engine + mastery state (`graph.py`)
- **Phase 3** — diagnostic traversal (`diagnostic.py`)

Decisions confirmed with the user on Aug 14:
1. Scope = Phases 1–3 (the full pre-web Python layer).
2. **Strict checkpoint stops** — Claude halts at every checkpoint with a short explanation;
   the user runs the code and says continue. (He's learning SymPy and this pattern from the code.)
3. `pigeonhole_nt` stays, as 3–5 **hand-authored** problems with fixed keys.
4. Restructure `claude/` → `ntgen/` to match every path the handoff references. *(Done.)*

---

## Findings from the code review (what shapes this plan)

### 🔴 Bug: `safe_eval` broke on comprehensions — the selftest was RED

`CLAUDE_CODE_HANDOFF.md` §0.1 claims all 6 templates pass. They didn't anymore:
`linear_congruence_all_01` failed and `demo.py` crashed, both with
`name 'a' is not defined` inside `sorted([x for x in range(n) if (a*x - b) % n == 0])`.

**Root cause** (`verify.py`, `safe_eval`): `eval(expr, {"__builtins__": {}}, namespace)`
passed the whitelist + params as eval's *locals*. A list comprehension creates its own inner
scope, and free variables inside it resolve against eval's *globals* — which contained only
the emptied `__builtins__`. So `range(n)` (evaluated in the outer expression) worked, but
`a`, `b`, `n` inside the comprehension body didn't exist.

**Fix (applied in Phase 0)**: merge everything into the globals dict —
`eval(expr, {**namespace, "__builtins__": {}})`. This does **not** change the sandbox model
(§0.1 forbids that): builtins are still emptied, only whitelisted names are reachable. It
changes *where* the whitelisted names sit, nothing else.

**Why fix it rather than avoid comprehensions:** several upcoming solution expressions
genuinely want them — `linear_diophantine` minimality scans, `digit_rules` "all valid digits"
scans, brute-force reference checks. Crippling the expression language would push logic into
Python code per template, which defeats "templates are data."

### Handoff discrepancies noticed (flagged, not silently "fixed")

- **Paths**: handoff said code lives in `ntgen/`; it actually lived in `claude/` with the DAG
  in `claude/files/`. Resolved: restructured to `ntgen/` (user approved).
- **Diagnostic inference direction** (handoff Phase 3): "mastered if *downstream* of a passed
  node, locked if *upstream* of a failed one" — this is backwards. If you pass `congruence`,
  it's your **prerequisites (ancestors)** that are safely inferred mastered; passing a node
  says nothing about the harder material downstream of it. Phase 3 below implements:
  pass ⇒ ancestors inferred mastered; fail ⇒ descendants inferred locked.
- `load_templates("templates.json")` used a CWD-relative path, so everything only ran from
  inside the code directory. Fixed in Phase 0 (`Path(__file__).parent`).

### Smaller gaps the plan accounts for

- `selftest.py`'s `condition` branch hardcodes Bezout's `a, b, g` and `gcdex` — it can't test
  any *other* condition-checked template. Needs generalizing before `linear_diophantine`.
- `format_variants` / off-by-one checks assume integer answers — will crash or misfire on
  string answers (`bases`) and sentinel answers (`mod_inverse` "none"). Needs guarding.
- `linear_congruence_all_01`'s answer format promises "if none, answer: none", but the sampler
  only ever produces solvable cases, and no checker understands a "none" sentinel yet.
- Environment: Python 3.9.6 + SymPy 1.14.0, both working. No git repo — recommend `git init`
  (two-person team, month-long project; user's call).

---

## Phase 0 — Restructure + restore green  *(small, do first)*

Nothing new gets built on a red selftest.

1. Create `ntgen/` at repo root; move the code, `templates.json`, and
   `number-theory-dag.json` into it. Move `PROJECT.md` and `CLAUDE_CODE_HANDOFF.md` to repo
   root. Delete the now-empty `claude/`.
2. Fix `safe_eval` scoping as described above (one line + a comment stating the constraint:
   *names must live in globals or comprehension bodies can't see them*).
3. Make `load_templates` resolve relative to the module file, not the CWD.
4. Offer `git init` + first commit (user's call).

**CHECKPOINT 0 (stop):** `python3 ntgen/selftest.py` → 6/6 templates, 300 trials each;
`python3 ntgen/demo.py` runs end-to-end. User runs both.

---

## Phase 1 — Complete the template library

**Goal:** all 22 tier 0–1 nodes covered, 2–3 templates per generated node, everything passing
the selftest gate. Verification methods per node are already specified in `PROJECT.md` §4.3 —
each is a single SymPy call. Split into three batches so each checkpoint is a readable diff.

### Batch 1a — selftest generalization + the 10 "easy" nodes

Infrastructure first, because every later template depends on the gate being trustworthy:

- **Generalize the selftest** with optional per-template fields (schema *extension*, no existing
  field changes — flagged per handoff §0.1 "keep the schema exactly"):
  - `"selftest": {"good": <expr>, "wrong": <expr>}` — expressions evaluated in the same safe
    namespace, producing a known-correct and a plausible-wrong answer string. This removes the
    hardcoded Bezout logic and lets *any* condition-checked template be gate-tested.
  - Guard `format_variants` so non-integer answers skip the numeric variants.
- **Extend `SAFE_NAMES`** (allowed: "extend with new checkers"): `factorial` (wilson),
  `euclid_steps(a, b)` reference implementation (euclidean step-count questions),
  `to_base(n, b)` helper (bases).
- **Author the straightforward exact-checker nodes** — one template each, in dependency order:
  `primes`, `euclidean`, `divisor_functions`, `congruence`, `mod_arith`, `fermat_little`,
  `totient`, `euler_theorem`, `order`, `wilson`.

**CHECKPOINT 1a (stop):** selftest green on ~16 templates; one sample problem printed per new node.

### Batch 1b — the five special-case nodes (each needs new machinery)

These are called out individually in the handoff because a naive template would grade wrongly:

| Node | Why it's special | What gets built |
|---|---|---|
| `bases` | answers are strings, not numbers | new `check_string_normalised` (strip spaces, case-fold; format instructions pin the expected form) |
| `mod_inverse` | ~half of samples must have `gcd(a,n) > 1` → answer "no inverse exists" | **sentinel convention**: solution may evaluate to `"none"`; checkers accept a small synonym set (`none`, `no inverse`, `dne`, case-insensitive) |
| `linear_diophantine` | full solution *family* is hard to grade | per handoff advice: ask for "smallest positive x" (single integer) + one condition-checked "any valid (x,y)" template using the generalized selftest |
| `crt` | must include non-coprime moduli, consistent *and* inconsistent | `sympy.ntheory.modular.crt` returns `None` when inconsistent → maps onto the sentinel convention naturally |
| `digit_rules` | "which digit d makes N divisible by 9" can have **two** answers (digit-sum ≡ 0 → both 0 and 9 work) | either `unordered_set` over all valid digits or a sampler constraint forcing uniqueness — decided per template, verified by the 300-trial gate |

Also: retrofit the sentinel into `linear_congruence` (add an inconsistent-case template so
"answer: none" stops being a promise the sampler never keeps).

**CHECKPOINT 1b (stop):** selftest green, all 21 generated nodes covered.

### Batch 1c — depth: variants, distractors, pigeonhole

- **2nd/3rd templates per node** so students don't see repeated wording (target ~45–55 total).
- **Distractor templates** (`PROJECT.md` §4.4): construct parameters so the classic mistake
  yields a plausible wrong value — `mod_arith` (illegal cancellation), `mod_exp` (exponent
  reduced mod n), `fermat_little` (exponent reduced mod p not p−1), `gcd_lcm` (lcm = ab),
  `divisor_functions` (eᵢ vs eᵢ+1). Alongside the prose `distractor_note`, add a
  `distractor_expr` field computing the predicted wrong value — Phase 5's distractor-aware
  hints need a machine-checkable value, and recording it now costs nothing.
- **`pigeonhole_nt`**: 3–5 hand-authored problems in `ntgen/hand_authored.json` with fixed
  keys, plus a small serving path in `generator.py`. This is deliberately the *only* place a
  stored key exists — a human wrote and verified it, so the "no LLM answer" invariant holds.
  Kept in a separate file so that invariant stays visible in the architecture.

**CHECKPOINT 1c = the handoff's CHECKPOINT 1 (stop):** selftest green, ≥22 nodes covered,
sample problem shown from every node.

---

## Phase 2 — Graph engine and mastery state (`ntgen/graph.py`)

Exactly as specced in the handoff (it's already a good design; no deviations):

- `load_graph(path)` — parse the DAG JSON.
- `validate()` — assert acyclicity + every prereq id exists; **also warn on tier 0–1 nodes
  with zero templates** (a typo'd node id in `templates.json` would otherwise silently orphan
  a node). Wired into `selftest.py` so the gate catches graph rot too.
- `is_unlocked(node, mastery)` / `frontier(mastery)` / `locked(mastery)`.
- `MASTERY_STREAK = 3` as a single named constant (frozen through user testing —
  `PROJECT.md` §5.3), state shape
  `{node_id: {"streak", "attempts", "correct", "mastered"}}`.

**CHECKPOINT 2 (stop):** a script that loads the graph, validates it, simulates mastering
along the DAG's `demo_path`, and prints frontier/locked evolving at each step.

---

## Phase 3 — Diagnostic (`ntgen/diagnostic.py`)

Binary search over the DAG, not a linear quiz:

- Start at `congruence` — the school-math/contest-math boundary (`PROJECT.md` §5.1).
- Correct → jump forward along outgoing edges; wrong → walk back to prerequisites.
- Stop at 6 questions or when the frontier is bracketed.
- Output: initial mastery state with **`tested` vs `inferred` marked distinctly** (inference
  is a guess; the UI must not present it as measured). Inference direction as corrected above:
  pass ⇒ ancestors mastered, fail ⇒ descendants locked.
- Questions come from the Phase 1 generator, which is why template coverage must land first.

Test harness: a `SimulatedStudent(known_nodes)` that answers correctly iff the node is in its
knowledge set. Run against several profiles — beginner (partial tier 0), mid (through
`mod_arith`), advanced (all of tier 1), plus the edge cases: fails question 1 (must walk back
to roots gracefully) and passes everything (frontier = tier 2 boundary).

**CHECKPOINT 3 (stop):** terminal run of the diagnostic against simulated students with known
levels; verify it brackets roughly the right frontier in ≤6 questions. Finish with a small
end-to-end CLI session — diagnostic → frontier shown → practice loop → node mastered/unlocked —
which is exactly the flow the Phase 4 web app will wrap.

---

## Verification (how we know each phase is real)

- **Every checkpoint**: `python3 ntgen/selftest.py` green — 300 trials/template; correct
  answers (and format variants `1/2`, `0.5`, `$…$`) accepted; wrong answers rejected;
  garbage returns False without raising.
- **Phase 1**: `demo.py` extended to showcase each new checker class (string, sentinel,
  condition, set) the way it currently showcases Bezout and linear congruence.
- **Phase 2**: checkpoint script output eyeballed against the DAG (e.g. mastering
  `factorization` must not unlock `mod_exp`).
- **Phase 3**: simulated-student runs where the true frontier is known in advance.
- The user personally runs each checkpoint before the next phase starts (agreed working style).

## Explicitly out of scope (decided, not forgotten)

- **Phase 4 (web app)** and **Phase 5 (LLM template authoring)** — the handoff requires asking
  about stack / LLM API / auth / hosting first; those questions come *after* Checkpoint 3.
- Tiers 2–3 templates (render locked in the demo; never authored — `PROJECT.md` §3.2).
- Any leaderboard/Elo, any second subject (both explicitly rejected in `PROJECT.md` §2).

## Cut order if time runs short (from the handoff, unchanged)

1. Extra template variants (1 per node still demos fine) → 2. `wilson`, `pigeonhole_nt`
(leaves; graph stays connected) → 3. distractor extras. **Never cut**: symbolic verification,
the graph, the mastery mechanic.

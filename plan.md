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
| 4 CP-A — API + leak test | ✅ done — 8 routes, tri-state grading, `backend/leaktest.py` green |
| 4 CP-B — frontend (graph view, diagnostic, practice UI) | 🟨 built 2026-08-19 — awaiting eyeball pass in the browser |
| 4 CP-C — deploy (PythonAnywhere; Render+disk fallback) | ⬜ target Aug 24–25, students ~Aug 26 |
| **2B — Bayesian Knowledge Tracing** | ✅ built 2026-08-22 — BKT is the mastery mechanic; gates green; awaiting browser eyeball (see dated block at end) |
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
- **`backend/`** (named `web/` until the 2026-08-19 restructure): Flask API (8 routes)
  over the untouched engine. Answers never leave the
  server — one serializer, and `backend/leaktest.py` proves it (key allowlist + forbidden
  keys + answer-value scan over full simulated sessions). Per-student JSON + `events.jsonl`
  under `data/` ($NTGEN_DATA_DIR). Input guard blocks sympify DoS (`9^9^9^9`,
  `factorial(10**9)`), thresholds verified against the whole answer corpus.
- Standing gate is now: `python3 backend/ntgen/selftest.py && python3 backend/leaktest.py`.

2026-08-19 — prompt readability pass (user: "the average student will not be able to
read this"):
- **31 of 50 problems reworded** — plain-words question first, technical term kept as a
  labeled aside, every congruence stated as "leaves the same remainder", format hints show
  concrete numbers (new derived display values nm1/pm1/pm2; `answer_format` and `hint` are
  now interpolated with params in `Problem.__init__`). Gate gained a leftover-brace check.
- Proof sheet with before/after for all 50: https://claude.ai/code/artifact/9521d75f-1274-467f-94d0-4998a776b88c

2026-08-19 — repo restructured by language (user request):
- **`backend/`** = all Python: `app.py`, `store.py`, `layout.py`, `leaktest.py`, and
  `backend/ntgen/` moved as a unit with its three JSON files. **`frontend/`** =
  `index.html`, `style.css`, `app.js`, `graph.js` (was `web/static/`). `data/` stays at
  the repo root — `store.py` resolves it there, and moving it would orphan student files.
- Only 3 lines of code changed: the two sys.path / static_folder lines in `app.py` and
  the sys.path line in `leaktest.py`; everything in ntgen resolves beside its own files.
- Run the app with `python3 backend/app.py`; gate as above. No commits made (user choice);
  git shows `ntgen/*` deleted + `backend/` untracked until the next commit pairs them up.

2026-08-19 — give up / reveal (user-designed feature: "a cost for the solution"):
- **Any practice problem can be surrendered** (never diagnostic problems): streak
  resets to 0, the server retires the problem FIRST (outstanding + SERVED cleared and
  persisted — 410s forever, restart included), and only then does a **full worked
  solution** leave the server. New `backend/ntgen/steps.py`: 45 per-template renderers in
  14 method families (Euclid ladder, back-substitution, square-and-multiply, factor
  tables, CRT merging, ...), every line Python-computed prose; hand-authored pigeonhole
  reveals its stored `why`. Not an attempt — new `graph.reset_streak` touches only the
  streak; logged as grade `"revealed"` for week-3 analysis. PROJECT.md §5.3 records it.
- Gate grew teeth: selftest check #7 renders steps every trial and requires the final
  line's answer to grade correct — an independent derivation cross-checking every stored
  solution. **It immediately caught two real grading bugs** that had been serving wrong
  answers to students: `divisibility_basic_01` trusted its `r` param as the remainder
  (wrong whenever r was a nonzero multiple of a — ~4% of samples), and `crt_value` in
  verify.py returned sympy's non-reduced representative for non-coprime moduli
  (crt([12,8],[8,0]) -> 32 where the smallest is 8), so the truly smallest answer graded
  wrong on `crt_noncoprime_01`. Both fixed; gate green.
- leaktest: `steps` is the one allowed answer-bearing key; `reveal_check` proves
  retirement is total (re-grade 410, second reveal 410, restart-then-grade 410,
  restart-then-reveal still works, attempts unchanged); reveal mid-diagnostic 410s.
  140 responses audited.
- Frontend: two-click "Stuck? Show the steps (streak resets to 0)" button (arms, 4s
  auto-disarm), steps render as cards through pretty(), pips shake to 0; fixed the
  "Next problem" button to branch on done-state instead of the disabled input.

2026-08-19 — frontend restructured around a homescreen; curriculum phase opened:
- **Two directions from a new homescreen** (hash-routed SPA: `#/` home, `#/test`
  practice, `#/learn` curriculum): **Practice** = the entire existing flow (login →
  diagnostic → graph → practice/reveal) moved under one direction unchanged; **Learn** =
  placeholder shell with a `#curriculum-body` mount point, waiting for the user's
  curriculum content (user has it written; NOT yet handed over). Labels chosen by user.
  Brand in the header links home; back button hops directions; refresh inside Practice
  still resumes via login replay.
- **Wrong-origin (Live Server) now auto-redirects** instead of showing a link: boot
  health probe fails → no-cors probe of http://127.0.0.1:5001 → jump there (hash
  preserved); if the app is down, the warning card shows and a 2s poll jumps the moment
  it comes up. Verified all three branches with a simulated :5500 static server.
- Next: user hands over curriculum content → build Learn; then CP-C deploy (runbook below).

2026-08-19 — curriculum landed in the app (user delivered the v0.1 doc as PDF):
- **One authored artifact**: `backend/ntgen/curriculum.md` — all 22 tier-0/1 lessons
  transcribed verbatim (five sections each: Concept / Key results / Worked example /
  Common mistakes / Problem types; pigeonhole keeps its implementation note), plus tier
  intros, the tiers-2/3 outline, and the doc's "open decisions" appendix marked resolved
  with real outcomes. `backend/ntgen/curriculum.py` parses it (strict format, fail-fast
  CurriculumError) and `validate()` checks ids, tiers, and **prereq edges against the
  DAG exactly** — the doc stays the source of truth for edges, drift fails the gate.
  Served at `GET /api/curriculum`; selftest gained `check_curriculum`; leaktest audits
  the payload (prose fields scrubbed — teaching numbers are pedagogy, not keys) and
  asserts all 22 authored nodes teach.
- **Learn direction is live**: `#/learn` = index (tier headers + lesson rows with
  teasers + "what lies beyond" outline), `#/learn/<node_id>` = lesson page (prereq
  chips linking across lessons, concept lede, worked-example and common-mistakes
  panels, "What you'll be asked", prev/next in doc order, "Practice this →" CTA).
  Lessons are open to read — no login, no locking; gating stays practice's job.
  New `prettyLesson()` renderer handles variable-base powers (a^k, p^e, a^(p−1)).
- PROJECT.md §3 now lists the three curriculum artifacts (Doc → md → DAG).

2026-08-19 — frontend split into real pages + top-bar navigation (user request):
- **One file per page**: `index.html` (home), `learn.html`, `practice.html` at clean
  URLs `/`, `/learn`, `/practice` (two tiny Flask send_static_file routes). The SPA
  hash-direction router is gone; app.js was redistributed into `shared.js` (api, toast,
  pretty, wrong-origin auto-redirect — now preserves pathname), `learn.js` (curriculum
  render; lesson deep-link is `/learn#<node_id>`), `practice.js` (login → diagnostic →
  graph/practice/reveal — those remain flow states of one page, not pages).
- **Top bar navigates**: Home / Learn / Practice on every page, active link highlighted
  per file; brand still links home; home's direction cards are now plain `<a>` links.
- Boot pattern: every page loads shared.js first; it health-probes, then calls the
  page's `window.pageInit`. Wrong-origin warning card is injected dynamically so every
  page gets the auto-jump safety net without markup duplication.
- Gates green; /, /learn, /practice all 200 with correct nav + scripts.

CP-C parked runbook — PythonAnywhere free tier, researched & verified 2026-08-19
(deploy deferred by user; do this in the deploy session):
- Their current "innit" image ships **Flask 3.0.3 + SymPy 1.13.2**, inside
  requirements.txt's ranges → **zero pip installs, zero consoles**. The whole deploy
  drives over their HTTP API with just username + API token: upload each file
  (`POST /api/v0/user/U/files/path/home/U/ntgen-app/...`, multipart field `content`,
  ~1.6s apart for the 40 req/min limit) → create webapp (`POST .../webapps/`,
  `python_version=python313`) → `PATCH` `source_directory=/home/U/ntgen-app/backend`
  and `force_https=true` → write the WSGI file via the files API at
  `/var/www/U_pythonanywhere_com_wsgi.py` → `POST .../reload/`.
- WSGI file: set `os.environ["NTGEN_DATA_DIR"] = "/home/U/ntdata"` (outside the code
  tree, persistent disk) BEFORE `from app import app as application`; put backend/ on
  sys.path. NO static mappings — Flask serves frontend/ itself; a "/" mapping would
  shadow /api/*.
- Free apps now expire after **1 month** (changed Mar 2026, not the old 3): one
  "Run until 1 month from today" click renews — set a 3-week repeating reminder. Free
  tier = exactly 1 web worker (matches the single-process constraint by construction);
  the CPU-seconds cap does NOT apply to web apps, so SymPy grading is safe.
- Pre-deploy parity check: local venv pinned to `flask==3.0.3 sympy==1.13.2`, run both
  gates under it (local dev is Flask 3.1.3 / SymPy 1.14).
- Unverified, check live: the `python313` API literal; files-API writes under
  `/var/www/`. Dashboard fallback for both: create the app / paste the WSGI by hand.

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

VoltHacks entry: a number theory mastery platform. The subject is modeled as a 35-node
prerequisite DAG (`backend/ntgen/number-theory-dag.json`); a ~6-question diagnostic locates each
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
- **`pigeonhole_nt`**: 3–5 hand-authored problems in `backend/ntgen/hand_authored.json` with fixed
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

- **Every checkpoint**: `python3 backend/ntgen/selftest.py` green — 300 trials/template; correct
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

---

2026-08-22 — **Phase 2B: Bayesian Knowledge Tracing is the mastery engine.**
User supplied `BKT_SPEC.md` + reference `bkt.py`/`fit_bkt.py`; saved (spec at repo root
with an as-built-deltas appendix, code in `backend/ntgen/`), improved, and wired through
the whole stack. Four owner decisions (recorded in PROJECT.md §5.3): BKT decides mastery
at P ≥ 0.95 (streak demoted to UI); learning transition on **correct answers only**;
a reveal counts as wrong evidence (posterior only, no learning credit); sticky unlock +
honest colour (the per-student `unlocked` set only grows, fill always shows current P).

Load-bearing math, all gate-checked (`selftest.py check_bkt`):
- **3-corrects theorem** — with shipped params (slip .10 / guess .20 / learn .30 uniform,
  p_init .20 tier 0 / .10 tiers 1–3), three consecutive corrects cross 0.95 from ANY
  prior; two from cold never do. "About 3 in a row" survives as a theorem. (The
  reference per-tier slip/guess profiles broke this bound and were flattened.)
- **Propagation alone can never master** (backward lift ≤ 0.85 < 0.95) ⇒ the diagnostic
  now runs live BKT observations for the deltas AND keeps the proven bisection sets,
  which **calibrate** final priors at finish (tested 0.96 / inferred 0.95 / unknown
  ≤ 0.40). Without that step every student would finish locked at the root.
- **No forward-cap deadlock** (backward pass runs first inside propagate) — a practiced
  node can always master; guard considered and rejected. Quirk documented in the spec
  appendix: a node's dependents' priors put a soft floor (0.85·max) under direct
  negative evidence, so wrong/reveal drops on root-ish nodes are damped.

Plumbing: student JSON gains `"bkt": {version, p, unlocked}` (lazy migration in
`ensure_bkt` — legacy mastered → 0.96, streaks/attempts untouched; verified live on
ekansh.json); `graph.py` and `store.py` untouched; `record_answer` still maintains the
streak (pips + cut-order fallback). Payloads: every node in `state_payload` carries
`p` + percent `progress`; `/api/answer`, `/api/diagnostic/answer`, `/api/reveal` return
`"moved"` {node: delta} — graph.js paints continuous fill (navy→amber@.5→green@.95) and
`ripple()`s moved nodes sized by |delta| (red-tinted stroke on drops); diagnostic
feedback says "updated N skills". Copy de-promises "3 in a row" → "95% (about 3 in a
row)". Gates rewritten and green: selftest +check_bkt +replay-determinism in
check_diagnostic; leaktest +{p, moved} allow/scrub (float digit-substring hazard),
reveal = exactly {steps, streak, progress, moved, status}, corrects-≤-4 bound.
`fit_bkt.py` runs standalone (recovery errors ≤ .036) — judge demo, never gated.
Known break: `session_demo.py` predates the new `Diagnostic.result()` shape (CLI demo
only, not gated). Next: user browser eyeball, then CP-C deploy.

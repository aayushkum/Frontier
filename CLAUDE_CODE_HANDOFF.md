# CLAUDE CODE — BUILD SPEC

**Project:** VoltHacks number theory mastery platform
**Deadline:** early September 2026 (~31 days from Aug 5)
**Read first:** `PROJECT.md` (full context, rejected ideas, curriculum) and `number-theory-dag.json` (the graph).

---

## 0. READ THIS BEFORE WRITING ANY CODE

### 0.1 What already exists and MUST NOT be rewritten

There is working, tested code in `backend/ntgen/`. It passes 300 trials per template on 6 templates. **Do not regenerate these files from scratch.** Extend them.

| File | Status | Rule |
|---|---|---|
| `backend/ntgen/verify.py` | working | Extend with new checkers. Do not change `safe_eval`'s sandbox model. |
| `backend/ntgen/generator.py` | working | Extend. Sampling/derivation/constraint flow is correct as-is. |
| `backend/ntgen/templates.json` | 6 of ~22 templates | Add templates. Keep the schema exactly. |
| `backend/ntgen/selftest.py` | working | Extend coverage. This is the quality gate. |
| `backend/ntgen/demo.py` | working | Keep runnable at all times. |

If you believe one of these files is wrong, **say so and explain why before changing it.** Do not silently refactor.

### 0.2 The one architectural rule

**The LLM never produces an answer. SymPy does.**

An LLM writes problem *templates* (wording + parameter ranges + a solution *expression*). At serve time the app samples parameters and computes the answer with SymPy. There must be no code path where a model's text output becomes an answer key. If a feature seems to require it, stop and flag it.

Reason: LLM-generated math answers are wrong often enough to destroy a live demo. This is the project's core reliability claim and its main pitch differentiator.

### 0.3 Working style — this matters more than usual

The user is a strong programmer (FTC lead programmer, shipped a Firebase/JS web app) but **new to SymPy and to this generator pattern.** He is handing off implementation specifically so he can read working code and understand the flow from it. That means:

- **Explain each phase in 3-5 sentences before writing its code.** What the phase does, why it's structured that way, what would break without it.
- **Stop at every CHECKPOINT.** Do not continue to the next phase unattended. He needs to run it and see it work.
- **Comment the non-obvious lines**, not the obvious ones. `# increment counter` is noise. `# condition-checked: no stored answer exists for this node` is the point.
- **Prefer boring, readable code over clever code.** He has to defend this to judges.
- **If he asks "why is this like this," answer honestly** — including if the answer is "I did it that way and a simpler way exists."

### 0.4 Ask before assuming

These are genuinely undecided. Ask, do not pick for him:
- Frontend framework (he knows vanilla JS + Firebase from a prior project; React is also fine)
- Hosting (Vercel and Firebase both used before)
- Which LLM API for template generation
- Whether auth is needed at all for the demo

---

## 1. TARGET

A web app where a student:
1. Takes a ~6 question diagnostic that walks the prerequisite graph
2. Sees a colored graph of mastered / frontier / locked nodes
3. Practices at their frontier with unlimited generated, verified problems
4. Watches nodes unlock as they hit mastery

Scope discipline: **number theory only.** Tiers 2-3 render as locked and are never authored. Adding a second subject is explicitly rejected in `PROJECT.md` §2.4 — do not propose it.

---

## 2. PHASES

Each phase ends at a CHECKPOINT. **Halt there.**

---

### PHASE 1 — Complete the template library

**Goal:** templates covering all 22 tier 0-1 nodes, all passing `selftest.py`.

Currently covered: `divisibility`, `factorization`, `gcd_lcm`, `mod_exp`, `bezout`, `linear_congruence`.

Still needed: `primes`, `euclidean`, `divisor_functions`, `bases`, `digit_rules`, `congruence`, `mod_arith`, `mod_inverse`, `linear_diophantine`, `fermat_little`, `totient`, `euler_theorem`, `order`, `crt`, `wilson`.

Aim for **2-3 templates per node** so students don't see the same wording repeatedly.

**Per-node verification methods are specified in `PROJECT.md` §4.3.** Use them. Every one is a single SymPy call.

**Special cases — get these right:**

- `pigeonhole_nt`: **DO NOT GENERATE.** It is proof-flavoured and does not parameterize. Hand-author 3-5 problems in a separate `hand_authored.json` with a fixed answer key, or flag it for cutting. Letting a model freestyle here is exactly how a wrong answer reaches a judge.
- `linear_diophantine`: some questions ask for the full solution *family*, not a value. Needs a new checker. Consider asking for "smallest positive x" instead — a single integer, far easier to grade, and it still tests the concept.
- `crt`: include occasional **non-coprime moduli** cases, both consistent and inconsistent. The curriculum teaches this explicitly rather than hiding it.
- `mod_inverse`: roughly half the samples should have `gcd(a,n) > 1` so the answer is "no inverse exists." Needs a sentinel answer format.
- `bases`: answers are strings, not numbers. `check_exact` will not work — write `check_string_normalised`.

**Distractor requirements.** These templates must be constructed so the common mistake yields a *plausible* wrong answer (mistakes listed in `PROJECT.md` §4.4): `mod_arith` (illegal cancellation), `mod_exp` (exponent reduced mod n), `fermat_little` (exponent reduced mod p not p−1), `gcd_lcm` (lcm = ab), `divisor_functions` (e_i not e_i+1).

Record the predicted wrong value in the template's `distractor_note` field. Phase 5 uses these.

**CHECKPOINT 1:** `python selftest.py` shows all templates passing, ≥22 nodes covered. Show a sample problem from each new node. **STOP.**

---

### PHASE 2 — Graph engine and mastery state

**Goal:** load the DAG, track per-student mastery, compute the frontier.

Build `backend/ntgen/graph.py`:

- `load_graph(path)` — parse `number-theory-dag.json`
- `validate()` — **assert the graph is acyclic and every prereq id exists.** Run this in `selftest.py`. A typo'd prereq id would silently make a node permanently unreachable.
- `is_unlocked(node, mastery)` — true when every prereq is mastered
- `frontier(mastery)` — unlocked but not yet mastered
- `locked(mastery)` — everything else

Mastery rule: **3 consecutive correct per node** (`PROJECT.md` §5.3). Put it in one named constant. It must not change during user testing or the results become incomparable.

Mastery state shape:
```
{ node_id: {"streak": int, "attempts": int, "correct": int, "mastered": bool} }
```

**CHECKPOINT 2:** a script that loads the graph, simulates mastering a path, and prints frontier/locked at each step. **STOP.**

---

### PHASE 3 — Diagnostic

**Goal:** locate a student's frontier in ~6 questions.

Binary search over the DAG, not a linear quiz:
- Start at `congruence` — the school-math / contest-math boundary (`PROJECT.md` §5.1)
- Correct → jump forward along outgoing edges
- Wrong → walk back to prerequisites
- Stop after 6 questions or when the frontier is bracketed

Output: initial mastery state, with unvisited nodes inferred (mastered if downstream of a passed node, locked if upstream of a failed one). **Mark inferred nodes distinctly from tested ones** — inference is a guess and the UI should not present it as measured.

**CHECKPOINT 3:** run the diagnostic in the terminal against a simulated student with a known knowledge level. Verify it finds roughly the right frontier. **STOP.**

---

### PHASE 4 — Web app

**ASK the user for stack preference before starting.**

Backend (Python, since SymPy is Python):
- `POST /diagnostic/start`, `POST /diagnostic/answer`
- `GET /problem?node=` — generate and serve
- `POST /answer` — grade, update mastery, return correctness + hint on failure
- `GET /state` — mastery for the graph view

**Never send the answer to the client.** Grade server-side. Otherwise the demo can be trivially inspected in devtools by any judge who opens the network tab.

Frontend — three screens:
1. Diagnostic (one question at a time)
2. **Graph view — this is the demo money shot.** Mastered solid, frontier highlighted, locked greyed. Tiers 2-3 always locked, which makes the graph look deep at no authoring cost. Invest disproportionate effort here.
3. Practice (problem, input, feedback, streak toward mastery)

On mastery: an unlock animation on newly available nodes. **No leaderboard, no Elo** — rejected in `PROJECT.md` §2.3.

Render math with KaTeX or MathJax.

**CHECKPOINT 4:** end-to-end run in a browser — diagnostic → graph → practice → unlock. **STOP.**

---

### PHASE 5 — LLM template generation

**Deliberately last.** Everything above works without a model. This phase adds scale, not function.

Build `backend/ntgen/authoring.py`:
- Prompt an LLM with the node's curriculum entry (concept, assesses, common mistakes) and the exact `templates.json` schema
- Model returns a **template**, never a problem, never an answer
- Pipe output directly into `selftest.py`
- **Anything failing the gate is discarded automatically, without a human reading it**

Also: **distractor-aware hints.** On a wrong answer, check whether the student's value matches the predicted mistake from `distractor_note`. If so, give the specific hint ("you reduced the exponent mod n — Fermat reduces it mod p−1") rather than the generic one. This uses the graph rather than sitting beside it and is the strongest stretch feature available.

**CHECKPOINT 5:** generate 5 templates for an uncovered node, show pass/fail on the gate. **STOP.**

---

## 3. TESTING WEEK (user does this, not you)

Week 3 is real students from the user's FLL outreach program and FTC team. Before it:

- Log **every unparseable answer submission**. The `normalise` function in `verify.py` handles `\frac`, `^`, `\cdot`, `$` — real students will type things nobody anticipated. That log is the only reliable way to find the gaps.
- Log every problem served, answer given, and correctness, with timestamps.
- Make a retention/progress chart possible from the logs. At a month-long hackathon judges ask *who used it* — a rougher app with 15 real students beats a polished one with zero.

---

## 4. CUT ORDER IF BEHIND

Cut in this order. Do not improvise a different order.

1. Phase 5 entirely (hand-authored templates are fine for a demo)
2. `wilson` and `pigeonhole_nt` — both **leaves**, nothing depends on them, graph stays connected
3. Distractor-aware hints → generic hints
4. Diagnostic → let students self-select a starting node

**Never cut:** the graph view, symbolic verification, or the mastery mechanic. Those three *are* the project.

---

## 5. FINAL WEEK

**Stop building with 4 days left.** Writeup, video, and pitch are graded and are always underestimated.

Submission blurb (replaces the current buzzword version):

> Students hit contest math and don't know *where* they're missing prerequisites — they only know they're stuck. We model number theory as a prerequisite graph, run a short diagnostic to locate each student's exact knowledge frontier, and generate unlimited practice problems at that frontier with symbolically verified answers.

"Biggest challenge" answer: LLM-generated problems had wrong answers; solved by making the model emit symbolic templates while SymPy computes every answer. **Keep notes as this actually happens** — the real story beats an invented one.

If a judge asks how this differs from AoPS Alcumus: *Alcumus adapts difficulty; we diagnose which prerequisite is missing and show it on a graph.*

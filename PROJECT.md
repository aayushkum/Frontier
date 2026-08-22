# VoltHacks — Number Theory Mastery Platform

**Status:** Phases 1–3 complete. The generator/verifier layer works — templates for all 22 tier 0–1 nodes pass `selftest.py` — and the graph engine and diagnostic are built and green. Phase 4 (web app) is next.
**Deadline:** ~31 days from Aug 5, 2026 (early September).
**Team:** Ekansh + 1 friend. Role split UNDECIDED — see Open Questions.

---

## 1. What this is

A math learning platform that models a subject as a **prerequisite graph**, locates each student's exact knowledge frontier with a short diagnostic, and generates unlimited practice problems at that frontier with **symbolically verified** answers.

Scope for the hackathon: **number theory only**.

### The one-paragraph pitch

> Students hit contest math and don't know *where* they're missing prerequisites — they only know they're stuck. We model number theory as a prerequisite graph, run a short diagnostic to locate each student's exact knowledge frontier, and generate unlimited practice problems at that frontier with symbolically verified answers.

Use this instead of the current submission blurb, which reads "software based solution, offering STEM education through an AI-powered website to create better mathematical outcomes" — four buzzwords that describe nothing a judge can picture.

---

## 2. How we got here (decisions and why)

This section exists so that in week 3, when someone says "why don't we just add geometry," the answer is already written down.

### 2.1 Rejected: the 4×4 topic grid

The original plan was a 4×4 table — rows Core Foundation / Contest Foundation / Olympiad / Applied, columns Number Theory / Combinatorics / Geometry / Algebra.

**Why it was cut:**
- A grid has nodes but no edges. Without prerequisite relationships there is nothing for a diagnostic to traverse and nothing for an "AI review" to actually check.
- Cells were wildly uneven. "Graph Theory" is a semester, not a topic. "Advanced Functions" is not a meaningful label.
- The Applied row had one entry in two columns — the tell that the grid was filled to look complete rather than derived from anything.
- The Applied row was decoration. No demo student reaches RSA or Fourier transforms.

### 2.2 Rejected: "AI reviews the curriculum" as a feature

Students do not care whether an LLM approved the topic list. That is a one-time internal QA step, not a product. If it is the AI story in the pitch, the pitch is dead.

### 2.3 Rejected: Elo / leaderboard ranking

Elo needs a population. With 6–15 users a leaderboard is random noise, and it is the single most-copied feature in ed-tech demos. **Replaced with per-node mastery percentage + a "frontier unlocked" animation** — same dopamine, meaningful at small N, and it reinforces the graph rather than competing with it.

### 2.4 Rejected: adding back combinatorics / geometry / algebra

Even with 31 days. Two reasons:
1. A month-long hackathon raises the bar on *finish quality*, not surface area. Four half-built subjects lose to one that works.
2. **Number theory is the only strand where answers are cleanly machine-verifiable.** Geometry answers are diagrams and constructions. Combinatorics answers are expressions with many equivalent forms. Number theory answers are integers and residues that SymPy checks in one line. This is a real technical advantage — do not throw it away.

### 2.5 Competitive honesty

AoPS **Alcumus** already does adaptive math problems with difficulty tracking, free, with a 20-year problem bank. **Brilliant** exists. The differentiator must be stated in one sentence or judges will notice:

> Alcumus adapts difficulty. We diagnose *which prerequisite* is missing and show it on a graph.

If a judge asks "how is this different from Alcumus," that is the answer. Have it ready.

---

## 3. The curriculum

Three artifacts, kept in sync. **The doc is the source of truth; the others follow it.**

| Artifact | Purpose |
|---|---|
| `VoltHacks — Number Theory Curriculum (v0.1 draft)` (Google Doc) | Human-editable. Full teaching content per node. |
| `backend/ntgen/curriculum.md` | In-repo transcription of the doc. Parsed at boot and served at `/api/curriculum` — this is what students read in the app's Learn direction. The gate validates its ids, tiers, and prereq edges against the DAG. |
| `number-theory-dag.json` | Machine-readable. Loaded directly by the app. |

Google Doc: https://docs.google.com/document/d/1Gx_azLCG9ULTTORTU8p1uzRtQBfm2Y3rQdRHFQxlG7o/edit

### 3.1 Structure

35 nodes across 4 tiers. Each node has: `id`, `name`, `tier`, `prereqs[]`, `concept`, `assesses`, `generator`, `verify`.

Prereqs are **hard edges**: a student cannot be served a problem from a node until every prereq is mastered.

### 3.2 Tiers

| Tier | Name | Nodes | Authored? |
|---|---|---|---|
| 0 | Core foundation | 8 | Full teaching content |
| 1 | Contest foundation | 14 | Full teaching content |
| 2 | Olympiad | 10 | Outline only |
| 3 | Applied / computational | 3 | Outline only |

Tiers 2–3 exist so the graph has **visible depth** in the demo. Render them greyed out and locked. Do not author problems for them unless there is time left after real student testing.

### 3.3 Tier 0 — Core foundation

| id | Name | Prereqs |
|---|---|---|
| `divisibility` | Divisibility and multiples | — |
| `primes` | Primes and composites | divisibility |
| `factorization` | Prime factorization | primes |
| `gcd_lcm` | GCD and LCM | factorization |
| `euclidean` | Euclidean algorithm | gcd_lcm |
| `divisor_functions` | Divisor count and sum | factorization |
| `bases` | Base representation | divisibility |
| `digit_rules` | Digit sums and divisibility rules | bases, divisibility |

### 3.4 Tier 1 — Contest foundation

| id | Name | Prereqs |
|---|---|---|
| `congruence` | Congruence relation | divisibility, euclidean |
| `mod_arith` | Modular addition and multiplication | congruence |
| `mod_exp` | Modular exponentiation | mod_arith, bases |
| `bezout` | Bezout's identity | euclidean |
| `mod_inverse` | Modular inverses | mod_arith, bezout |
| `linear_diophantine` | Linear Diophantine equations | bezout |
| `linear_congruence` | Linear congruences | mod_inverse, linear_diophantine |
| `fermat_little` | Fermat's little theorem | mod_exp, mod_inverse |
| `totient` | Euler's totient function | factorization, congruence |
| `euler_theorem` | Euler's theorem | totient, fermat_little |
| `order` | Multiplicative order and cyclicity | euler_theorem |
| `crt` | Chinese remainder theorem | linear_congruence |
| `wilson` | Wilson's theorem | fermat_little |
| `pigeonhole_nt` | Pigeonhole in number theory | congruence |

### 3.5 Tiers 2–3 (outline)

**Tier 2:** `p_adic` → `legendre_formula` → `lte`; `quadratic_residues` → `legendre_symbol`; `primitive_roots`; `multiplicative_functions` → `mobius_inversion`; `descent`; `sum_two_squares`.

**Tier 3:** `sieve`; `primality_testing`; `rsa` (from euler_theorem + mod_inverse + primality_testing — a genuine endpoint with real edges, not decoration).

### 3.6 Non-obvious curriculum choices — do not silently revert these

**`bezout` sits BEFORE `mod_inverse`.** Most curricula teach inverses first and Bézout later as trivia. That is backwards — extended Euclid is *how* you construct an inverse. If you flip this edge, students memorize inverse tables instead of constructing them, and the diagnostic cannot tell the difference.

**`totient` branches off `factorization`, NOT off `fermat_little`.** phi is a counting fact about factorizations; it does not need Fermat. Wiring it downstream of Fermat would assert a prerequisite that does not exist and would lock students out of a node they can already do.

**`digit_rules` is framed as the first modular arithmetic, one tier early.** The rule for 3 and 9 works because 10 ≡ 1; the rule for 11 alternates because 10 ≡ −1. Teaching it as a memorized trick means reteaching the same fact three nodes later.

**`pigeonhole_nt` is marked non-generated.** It is proof-flavoured and does not parameterize cleanly. Hand-author 3–5 problems or cut the node. **Do not let the LLM freestyle it** — that is exactly where it will hallucinate a wrong answer live on stage.

---

## 4. The technical core: verified problem generation

**This is the highest-risk part of the project and the most interesting part of the pitch. Build it first.**

### 4.1 The problem

LLMs produce math problems with wrong answers at a rate that will humiliate you during a live demo. A single wrong answer in front of a judge destroys credibility for the entire submission.

### 4.2 The solution

**The LLM never produces the answer.**

Pipeline:
1. LLM emits a **parameterized template** — problem wording with slots, plus a symbolic solution expression. Not a concrete problem.
2. Template is stored and reused.
3. At serve time, sample random parameters within declared ranges.
4. Compute the answer with **SymPy** (server) or **math.js** (client) from the symbolic solution.
5. Grade by **symbolic equivalence**, not string match, so `1/2`, `0.5`, and `\frac{1}{2}` all pass.

Consequences: infinite problems per node, provably correct answers, and the LLM cost is paid once per template rather than once per problem.

### 4.3 Per-node verification methods

Every tier 0–1 node has a one-line reference check:

| Node | Verify with |
|---|---|
| `divisibility` | integer equality |
| `primes` | `sympy.isprime` |
| `factorization` | `sympy.factorint` dict equality |
| `gcd_lcm` | `sympy.gcd` / `sympy.lcm` |
| `euclidean` | `sympy.gcd`; step count from reference impl |
| `divisor_functions` | `sympy.divisor_count` / `divisor_sigma` |
| `bases` | string equality after normalization |
| `digit_rules` | modular check over all 10 digit values |
| `congruence`, `mod_arith` | integer arithmetic |
| `mod_exp`, `fermat_little`, `euler_theorem` | `pow(a, k, n)` |
| `bezout` | **evaluate `ax + by == gcd(a,b)`** — answer is NOT unique |
| `mod_inverse` | check `a*x ≡ 1 (mod n)` |
| `linear_diophantine` | substitution check + minimality scan |
| `linear_congruence` | brute-force residue scan on reference side |
| `crt` | `sympy.ntheory.modular.crt` |
| `totient` | `sympy.totient` |
| `order` | `sympy.n_order` |
| `wilson` | direct factorial mod |
| `pigeonhole_nt` | hand-authored key |

**`bezout` is the case that proves the design.** The answer is not unique — any valid (x, y) is correct. If you hardcode one stored answer there, you will mark correct students wrong. The grader must *evaluate the condition*, not compare to a key. Build this node early specifically because it forces the grader architecture to be right.

**Unparseable input never reaches these checkers.** If `normalise()` cannot read a submission, it is rejected with a "couldn't read that" message before grading — it is not an attempt and does not touch the streak (mastery rule, §5.3). Every unparseable submission must be logged for week 3 analysis: each one is either a UI gap or an answer-format instruction that failed to communicate.

### 4.4 Distractor design

Some nodes need problems specifically constructed so that the common mistake produces a *plausible wrong answer*, not an obvious one. These are the mistakes worth detecting and hinting on:

- `mod_arith`: cancelling a common factor from both sides (looks legal, isn't)
- `mod_exp`: reducing the exponent mod n instead of the base
- `fermat_little`: reducing the exponent mod p instead of p−1
- `linear_congruence`: reporting one solution when gcd(a,n) > 1 gives several
- `gcd_lcm`: assuming lcm(a,b) = ab
- `divisor_functions`: using e_i instead of e_i + 1

---

## 5. Diagnostic and mastery

### 5.1 Diagnostic

Binary search over the DAG. Do **not** ask 40 questions. Ask ~6:
- Pass a node → jump forward along outgoing edges.
- Fail a node → walk back to prerequisites.

**Suggested start point: `congruence` (1.1).** Starting at the root wastes questions on strong students; starting deep confuses weak ones. `congruence` sits at the natural boundary between school math and contest math — which is exactly the gap the pitch claims to close.

### 5.2 Output — the demo money shot

A colored graph:
- **Mastered** — solid
- **Frontier** — highlighted, currently available
- **Locked** — greyed (includes all of tiers 2–3)

This visualization *is* the demo. Alcumus does not show it. Build it well.

### 5.3 Mastery rule

Decided. Five choices, frozen together:

**Threshold: three consecutive correct per node.** Frozen — it must not change during user testing or results collected before and after the change stop being comparable. It lives as one named constant in code (`MASTERY_STREAK` in `backend/ntgen/graph.py`) and nowhere else.

**Reset: a wrong answer resets the streak to zero,** not decrement-by-one. "Three in a row" is a defensible, sayable mastery claim; decrement-by-one lets a student alternate right and wrong indefinitely without ever mastering or failing.

**Unparseable submissions do not count as attempts.** If `normalise()` in `verify.py` cannot parse the input, reject it with a "couldn't read that" message and leave the streak untouched. A typo is a formatting slip, not a math error, and should not cost a streak. Only parseable answers count as attempts.

**UI: show the streak as filling pips** (○○○ → ●○○ → ●●○) that visibly clear on a miss, so the reset reads as a mechanic rather than invisible punishment.

*Accuracy caveat:* a 3-streak means three consecutive correct, **not** a clean record on the node — a student may miss several times and then master it. UI copy should say "3 in a row," never "perfect."

**Reveal (give up) — decided 2026-08-19.** In practice only — never during the diagnostic — a student may surrender the current problem at any time and see a full worked solution, computed by Python (`backend/ntgen/steps.py`), never by an LLM. The cost: the node's streak resets to zero. A surrender is **not** an attempt (attempts/correct stay untouched, it is never recorded as a wrong answer); it is logged to `events.jsonl` as its own event kind `revealed` — week-3 accuracy scripts must exclude it from the correct/wrong/unparseable enum, and "which templates get surrendered on" is itself a too-hard signal worth reading. The server **retires the problem before the solution leaves it** (a revealed problem can never be graded, even after a restart), which is how this coexists with the answers-never-leave-the-server rule: that rule now reads "answers for *gradable* problems never leave the server." The cost is per-node, not per-reveal — once the streak is 0, further reveals cost nothing more; that is fine because mastery still requires three unaided corrects, so reveals can never light up a node.

**Bayesian Knowledge Tracing — decided 2026-08-22 (Phase 2B, supersedes the streak as the *mechanic*).** Mastery is now `P(mastered) ≥ 0.95` per node, from a BKT model (`backend/ntgen/bkt.py`, spec + as-built deltas in `BKT_SPEC.md`) whose evidence propagates along the prerequisite edges. Four sub-decisions, made together:

1. *BKT decides mastery; the streak is UI.* The pips and the reset-to-zero mechanic stay on screen exactly as before, but they no longer gate anything. The pacing is preserved as a checked theorem, not a hope: with the shipped parameters, three consecutive corrects cross 0.95 from **any** prior (and two from a cold prior never do), so "about 3 in a row" remains true — while a strong diagnostic can earn a 2-correct mastery and a struggling run can take more. `selftest.py check_bkt` gates this bound.
2. *Learning transition on correct answers only* (documented deviation from textbook BKT). A wrong answer strictly lowers P — no node ever brightens after a miss.
3. *A reveal is evidence.* Surrendering applies the wrong-answer posterior (no learning credit) and propagates. Still not an attempt; the streak wipe stays.
4. *Sticky unlock, honest colour.* Once unlocked, a node never re-locks (the per-student `unlocked` set only grows), but its fill colour always shows current P — a mastered node can honestly fade below threshold and needs at most 3 corrects to re-cross.

Still frozen from the original five: reset-to-zero on a wrong answer (now both streak and posterior), and unparseable-is-not-an-attempt (the model never sees a typo). The diagnostic keeps its proven graph-bisection sets and adds live BKT observation; because backward propagation maxes at 0.85·P < 0.95, the finish **calibrates** priors from the sets (tested 0.96 / inferred 0.95 / unknown capped 0.40) — without that step no student could ever unlock past the root. Cut order: if BKT breaks before demo day, revert to the streak mechanic (`MASTERY_STREAK` and `record_answer` still fully maintain it under the hood — the cut is one payload change, not a rebuild).

When a student is stuck at their frontier, the LLM gives a nudge based on **which prerequisite they are weakest at**, not the answer. This is genuinely differentiated, it *uses* the DAG rather than sitting beside it, and it was impossible in a 24-hour hackathon. This is where slack time goes — not into a second subject.

---

## 6. Timeline

### Budget reality

31 calendar days for two grade-11 students in August is **not** 31 days of work. Robotics and other commitments, plus days nobody feels like touching it. Plan against **60–90 hours across both people**, not 31 days.

### Week 1 — risk week

Build the generator + SymPy verification loop for **six nodes and nothing else**. No UI beyond a text box.

The goal is to find out whether LLM-generated parameterized templates actually produce clean problems. **If they don't, you need to know on day 5, not day 22.**

Suggested six: `divisibility`, `factorization`, `gcd_lcm`, `congruence`, `mod_exp`, `bezout`. (`bezout` included deliberately — it forces the non-unique-answer grader.)

### Week 2 — the product

- Diagnostic traversal over the DAG
- Mastery visualization
- Problems for all 22 tier 0–1 nodes

### Week 3 — real users

Put it in front of actual students. **Ekansh has an unfair advantage here that most teams don't: the FLL outreach program and the FTC team are a ready-made user pool.** Nobody else at VoltHacks can get 15 real students in a month.

**Watch them use it without helping.** This will be uncomfortable and will surface things you cannot predict from your desk.

At a month-long hackathon, judges ask "who used it?" A working prototype with zero users loses to a rougher one with 15 students and a retention chart.

### Week 4 — ship

Fix what week 3 broke, then **stop building**. Reserve **at least four days** for writeup, video, and pitch. These are graded and teams always underestimate them.

---

## 7. Submission answers

**What problem does your project solve?** — Use the pitch in §1. The "gap between school pedagogy and contest math" framing is good and true; keep it. Cut the buzzword sentence after it.

**What technologies did you use?** — TBD, pending stack decision (§8).

**What was the biggest challenge?** — TBD, but **start keeping notes now.** The honest answer is probably "LLM-generated problems had wrong answers, and we solved it by making the LLM emit symbolic templates while SymPy computes the answers." That is a far stronger story than anything invented on day 30. Write it down when it happens.

---

## 8. Open questions — settle these before week 2

1. **Role split.** If both people are full-stack you will collide on the same files all month. Decide now: who owns generation/verification, who owns frontend/visualization. Solve this in week 1.
2. **Tech stack.** Undecided. Constraint: SymPy is Python, so either a Python backend or math.js on the client. Prior experience with Firebase and Vercel (from R-Tracker) is relevant.
3. **Does `pigeonhole_nt` stay?** Only tier 1 node that cannot be auto-generated. Keeping it costs hand-authoring time; cutting it removes the only proof-style reasoning from the demo.
4. **Mastery threshold.** ~~Pick the number (default 3) and freeze it before student testing.~~ Decided — see §5.3: three consecutive correct, reset-to-zero on a miss, unparseable input doesn't count, frozen through user testing.
5. **What gets cut if you fall behind?** `wilson` and `pigeonhole_nt` are both **leaves** — nothing depends on them. They are the two cheapest cuts and the graph stays connected. Cut these before cutting anything structural.

---

## 9. File inventory

| File | Location | Purpose |
|---|---|---|
| Curriculum doc (v0.1) | Google Docs (link in §3) | Source of truth, human-editable |
| `number-theory-dag.json` | local | Machine-readable graph, loaded by app |
| `PROJECT.md` | this file | Full project context |

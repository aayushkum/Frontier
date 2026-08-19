"""
selftest.py — run this before you trust a template.

This is the gate from PROJECT.md section 4.3: if a node cannot pass here,
it is not ready to be served to students.

Checks per template:
  1. It generates without crashing, many times.
  2. The correct answer is graded correct.
  3. Formatting variants of the correct answer are also graded correct.
  4. A deliberately wrong answer is graded wrong.
  5. Garbage input is graded wrong without raising.

Templates may carry a "selftest" block — and condition-checked templates
MUST, because they have no stored answer the gate could use:

    "selftest": {
      "good":  ["<expr producing a correct answer>", ...],
      "wrong": ["<expr producing an incorrect answer>", ...]
    }

The expressions run in the same sandbox as solution expressions, with the
problem's params in scope. A tuple/list result is formatted as
comma-separated values, matching how a student types a pair or a set.
"""

import random
import sys

from generator import (
    load_templates, generate, load_hand_authored, hand_authored_problem,
)
from verify import TemplateError, safe_eval, is_sentinel
from graph import load_graph, GraphError, is_mastered
from diagnostic import Diagnostic, SimulatedStudent, MAX_QUESTIONS

TRIALS = 300

# Ways a student might phrase "no such value exists". The gate checks that
# every one of these is accepted when that IS the answer, and rejected when
# a real answer exists.
NONE_PHRASINGS = ["none", "None", "  none  ", "no solution", "DNE"]


def fmt(value):
    """Render an expression result the way a student would type it."""
    if isinstance(value, (tuple, list)):
        return ", ".join(str(v) for v in value)
    return str(value)


def format_variants(answer, checker):
    """Ways a student might legitimately type the same value."""
    variants = [str(answer)]
    if checker == "string":
        # Base representations: whitespace and $...$ wrappers are noise, but
        # "1011.0" is NOT the same answer, so no decimal variant here.
        variants.append(f" {answer} ")
        variants.append(f"${answer}$")
        return variants
    try:
        n = int(answer)
        variants.append(f" {n} ")
        variants.append(f"{n}.0")
        if n != 0:
            variants.append(f"$ {n} $")
    except (TypeError, ValueError):
        pass
    return variants


def check_no_solution_case(p):
    """
    The correct answer is "no such value exists".

    Every reasonable phrasing must be accepted, and a made-up number must be
    rejected — otherwise a student who correctly spots that an inverse does
    not exist gets marked wrong, which is the worst possible failure on the
    exact node where that insight is the skill being tested.
    """
    out = []
    for phrasing in NONE_PHRASINGS:
        if not p.check(phrasing):
            out.append(f"no-solution phrasing rejected: {p.prompt} -> {phrasing!r}")
    for bogus in ["0", "1", "7"]:
        if p.check(bogus):
            out.append(f"number accepted though no answer exists: {p.prompt} -> {bogus}")
    return out


def test_template(tpl, rng):
    failures = []
    seen_prompts, seen_answers = set(), set()
    distractor_differed = 0

    for i in range(TRIALS):
        try:
            p = generate(tpl, rng)
        except TemplateError as e:
            failures.append(f"generation failed: {e}")
            break

        checker = tpl.get("checker", "exact")
        st = tpl.get("selftest", {})
        seen_prompts.add(p.prompt)
        seen_answers.add(str(p._answer))

        if checker == "condition":
            # No stored answer exists for this checker, so the template itself
            # must say how to build correct and incorrect answers.
            if not st.get("good") or not st.get("wrong"):
                failures.append("condition template needs selftest.good and selftest.wrong")
                break

        elif checker == "unordered_set":
            sols = p._answer
            # An empty solution set means "no solutions exist" — graded the
            # same way as a sentinel answer, not as an empty string.
            if is_sentinel(sols) or len(sols) == 0:
                failures += check_no_solution_case(p)
            else:
                joined = ", ".join(str(s) for s in sols)
                if not p.check(joined):
                    failures.append(f"correct set rejected: {p.prompt} -> {joined}")
                # reversed order must still pass
                rev = ", ".join(str(s) for s in reversed(list(sols)))
                if not p.check(rev):
                    failures.append(f"reversed set rejected: {p.prompt}")
                # only the first solution must FAIL (the whole point of this node)
                if len(sols) > 1 and p.check(str(sols[0])):
                    failures.append(f"partial answer accepted: {p.prompt}")
                if p.check("none"):
                    failures.append(f"'none' accepted though solutions exist: {p.prompt}")

        else:
            ans = p._answer
            if is_sentinel(ans):
                failures += check_no_solution_case(p)
            else:
                for v in format_variants(ans, checker):
                    if not p.check(v):
                        failures.append(f"variant rejected: {p.prompt} -> {v!r}")
                # alternate accepted forms (e.g. -1 alongside p-1 in Wilson)
                for expr in tpl.get("also_accept", []):
                    alt = fmt(safe_eval(expr, p.params))
                    if not p.check(alt):
                        failures.append(f"also_accept rejected: {p.prompt} -> {alt!r}")
                # claiming no answer exists when one does must be rejected
                if p.check("none"):
                    failures.append(f"'none' accepted though an answer exists: {p.prompt}")
                # off-by-one only makes sense for numeric answers
                if checker != "string":
                    try:
                        wrong = str(int(ans) + 1)
                    except (TypeError, ValueError):
                        wrong = None
                    if wrong is not None and p.check(wrong):
                        failures.append(f"off-by-one accepted: {p.prompt}")

        # distractor_expr predicts the value a student produces when they make
        # this node's classic mistake. Phase 5 uses it for targeted hints, so
        # it must at least evaluate without crashing.
        dexpr = tpl.get("distractor_expr")
        if dexpr:
            try:
                if str(safe_eval(dexpr, p.params)) != str(p._answer):
                    distractor_differed += 1
            except TemplateError as e:
                failures.append(f"distractor_expr failed to evaluate: {e}")

        # template-declared good/wrong answers, applied under any checker
        for expr in st.get("good", []):
            good = fmt(safe_eval(expr, p.params))
            if not p.check(good):
                failures.append(f"selftest.good rejected: {p.prompt} -> {good!r}")
        for expr in st.get("wrong", []):
            wrong = fmt(safe_eval(expr, p.params))
            if p.check(wrong):
                failures.append(f"selftest.wrong accepted: {p.prompt} -> {wrong!r}")

        # --- garbage must fail quietly ---
        for junk in ["", "banana", "??", "1/0"]:
            try:
                if p.check(junk):
                    failures.append(f"garbage accepted: {junk!r}")
            except Exception as e:
                failures.append(f"garbage raised instead of returning False: {e}")

        if failures:
            break

    # A sampler that always produces the same problem passes every check above
    # while being useless — the student sees one question forever. Catch it
    # here rather than in front of a class. This also matters for phase 5,
    # where LLM-written templates are auto-discarded on gate failure with no
    # human reading them.
    # A distractor that always equals the correct answer signals nothing — the
    # student who "makes the mistake" is right, so the hint could never fire.
    if not failures and tpl.get("distractor_expr") and distractor_differed == 0:
        failures.append(
            "distractor_expr always equals the correct answer — it cannot "
            "identify a mistake"
        )

    if not failures:
        if len(seen_prompts) < 2:
            failures.append(
                f"degenerate sampler: {TRIALS} trials produced 1 distinct prompt"
            )
        elif (
            len(seen_answers) < 2
            and tpl.get("checker") != "condition"
            # Some templates are deliberately always the same answer — the
            # "this congruence has no solutions" drill, for instance. Those
            # must SAY so, so that an accidental collapse still fails here.
            and not tpl.get("constant_answer_by_design")
        ):
            failures.append(
                f"degenerate answers: {TRIALS} trials produced 1 distinct answer "
                f"({seen_answers.pop()!r})"
            )

    return failures


def test_hand_authored(entry):
    """
    Hand-authored problems have a STORED key, so SymPy cannot vouch for them.
    The gate checks what it still can: the key grades itself correct, obvious
    variants pass, a wrong value fails, and the entry carries the written
    argument that justifies its answer.
    """
    failures = []
    p = hand_authored_problem(entry)

    if not str(entry.get("why", "")).strip():
        failures.append("no 'why' field — a stored answer with no written argument")

    for v in format_variants(entry["answer"], entry.get("checker", "exact")):
        if not p.check(v):
            failures.append(f"stored answer rejected: {v!r}")

    try:
        wrong = str(int(entry["answer"]) + 1)
        if p.check(wrong):
            failures.append(f"off-by-one accepted: {wrong}")
    except (TypeError, ValueError):
        pass

    for junk in ["", "banana", "??", "1/0"]:
        try:
            if p.check(junk):
                failures.append(f"garbage accepted: {junk!r}")
        except Exception as e:
            failures.append(f"garbage raised instead of returning False: {e}")

    return failures


def check_graph(templates, hand):
    """
    Structural check on the DAG. A prereq id with a typo would make its node
    permanently unreachable while every template still passed, so this runs
    inside the same gate rather than beside it.
    """
    available = {t["node"] for t in templates.values()} | {e["node"] for e in hand.values()}
    graph = load_graph()
    try:
        warnings = graph.validate(available_nodes=available)
    except GraphError as e:
        print(f"FAIL  graph  ({e})")
        return False
    print(f"ok    graph  {len(graph)} nodes, acyclic, all prereqs resolve")
    for w in warnings:
        print(f"      warning: {w}")
    return True


def check_diagnostic():
    """
    The diagnostic must stay inside its question budget and must never hand a
    student a frontier node whose prerequisites are not mastered — that would
    serve someone a problem they have no route to.
    """
    G = load_graph()
    failures = []
    profiles = [
        ("knows nothing", [], ["divisibility"]),
        ("early tier 0", ["primes"], None),
        ("finished tier 0", ["euclidean", "divisor_functions", "digit_rules"], None),
        ("into tier 1", ["mod_arith", "bezout"], None),
        ("all authored", ["order", "wilson", "pigeonhole_nt", "digit_rules"], None),
    ]
    for label, knows, expect_frontier in profiles:
        student = SimulatedStudent(G, knows)
        d = Diagnostic(G)
        mastery = d.run(student.answer)

        if d.asked > MAX_QUESTIONS:
            failures.append(f"{label}: asked {d.asked} questions, budget is {MAX_QUESTIONS}")
        if d.known & d.unknown:
            failures.append(f"{label}: nodes both known and unknown: {d.known & d.unknown}")

        frontier = G.frontier(mastery)
        for n in frontier:
            if not G.is_authored(n):
                failures.append(f"{label}: frontier contains unauthored node {n}")
            missing = [p for p in G.prereqs(n) if not is_mastered(mastery, p)]
            if missing:
                failures.append(f"{label}: frontier node {n} needs unmastered {missing}")
        if expect_frontier is not None and frontier != expect_frontier:
            failures.append(f"{label}: frontier {frontier} != expected {expect_frontier}")

    if failures:
        print("FAIL  diagnostic")
        for f in failures[:3]:
            print(f"        {f}")
        return False
    print(f"ok    diagnostic  {len(profiles)} student profiles, "
          f"<={MAX_QUESTIONS} questions each")
    return True


def main():
    rng = random.Random(20260805)
    templates = load_templates()
    hand = load_hand_authored()
    all_ok = check_graph(templates, hand)
    all_ok = check_diagnostic() and all_ok

    for tid, tpl in templates.items():
        failures = test_template(tpl, rng)
        if failures:
            all_ok = False
            print(f"FAIL  {tid}  ({tpl['node']})")
            for f in failures[:3]:
                print(f"        {f}")
        else:
            print(f"ok    {tid}  ({tpl['node']})  {TRIALS} trials")

    for hid, entry in hand.items():
        failures = test_hand_authored(entry)
        if failures:
            all_ok = False
            print(f"FAIL  {hid}  ({entry['node']}, hand-authored)")
            for f in failures[:3]:
                print(f"        {f}")
        else:
            print(f"ok    {hid}  ({entry['node']}, hand-authored)")

    nodes = {t["node"] for t in templates.values()} | {e["node"] for e in hand.values()}
    print()
    print(f"{len(templates)} generated templates + {len(hand)} hand-authored, "
          f"covering {len(nodes)} nodes.")
    if all_ok:
        print("All passed.")
    else:
        print("Some failed. Do not serve these.")
        sys.exit(1)


if __name__ == "__main__":
    main()

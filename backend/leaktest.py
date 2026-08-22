"""
leaktest.py — proves no answer ever leaves the server.

    python3 backend/leaktest.py    (exit 0 = pass)

Runs beside backend/ntgen/selftest.py as the second half of the standing gate:

    python3 backend/ntgen/selftest.py && python3 backend/leaktest.py

It drives full sessions through the API in-process (Flask test_client, no
network, no server) and holds every response to four checks:

  1. Key allowlist — every dict key in every response must be expected.
     A future debug field that dumps a Problem fails here.
  2. Forbidden keys — answer, solution, params, template_id etc. hard-fail
     anywhere (params + template_id together recompute the answer).
  3. Problem payloads carry EXACTLY the five public fields.
  4. Answer-value scan — the computed answer of every problem served in the
     session must not appear anywhere in the response outside display text.

It also asserts the behavioural rules the UI will rely on: unparseable input
advances nothing (PROJECT.md 5.3), skip consumes a diagnostic question, a
server restart mid-problem grades identically after the rebuild, and the
input guard in app.py rejects no legitimate answer in the whole corpus.

One deliberate exception to "no answer ever": POST /api/reveal (give up)
returns a worked solution — but only for a problem the server has already
retired. reveal_check() proves the retirement is total: the revealed
problem 410s on every later grade or reveal, even across a restart, and a
surrender never counts as an attempt.
"""

import json
import os
import random
import re
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE / "ntgen"))

# Point the store at a throwaway directory BEFORE the app is imported, so
# nothing here can ever touch real student files.
os.environ["NTGEN_DATA_DIR"] = tempfile.mkdtemp(prefix="ntgen-leaktest-")

import app as webapp                    # noqa: E402
from generator import generate          # noqa: E402
from selftest import format_variants    # noqa: E402
from verify import is_sentinel, safe_eval  # noqa: E402


NODE_IDS = set(webapp.G.order)

ALLOWED_KEYS = {
    # problem payload (exactly these five inside "problem")
    "problem_id", "node", "node_name", "prompt", "answer_format", "problem",
    # session
    "student", "display_name", "phase", "ok", "error",
    # diagnostic
    "done", "question_number", "max_questions", "summary", "questions",
    "tested_pass", "tested_fail", "inferred_mastered", "inferred_locked",
    # graph + state
    "nodes", "edges", "status", "source", "streak", "attempts", "progress",
    "frontier", "id", "name", "tier", "authored", "x", "y",
    # grading
    "grade", "just_mastered", "newly_unlocked", "hint",
    # knowledge tracing: per-node P(mastered) and the per-answer delta map
    "p", "moved",
    # the reveal's worked solution — the one answer-bearing field, and only
    # ever for an already-retired problem (see reveal_check)
    "steps",
    # curriculum payload (static teaching content, /api/curriculum)
    "tiers", "lessons", "blurb", "number", "prereqs", "concept",
    "key_results", "worked_example", "common_mistakes", "problem_types",
    "note", "beyond",
} | NODE_IDS

FORBIDDEN_KEYS = {
    "answer", "_answer", "solution", "check_spec", "also_accept", "selftest",
    "distractor_expr", "distractor_note", "why", "params", "template_id",
}

PROBLEM_KEYS = {"problem_id", "node", "node_name", "prompt", "answer_format"}

# Removed before the answer-value scan: display text that legitimately
# contains numbers (a prompt contains its params), structural counters, and
# random ids. Everything that survives is enums and node ids — any answer
# value found there is a real leak.
SCRUB = {
    "prompt", "answer_format", "hint", "node_name", "name", "display_name",
    "created", "updated", "ts", "streak", "attempts", "question_number",
    "max_questions", "x", "y", "tier", "questions", "progress", "problem_id",
    # identity echo — the client sent this value itself, it can't leak
    "student",
    # the reveal's steps deliberately state the answer of a RETIRED problem;
    # selftest's check #7 is the compensating control on their content
    "steps",
    # curriculum prose legitimately contains numbers (worked examples,
    # formulas) — fixed pedagogy, not answer keys
    "blurb", "concept", "key_results", "worked_example", "common_mistakes",
    "problem_types", "note", "beyond", "number",
    # knowledge-tracing floats: "0.87" stringifies containing "87" — a pure
    # model probability would false-positive against a served answer of 87
    "p", "moved",
}


def fmt(value):
    if isinstance(value, (tuple, list)):
        return ", ".join(str(v) for v in value)
    return str(value)


def correct_answer(p):
    """What a right student would type. Condition-checked problems have no
    stored answer, so one is built from the template's own selftest.good."""
    a = p._answer
    if a is None:
        a = safe_eval(p._template["selftest"]["good"][0], p.params)
    if is_sentinel(a) or (isinstance(a, (list, tuple)) and len(a) == 0):
        return "none"  # an empty solution set is answered in words
    return fmt(a)


def wrong_answer_for(p):
    """Something this problem definitely grades wrong — never unparseable,
    since that would not consume the attempt we are trying to test."""
    for cand in ["0", "1", "none", "-1", "0, 0", "zzz"]:
        if p.grade(cand) == "wrong":
            return cand
    raise AssertionError(f"no wrong answer found for {p.prompt}")


# ---------------------------------------------------------------------------
# Response checking
# ---------------------------------------------------------------------------

def _walk_keys(obj, path, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_KEYS:
                out.append(f"forbidden key {k!r} at {path}")
            elif k not in ALLOWED_KEYS:
                out.append(f"unexpected key {k!r} at {path}")
            _walk_keys(v, f"{path}.{k}", out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk_keys(v, f"{path}[{i}]", out)


def _scrub(obj):
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items() if k not in SCRUB}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


def _leaves(obj, out):
    if isinstance(obj, dict):
        for v in obj.values():
            _leaves(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _leaves(v, out)
    else:
        out.append(obj)


class Checker:
    """Accumulates every answer served during a session and audits every
    response against all of them."""

    def __init__(self):
        self.answers = set()
        self.problems = []
        self.checked = 0

    def note_problem(self, p):
        self.answers.add(correct_answer(p))
        if p._answer is not None:
            self.answers.add(str(p._answer))

    def audit(self, url, body):
        self.checked += 1
        out = []
        _walk_keys(body, url, out)

        for container in [body] + ([body["status"]] if isinstance(body.get("status"), dict) else []):
            prob = container.get("problem") if isinstance(container, dict) else None
            if isinstance(prob, dict) and set(prob) != PROBLEM_KEYS:
                out.append(f"problem payload keys {sorted(prob)} != expected at {url}")

        leaves = []
        _leaves(_scrub(body), leaves)
        for a in self.answers:
            for leaf in leaves:
                s = str(leaf)
                if (len(a) >= 2 and a in s) or (len(a) == 1 and a == s):
                    out.append(f"answer value {a!r} leaked in {url}: {s!r}")
        for f in out:
            self.problems.append(f)


# ---------------------------------------------------------------------------
# Session driver
# ---------------------------------------------------------------------------

class Session:
    def __init__(self, name, checker):
        self.c = webapp.app.test_client()
        self.checker = checker
        body = self.post("/api/login", {"name": name})
        self.key = body["student"]

    def _audit(self, url, resp):
        body = resp.get_json()
        assert body is not None, f"non-JSON response from {url}"
        # register any served problem's answer BEFORE auditing, so the very
        # response that introduces a problem is scanned against its answer
        prob = body.get("problem")
        if isinstance(prob, dict):
            entry = webapp.SERVED.get(prob.get("problem_id"))
            if entry:
                self.checker.note_problem(entry["problem"])
        self.checker.audit(url, body)
        return body

    def post(self, url, payload, expect=200):
        r = self.c.post(url, json=payload)
        assert r.status_code == expect, f"{url}: {r.status_code} != {expect}"
        return self._audit(url, r)

    def get(self, url, expect=200):
        r = self.c.get(url)
        assert r.status_code == expect, f"{url}: {r.status_code} != {expect}"
        return self._audit(url, r)

    def served(self, body):
        pid = body["problem"]["problem_id"]
        return pid, webapp.SERVED[pid]["problem"]

    # -- flows --------------------------------------------------------------

    def diagnostic(self, policy):
        """policy(node, question_number) -> 'correct' | 'wrong' | 'skip'."""
        body = self.post("/api/diagnostic/start", {"student": self.key})
        garbage_done = False
        while not body["done"]:
            pid, p = self.served(body)
            qn = body["question_number"]

            if not garbage_done:
                # Unparseable must change nothing: same problem, same count.
                r = self.post("/api/diagnostic/answer",
                              {"student": self.key, "problem_id": pid,
                               "answer": "@@@"})
                assert r["grade"] == "unparseable", r
                assert r["question_number"] == qn, "unparseable consumed a question"
                assert r["problem"]["problem_id"] == pid, "unparseable rerolled the problem"
                garbage_done = True

            action = policy(p.node, qn)
            payload = {"student": self.key, "problem_id": pid}
            if action == "skip":
                payload["skip"] = True
            else:
                payload["answer"] = (correct_answer(p) if action == "correct"
                                     else wrong_answer_for(p))
            body = self.post("/api/diagnostic/answer", payload)
            if not body["done"]:
                assert body["question_number"] == qn + 1, "question count drifted"
        return body

    def practice_to_mastery(self, node):
        """One wrong, one unparseable, then correct until mastered — checks
        every streak rule from PROJECT.md 5.3 along the way."""
        body = self.get(f"/api/problem?student={self.key}&node={node}")
        pid, p = self.served(body)

        r = self.post("/api/answer", {"student": self.key, "problem_id": pid,
                                      "answer": wrong_answer_for(p)})
        assert r["grade"] == "wrong" and r["streak"] == 0, r
        assert r["hint"] is None or isinstance(r["hint"], str)

        body = self.get(f"/api/problem?student={self.key}&node={node}")
        pid, p = self.served(body)
        r = self.post("/api/answer", {"student": self.key, "problem_id": pid,
                                      "answer": "??"})
        assert r["grade"] == "unparseable" and r["streak"] == 0, r

        # the problem survived the unparseable submission — grade it now
        r = self.post("/api/answer", {"student": self.key, "problem_id": pid,
                                      "answer": correct_answer(p)})
        assert r["grade"] == "correct" and r["streak"] == 1, r

        last, corrects = r, 1
        while not last["just_mastered"]:
            body = self.get(f"/api/problem?student={self.key}&node={node}")
            pid, p = self.served(body)
            last = self.post("/api/answer",
                             {"student": self.key, "problem_id": pid,
                              "answer": correct_answer(p)})
            assert last["grade"] == "correct", last
            corrects += 1
            # The pacing theorem (bkt.py / selftest check_bkt): from ANY
            # prior, 3 consecutive corrects cross 0.95. If this trips, the
            # parameters or the propagation pass order broke.
            assert corrects <= 4, "mastery took >4 consecutive corrects"
        # In THIS deterministic flow (one wrong, then corrects from a
        # post-diagnostic low prior) mastery lands exactly on the 3rd
        # correct, so the familiar streak reading still holds.
        assert last["streak"] == 3, last
        assert last["status"]["nodes"][node]["p"] >= 0.95, last["status"]["nodes"][node]
        assert node in last["moved"], "the practiced node itself didn't move"
        return last

    def restart_check(self, node):
        """Serve, wipe server memory, submit — the rebuild from the student
        file must grade the same problem correctly."""
        body = self.get(f"/api/problem?student={self.key}&node={node}")
        pid, p = self.served(body)
        answer = correct_answer(p)
        webapp.SERVED.clear()
        webapp.DIAGS.clear()
        r = self.post("/api/answer", {"student": self.key, "problem_id": pid,
                                      "answer": answer})
        assert r["grade"] == "correct", f"restart rebuild failed to grade: {r}"

    def reveal_check(self, node):
        """The give-up flow: a reveal costs the streak (and ONLY the streak),
        retires the problem permanently — restart included — and is the one
        response allowed to carry an answer."""
        # build a visible streak so the reset is observable
        body = self.get(f"/api/problem?student={self.key}&node={node}")
        pid, p = self.served(body)
        r = self.post("/api/answer", {"student": self.key, "problem_id": pid,
                                      "answer": correct_answer(p)})
        assert r["grade"] == "correct" and r["streak"] >= 1, r

        before = self.get(f"/api/state?student={self.key}")
        attempts_before = before["nodes"][node]["attempts"]

        body = self.get(f"/api/problem?student={self.key}&node={node}")
        pid, p = self.served(body)
        r = self.post("/api/reveal", {"student": self.key, "problem_id": pid})
        assert set(r) == {"steps", "streak", "progress", "moved", "status"}, sorted(r)
        assert isinstance(r["steps"], list) and r["steps"], r["steps"]
        assert all(isinstance(s, str) and s for s in r["steps"]), r["steps"]
        assert not any("{" in s for s in r["steps"]), "placeholder in steps"
        assert r["streak"] == 0, r
        assert re.fullmatch(r"\d{1,3}%|mastered", r["progress"]), r["progress"]
        # a surrender is evidence: the node's P(mastered) must drop
        assert r["moved"].get(node, 0) < 0, "reveal applied no evidence"
        assert r["status"]["nodes"][node]["p"] < before["nodes"][node]["p"], \
            "reveal did not lower P(mastered)"
        assert r["status"]["nodes"][node]["attempts"] == attempts_before, \
            "a surrender must not count as an attempt"

        # the revealed problem is dead: no grade, no second reveal
        self.post("/api/answer", {"student": self.key, "problem_id": pid,
                                  "answer": correct_answer(p)}, expect=410)
        self.post("/api/reveal", {"student": self.key, "problem_id": pid},
                  expect=410)

        # retirement survives a restart: reveal, wipe memory, still 410
        body = self.get(f"/api/problem?student={self.key}&node={node}")
        pid, p = self.served(body)
        self.post("/api/reveal", {"student": self.key, "problem_id": pid})
        webapp.SERVED.clear()
        webapp.DIAGS.clear()
        self.post("/api/answer", {"student": self.key, "problem_id": pid,
                                  "answer": "1"}, expect=410)
        self.post("/api/reveal", {"student": self.key, "problem_id": pid},
                  expect=410)

        # positive twin: a restart BEFORE the reveal must not block it —
        # find_problem's rebuild path has to feed steps_for
        body = self.get(f"/api/problem?student={self.key}&node={node}")
        pid, p = self.served(body)
        webapp.SERVED.clear()
        r = self.post("/api/reveal", {"student": self.key, "problem_id": pid})
        assert r["steps"], "reveal after restart produced no steps"


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def guard_corpus_check():
    """The input guard must reject no legitimate answer, for any template,
    in any accepted formatting variant. This is what licenses treating a
    guard rejection as 'unparseable'."""
    rng = random.Random(20260819)
    bad = []
    for tid, tpl in webapp.TEMPLATES.items():
        checker = tpl.get("checker", "exact")
        for _ in range(40):
            p = generate(tpl, rng)
            candidates = ["none"]
            if p._answer is not None:
                candidates += format_variants(p._answer, checker)
                candidates.append(fmt(p._answer))
            for expr in tpl.get("selftest", {}).get("good", []):
                candidates.append(fmt(safe_eval(expr, p.params)))
            for expr in tpl.get("also_accept", []):
                candidates.append(fmt(safe_eval(expr, p.params)))
            for a in candidates:
                if webapp.unreadable(a):
                    bad.append(f"guard rejects legitimate answer for {tid}: {a!r}")
    for hid, entry in webapp.HAND.items():
        for v in format_variants(entry["answer"], entry.get("checker", "exact")):
            if webapp.unreadable(v):
                bad.append(f"guard rejects hand-authored answer for {hid}: {v!r}")
    return sorted(set(bad))


def error_paths(s):
    """Wrong ids must fail loudly and correctly, never 500."""
    s.get("/api/state?student=ghost_student", expect=404)
    s.get(f"/api/problem?student={s.key}&node=p_adic", expect=403)   # tier 2
    s.get(f"/api/problem?student={s.key}&node=nope", expect=404)
    s.post("/api/answer", {"student": s.key, "problem_id": "deadbeefcafe",
                           "answer": "1"}, expect=410)
    s.post("/api/reveal", {"student": s.key, "problem_id": "deadbeefcafe"},
           expect=410)
    s.post("/api/reveal", {"student": "ghost_student", "problem_id": "x"},
           expect=404)
    s.post("/api/login", {"name": "   "}, expect=400)


def main():
    # Guard-vs-corpus first: if the input guard rejects a real answer, every
    # session after it would fail confusingly — fail fast with the cause.
    guard_failures = guard_corpus_check()
    if guard_failures:
        for f in guard_failures[:20]:
            print(f"FAIL  {f}")
        print(f"\n{len(guard_failures)} failure(s). Do not deploy.")
        sys.exit(1)

    checker = Checker()

    # Session 1 — deterministic: fails everything, so the frontier must be
    # exactly [divisibility]; mastering it must unlock its dependents.
    s = Session("Leak Test A", checker)
    done = s.diagnostic(lambda node, qn: "wrong")
    assert done["status"]["frontier"] == ["divisibility"], done["status"]["frontier"]
    s.get(f"/api/state?student={s.key}")
    s.get("/api/graph")
    last = s.practice_to_mastery("divisibility")
    assert last["just_mastered"], last
    assert set(last["newly_unlocked"]) >= {"primes", "bases"}, last["newly_unlocked"]
    s.restart_check("primes")
    s.reveal_check("primes")
    error_paths(s)

    # Curriculum: audited like everything else, and complete — every authored
    # node teaches, and every lesson carries all five sections.
    cur = s.get("/api/curriculum")
    authored = {nid for nid in webapp.G.order if webapp.G.is_authored(nid)}
    assert set(cur["lessons"]) == authored, \
        f"lessons != authored nodes: {sorted(set(cur['lessons']) ^ authored)}"
    for lid, lesson in cur["lessons"].items():
        for field in ("concept", "key_results", "worked_example",
                      "common_mistakes", "problem_types"):
            assert isinstance(lesson.get(field), str) and lesson[field], \
                f"lesson {lid}: empty {field}"

    # Reveal must be impossible during the diagnostic: a diagnostic
    # problem_id mismatches on purpose inside find_problem and 410s.
    s_d = Session("Leak Test Reveal", checker)
    body_d = s_d.post("/api/diagnostic/start", {"student": s_d.key})
    pid_d, _ = s_d.served(body_d)
    s_d.post("/api/reveal", {"student": s_d.key, "problem_id": pid_d},
             expect=410)

    # Session 2 — deterministic: aces everything, then skips are exercised
    # in session 3. Strong student's frontier must sit past the diagnostic.
    s2 = Session("Leak Test B", checker)
    done2 = s2.diagnostic(lambda node, qn: "correct")
    assert done2["status"]["frontier"], "strong student has an empty frontier"

    # Sessions 3..10 — seeded random walks, one includes an explicit skip.
    for i in range(3, 11):
        rng = random.Random(i)
        s_i = Session(f"Leak Test {i}", checker)

        def policy(node, qn, rng=rng, force_skip=(i == 3)):
            if force_skip and qn == 2:
                return "skip"
            return rng.choice(["correct", "correct", "wrong", "skip"])

        done_i = s_i.diagnostic(policy)
        frontier = done_i["status"]["frontier"]
        if frontier:
            node = rng.choice(frontier)
            body = s_i.get(f"/api/problem?student={s_i.key}&node={node}")
            pid, p = s_i.served(body)
            answer = (correct_answer(p) if rng.random() < 0.5
                      else wrong_answer_for(p))
            s_i.post("/api/answer", {"student": s_i.key, "problem_id": pid,
                                     "answer": answer})

    failures = checker.problems

    print(f"leaktest: {checker.checked} responses audited, "
          f"{len(checker.answers)} distinct answers tracked")
    if failures:
        for f in failures[:20]:
            print(f"FAIL  {f}")
        print(f"\n{len(failures)} failure(s). Do not deploy.")
        sys.exit(1)
    print("No answer left the server. All behavioural checks passed.")


if __name__ == "__main__":
    main()

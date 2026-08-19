"""
app.py — the web layer over the ntgen engine.

    python3 web/app.py            ->  http://127.0.0.1:5000

The dividing line: this file (and store/layout beside it) owns HTTP, identity
and persistence. Everything mathematical — generation, grading, the graph,
the diagnostic — is ntgen's, called through its public functions.

Two rules this file exists to enforce:

  1. Answers never leave the server. problem_payload() is the ONLY place a
     Problem is serialized for the client, and web/leaktest.py proves the
     rule mechanically. Grading happens here, server-side, always.
  2. Unparseable input is not an attempt (PROJECT.md 5.3). It is logged,
     answered with "couldn't read that", and the same problem is re-served —
     record_answer is never called for it, so streaks cannot be hurt by typos.

Deployment note: run ONE OS process only (PythonAnywhere's default worker,
or gunicorn -w 1 --threads 4). The served-problem registry and the live
diagnostics are in memory; a second process would split them. Everything
durable is on disk, so a restart is a non-event — problems on screen are
rebuilt from the student file and grade identically.
"""

import random
import re
import sys
import uuid
from pathlib import Path

# ntgen uses flat imports (from graph import ...), so it goes on sys.path
# rather than becoming a package — its tested files stay untouched. web/ is
# added too so `gunicorn web.app:app` can find store/layout.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "ntgen"))

from flask import Flask, jsonify, request  # noqa: E402

import graph as g                                            # noqa: E402
from diagnostic import Diagnostic                            # noqa: E402
from generator import (                                      # noqa: E402
    Problem, load_templates, load_hand_authored,
    hand_authored_problem, problem_for_node,
)
from verify import safe_eval                                 # noqa: E402

import layout                                                # noqa: E402
import store                                                 # noqa: E402

app = Flask(__name__, static_folder="static", static_url_path="")

# Loaded once at import; the process refuses to boot on broken data, which
# beats discovering it when a student hits the first endpoint.
G = g.load_graph()
G.validate()
TEMPLATES = load_templates()
HAND = load_hand_authored()
POSITIONS = layout.positions(G)
RNG = random.Random()

SERVED = {}   # problem_id -> {"student", "purpose", "node", "problem"}
DIAGS = {}    # student key -> live Diagnostic


# ---------------------------------------------------------------------------
# Input guard
# ---------------------------------------------------------------------------

MAX_INPUT_LEN = 60


def unreadable(raw: str) -> bool:
    """
    App-layer guard in front of the grader.

    normalise() maps ^ to ** and sympify EVALUATES what it parses, so
    "9^9^9^9" (a power tower), "2^999999999" (a gigabyte integer) or
    "factorial(10**9)" would pin this single-process server forever. The
    sandbox in verify.py must not change, so the guard lives here instead:
    anything no legitimate answer ever looks like gets the same
    student-facing outcome as a typo — "couldn't read that", logged, not an
    attempt.

    Thresholds are set against the measured corpus (longest real answer 33
    chars, longest digit run 13 — a binary representation) and the leak
    test walks every template's answers through this guard to keep that
    true as templates are added.
    """
    s = str(raw)
    return (
        len(s) > MAX_INPUT_LEN
        or s.count("^") + s.count("**") >= 2                            # towers
        or re.search(r"(\^|\*\*)\s*\(?\s*-?\s*\d{6}", s) is not None    # huge exponents
        or re.search(r"[A-Za-z_]\s*\(", s) is not None                  # function calls
        or re.search(r"\d{20}", s) is not None                          # absurd literals
    )


# ---------------------------------------------------------------------------
# Serving problems
# ---------------------------------------------------------------------------

def problem_payload(pid: str, p: Problem) -> dict:
    """The ONLY serializer for a Problem. Params and template_id stay
    server-side too — together they recompute the answer."""
    return {
        "problem_id": pid,
        "node": p.node,
        "node_name": G.name(p.node),
        "prompt": p.prompt,
        "answer_format": p.answer_format,
    }


def serve_problem(state: dict, key: str, node: str, purpose: str):
    """Generate, register, persist. One outstanding problem per (student,
    purpose): serving a new one evicts the old, which bounds SERVED at two
    entries per student with no TTL bookkeeping."""
    p = problem_for_node(TEMPLATES, node, RNG, HAND)
    pid = uuid.uuid4().hex[:12]
    for old_pid, entry in list(SERVED.items()):
        if entry["student"] == key and entry["purpose"] == purpose:
            del SERVED[old_pid]
    SERVED[pid] = {"student": key, "purpose": purpose, "node": node, "problem": p}
    state["outstanding"] = {
        "problem_id": pid,
        "template_id": p.template_id,
        "params": store.jsonable(p.params),
        "node": node,
        "purpose": purpose,
    }
    store.save_student(key, state)
    return pid, p


def rebuild_problem(outstanding: dict):
    """Rebuild a served problem after a restart. Same template + same params
    -> same prompt, same answer, so the student never notices the server
    died with their problem on screen."""
    tid = outstanding["template_id"]
    if tid in HAND:
        return hand_authored_problem(HAND[tid])
    tpl = TEMPLATES.get(tid)
    if tpl is None:
        return None
    params = dict(outstanding["params"])
    sol = tpl.get("solution")
    answer = safe_eval(sol, params) if sol else None
    return Problem(tpl, params, tpl["prompt"].format(**params), answer)


def find_problem(state: dict, key: str, pid: str, purpose: str):
    """The Problem a submission refers to, surviving restarts. None means
    it is genuinely gone and the client should fetch a fresh one."""
    entry = SERVED.get(pid)
    if entry and entry["student"] == key and entry["purpose"] == purpose:
        return entry["problem"]
    out = state.get("outstanding")
    if out and out.get("problem_id") == pid and out.get("purpose") == purpose:
        p = rebuild_problem(out)
        if p is not None:
            SERVED[pid] = {"student": key, "purpose": purpose,
                           "node": out["node"], "problem": p}
            return p
    return None


def state_payload(state: dict) -> dict:
    """Everything the graph view needs, straight off the engine."""
    mastery = state["mastery"]
    status = G.status(mastery)
    return {
        "nodes": {
            nid: {
                "status": status[nid],
                "source": mastery[nid]["source"],
                "streak": mastery[nid]["streak"],
                "attempts": mastery[nid]["attempts"],
                "progress": g.progress(mastery, nid),
            }
            for nid in G.order
        },
        "frontier": G.frontier(mastery),
    }


def live_diag(key: str, state: dict) -> Diagnostic:
    """The student's diagnostic, rebuilt from history when memory is cold.
    A Diagnostic is a pure function of its answer history (deterministic
    tie-breaks), so replay IS recovery — refreshes and restarts land in
    exactly the same place."""
    d = DIAGS.get(key)
    if d is None:
        d = Diagnostic(G)
        for node, ok in state["diagnostic"]["history"]:
            d.record(node, bool(ok))
        DIAGS[key] = d
    return d


def finish_diagnostic(key: str, state: dict, d: Diagnostic) -> dict:
    """Persist result() exactly once, at the moment the search completes."""
    state["mastery"] = d.result()
    state["diagnostic"]["done"] = True
    state["outstanding"] = None
    store.save_student(key, state)
    DIAGS.pop(key, None)
    return {
        "done": True,
        "question_number": d.asked,
        "max_questions": d.max_questions,
        "summary": d.summary(),
        "status": state_payload(state),
    }


def load_or_404(key: str):
    state = store.load_student(key)
    if state is None:
        return None, (jsonify({"error": "unknown_student"}), 404)
    return state, None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/api/login")
def login():
    name = str((request.get_json(silent=True) or {}).get("name", "")).strip()
    key = store.slugify(name)
    if not key:
        return jsonify({"error": "name_required"}), 400
    with store.LOCK:
        state = store.load_student(key)
        if state is None:
            state = {
                "display_name": name,
                "created": store.timestamp(),
                "mastery": g.new_mastery(G),
                "diagnostic": {"done": False, "history": []},
                "outstanding": None,
            }
            store.save_student(key, state)
    phase = "practice" if state["diagnostic"]["done"] else "diagnostic"
    return jsonify({"student": key,
                    "display_name": state["display_name"],
                    "phase": phase})


@app.get("/api/graph")
def graph_route():
    # Pure structure — no student data, fetched once and cached client-side.
    return jsonify({
        "nodes": [
            {"id": nid, "name": G.name(nid), "tier": G.tier(nid),
             "authored": G.is_authored(nid),
             "x": POSITIONS[nid][0], "y": POSITIONS[nid][1]}
            for nid in G.order
        ],
        "edges": [[p, nid] for nid in G.order for p in G.prereqs(nid)],
    })


@app.get("/api/state")
def state_route():
    key = store.slugify(request.args.get("student", ""))
    with store.LOCK:
        state, err = load_or_404(key)
        if err:
            return err
        return jsonify(state_payload(state))


@app.post("/api/diagnostic/start")
def diagnostic_start():
    key = store.slugify((request.get_json(silent=True) or {}).get("student", ""))
    with store.LOCK:
        state, err = load_or_404(key)
        if err:
            return err
        if state["diagnostic"]["done"]:
            d = live_diag(key, state)
            return jsonify({"done": True, "summary": d.summary(),
                            "status": state_payload(state)})
        d = live_diag(key, state)

        # After a refresh the SAME question comes back, not a reroll.
        out = state.get("outstanding")
        pid, p = None, None
        if out and out.get("purpose") == "diagnostic":
            pid = out["problem_id"]
            p = find_problem(state, key, pid, "diagnostic")
        if p is None:
            node = d.next_node()
            if node is None:
                return jsonify(finish_diagnostic(key, state, d))
            pid, p = serve_problem(state, key, node, "diagnostic")
        return jsonify({
            "done": False,
            "question_number": d.asked + 1,
            "max_questions": d.max_questions,
            "problem": problem_payload(pid, p),
        })


@app.post("/api/diagnostic/answer")
def diagnostic_answer():
    body = request.get_json(silent=True) or {}
    key = store.slugify(body.get("student", ""))
    pid = str(body.get("problem_id", ""))
    skip = bool(body.get("skip"))
    raw = "" if skip else str(body.get("answer", ""))

    with store.LOCK:
        state, err = load_or_404(key)
        if err:
            return err
        if state["diagnostic"]["done"]:
            return jsonify({"error": "diagnostic_done"}), 409
        p = find_problem(state, key, pid, "diagnostic")
        if p is None:
            return jsonify({"error": "problem_expired"}), 410
        d = live_diag(key, state)

        if skip:
            grade = "wrong"
        elif unreadable(raw):
            grade = "unparseable"
        else:
            grade = p.grade(raw)

        store.log_event({
            "student": key, "purpose": "diagnostic", "node": p.node,
            "template_id": p.template_id, "params": p.params,
            "raw": None if skip else raw, "grade": grade, "skipped": skip,
        })

        if grade == "unparseable":
            # Not an attempt: the same question returns and question_number
            # holds — a typo cannot consume one of the six questions.
            return jsonify({
                "grade": grade,
                "done": False,
                "question_number": d.asked + 1,
                "max_questions": d.max_questions,
                "problem": problem_payload(pid, p),
            })

        correct = grade == "correct"
        d.record(p.node, correct)
        state["diagnostic"]["history"].append([p.node, correct])
        state["outstanding"] = None
        SERVED.pop(pid, None)

        if d.is_done() or d.next_node() is None:
            resp = finish_diagnostic(key, state, d)
            resp["grade"] = grade
            return jsonify(resp)

        new_pid, new_p = serve_problem(state, key, d.next_node(), "diagnostic")
        return jsonify({
            "grade": grade,
            "done": False,
            "question_number": d.asked + 1,
            "max_questions": d.max_questions,
            "problem": problem_payload(new_pid, new_p),
        })


@app.get("/api/problem")
def problem_route():
    key = store.slugify(request.args.get("student", ""))
    node = request.args.get("node", "")
    with store.LOCK:
        state, err = load_or_404(key)
        if err:
            return err
        if node not in G:
            return jsonify({"error": "unknown_node"}), 404
        # Mastered nodes stay practicable for review; locked ones never serve.
        if not G.is_unlocked(node, state["mastery"]):
            return jsonify({"error": "node_locked"}), 403
        pid, p = serve_problem(state, key, node, "practice")
        return jsonify({
            "problem": problem_payload(pid, p),
            "streak": state["mastery"][node]["streak"],
            "progress": g.progress(state["mastery"], node),
        })


@app.post("/api/answer")
def answer_route():
    body = request.get_json(silent=True) or {}
    key = store.slugify(body.get("student", ""))
    pid = str(body.get("problem_id", ""))
    raw = str(body.get("answer", ""))

    with store.LOCK:
        state, err = load_or_404(key)
        if err:
            return err
        p = find_problem(state, key, pid, "practice")
        if p is None:
            return jsonify({"error": "problem_expired"}), 410

        grade = "unparseable" if unreadable(raw) else p.grade(raw)
        store.log_event({
            "student": key, "purpose": "practice", "node": p.node,
            "template_id": p.template_id, "params": p.params,
            "raw": raw, "grade": grade, "skipped": False,
        })

        mastery = state["mastery"]
        if grade == "unparseable":
            # Streak untouched, problem still live — the student retypes.
            return jsonify({
                "grade": grade,
                "streak": mastery[p.node]["streak"],
                "progress": g.progress(mastery, p.node),
                "just_mastered": False,
                "newly_unlocked": [],
                "hint": None,
            })

        before = {k: dict(v) for k, v in mastery.items()}
        just_mastered = g.record_answer(mastery, p.node, grade == "correct")
        state["outstanding"] = None
        SERVED.pop(pid, None)
        store.save_student(key, state)

        return jsonify({
            "grade": grade,
            "streak": mastery[p.node]["streak"],
            "progress": g.progress(mastery, p.node),
            "just_mastered": just_mastered,
            "newly_unlocked": G.newly_unlocked(before, mastery),
            # The hint, never the answer — the next problem is fresh anyway.
            "hint": (p.hint or None) if grade == "wrong" else None,
            "status": state_payload(state),
        })


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/")
def index():
    return app.send_static_file("index.html")


if __name__ == "__main__":
    # threaded is fine (store.LOCK serializes mutation); a second PROCESS is
    # not — see the module docstring. debug stays off: the werkzeug debugger
    # is remote code execution, and the reloader would wipe SERVED/DIAGS.
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)

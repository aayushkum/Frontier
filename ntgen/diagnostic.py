"""
diagnostic.py — find where a student's knowledge stops, in about six questions.

The idea. A linear quiz that walks the curriculum from the start wastes every
question on a strong student and never reaches the interesting part. Instead we
binary search the prerequisite graph:

    a CORRECT answer rules out everything BELOW the node   (its prerequisites)
    a WRONG   answer rules out everything ABOVE the node   (what depends on it)

so each question removes a chunk of the graph rather than one node. Six
questions is enough to bracket the frontier in a 22-node graph, where a linear
quiz would need 22.

Where to start. `congruence` (PROJECT.md 5.1) sits on the boundary between
school math and contest math — exactly the gap this project claims to close.
Starting at the root wastes questions on strong students; starting deep
confuses weak ones.

Inference, and why the direction matters. Passing a node means its
prerequisites are safe to assume: you cannot do modular exponentiation without
modular arithmetic. Failing a node means everything downstream is out of
reach. But passing a node says NOTHING about the harder material above it —
that is still unknown. So:

    pass  ->  ANCESTORS   inferred mastered
    fail  ->  DESCENDANTS inferred locked

(The build spec states this the other way round. It is written up in plan.md;
inferring that a pass implies mastery of everything downstream would hand a
student a frontier far past what they can actually do.)

Every conclusion is tagged `tested` or `inferred` in the mastery state.
Inference is a guess and the UI must never present it as a measurement.

The class below is deliberately shaped like the web API it will sit behind in
phase 4: construct, ask for the next node, record one answer, repeat.
"""

from graph import new_mastery, set_mastered


# Where the search starts (PROJECT.md 5.1).
START_NODE = "congruence"

# Question budget. "Do not ask 40 questions. Ask ~6."
MAX_QUESTIONS = 6


class Diagnostic:
    def __init__(self, graph, start=START_NODE, max_questions=MAX_QUESTIONS):
        self.graph = graph
        self.start = start
        self.max_questions = max_questions

        self.known = set()      # believed mastered
        self.unknown = set()    # believed not mastered
        self.tested = {}        # node -> bool, only nodes actually asked
        self.history = []       # [(node, correct)] in order

    # -- driving the session ------------------------------------------------

    @property
    def asked(self):
        return len(self.history)

    def _pool(self):
        """Authored nodes we have not yet placed on either side."""
        return [
            n for n in self.graph.authored_nodes()
            if n not in self.known and n not in self.unknown
        ]

    def next_node(self):
        """Which node to ask about next, or None when the search is done."""
        if self.asked >= self.max_questions:
            return None
        pool = self._pool()
        if not pool:
            return None
        if self.asked == 0 and self.start in pool:
            return self.start

        # Bisect: the best question is the one whose two possible outcomes
        # eliminate similar amounts of the remaining space. A node that would
        # tell us a lot when correct but nothing when wrong is a bad question.
        pool_set = set(pool)
        best, best_score = None, -1
        for cand in pool:  # file order, so ties break deterministically
            if_correct = 1 + len(self.graph.ancestors(cand) & pool_set)
            if_wrong = 1 + len(self.graph.descendants(cand) & pool_set)
            score = min(if_correct, if_wrong)
            if score > best_score:
                best, best_score = cand, score
        return best

    def record(self, node, correct):
        """Fold one answer into what we believe."""
        self.history.append((node, correct))
        self.tested[node] = bool(correct)

        if correct:
            implied = {node} | self.graph.ancestors(node)
            gain, lose = self.known, self.unknown
        else:
            implied = {node} | self.graph.descendants(node)
            gain, lose = self.unknown, self.known

        for n in implied:
            # A node we actually tested keeps its measured result. Only
            # inferences get overwritten — this is what keeps one careless
            # slip from erasing a demonstrated success.
            if n != node and n in self.tested:
                continue
            gain.add(n)
            lose.discard(n)

    def is_done(self):
        return self.asked >= self.max_questions or not self._pool()

    def run(self, answer_fn):
        """
        Drive the whole session. `answer_fn(node) -> bool` decides whether the
        student got that node's question right.
        """
        while not self.is_done():
            node = self.next_node()
            if node is None:
                break
            self.record(node, answer_fn(node))
        return self.result()

    # -- output -------------------------------------------------------------

    def result(self):
        """
        The starting mastery state, with every conclusion tagged.

        source == "tested"   we asked, this is measured
        source == "inferred" we deduced it from the graph
        source is None       never determined; treated as not mastered
        """
        mastery = new_mastery(self.graph)
        for n in self.known:
            source = "tested" if self.tested.get(n) is True else "inferred"
            set_mastered(mastery, n, True, source)
        for n in self.unknown:
            source = "tested" if self.tested.get(n) is False else "inferred"
            set_mastered(mastery, n, False, source)
        return mastery

    def summary(self):
        """Counts for a results screen."""
        mastery = self.result()
        tested_pass = [n for n, ok in self.tested.items() if ok]
        tested_fail = [n for n, ok in self.tested.items() if not ok]
        return {
            "questions": self.asked,
            "tested_pass": tested_pass,
            "tested_fail": tested_fail,
            "inferred_mastered": sorted(self.known - set(self.tested)),
            "inferred_locked": sorted(
                n for n in self.unknown - set(self.tested)
                if self.graph.is_authored(n)
            ),
            "frontier": self.graph.frontier(mastery),
        }


# ---------------------------------------------------------------------------
# Testing aid
# ---------------------------------------------------------------------------

class SimulatedStudent:
    """
    A student with a known knowledge level, for checking that the diagnostic
    lands where it should. `knows` is closed downwards: knowing a node implies
    knowing everything it depends on.
    """

    def __init__(self, graph, knows, slip_on=None):
        self.graph = graph
        self.knows = set()
        for n in knows:
            self.knows.add(n)
            self.knows |= graph.ancestors(n)
        # nodes this student answers wrong despite knowing them, to exercise
        # the tested-beats-inferred rule
        self.slip_on = set(slip_on or ())

    def answer(self, node):
        if node in self.slip_on:
            return False
        return node in self.knows

    def true_frontier(self):
        """What the student should actually be working on."""
        return [
            n for n in self.graph.authored_nodes()
            if n not in self.knows
            and all(p in self.knows for p in self.graph.prereqs(n))
        ]

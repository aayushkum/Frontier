/* app.js — screen flow: login -> diagnostic -> graph + practice.

   Everything is graded on the server; this file never sees an answer key.
   The one grading rule it must respect (PROJECT.md 5.3): a response of
   "unparseable" is NOT an attempt — keep the student's text so they can fix
   the typo, and change nothing else on screen. */

const S = {
  student: null,
  displayName: null,
  graphReady: false,
  practice: null,   // {problemId, node, streak}
};

const $ = (id) => document.getElementById(id);

async function api(path, body) {
  const opts = body
    ? { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body) }
    : {};
  let r;
  try {
    r = await fetch(path, opts);
  } catch {
    return { error: "server_unreachable" };
  }
  let data = null;
  try { data = await r.json(); } catch { data = null; }
  // A static file server (Live Server etc.) answers /api/* with an HTML 404
  // or a 405 — non-JSON either way. Surface that as its own condition so the
  // UI can explain it instead of blaming the student's input.
  if (data === null) return { error: r.ok ? "bad_response" : `http_${r.status}` };
  if (!r.ok && !data.error) data.error = `http_${r.status}`;
  return data;
}

function serverDown(err) {
  return err === "server_unreachable" || err === "bad_response"
      || /^http_(404|405|5\d\d)$/.test(err || "");
}

function showServerWarning() {
  show("screen-login");
  $("login-card").hidden = true;
  $("warn-origin").textContent = location.origin;
  $("server-warning").hidden = false;
}

function show(screen) {
  for (const id of ["screen-login", "screen-diagnostic", "screen-graph"]) {
    $(id).hidden = id !== screen;
  }
}

function toast(msg, ms = 3200) {
  const t = $("toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.hidden = true; }, ms);
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/* "23^45231" reads badly as plain text; superscript the exponent and swap
   ASCII comparators for real symbols. The whole corpus is plain text with
   carets — this is the entire math renderer. */
function pretty(prompt) {
  return escapeHtml(prompt)
    .replace(/(\d+)\^(-?\w+)/g, "$1<sup>$2</sup>")
    .replace(/&lt;=/g, "≤")
    .replace(/&gt;=/g, "≥");
}

function feedback(elId, msg, kind) {
  const f = $(elId);
  f.textContent = msg;
  f.className = "feedback" + (kind ? " " + kind : "");
}

/* ------------------------------------------------------------------ login */

$("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = $("login-name").value.trim();
  if (!name) return;
  const r = await api("/api/login", { name });
  if (serverDown(r.error)) { showServerWarning(); return; }
  if (r.error === "name_required") {
    toast("Type a name — letters and numbers work best.");
    return;
  }
  if (r.error) { toast(`Couldn't log in (${r.error}).`); return; }
  enter(r);
});

$("switch-user").addEventListener("click", (e) => {
  e.preventDefault();
  localStorage.removeItem("nt_name");
  location.reload();
});

function enter(login) {
  S.student = login.student;
  S.displayName = login.display_name;
  localStorage.setItem("nt_name", login.display_name);
  $("who").hidden = false;
  $("who-name").textContent = login.display_name;
  if (login.phase === "diagnostic") startDiagnostic();
  else enterGraph(null, null);
}

/* ------------------------------------------------------------- diagnostic */

let diagProblem = null;

async function startDiagnostic() {
  show("screen-diagnostic");
  const r = await api("/api/diagnostic/start", { student: S.student });
  if (r.done) { enterGraph(r.status, r.summary); return; }
  renderQuestion(r);
}

function renderQuestion(r) {
  diagProblem = r.problem;
  $("diag-node").textContent = r.problem.node_name;
  $("diag-progress").textContent = `Question ${r.question_number} of ${r.max_questions}`;
  $("diag-prompt").innerHTML = pretty(r.problem.prompt);
  $("diag-format").textContent = r.problem.answer_format || "";
  $("diag-answer").value = "";
  $("diag-answer").focus();
  feedback("diag-feedback", "", "");
}

async function submitDiagnostic(skip) {
  const answer = $("diag-answer").value.trim();
  if (!skip && !answer) {
    feedback("diag-feedback", "Type an answer, or press Skip.", "info");
    return;
  }
  const payload = { student: S.student, problem_id: diagProblem.problem_id };
  if (skip) payload.skip = true; else payload.answer = answer;
  const r = await api("/api/diagnostic/answer", payload);

  if (serverDown(r.error)) {
    toast("Lost the server — is python3 web/app.py still running?");
    return;
  }
  if (r.error === "problem_expired") { startDiagnostic(); return; }

  if (r.grade === "unparseable") {
    // not an attempt: same question, same count, text kept for fixing
    feedback("diag-feedback", "Couldn't read that — check the formatting and try again.", "info");
    return;
  }
  if (r.done) { enterGraph(r.status, r.summary); return; }
  feedback("diag-feedback", skip ? "Skipped." : (r.grade === "correct" ? "✓" : "✗"),
           r.grade === "correct" ? "good" : "bad");
  setTimeout(() => renderQuestion(r), 450);
}

$("diag-form").addEventListener("submit", (e) => { e.preventDefault(); submitDiagnostic(false); });
$("diag-skip").addEventListener("click", () => submitDiagnostic(true));

/* ---------------------------------------------------------- graph screen */

async function enterGraph(status, summary) {
  show("screen-graph");
  if (!S.graphReady) {
    const data = await api("/api/graph");
    NTGraph.init($("graph-holder"), data, openPractice);
    S.graphReady = true;
  }
  if (!status) status = await api(`/api/state?student=${S.student}`);
  NTGraph.paint(status);
  if (summary) renderSummary(summary);
}

function chipList(ids, cls) {
  if (!ids || !ids.length) return "<span class='n'>none</span>";
  return ids.map((n) => `<span class="chip ${cls || ""}">${n.replace(/_/g, " ")}</span>`).join("");
}

function renderSummary(sum) {
  $("summary-card").hidden = false;
  $("summary-body").innerHTML = `
    <div class="sum-row"><span class="n">${sum.questions} questions asked.</span></div>
    <div class="sum-row">Answered: ${chipList(sum.tested_pass, "pass")}${chipList(sum.tested_fail, "fail")}</div>
    <div class="sum-row"><span class="n">Inferred from those answers (dashed on the graph —
      a guess, not a measurement):</span> ${chipList(sum.inferred_mastered)}</div>
    <div class="sum-row">Start here: ${chipList(sum.frontier)}</div>`;
}

/* -------------------------------------------------------------- practice */

function drawPips(streak, shake) {
  const p = $("prac-pips");
  p.innerHTML = "";
  for (let i = 0; i < 3; i++) {
    const dot = document.createElement("i");
    dot.className = "pip" + (i < streak ? " full" : "");
    p.appendChild(dot);
  }
  if (shake) {
    p.classList.remove("shake");
    void p.offsetWidth;           // restart the animation
    p.classList.add("shake");
  }
}

async function openPractice(node) {
  const r = await api(`/api/problem?student=${S.student}&node=${node}`);
  if (serverDown(r.error)) {
    toast("Lost the server — is python3 web/app.py still running?");
    return;
  }
  if (r.error) { toast("That node isn't available yet."); return; }
  $("summary-card").hidden = true;
  $("pick-card").hidden = true;
  $("practice-card").hidden = false;
  S.practice = { problemId: r.problem.problem_id, node: r.problem.node };
  $("prac-node").textContent = r.problem.node_name;
  $("prac-prompt").innerHTML = pretty(r.problem.prompt);
  $("prac-format").textContent = r.problem.answer_format || "";
  $("prac-answer").value = "";
  $("prac-answer").disabled = false;
  $("prac-answer").focus();
  $("prac-hint").hidden = true;
  $("prac-next").hidden = true;
  feedback("prac-feedback", "", "");
  drawPips(r.streak, false);
}

$("prac-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!S.practice) return;
  const answer = $("prac-answer").value.trim();
  if (!answer) {
    feedback("prac-feedback", 'Type an answer — "none" counts when nothing works.', "info");
    return;
  }
  const r = await api("/api/answer",
    { student: S.student, problem_id: S.practice.problemId, answer });

  if (serverDown(r.error)) {
    toast("Lost the server — is python3 web/app.py still running?");
    return;
  }
  if (r.error === "problem_expired") { openPractice(S.practice.node); return; }

  if (r.grade === "unparseable") {
    // streak untouched, same problem still live, text kept (PROJECT.md 5.3)
    feedback("prac-feedback", "Couldn't read that — check the formatting and try again.", "info");
    return;
  }

  if (r.status) NTGraph.paint(r.status);

  if (r.grade === "correct") {
    drawPips(r.streak, false);
    if (r.just_mastered) {
      feedback("prac-feedback", "Mastered — 3 in a row!", "good");
      $("prac-answer").disabled = true;
      if (r.newly_unlocked.length) {
        NTGraph.celebrate(r.newly_unlocked);
        toast(`Unlocked: ${r.newly_unlocked.map((n) => n.replace(/_/g, " ")).join(", ")}`);
      } else {
        toast("Mastered. Pick your next frontier node.");
      }
      $("prac-next").textContent = "Back to the graph";
      $("prac-next").hidden = false;
    } else {
      feedback("prac-feedback", "Correct.", "good");
      setTimeout(() => openPractice(S.practice.node), 800);
    }
  } else {
    drawPips(0, true);            // the reset is a visible mechanic
    feedback("prac-feedback", "Not quite — streak resets.", "bad");
    if (r.hint) {
      $("prac-hint").textContent = r.hint;
      $("prac-hint").hidden = false;
    }
    $("prac-next").textContent = "Next problem";
    $("prac-next").hidden = false;
  }
});

$("prac-next").addEventListener("click", () => {
  if ($("prac-answer").disabled) {
    // just mastered: back to node picking
    $("practice-card").hidden = true;
    $("pick-card").hidden = false;
    S.practice = null;
  } else {
    openPractice(S.practice.node);
  }
});

/* ----------------------------------------------------------------- start */

(async function boot() {
  // Before anything else: is the thing serving this page actually the app?
  // If not (Live Server, python -m http.server, ...), explain — nothing
  // else on this page can work without the Flask process.
  const health = await api("/api/health");
  if (health.ok !== true) { showServerWarning(); return; }

  const saved = localStorage.getItem("nt_name");
  if (saved) {
    const r = await api("/api/login", { name: saved });
    if (!r.error) { enter(r); return; }
  }
  show("screen-login");
  $("login-name").focus();
})();

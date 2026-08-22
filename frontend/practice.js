/* practice.js — the practice page: login -> diagnostic -> graph + practice.

   This file never sees an answer key for a gradable problem. The one grading
   rule it must respect (PROJECT.md 5.3): a response of "unparseable" is NOT
   an attempt — keep the student's text so they can fix the typo, and change
   nothing else on screen. */

const S = {
  student: null,
  displayName: null,
  graphReady: false,
  practice: null,   // {problemId, node, done: null|"mastered"|"revealed"}
};

function show(screen) {
  for (const id of ["screen-login", "screen-diagnostic", "screen-graph"]) {
    $(id).hidden = id !== screen;
  }
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
    toast("Lost the server — is python3 backend/app.py still running?");
    return;
  }
  if (r.error === "problem_expired") { startDiagnostic(); return; }

  if (r.grade === "unparseable") {
    // not an attempt: same question, same count, text kept for fixing
    feedback("diag-feedback", "Couldn't read that — check the formatting and try again.", "info");
    return;
  }
  if (r.done) { enterGraph(r.status, r.summary); return; }
  // one answer moves many nodes — say so; this is the model working
  const movedN = r.moved ? Object.keys(r.moved).length : 0;
  const movedTxt = movedN ? ` — updated ${movedN} skill${movedN === 1 ? "" : "s"}` : "";
  feedback("diag-feedback",
           (skip ? "Skipped." : (r.grade === "correct" ? "✓" : "✗")) + movedTxt,
           r.grade === "correct" ? "good" : "bad");
  setTimeout(() => renderQuestion(r), 650);
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
    toast("Lost the server — is python3 backend/app.py still running?");
    return;
  }
  if (r.error) { toast("That node isn't available yet."); return; }
  $("summary-card").hidden = true;
  $("pick-card").hidden = true;
  $("practice-card").hidden = false;
  S.practice = { problemId: r.problem.problem_id, node: r.problem.node,
                 done: null };
  $("prac-node").textContent = r.problem.node_name;
  $("prac-prompt").innerHTML = pretty(r.problem.prompt);
  $("prac-format").textContent = r.problem.answer_format || "";
  $("prac-answer").value = "";
  $("prac-answer").disabled = false;
  $("prac-answer").focus();
  $("prac-hint").hidden = true;
  $("prac-steps").hidden = true;
  $("prac-steps").innerHTML = "";
  disarmReveal();
  $("prac-reveal").hidden = false;
  $("prac-next").hidden = true;
  feedback("prac-feedback", "", "");
  drawPips(r.streak, false);
}

$("prac-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!S.practice) return;
  disarmReveal();
  const answer = $("prac-answer").value.trim();
  if (!answer) {
    feedback("prac-feedback", 'Type an answer — "none" counts when nothing works.', "info");
    return;
  }
  const r = await api("/api/answer",
    { student: S.student, problem_id: S.practice.problemId, answer });

  if (serverDown(r.error)) {
    toast("Lost the server — is python3 backend/app.py still running?");
    return;
  }
  if (r.error === "problem_expired") { openPractice(S.practice.node); return; }

  if (r.grade === "unparseable") {
    // streak untouched, same problem still live, text kept (PROJECT.md 5.3)
    feedback("prac-feedback", "Couldn't read that — check the formatting and try again.", "info");
    return;
  }

  if (r.status) NTGraph.paint(r.status);
  NTGraph.ripple(r.moved);

  if (r.grade === "correct") {
    drawPips(r.streak, false);
    if (r.just_mastered) {
      S.practice.done = "mastered";
      // the model decides mastery now — it can land on streak 2 after a
      // strong diagnostic, so the copy claims confidence, not a count
      const pm = r.status && r.status.nodes[S.practice.node]
        ? r.status.nodes[S.practice.node].p : 0.95;
      feedback("prac-feedback",
               `Mastered — the model is ${Math.round(pm * 100)}% sure you've got this.`,
               "good");
      $("prac-answer").disabled = true;
      $("prac-reveal").hidden = true;
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
    // the problem is retired server-side, so there is nothing to reveal
    $("prac-reveal").hidden = true;
    $("prac-next").textContent = "Next problem";
    $("prac-next").hidden = false;
  }
});

/* --------------------------------------------------------------- reveal */
/* Two-step confirm: the first click arms the button and shows the cost,
   the second actually surrenders. Anything else — submitting, 4 seconds of
   hesitation, a new problem — disarms it. */

let revealTimer = null;

function disarmReveal() {
  clearTimeout(revealTimer);
  const b = $("prac-reveal");
  b.classList.remove("armed");
  b.innerHTML = 'Stuck? Show the steps <span class="cost">(streak resets to 0)</span>';
}

$("prac-reveal").addEventListener("click", () => {
  if (!S.practice || S.practice.done) return;
  const b = $("prac-reveal");
  if (!b.classList.contains("armed")) {
    b.classList.add("armed");
    b.textContent = "Click again to reveal — your streak goes to 0";
    clearTimeout(revealTimer);
    revealTimer = setTimeout(disarmReveal, 4000);
    return;
  }
  disarmReveal();
  revealProblem();
});

async function revealProblem() {
  const r = await api("/api/reveal",
    { student: S.student, problem_id: S.practice.problemId });

  if (serverDown(r.error)) {
    toast("Lost the server — is python3 backend/app.py still running?");
    return;
  }
  if (r.error === "problem_expired") { openPractice(S.practice.node); return; }
  if (r.error) { toast(`Couldn't reveal (${r.error}).`); return; }

  if (r.status) NTGraph.paint(r.status);
  NTGraph.ripple(r.moved);        // the drop propagates — show it
  drawPips(0, true);              // the cost is a visible mechanic (5.3)
  S.practice.done = "revealed";
  $("prac-answer").disabled = true;
  $("prac-reveal").hidden = true;
  $("prac-hint").hidden = true;
  feedback("prac-feedback", "Streak reset — here's the full working.", "info");

  const holder = $("prac-steps");
  holder.innerHTML = "";
  for (const line of r.steps) {
    const d = document.createElement("div");
    d.className = "step";
    d.innerHTML = pretty(line);
    holder.appendChild(d);
  }
  holder.hidden = false;

  $("prac-next").textContent = "Next problem";
  $("prac-next").hidden = false;
}

$("prac-next").addEventListener("click", () => {
  if (!S.practice) return;
  if (S.practice.done === "mastered") {
    // just mastered: back to node picking. (Branch on done, not on the
    // disabled input — a reveal also disables the input but should serve
    // the next problem.)
    $("practice-card").hidden = true;
    $("pick-card").hidden = false;
    S.practice = null;
  } else {
    openPractice(S.practice.node);
  }
});

/* ----------------------------------------------------------------- start */

/* A known name logs straight back in (the server replays their state —
   mid-diagnostic resumes, otherwise the graph); a new visitor gets the
   login form. */
window.pageInit = async function () {
  const name = localStorage.getItem("nt_name");
  if (name) {
    const r = await api("/api/login", { name });
    if (serverDown(r.error)) { showServerWarning(); return; }
    if (!r.error) { enter(r); return; }
  }
  show("screen-login");
  $("login-name").focus();
};

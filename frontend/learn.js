/* learn.js — the curriculum pages. /learn is the lesson index; /learn#<id>
   is one lesson. Content comes from /api/curriculum (parsed from
   backend/ntgen/curriculum.md and validated against the DAG server-side).

   Lessons are open to read — no login, no locking. Gating is practice's
   job; reading ahead is how you learn. */

let CUR = null;   // /api/curriculum payload, fetched once per page load

/* Curriculum prose has variable-base powers (a^k, p^e, a^(p−1)) that the
   prompt renderer deliberately ignores; here every caret is math. */
function prettyLesson(text) {
  return escapeHtml(text)
    .replace(/(\w+)\^\(([^)]+)\)/g, "$1<sup>$2</sup>")
    .replace(/(\w+)\^(-?\w+)/g, "$1<sup>$2</sup>")
    .replace(/\)\^(-?\w+)/g, ")<sup>$1</sup>")
    .replace(/&lt;=/g, "≤")
    .replace(/&gt;=/g, "≥");
}

function firstSentence(t) {
  const i = t.indexOf(". ");
  return i === -1 ? t : t.slice(0, i + 1);
}

function indexHtml(c) {
  let h = `<h1>Learn</h1>
    <p class="muted">Every node on the map, as a lesson. Read them in any
    order — mastering them happens over in Practice.</p>`;
  for (const t of c.tiers) {
    h += `<div class="tier-head">Tier ${t.tier} — ${escapeHtml(t.name)}</div>`;
    if (t.blurb) h += `<p class="tiny muted tier-blurb">${escapeHtml(t.blurb)}</p>`;
    h += `<div class="lesson-list">`;
    for (const id of t.lessons) {
      const l = c.lessons[id];
      h += `<a class="lesson-row" href="#${id}">
        <span class="num">${l.number}</span>
        <span class="lname">${escapeHtml(l.name)}</span>
        <span class="teaser">${prettyLesson(firstSentence(l.concept))}</span></a>`;
    }
    h += `</div>`;
  }
  h += `<div class="card beyond"><h2>What lies beyond</h2>`
     + c.beyond.split("\n\n").map((p) => `<p class="tiny muted">${escapeHtml(p)}</p>`).join("")
     + `</div>`;
  return h;
}

function lessonHtml(c, id) {
  const l = c.lessons[id];
  const order = c.tiers.flatMap((t) => t.lessons);
  const i = order.indexOf(id);
  const prev = i > 0 ? c.lessons[order[i - 1]] : null;
  const next = i < order.length - 1 ? c.lessons[order[i + 1]] : null;
  const prereqs = l.prereqs.length
    ? l.prereqs.map((p) => `<a class="chip" href="#${p}">`
        + `${escapeHtml(c.lessons[p] ? c.lessons[p].name : p)}</a>`).join(" ")
    : `<span class="muted">nothing — this is where the map starts</span>`;
  const sec = (label, cls, text) =>
    `<div class="lsec ${cls}"><div class="eyebrow">${label}</div>
     <p>${prettyLesson(text)}</p></div>`;
  return `<p><a class="crumb" href="#">← All lessons</a></p>
    <div class="lesson">
      <h1><span class="num">${l.number}</span> ${escapeHtml(l.name)}</h1>
      <p class="tiny muted prereq-line">Builds on: ${prereqs}</p>
      <p class="lede">${prettyLesson(l.concept)}</p>
      ${sec("Key results", "", l.key_results)}
      ${sec("Worked example", "worked", l.worked_example)}
      ${sec("Common mistakes", "mistakes", l.common_mistakes)}
      ${sec("What you'll be asked", "asked", l.problem_types)}
      ${l.note ? `<p class="tiny muted"><em>${prettyLesson(l.note)}</em></p>` : ""}
      <div class="lesson-cta"><a class="btn-link" href="/practice">Practice this →</a></div>
      <div class="lesson-nav">
        <span>${prev ? `<a href="#${prev.id}">← ${prev.number} ${escapeHtml(prev.name)}</a>` : ""}</span>
        <span>${next ? `<a href="#${next.id}">${next.number} ${escapeHtml(next.name)} →</a>` : ""}</span>
      </div>
    </div>`;
}

async function render() {
  if (!CUR) {
    const r = await api("/api/curriculum");
    if (serverDown(r.error)) {
      toast("Lost the server — is python3 backend/app.py still running?");
      return;
    }
    if (r.error) { toast("Couldn't load the lessons."); return; }
    CUR = r;
  }
  const id = location.hash.replace(/^#/, "");
  $("curriculum-body").innerHTML = (id && CUR.lessons[id])
    ? lessonHtml(CUR, id)
    : indexHtml(CUR);
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", render);
window.pageInit = render;

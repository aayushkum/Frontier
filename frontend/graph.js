/* graph.js — draws the DAG the server laid out, and recolors it on demand.
   All positions come precomputed from /api/graph; this file only places
   circles, draws curves, and swaps CSS classes. No layout math here.

   Since Phase 2B every node carries a continuous P(mastered) from the
   knowledge-tracing model: the fill colour interpolates on it (classes still
   drive stroke, pulse and click behaviour), and ripple() pulses the nodes a
   single answer moved, sized by how far they moved. */

const NTGraph = (() => {
  const SVG = "http://www.w3.org/2000/svg";
  let nodeEls = {};   // node id -> <g>
  let edgeEls = [];   // [{el, from, to}]
  let onClick = null; // set by init
  let lastStatus = null;

  /* ---- continuous colour: locked navy -> frontier amber -> mastered green.
     The amber midpoint sits at p = 0.5 and the green endpoint at the 0.95
     mastery threshold, so the colour IS the model's belief. */
  function lerpHex(a, b, t) {
    const ca = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
    const cb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
    const c = ca.map((v, i) => Math.round(v + (cb[i] - v) * t));
    return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
  }

  function fillFor(p) {
    if (p >= 0.95) return "#34d399";
    if (p <= 0.5) return lerpHex("#232b40", "#fbbf24", p / 0.5);
    return lerpHex("#fbbf24", "#34d399", (p - 0.5) / 0.45);
  }

  const pct = (p) => `${Math.round(p * 100)}%`;

  function el(name, attrs) {
    const e = document.createElementNS(SVG, name);
    for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
    return e;
  }

  // Node names are long ("Linear Diophantine equations"); two short lines
  // read better than one clipped one.
  function labelLines(name) {
    if (name.length <= 14) return [name];
    const words = name.split(" ");
    const mid = Math.ceil(words.length / 2);
    return [words.slice(0, mid).join(" "), words.slice(mid).join(" ")];
  }

  function init(holder, data, clickHandler) {
    onClick = clickHandler;
    nodeEls = {}; edgeEls = [];
    const pos = {};
    for (const n of data.nodes) pos[n.id] = n;

    const svg = el("svg", { viewBox: "0 0 900 1300" });

    // edges first, under the nodes
    for (const [from, to] of data.edges) {
      const a = pos[from], b = pos[to];
      if (!a || !b) continue;
      const m = (a.y + b.y) / 2;
      const d = `M ${a.x} ${a.y} C ${a.x} ${m}, ${b.x} ${m}, ${b.x} ${b.y}`;
      const p = el("path", { d, class: "edge" });
      svg.appendChild(p);
      edgeEls.push({ el: p, from, to });
    }

    for (const n of data.nodes) {
      const g = el("g", { class: "node locked" });
      const r = n.authored ? 16 : 11;
      g.appendChild(el("circle", { cx: n.x, cy: n.y, r }));
      const lines = labelLines(n.name);
      lines.forEach((line, i) => {
        const t = el("text", { x: n.x, y: n.y + r + 13 + i * 12 });
        t.textContent = line;
        g.appendChild(t);
      });
      const tip = el("title", {});
      g.appendChild(tip);
      g.addEventListener("click", () => {
        if (g.classList.contains("clickable") && onClick) onClick(n.id);
      });
      svg.appendChild(g);
      nodeEls[n.id] = g;
    }

    holder.innerHTML = "";
    holder.appendChild(svg);
  }

  /* status payload: {nodes: {id: {status, source, p, progress, ...}}, frontier} */
  function paint(status) {
    lastStatus = status;
    for (const [id, g] of Object.entries(nodeEls)) {
      const s = status.nodes[id];
      if (!s) continue;
      g.classList.remove("mastered", "frontier", "locked", "inferred", "clickable");
      g.classList.add(s.status);
      const inferred = s.status === "mastered" && s.source === "inferred";
      if (inferred) g.classList.add("inferred");
      // frontier nodes practise; mastered ones stay open for review
      if (s.status === "frontier" || s.status === "mastered") g.classList.add("clickable");

      // The model's belief, painted directly. Inferred mastery keeps its
      // dashed class-driven look — a guess must never render as measured.
      const circle = g.querySelector("circle");
      circle.style.fill = (!inferred && typeof s.p === "number") ? fillFor(s.p) : "";

      const tip = g.querySelector("title");
      if (s.status === "mastered") {
        tip.textContent = inferred
          ? `inferred, ${pct(s.p)} — not tested yet (click to prove it)`
          : `mastered — ${pct(s.p)}`;
      } else if (s.status === "frontier") {
        tip.textContent = `available now — ${s.progress} toward mastery`;
      } else {
        tip.textContent = `locked — master its prerequisites first (${pct(s.p)})`;
      }
    }
    for (const { el: p, to } of edgeEls) {
      const s = status.nodes[to];
      p.classList.remove("to-frontier", "to-mastered");
      if (!s) continue;
      if (s.status === "frontier") p.classList.add("to-frontier");
      else if (s.status === "mastered") p.classList.add("to-mastered");
    }
  }

  /* the unlock moment: pop the newly available nodes (PROJECT.md 5.2) */
  function celebrate(ids) {
    for (const id of ids) {
      const g = nodeEls[id];
      if (!g) continue;
      g.classList.add("unlocking");
      setTimeout(() => g.classList.remove("unlocking"), 800);
    }
  }

  /* one answer moved these nodes: pulse each, sized by |delta|, tinted by
     direction. moved is the server's {node_id: delta} map. */
  function ripple(moved) {
    if (!moved) return;
    for (const [id, delta] of Object.entries(moved)) {
      const g = nodeEls[id];
      const mag = Math.abs(delta);
      if (!g || mag < 0.01) continue;
      const cls = mag >= 0.15 ? "moved-lg" : mag >= 0.05 ? "moved-md" : "moved-sm";
      g.classList.remove("moved-sm", "moved-md", "moved-lg", "down");
      void g.getBoundingClientRect();   // restart the animation
      g.classList.add(cls);
      if (delta < 0) g.classList.add("down");
      setTimeout(() => g.classList.remove(cls, "down"), 950);
    }
  }

  return { init, paint, celebrate, ripple };
})();

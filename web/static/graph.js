/* graph.js — draws the DAG the server laid out, and recolors it on demand.
   All positions come precomputed from /api/graph; this file only places
   circles, draws curves, and swaps CSS classes. No layout math here. */

const NTGraph = (() => {
  const SVG = "http://www.w3.org/2000/svg";
  let nodeEls = {};   // node id -> <g>
  let edgeEls = [];   // [{el, from, to}]
  let onClick = null; // set by init
  let lastStatus = null;

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

  /* status payload: {nodes: {id: {status, source, progress, ...}}, frontier} */
  function paint(status) {
    lastStatus = status;
    for (const [id, g] of Object.entries(nodeEls)) {
      const s = status.nodes[id];
      if (!s) continue;
      g.classList.remove("mastered", "frontier", "locked", "inferred", "clickable");
      g.classList.add(s.status);
      if (s.status === "mastered" && s.source === "inferred") g.classList.add("inferred");
      // frontier nodes practise; mastered ones stay open for review
      if (s.status === "frontier" || s.status === "mastered") g.classList.add("clickable");

      const tip = g.querySelector("title");
      if (s.status === "mastered") {
        tip.textContent = s.source === "inferred"
          ? "inferred — not tested yet (click to prove it)"
          : "mastered";
      } else if (s.status === "frontier") {
        tip.textContent = `available now — ${s.progress} toward mastery`;
      } else {
        tip.textContent = "locked — master its prerequisites first";
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

  return { init, paint, celebrate };
})();

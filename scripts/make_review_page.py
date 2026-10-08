#!/usr/bin/env python3
"""Build staging/review.html: a local page to audition staged assets and record verdicts.

  python3 scripts/make_review_page.py && open staging/review.html

Decisions are kept in the browser (localStorage) while you work. "Export decisions"
downloads review-decisions.json; apply it with:

  python3 scripts/apply_review.py ~/Downloads/review-decisions.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_lib import REPO_ROOT, SKILLS  # noqa: E402


def collect(staging: Path, include_reviewed: bool = False) -> list[dict]:
    items = []
    for skill in SKILLS:
        for record_path in sorted((staging / skill).glob("*/record.json")):
            r = json.loads(record_path.read_text(encoding="utf-8"))
            if r.get("status") != "generated":
                continue
            if not include_reviewed and r.get("review", {}).get("status", "pending") != "pending":
                continue
            folder = f"{skill}/{record_path.parent.name}"
            if r.get("takes"):
                takes = [{"file": f"{folder}/{t['file']}", "duration": t.get("duration_seconds"),
                          "flags": t.get("flags", []),
                          "vocals": (t.get("prescreen") or {}).get("vocals")} for t in r["takes"]]
            else:
                takes = [{"file": f"{folder}/{r['staged_file']}",
                          "duration": (r.get("auto_checks") or {}).get("duration_seconds"),
                          "flags": r.get("flags", []), "vocals": None}]
            review = r.get("review", {})
            names = [t["file"] for t in r.get("takes", [])]
            default_take = names.index(r["staged_file"]) + 1 if r.get("staged_file") in names else 1
            items.append({
                "id": r["id"], "skill": skill, "title": r.get("title", ""),
                "category": r.get("category", ""), "description": r.get("description", ""),
                "target": r.get("target_duration_seconds"), "loop": bool(r.get("loop_intended")),
                "takes": takes, "default_take": default_take, "status": review.get("status", "pending"),
            })
    return items


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Asset Review</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1b;--mute:#6b6b66;--line:#e2e2dc;--ok:#2f7d4a;--bad:#b23b3b;--warn:#a96a00;--acc:#2c5fb3}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#20201e;--ink:#ecece8;--mute:#9a9a93;--line:#34342f;--ok:#5cbf7d;--bad:#e07070;--warn:#e0a640;--acc:#7aa5ee}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,system-ui,sans-serif}
header{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 16px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
h1{font-size:16px;margin:0 12px 0 0}select,input,button{font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:5px 8px}
button{cursor:pointer}button.primary{background:var(--acc);color:#fff;border-color:var(--acc)}
#stats{color:var(--mute);margin-left:auto}main{max-width:980px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--line);border-radius:8px;padding:12px 14px;margin-bottom:10px}
.card.approved{border-left-color:var(--ok)}.card.rejected{border-left-color:var(--bad)}
.top{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap}.id{font-family:ui-monospace,monospace;color:var(--mute);font-size:12px}
.title{font-weight:600}.desc{color:var(--mute);margin:4px 0 8px}.flag{color:var(--warn);font-size:12px;font-weight:600}
.take{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:4px 0}audio{height:32px;width:min(420px,100%)}
.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-top:8px}label{display:inline-flex;gap:4px;align-items:center}
.notes{flex:1;min-width:180px}
</style></head><body>
<header><h1>Asset review</h1>
<select id="fskill"><option value="">All skills</option><option>sound-effects</option><option>background-music</option></select>
<select id="fcat"><option value="">All categories</option></select>
<select id="fstate"><option value="">All</option><option value="undecided">Undecided</option><option value="flagged">Flagged</option><option value="approved">Approved</option><option value="rejected">Rejected</option></select>
<button id="approveVisible">Approve visible undecided</button>
<button class="primary" id="export">Export decisions</button>
<span id="stats"></span></header>
<main id="list"></main>
<script>
const ITEMS = __DATA__;
const KEY = "sounddirector-review-v1";
let D = {};
try { D = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(D)); } catch (e) {} stats(); };
const dec = it => D[it.skill + "/" + it.id] || (D[it.skill + "/" + it.id] = {skill: it.skill, id: it.id, take: it.default_take || 1});
const flagged = it => it.takes.some(t => t.flags.length || t.vocals === "possible" || t.vocals === "likely");
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const cats = [...new Set(ITEMS.map(i => i.category))].sort();
fcat.innerHTML += cats.map(c => `<option>${esc(c)}</option>`).join("");

function visible() {
  return ITEMS.filter(it => {
    const d = D[it.skill + "/" + it.id] || {};
    if (fskill.value && it.skill !== fskill.value) return false;
    if (fcat.value && it.category !== fcat.value) return false;
    const s = fstate.value;
    if (s === "undecided" && d.status) return false;
    if (s === "flagged" && !flagged(it)) return false;
    if ((s === "approved" || s === "rejected") && d.status !== s) return false;
    return true;
  });
}
function card(it) {
  const d = D[it.skill + "/" + it.id] || {};
  const music = it.skill === "background-music";
  const takes = it.takes.map((t, i) => `<div class="take">
      ${it.takes.length > 1 ? `<label><input type="radio" name="take-${esc(it.id)}" data-k="take" value="${i+1}" ${(d.take||it.default_take||1)==i+1?"checked":""}>Take ${i+1}</label>` : ""}
      <audio controls preload="none" src="${esc(t.file)}"></audio>
      <span class="id">${t.duration ?? "?"}s${it.target ? " / target " + it.target + "s" : ""}</span>
      ${t.flags.map(f => `<span class="flag">${esc(f)}</span>`).join(" ")}
      ${t.vocals && t.vocals !== "none" ? `<span class="flag">vocals: ${esc(t.vocals)}</span>` : ""}
    </div>`).join("");
  return `<div class="card ${d.status||""}" data-key="${esc(it.skill+"/"+it.id)}">
    <div class="top"><span class="title">${esc(it.title)}</span><span class="id">${esc(it.id)} · ${esc(it.category)}</span></div>
    <div class="desc">${esc(it.description)}</div>${takes}
    <div class="row">
      <label><input type="radio" name="st-${esc(it.id)}" data-k="status" value="approved" ${d.status==="approved"?"checked":""}>Approve</label>
      <label><input type="radio" name="st-${esc(it.id)}" data-k="status" value="rejected" ${d.status==="rejected"?"checked":""}>Reject</label>
      ${music ? `<label><input type="checkbox" data-k="vocals" ${d.vocals?"checked":""}>Vocals heard</label>
                 <label><input type="checkbox" data-k="voiceover" ${d.voiceover?"checked":""}>Good under narration</label>` : ""}
      ${music || it.loop ? `<label><input type="checkbox" data-k="loop" ${d.loop?"checked":""}>Loop seam tested OK</label>` : ""}
      <input class="notes" data-k="notes" placeholder="notes" value="${esc(d.notes||"")}">
    </div></div>`;
}
function render() { list.innerHTML = visible().map(card).join("") || "<p>Nothing matches.</p>"; stats(); }
function stats() {
  const v = Object.values(D);
  const a = v.filter(d => d.status === "approved").length, r = v.filter(d => d.status === "rejected").length;
  document.getElementById("stats").textContent = `${a} approved · ${r} rejected · ${ITEMS.length - a - r} undecided of ${ITEMS.length}`;
}
list.addEventListener("change", e => {
  const el = e.target, c = el.closest(".card"); if (!c || !el.dataset.k) return;
  const it = ITEMS.find(i => i.skill + "/" + i.id === c.dataset.key), d = dec(it), k = el.dataset.k;
  d[k] = el.type === "checkbox" ? el.checked : (k === "take" ? Number(el.value) : el.value);
  if (k === "status") c.className = "card " + el.value;
  save();
});
list.addEventListener("play", e => document.querySelectorAll("audio").forEach(a => a !== e.target && a.pause()), true);
[fskill, fcat, fstate].forEach(s => s.addEventListener("change", render));
approveVisible.onclick = () => { visible().forEach(it => { const d = dec(it); if (!d.status) d.status = "approved"; }); save(); render(); };
document.getElementById("export").onclick = () => {
  const out = Object.values(D).filter(d => d.status);
  const blob = new Blob([JSON.stringify({version: 1, decisions: out}, null, 2)], {type: "application/json"});
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "review-decisions.json"; a.click();
};
render();
</script></body></html>
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--staging", type=Path, default=REPO_ROOT / "staging")
    p.add_argument("--include-reviewed", action="store_true", help="also list already approved/rejected items")
    args = p.parse_args(argv)
    items = collect(args.staging, args.include_reviewed)
    data = json.dumps(items).replace("</", "<\\/")
    out = args.staging / "review.html"
    out.write_text(PAGE.replace("__DATA__", data), encoding="utf-8")
    print(f"wrote {out} with {len(items)} item(s); open it in a browser")
    return 0


if __name__ == "__main__":
    sys.exit(main())

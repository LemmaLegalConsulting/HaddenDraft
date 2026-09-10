"""Build the reviewer's working page: one screen, two jobs, saves as you go.

The worksheet files are correct and unusable: nobody adjudicates 73 challenges
by editing YAML. This emits a single page that shows the planted defect on the
left and one challenge at a time on the right, takes y/n/u from the keyboard,
and writes each answer to the artifact's store as it is made.

Blinding is preserved exactly as the worksheet preserves it: the fixture is
named, because the planted defect is what the judgment is against, and the
condition, model and every judge-produced field are not in the page at all --
not hidden by CSS, not present. The key stays on disk.
"""

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENT = ROOT / "lexis_real_briefs" / "experiment"
FIXTURES = EXPERIMENT / "fixtures"


def challenges_from_worksheet(path):
    """Parse the blind worksheet back into structured items."""
    text = path.read_text()
    out, fixture = {}, None
    for block in re.split(r"\n(?=## |### )", text):
        heading = block.split("\n", 1)[0]
        if heading.startswith("## "):
            match = re.match(r"## (F\d{3})", heading)
            fixture = match.group(1) if match else None
        elif heading.startswith("### ") and fixture:
            match = re.match(r"### `(C[0-9a-f]+)`\s+\((\w*)\)", heading)
            if not match:
                continue
            body = block.split("\n", 1)[1] if "\n" in block else ""
            why = re.search(r"\*Why it matters:\* (.+?)(?:\n\n|\Z)", body, re.S)
            anchor = re.search(r"\*Anchored at:\* `(.+?)`", body, re.S)
            argument = re.split(r"\n\*Why it matters:\*|\n\*Anchored at:\*", body)[0].strip()
            out.setdefault(fixture, []).append({
                "id": match.group(1),
                "category": match.group(2) or "",
                "argument": argument,
                "why": (why.group(1).strip() if why else ""),
                "anchor": (anchor.group(1).strip() if anchor else ""),
            })
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worksheet", default=str(EXPERIMENT / "adjudication-baseline" / "WORKSHEET.md"))
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    pool = challenges_from_worksheet(Path(args.worksheet))
    fixtures = []
    for home in sorted(FIXTURES.iterdir()):
        if not home.is_dir():
            continue
        manifest = json.loads((home / "fixture.json").read_text())
        mutation = manifest["mutation"]
        fixtures.append({
            "id": manifest["fixture_id"],
            "case": manifest["case_family_id"],
            "title": manifest["document"]["title"],
            "court": manifest["document"]["court"],
            "filed": manifest["document"]["filed"],
            "side": manifest["document"]["side"],
            "stratum": manifest["stratum"],
            "type": mutation["type"],
            "section": mutation["section"],
            "before": mutation["target_location"]["control_excerpt"].strip(),
            "after": mutation["target_location"]["mutant_excerpt"].strip(),
            "changed": mutation["characters_changed"],
            "of": mutation["control_chars"],
            "gold": mutation["gold_vulnerability"].strip(),
            "description": mutation["description"].strip(),
            "realistic": mutation["why_this_is_realistic"].strip(),
            "caution": mutation.get("note_on_size", "").strip(),
            "record": manifest["files"]["attachments"],
            "challenges": pool.get(manifest["fixture_id"], []),
        })

    data = json.dumps({"fixtures": fixtures}, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("__DATA__", data)
    Path(args.out).write_text(html)
    total = sum(len(f["challenges"]) for f in fixtures)
    print(f"wrote {args.out}")
    print(f"  {len(fixtures)} fixtures to review, {total} challenges to score")


TEMPLATE = r"""<title>Brief Defect Review</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{
  --ground:#eef0ee; --paper:#fcfcfa; --raised:#f5f6f3;
  --ink:#16202c; --ink-soft:#4a5560; --muted:#79838d;
  --rule:#d8dcdf; --rule-firm:#b9c0c6;
  --stamp:#1f4e79; --stamp-soft:#e4ecf4;
  --yes:#1a6b4a; --yes-soft:#e2efe8;
  --no:#a8402f; --no-soft:#f6e5e1;
  --maybe:#8a6a1f; --maybe-soft:#f4eddb;
  --shadow:0 1px 2px rgba(22,32,44,.07), 0 6px 18px rgba(22,32,44,.05);
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --ground:#0f1418; --paper:#171d23; --raised:#1e252c;
  --ink:#e7eaed; --ink-soft:#b3bcc4; --muted:#85929c;
  --rule:#2a333b; --rule-firm:#3c4751;
  --stamp:#7db3e0; --stamp-soft:#1a2b3a;
  --yes:#68c79b; --yes-soft:#152a22;
  --no:#e08d7c; --no-soft:#2e1c19;
  --maybe:#d4b464; --maybe-soft:#2b2416;
  --shadow:0 1px 2px rgba(0,0,0,.3), 0 6px 18px rgba(0,0,0,.24);
}}
:root[data-theme="dark"]{
  --ground:#0f1418; --paper:#171d23; --raised:#1e252c;
  --ink:#e7eaed; --ink-soft:#b3bcc4; --muted:#85929c;
  --rule:#2a333b; --rule-firm:#3c4751;
  --stamp:#7db3e0; --stamp-soft:#1a2b3a;
  --yes:#68c79b; --yes-soft:#152a22;
  --no:#e08d7c; --no-soft:#2e1c19;
  --maybe:#d4b464; --maybe-soft:#2b2416;
  --shadow:0 1px 2px rgba(0,0,0,.3), 0 6px 18px rgba(0,0,0,.24);
}
*{box-sizing:border-box}
/* The artifact wrapper supplies this; a standalone file does not, and without
   it `hidden` loses to the display value set on .gate and the hidden view. */
[hidden]{display:none!important}
body{margin:0;background:var(--ground);color:var(--ink);
  font-family:"Libre Franklin",system-ui,-apple-system,sans-serif;font-size:15px;line-height:1.5}
h1,h2,h3{margin:0;text-wrap:balance;font-weight:600}
button{font:inherit;color:inherit;cursor:pointer}
.lab{font-size:11px;font-weight:600;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}
.mono{font-family:"IBM Plex Mono",ui-monospace,monospace}

header{position:sticky;top:0;z-index:20;background:var(--paper);border-bottom:1px solid var(--rule-firm);
  display:flex;align-items:center;gap:18px;padding:10px 20px;flex-wrap:wrap}
.brand{font-weight:700;letter-spacing:-.01em;font-size:15px}
.brand span{color:var(--stamp)}
nav{display:flex;gap:2px;margin-left:6px}
nav button{background:none;border:1px solid transparent;border-radius:5px;padding:5px 11px;
  font-size:13px;font-weight:500;color:var(--ink-soft)}
nav button[aria-current="true"]{background:var(--stamp-soft);color:var(--stamp);border-color:var(--rule)}
.spacer{flex:1}
.meter{display:flex;align-items:center;gap:9px;font-size:12px;color:var(--muted)}
.bar{width:132px;height:5px;background:var(--rule);border-radius:3px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--stamp);transition:width .25s}
.saved{font-size:11px;color:var(--muted);min-width:96px;text-align:right}

main{max-width:1220px;margin:0 auto;padding:20px}
.two{display:grid;grid-template-columns:minmax(0,4fr) minmax(0,6fr);gap:20px;align-items:start}
@media (max-width:900px){.two{grid-template-columns:1fr}}
.panel{background:var(--paper);border:1px solid var(--rule);border-radius:9px;box-shadow:var(--shadow)}
.pad{padding:17px 19px}
.sticky{position:sticky;top:64px}

.fixhead{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap;margin-bottom:3px}
.fixhead h2{font-size:19px;letter-spacing:-.01em}
.chip{font-size:11px;font-weight:600;padding:2px 8px;border-radius:20px;
  background:var(--stamp-soft);color:var(--stamp);letter-spacing:.02em}
.meta{font-size:12.5px;color:var(--muted);line-height:1.6}
.gold{margin-top:14px;padding:14px 15px;background:var(--raised);
  border-left:3px solid var(--stamp);border-radius:0 6px 6px 0}
.gold p{margin:7px 0 0;font-family:"Source Serif 4",Georgia,serif;font-size:15.5px;line-height:1.62}
.excerpt{margin-top:13px}
.excerpt div{padding:10px 12px;border-radius:6px;font-family:"Source Serif 4",Georgia,serif;
  font-size:13.5px;line-height:1.56;margin-top:5px}
.was{background:var(--no-soft);border:1px solid color-mix(in srgb,var(--no) 22%,transparent)}
.now{background:var(--yes-soft);border:1px solid color-mix(in srgb,var(--yes) 22%,transparent)}

.qhead{display:flex;align-items:center;gap:10px;padding:13px 19px;border-bottom:1px solid var(--rule)}
.qhead .n{font-size:13px;color:var(--muted)}
.arrow{background:var(--raised);border:1px solid var(--rule);border-radius:5px;
  width:28px;height:26px;line-height:1;color:var(--ink-soft)}
.arrow:disabled{opacity:.35;cursor:default}
.claim{padding:19px;font-family:"Source Serif 4",Georgia,serif;font-size:16.5px;line-height:1.63}
.why{margin:13px 19px 0;padding:11px 13px;background:var(--raised);border-radius:6px;
  font-size:13.5px;color:var(--ink-soft);line-height:1.55}
.anchor{margin:12px 19px 0;font-size:12px;color:var(--muted);line-height:1.5;
  border-left:2px solid var(--rule-firm);padding-left:10px}
.choices{display:flex;gap:9px;padding:17px 19px 19px}
.choice{flex:1;border:1px solid var(--rule-firm);background:var(--paper);border-radius:7px;
  padding:11px 8px;font-weight:600;font-size:14px;display:flex;flex-direction:column;
  align-items:center;gap:3px;transition:.12s}
.choice kbd{font-family:"IBM Plex Mono",monospace;font-size:10.5px;font-weight:400;color:var(--muted)}
.choice:hover{border-color:var(--ink-soft)}
.choice[data-on="yes"]{background:var(--yes-soft);border-color:var(--yes);color:var(--yes)}
.choice[data-on="no"]{background:var(--no-soft);border-color:var(--no);color:var(--no)}
.choice[data-on="unsure"]{background:var(--maybe-soft);border-color:var(--maybe);color:var(--maybe)}
.choice:focus-visible{outline:2px solid var(--stamp);outline-offset:2px}

.rail{display:flex;flex-wrap:wrap;gap:5px;padding:0 19px 17px}
.dot{width:25px;height:25px;border-radius:5px;border:1px solid var(--rule-firm);
  background:var(--paper);font-size:11px;font-weight:600;color:var(--muted);padding:0}
.dot[aria-current="true"]{outline:2px solid var(--stamp);outline-offset:1px}
.dot[data-on="yes"]{background:var(--yes);border-color:var(--yes);color:#fff}
.dot[data-on="no"]{background:var(--no);border-color:var(--no);color:#fff}
.dot[data-on="unsure"]{background:var(--maybe);border-color:var(--maybe);color:#fff}

.tabs{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:16px}
.tab{border:1px solid var(--rule);background:var(--paper);border-radius:7px;padding:7px 12px;
  font-size:13px;font-weight:500;display:flex;align-items:center;gap:7px}
.tab[aria-current="true"]{border-color:var(--stamp);background:var(--stamp-soft);color:var(--stamp)}
.tab i{font-style:normal;font-size:11px;color:var(--muted);font-family:"IBM Plex Mono",monospace}
.tab[aria-current="true"] i{color:var(--stamp)}
.tab.done i{color:var(--yes)}

.q{border-top:1px solid var(--rule);padding:15px 19px}
.q:first-of-type{border-top:none}
.q p{margin:0 0 4px;font-weight:600;font-size:14.5px}
.q .hint{font-weight:400;font-size:13px;color:var(--muted);margin-bottom:9px;line-height:1.5}
.q .choices{padding:0;gap:7px}
.q .choice{padding:7px 6px;font-size:13px}
textarea{width:100%;margin-top:4px;padding:9px 11px;border:1px solid var(--rule);border-radius:6px;
  background:var(--raised);color:var(--ink);font:inherit;font-size:13.5px;resize:vertical;min-height:58px}
textarea:focus-visible{outline:2px solid var(--stamp);outline-offset:-1px;border-color:var(--stamp)}
.note{margin:16px 0 0;font-size:12.5px;color:var(--muted);line-height:1.6}
.send{background:var(--stamp);color:#fff;border:1px solid var(--stamp);border-radius:6px;
  padding:5px 12px;font-size:12.5px;font-weight:600}
.send:hover{filter:brightness(1.08)}
.send.ready{animation:nudge 1.6s ease-in-out 3}
@keyframes nudge{0%,100%{transform:none}50%{transform:translateY(-2px)}}
@media (prefers-reduced-motion:reduce){.send.ready{animation:none}}
.finish{margin:16px 0 0;padding:15px 17px;background:var(--yes-soft);
  border:1px solid color-mix(in srgb,var(--yes) 35%,transparent);border-radius:8px}
.finish b{color:var(--yes)}
.who{background:var(--raised);border:1px solid var(--rule);border-radius:20px;
  padding:4px 11px;font-size:12px;font-weight:600;color:var(--ink-soft)}
.who:hover{border-color:var(--ink-soft)}
.gate{position:fixed;inset:0;z-index:50;background:color-mix(in srgb,var(--ground) 86%,transparent);
  backdrop-filter:blur(3px);display:grid;place-items:center;padding:20px}
.gatecard{background:var(--paper);border:1px solid var(--rule-firm);border-radius:11px;
  box-shadow:var(--shadow);padding:26px 28px;max-width:430px;display:flex;flex-direction:column;gap:10px}
.gatecard h2{font-size:19px;letter-spacing:-.01em}
.gatecard p{margin:0;font-size:13.5px;color:var(--ink-soft);line-height:1.6}
.gatecard input{padding:9px 11px;border:1px solid var(--rule-firm);border-radius:6px;
  background:var(--raised);color:var(--ink);font:inherit;font-size:14.5px}
.gatecard input:focus-visible{outline:2px solid var(--stamp);outline-offset:-1px}
.gatecard button{margin-top:4px;background:var(--stamp);color:#fff;border:none;border-radius:6px;
  padding:10px 14px;font-weight:600;font-size:14px}
.done{padding:34px 19px;text-align:center;color:var(--muted)}
.done strong{display:block;font-size:17px;color:var(--ink);margin-bottom:5px}
</style>

<header>
  <div class="brand">Brief Defect <span>Review</span></div>
  <nav>
    <button id="tab-score" aria-current="true">Score challenges</button>
    <button id="tab-check">Check the defects</button>
  </nav>
  <div class="spacer"></div>
  <div class="meter"><span id="count">0 / 0</span><div class="bar"><i id="fill" style="width:0"></i></div></div>
  <button class="who" id="who" title="Switch reviewer"></button>
  <button class="send" id="send">Send my answers</button>
  <div class="saved" id="saved">saved on this device</div>
</header>

<div class="gate" id="gate" hidden>
  <form class="gatecard" id="gateform">
    <h2>Who is reviewing?</h2>
    <p>Several people are scoring these independently, so each set of answers is
      kept under its own name. You will not see anyone else's while you work &mdash;
      that is the point of doing it separately.</p>
    <p>Your answers stay in this browser as you go &mdash; nothing is sent anywhere.
      When you finish, press <b>Send my answers</b> to save a small file, and email
      that back.</p>
    <label class="lab" for="rev">Your name or initials</label>
    <input id="rev" autocomplete="off" required maxlength="40" placeholder="e.g. Q. Steenhuis">
    <button type="submit">Start reviewing</button>
  </form>
</div>

<main>
  <div id="view-score">
    <div class="tabs" id="fixtabs"></div>
    <div class="two">
      <section class="panel sticky" id="ref"></section>
      <section class="panel" id="work"></section>
    </div>
    <p class="note" id="scorenote"></p>
  </div>
  <div id="view-check" hidden>
    <div class="tabs" id="checktabs"></div>
    <div class="two">
      <section class="panel sticky" id="checkref"></section>
      <section class="panel" id="checkwork"></section>
    </div>
  </div>
</main>

<script type="application/json" id="data">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById("data").textContent);
const FX = DATA.fixtures;
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

let db = null, fixi = 0, chi = 0, checki = 0, tab = "score", reviewer = "";
const slug = s => s.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"").slice(0,40) || "anon";
const scores = {};      // challengeId -> yes|no|unsure
const reviews = {};     // fixtureId -> {q1..q4, notes}
const QS = [
  ["identical", "Are the two versions identical apart from the one intended change?",
   "Anything else that moved — a heading that no longer follows its neighbour, a dangling cross-reference — is a second change and disqualifies the pair."],
  ["control_clean", "Is the original free of this defect?",
   "If the unmodified brief already had the problem, the edit did not introduce it."],
  ["mutant_has", "Does the edited version actually have the defect described?",
   "The claim has to be true, not just plausible."],
  ["material", "Would opposing counsel realistically raise it?",
   "Not whether a machine would notice — whether a lawyer would use it."],
];

/* ---------- persistence: local first, server when the store answers ---------- */
function localSave(){
  try{ localStorage.setItem("bdr:"+slug(reviewer), JSON.stringify({scores, reviews})); }catch(e){}
}
function localLoad(){
  try{
    const raw = localStorage.getItem("bdr:"+slug(reviewer)); if(!raw) return;
    const v = JSON.parse(raw);
    Object.assign(scores, v.scores || {}); Object.assign(reviews, v.reviews || {});
  }catch(e){}
}
// Answers live under the reviewer, so two attorneys scoring the same challenge
// record two independent judgments instead of overwriting one another. The page
// only ever reads back your own, so nobody is anchored by a colleague's call.
async function push(kind, id, value){
  localSave();
  if(!db) return;
  try{
    await db.doc(`reviews/${slug(reviewer)}/${kind}/${id}`)
      .set({...value, reviewer, at: new Date().toISOString()});
    setSaved("saved");
  }catch(e){ setSaved("saved on this device"); }
}
function setSaved(t){ document.getElementById("saved").textContent = t; }

/* ---------- reference pane: the planted defect ---------- */
function refPane(f){
  return `<div class="pad">
    <div class="fixhead"><h2>${esc(f.id)}</h2><span class="chip">${esc(f.type.replace(/_/g," "))}</span></div>
    <div class="meta">${esc(f.title)}<br>${esc(f.court)} · filed ${esc(f.filed)} · ${esc(f.side)}</div>
    <div class="gold">
      <div class="lab">The defect that was planted</div>
      <p>${esc(f.gold)}</p>
    </div>
    <div class="excerpt">
      <div class="lab">What the brief said, in ${esc(f.section.replace(/\s*--\s*/g," \u2014 "))}</div>
      <div class="was">${esc(f.before)}</div>
      <div class="lab" style="margin-top:11px">What it says now</div>
      <div class="now">${f.after ? esc(f.after) : "<em>— removed —</em>"}</div>
    </div>
    <p class="note">${f.changed} characters of ${f.of.toLocaleString()} changed${f.record.length ? " · a case record is attached to this brief" : ""}.</p>
  </div>`;
}

/* ---------- job 2: score challenges ---------- */
function renderScore(){
  const f = FX[fixi];
  document.getElementById("fixtabs").innerHTML = FX.map((x,i)=>{
    const n = x.challenges.filter(c=>scores[c.id]).length;
    return `<button class="tab${n===x.challenges.length&&n>0?" done":""}" data-i="${i}"
      aria-current="${i===fixi}">${esc(x.id)} <i>${n}/${x.challenges.length}</i></button>`;
  }).join("");
  document.getElementById("ref").innerHTML = refPane(f);

  const list = f.challenges;
  const work = document.getElementById("work");
  if(!list.length){ work.innerHTML = `<div class="done">No challenges were raised against this brief.</div>`; }
  else{
    chi = Math.min(chi, list.length-1);
    const c = list[chi];
    work.innerHTML = `
      <div class="qhead">
        <button class="arrow" id="prev" ${chi===0?"disabled":""} aria-label="Previous">&larr;</button>
        <button class="arrow" id="next" ${chi===list.length-1?"disabled":""} aria-label="Next">&rarr;</button>
        <span class="n">Challenge ${chi+1} of ${list.length}</span>
        <div class="spacer"></div>
        <span class="lab">${esc(c.category.replace(/_/g," "))}</span>
      </div>
      <div class="claim">${esc(c.argument)}</div>
      ${c.why?`<div class="why"><span class="lab">Why it matters</span><br>${esc(c.why)}</div>`:""}
      ${c.anchor?`<div class="anchor">Pointing at: “${esc(c.anchor.replace(/^["\u201c\u2018']+|["\u201d\u2019']+$/g,""))}”</div>`:""}
      <div class="choices">
        <button class="choice" data-v="yes"    data-on="${scores[c.id]==="yes"?"yes":""}">Yes, that's it <kbd>Y</kbd></button>
        <button class="choice" data-v="no"     data-on="${scores[c.id]==="no"?"no":""}">No, different point <kbd>N</kbd></button>
        <button class="choice" data-v="unsure" data-on="${scores[c.id]==="unsure"?"unsure":""}">Unsure <kbd>U</kbd></button>
      </div>
      <div class="rail">${list.map((x,i)=>`<button class="dot" data-i="${i}"
        aria-current="${i===chi}" data-on="${scores[x.id]||""}">${i+1}</button>`).join("")}</div>`;
  }
  document.getElementById("scorenote").textContent =
    "You are asked one thing: does this challenge name the planted defect? It does not have to use the same words. "
    + "A challenge that merely notices something is missing, without saying what, is not a match. "
    + "You are not told which version produced it, or which model wrote it.";
  progress();
}

function answer(v){
  const c = FX[fixi].challenges[chi]; if(!c) return;
  scores[c.id] = v;
  push("challenge_answers", c.id, {fixture: FX[fixi].id, answer: v});
  const list = FX[fixi].challenges;
  if(chi < list.length-1) chi++;
  else { const nx = FX.findIndex((f,i)=> i>fixi && f.challenges.some(x=>!scores[x.id]));
         if(nx>=0){ fixi=nx; chi=0; } }
  renderScore();
}

/* ---------- job 1: check the defects ---------- */
function renderCheck(){
  const f = FX[checki];
  document.getElementById("checktabs").innerHTML = FX.map((x,i)=>{
    const r = reviews[x.id]||{}; const n = QS.filter(q=>r[q[0]]).length;
    return `<button class="tab${n===4?" done":""}" data-i="${i}"
      aria-current="${i===checki}">${esc(x.id)} <i>${n}/4</i></button>`;
  }).join("");
  document.getElementById("checkref").innerHTML = refPane(f);
  const r = reviews[f.id] || {};
  document.getElementById("checkwork").innerHTML = `
    <div class="qhead"><span class="lab">What I claim this change does</span></div>
    <div class="claim" style="font-size:15px">${esc(f.description)}</div>
    <div class="why"><span class="lab">Why I thought it realistic</span><br>${esc(f.realistic)}</div>
    ${f.caution?`<div class="why" style="border-left:3px solid var(--maybe)"><span class="lab">A caution I flagged</span><br>${esc(f.caution)}</div>`:""}
    ${QS.map(([k,q,hint])=>`<div class="q">
      <p>${esc(q)}</p><div class="hint">${esc(hint)}</div>
      <div class="choices">
        <button class="choice" data-q="${k}" data-v="yes" data-on="${r[k]==="yes"?"yes":""}">Yes</button>
        <button class="choice" data-q="${k}" data-v="no" data-on="${r[k]==="no"?"no":""}">No</button>
        <button class="choice" data-q="${k}" data-v="unsure" data-on="${r[k]==="unsure"?"unsure":""}">Unsure</button>
      </div></div>`).join("")}
    <div class="q"><p>Anything the yes/no does not carry</p>
      <textarea id="notes" placeholder="Optional.">${esc(r.notes||"")}</textarea></div>`;
  progress();
}

function progress(){
  const total = FX.reduce((n,f)=>n+f.challenges.length,0) + FX.length*4;
  const done = Object.keys(scores).length
    + FX.reduce((n,f)=>n+QS.filter(q=>(reviews[f.id]||{})[q[0]]).length,0);
  document.getElementById("count").textContent = `${done} / ${total}`;
  document.getElementById("fill").style.width = total? (100*done/total)+"%" : "0";
  const send = document.getElementById("send");
  if(send){ if(done>0 && done===total) send.classList.add("ready"); else send.classList.remove("ready"); }
  const old = document.getElementById("finish"); if(old) old.remove();
  const note = document.getElementById("scorenote");
  if(done===total && total>0 && note){
    const el = document.createElement("div");
    el.className = "finish"; el.id = "finish";
    el.innerHTML = "<b>That is everything.</b> Press <b>Send my answers</b> in the top right "
      + "to save the file, then email it back. You can still change any answer first.";
    note.parentNode.insertBefore(el, note);
  }
}

/* ---------- wiring ---------- */
document.addEventListener("click", e => {
  const t = e.target.closest("button"); if(!t) return;
  if(t.id==="tab-score"||t.id==="tab-check"){
    tab = t.id==="tab-score"?"score":"check";
    document.getElementById("tab-score").setAttribute("aria-current", tab==="score");
    document.getElementById("tab-check").setAttribute("aria-current", tab==="check");
    document.getElementById("view-score").hidden = tab!=="score";
    document.getElementById("view-check").hidden = tab!=="check";
    (tab==="score"?renderScore:renderCheck)(); return;
  }
  if(t.closest("#fixtabs")){ fixi=+t.dataset.i; chi=0; renderScore(); return; }
  if(t.closest("#checktabs")){ checki=+t.dataset.i; renderCheck(); return; }
  if(t.id==="prev"){ chi--; renderScore(); return; }
  if(t.id==="next"){ chi++; renderScore(); return; }
  if(t.classList.contains("dot")){ chi=+t.dataset.i; renderScore(); return; }
  if(t.classList.contains("choice") && t.dataset.q){
    const f = FX[checki]; const r = reviews[f.id] = reviews[f.id]||{};
    r[t.dataset.q] = t.dataset.v;
    push("fixture_reviews", f.id, r); renderCheck(); return;
  }
  if(t.classList.contains("choice")){ answer(t.dataset.v); return; }
});
document.addEventListener("input", e => {
  if(e.target.id==="notes"){
    const f = FX[checki]; const r = reviews[f.id] = reviews[f.id]||{};
    r.notes = e.target.value; localSave();
    clearTimeout(window._nt); window._nt = setTimeout(()=>push("fixture_reviews", f.id, r), 700);
  }
});
document.addEventListener("keydown", e => {
  if(e.target.tagName==="TEXTAREA" || e.metaKey || e.ctrlKey) return;
  if(tab!=="score") return;
  const k = e.key.toLowerCase();
  if(k==="y"||k==="n"||k==="u"){ e.preventDefault(); answer({y:"yes",n:"no",u:"unsure"}[k]); }
  else if(e.key==="ArrowLeft" && chi>0){ chi--; renderScore(); }
  else if(e.key==="ArrowRight" && chi<FX[fixi].challenges.length-1){ chi++; renderScore(); }
});

function start(name){
  reviewer = name;
  try{ localStorage.setItem("bdr:reviewer", name); }catch(e){}
  document.getElementById("gate").hidden = true;
  document.getElementById("who").textContent = name;
  localLoad(); renderScore(); renderCheck();
  document.getElementById("view-check").hidden = tab !== "check";
  connect();
}
document.getElementById("gateform").addEventListener("submit", e => {
  e.preventDefault();
  const v = document.getElementById("rev").value.trim();
  if(v) start(v);
});
function payload(){
  return {
    tool: "brief-defect-review", version: 1,
    reviewer, saved_at: new Date().toISOString(),
    challenge_answers: {...scores}, fixture_reviews: JSON.parse(JSON.stringify(reviews)),
    counts: {
      challenges_scored: Object.keys(scores).length,
      challenges_total: FX.reduce((n,f)=>n+f.challenges.length,0),
      fixtures_reviewed: FX.filter(f=>QS.every(q=>(reviews[f.id]||{})[q[0]])).length,
      fixtures_total: FX.length,
    },
  };
}
document.getElementById("send").addEventListener("click", () => {
  const blob = new Blob([JSON.stringify(payload(), null, 2)], {type:"application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `review-${slug(reviewer)}-${new Date().toISOString().slice(0,10)}.json`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(()=>URL.revokeObjectURL(a.href), 4000);
  setSaved("file saved \u2014 email it back");
});
document.getElementById("who").addEventListener("click", () => {
  for(const k in scores) delete scores[k];
  for(const k in reviews) delete reviews[k];
  document.getElementById("gate").hidden = false;
  document.getElementById("rev").value = "";
  document.getElementById("rev").focus();
});

renderScore(); renderCheck();
document.getElementById("view-check").hidden = true;
let saved = "";
try{ saved = localStorage.getItem("bdr:reviewer") || ""; }catch(e){}
if(saved){ start(saved); }
else { document.getElementById("gate").hidden = false;
       setTimeout(()=>document.getElementById("rev").focus(), 60); }

async function connect(){
  // Standalone file: there is no window.claude, and that is the normal case --
  // most reviewers open this from an email attachment, signed in to nothing.
  // Everything works without it; the store is a convenience for the copy that
  // happens to be opened inside claude.ai.
  if(typeof claude === "undefined" || !claude || typeof claude.use !== "function") return;
  const d = await claude.use("db");
  if(!d) return;
  db = d;
  setSaved("saved");
  try{
    const base = `reviews/${slug(reviewer)}`;
    const [a, r] = await Promise.all([
      db.collection(`${base}/challenge_answers`).get(),
      db.collection(`${base}/fixture_reviews`).get(),
    ]);
    a.docs.forEach(doc => { const v = doc.data(); if(v && v.answer) scores[doc.id] = v.answer; });
    r.docs.forEach(doc => { reviews[doc.id] = {...(reviews[doc.id]||{}), ...doc.data()}; });
    localSave(); setSaved("saved");
    (tab==="score"?renderScore:renderCheck)();
  }catch(e){ setSaved("saved on this device"); }
}
</script>
"""

if __name__ == "__main__":
    main()

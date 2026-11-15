"""Screen-recordable walkthrough of the DALI setup flow, annotated for Lb2Lg.

Produces three artifacts (default into the lb2lg harness reports/ dir):

  lb2lg_dali_flow.svg          the setup flow, each node captioned with what it
                               does for the Lb2Lg BR reproduction
  lb2lg_dali_walkthrough.html  one flow node per screen, arrow-key navigable,
                               fullscreen - this is what you screen-record
  lb2lg_dali_flow_report.md    the write-up: flow, lb2lg mapping, gate rules

The flow is read from the live graph (rag_ai_scientist.flow_diagram), so the
picture cannot drift from dali_onboard.py. The Lb2Lg captions are hand-written
below and reference the real measurement `br2016-closure` (PRL 123, 031801).
"""
from __future__ import annotations

import argparse
import html
from datetime import datetime, timezone
from pathlib import Path

from rag_ai_scientist import flow_diagram as fd
from rag_ai_scientist.flow_diagram import build_svg

# node id -> (lb2lg caption, one-line "what happens here for Lb2Lg")
LB2LG: dict[str, tuple[str, str]] = {
    "__start__": ("Start", "Reproduce BR(Lambda_b -> Lambda gamma) from a paper + code."),
    "get_inputs": ("paper + code",
                   "paper: PRL 123, 031801 (2019) + LHCb-ANA-2023-029; "
                   "code: lb02lbgammabr @ c43b1f58."),
    "check_agent": ("is /agent dali there?",
                    "confirm the dali agent is installed before the expensive embedding run."),
    "fetch_inputs": ("fetch paper + code",
                     "local clones used as-is; gitlab.cern.ch needs a PAT in ~/.netrc."),
    "choose_embedding_model": ("pick the brain size",
                               "base tier on an 8-core box; the model defines retrieval geometry."),
    "embed_and_chunk": ("chunk paper + code",
                        "3072 chunks over the analysis notes and the closure pipeline code."),
    "build_brain": ("build the RAG brain",
                    "persistent chroma index at .dali/brain - the corpus every gate cites from."),
    "test_brain": ("GATE: does retrieval work?",
                   "ask 'what is the 2016 signal yield?' and check it returns N_sig = 62.1 +/- 12.8."),
    "summarize": ("plain-words summary",
                  "goal: measure BR; result to land on: (6.66 +/- 1.5)e-6 vs PRL (7.1 +/- 2.3)e-6."),
    "approve_summary": ("GATE: is the goal right?",
                        "human confirms the headline number before planning against it."),
    "plan_dag": ("plan the steps + benchmarks",
                 "closure fit -> BR; benchmarks are numbers read verbatim from the notes."),
    "render_artifacts": ("write WORKFLOW.md + pipeline.yaml",
                         "the plan as files a human can edit; pipeline.yaml is the source of truth."),
    "approve_plan": ("GATE: approve the plan",
                     "last gate before any shell command runs."),
    "execute": ("GATE + run one step",
                "run the closure pipeline / calculate_br_magdown.py, or ask first."),
    "validate": ("br_inputs_cited + br_within_envelope",
                 "every input must cite a corpus line; BR must agree with PRL within combined error."),
    "advance": ("next step",
                "bump the step counter; loop back to execute while steps remain."),
    "smoke_test": ("GATE: end-to-end check",
                   "human runs the small smoke test and answers pass/fail."),
    "__end__": ("done", "measurement recorded in measurement.yaml with provenance."),
}

ORDER = fd.SPINE


def annotated_svg() -> str:
    """The flow SVG with an lb2lg caption column on the right of each spine node."""
    base = build_svg().rstrip()
    assert base.endswith("</svg>"), "unexpected svg tail"
    body = base[: -len("</svg>")]
    positions = {n: fd.ROW0 + i * fd.ROWP for i, n in enumerate(fd.SPINE)}
    cap_x = fd.X_ABORT + 40   # clear of the abort rail so captions never overlap it
    caps = []
    for node in ORDER:
        if node not in LB2LG:
            continue
        cap, _ = LB2LG[node]
        cy = positions[node]
        caps.append(
            f'<text x="{cap_x}" y="{cy + 4}" class="cap" text-anchor="start">'
            f'{html.escape(cap)}</text>')
    style = ("<style>.cap{font:12px 'IBM Plex Sans',system-ui,sans-serif;"
             "fill:var(--fg)}</style>")
    # widen the viewBox so the caption column (right of the abort rail) is not clipped
    merged = body + style + "".join(caps) + "</svg>\n"
    return merged.replace('viewBox="0 0 880 ', 'viewBox="0 0 1240 ', 1)


def walkthrough_html() -> str:
    slides = []
    for i, node in enumerate(ORDER):
        cap, detail = LB2LG[node]
        kind = fd.SHAPES.get(node, "proc")
        badge = {"gate": "HUMAN GATE", "loop": "LOOP", "term": ""}.get(kind, "STEP")
        slides.append(
            f'<section class="slide" data-kind="{kind}">'
            f'<div class="idx">{i + 1} / {len(ORDER)}</div>'
            f'<div class="badge b-{kind}">{badge}</div>'
            f'<h1>{html.escape(node)}</h1>'
            f'<h2>{html.escape(cap)}</h2>'
            f'<p>{html.escape(detail)}</p>'
            f'<div class="flow">{_mini_flow(i)}</div>'
            f'</section>')
    return _HTML_TEMPLATE.replace("__SLIDES__", "".join(slides)).replace(
        "__N__", str(len(ORDER)))


def _mini_flow(active: int) -> str:
    cells = []
    for i, node in enumerate(ORDER):
        cls = "dot"
        if i == active:
            cls += " on"
        if fd.SHAPES.get(node) == "gate":
            cls += " g"
        cells.append(f'<span class="{cls}" title="{html.escape(node)}"></span>')
    return "".join(cells)


_HTML_TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DALI setup flow - Lb2Lg walkthrough</title>
<style>
:root{--bg:#fff;--fg:#1f2937;--mut:#5b6678;--pf:#eef1f6;--ps:#8a97ab;--gf:#fff2cc;
--gs:#d6b656;--lf:#e2efda;--ls:#82b366}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--fg:#e5e9f0;--mut:#9aa6b8;
--pf:#1f2633;--ps:#5b6a80;--gf:#3d3315;--gs:#b8963a;--lf:#1b3322;--ls:#5a9a6a}}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);
font:16px/1.5 'IBM Plex Sans',system-ui,sans-serif}
.slide{display:none;min-height:100vh;padding:6vh 8vw;flex-direction:column;justify-content:center}
.slide.on{display:flex}
.idx{position:absolute;top:24px;right:32px;color:var(--mut);font:14px 'IBM Plex Mono',monospace}
.badge{display:inline-block;align-self:flex-start;padding:4px 12px;border-radius:999px;
font:600 12px 'IBM Plex Mono',monospace;letter-spacing:.08em;margin-bottom:18px}
.b-gate{background:var(--gf);color:var(--gs);border:1px solid var(--gs)}
.b-loop{background:var(--lf);color:var(--ls);border:1px solid var(--ls)}
.b-proc{background:var(--pf);color:var(--ps);border:1px solid var(--ps)}
.b-term{background:none;border:none;color:var(--mut)}
h1{font:600 clamp(28px,5vw,56px)/1.1 'IBM Plex Mono',monospace;margin:0 0 8px}
h2{font:500 clamp(18px,2.6vw,28px)/1.3 'IBM Plex Sans',sans-serif;margin:0 0 18px;color:var(--fg)}
p{max-width:60ch;font-size:clamp(15px,1.8vw,20px);color:var(--mut)}
.flow{margin-top:40px;display:flex;gap:6px;flex-wrap:wrap}
.dot{width:16px;height:16px;border-radius:4px;background:var(--pf);border:1px solid var(--ps)}
.dot.g{background:var(--gf);border-color:var(--gs)}
.dot.on{outline:3px solid var(--fg);outline-offset:2px}
.hint{position:absolute;bottom:20px;left:8vw;color:var(--mut);font-size:13px}
</style></head><body>
__SLIDES__
<div class="hint">space / &darr; next &nbsp;&middot;&nbsp; &uarr; prev &nbsp;&middot;&nbsp;
home/end first/last &nbsp;&middot;&nbsp; f fullscreen</div>
<script>
const s=[...document.querySelectorAll('.slide')];let i=0;
function show(n){i=Math.max(0,Math.min(s.length-1,n));
s.forEach((e,k)=>e.classList.toggle('on',k===i));location.hash=i+1;}
addEventListener('keydown',e=>{
 if([' ','ArrowRight','PageDown'].includes(e.key)){e.preventDefault();show(i+1);}
 else if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();show(i-1);}
 else if(e.key==='Home')show(0);else if(e.key==='End')show(s.length-1);
 else if(e.key.toLowerCase()==='f'){if(!document.fullscreenElement)
 document.documentElement.requestFullscreen();else document.exitFullscreen();}});
addEventListener('click',()=>show(i+1));
show((parseInt(location.hash.slice(1))||1)-1);
</script></body></html>"""


def report_md() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = "\n".join(
        f"| `{n}` | {LB2LG[n][0]} | {LB2LG[n][1]} |" for n in ORDER if n in LB2LG)
    gates = "\n".join(f"- `{n}`" for n in ORDER if fd.SHAPES.get(n) == "gate")
    return f"""# DALI setup flow - Lb2Lg walkthrough

Generated {now} from the live `dali_onboard.py` graph (via `flow_diagram`).
Companion files: `lb2lg_dali_flow.svg` (annotated diagram) and
`lb2lg_dali_walkthrough.html` (screen-record this - one node per screen).

## What this demonstrates

The DALI onboarding flow is a LangGraph state machine. This walkthrough runs
it against the **Lb2Lg** reproduction target: BR(Lambda_b -> Lambda gamma),
measurement `br2016-closure`, reference PRL 123, 031801 (2019), landing on
(6.66 +/- 1.5)e-6 against the published (7.1 +/- 2.3)e-6.

Three design ideas the diagram encodes:

1. **Deterministic nodes do the work** - chunking, embedding, retrieval,
   execution, validation are plain code with plain checks.
2. **The LLM only proposes** - it appears in summarize / plan / correct; every
   proposal is executed and validated by the harness, never trusted.
3. **A human sits on every consequential edge** - the gates below; each records
   its verdict verbatim in `state["checks"]`.

## Flow, node by node (Lb2Lg mapping)

| node | what it is | what happens for Lb2Lg |
|---|---|---|
{rows}

## The human gates

{gates}

Plus the per-step run gate inside `execute` (run / skip / stop).

## The gate rules that make this trustworthy

- **`br_inputs_cited`** - every numeric input (signal yield, norm yield,
  efficiency ratio, fragmentation ratio) must quote a line from the indexed
  corpus that contains that exact value. No uncited numbers.
- **`br_within_envelope`** - the computed BR must agree with the published
  reference within the combined uncertainty.
- A failed check is fixed in the **code or config**, never in an output or a
  reference value; max attempts per step, then escalate to a human.

## How to record

Open `lb2lg_dali_walkthrough.html` in a browser, press `f` for fullscreen,
and screen-record while stepping with the space bar. Each screen is one flow
node with its Lb2Lg meaning; the dot strip at the bottom shows position in the
flow and highlights gates in amber.
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="lb2lg-dali-demo",
                                     description="DALI flow walkthrough for Lb2Lg.")
    parser.add_argument("--out", default=".", help="Output directory.")
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "lb2lg_dali_flow.svg").write_text(annotated_svg(), encoding="utf-8")
    (out / "lb2lg_dali_walkthrough.html").write_text(walkthrough_html(), encoding="utf-8")
    (out / "lb2lg_dali_flow_report.md").write_text(report_md(), encoding="utf-8")
    for name in ("lb2lg_dali_flow.svg", "lb2lg_dali_walkthrough.html",
                 "lb2lg_dali_flow_report.md"):
        print(f"wrote {out / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

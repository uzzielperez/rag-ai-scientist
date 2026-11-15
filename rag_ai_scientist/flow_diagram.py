"""Render the DALI onboarding flow as a clean, dark-mode-aware SVG.

Hand-laid single-column spine (not a graphviz auto-layout): the linear
trunk runs down the centre, gate rebuilds loop up the left, the
execute/validate/correct cycle sits to the right, and the two abort edges
run down the far right to `done`. Colours are CSS variables so the figure
follows the host page's light/dark theme.

Generated from `build_graph()` - run it after changing the flow so the
picture cannot drift from the code:

    python -m rag_ai_scientist.flow_diagram --out dali_flow.svg
    python -m rag_ai_scientist.flow_diagram --check      # exit 1 if stale
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

# node id -> shape: "gate" (hexagon), "loop" (pill), "proc" (box), "term" (circle)
SHAPES = {
    "check_agent": "gate", "fetch_inputs": "gate", "choose_embedding_model": "gate",
    "test_brain": "gate", "approve_summary": "gate", "approve_plan": "gate",
    "execute": "gate", "smoke_test": "gate",
    "validate": "loop", "advance": "loop", "correct": "loop",
    "__start__": "term", "__end__": "term",
}

# vertical order of the central spine (correct sits off-spine, added separately)
SPINE = ["__start__", "get_inputs", "check_agent", "fetch_inputs",
         "choose_embedding_model", "embed_and_chunk", "build_brain",
         "test_brain", "summarize", "approve_summary", "plan_dag",
         "render_artifacts", "approve_plan", "execute", "validate",
         "advance", "smoke_test", "__end__"]

# (source, target, label) side routes, keyed so the picture matches the graph.
# kind: left-loop (up), right-loop (down), right-abort, correct-cycle
SIDES = {
    ("test_brain", "build_brain"): ("left", "rebuild"),
    ("approve_summary", "build_brain"): ("left", "rebuild"),
    ("approve_plan", "build_brain"): ("left", "rebuild"),
    ("advance", "execute"): ("left", "steps left"),
    ("validate", "correct"): ("right", "fail"),
    ("correct", "execute"): ("right", "loops < MAX"),
    ("validate", "smoke_test"): ("right", "stopped / exhausted"),
    ("check_agent", "__end__"): ("abort", "abort"),
    ("fetch_inputs", "__end__"): ("abort", "abort"),
}

X_CENTER = 360
X_LEFT = 150          # left-loop vertical rail
X_ABORT = 820         # far-right abort rail
NODE_W, NODE_H = 220, 40
ROW0, ROWP = 48, 66   # start cy, row pitch
LABELS = {"__start__": "start", "__end__": "done"}

STYLE = """\
:root{--bg:#fff;--fg:#1f2937;--mut:#5b6678;--line:#64748b;--pf:#eef1f6;--ps:#8a97ab;\
--gf:#fff2cc;--gs:#d6b656;--lf:#e2efda;--ls:#82b366}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#14171c;--fg:#e5e9f0;\
--mut:#9aa6b8;--line:#8b98ad;--pf:#1f2633;--ps:#5b6a80;--gf:#3d3315;--gs:#b8963a;\
--lf:#1b3322;--ls:#5a9a6a}}
:root[data-theme="dark"]{--bg:#14171c;--fg:#e5e9f0;--mut:#9aa6b8;--line:#8b98ad;--pf:#1f2633;\
--ps:#5b6a80;--gf:#3d3315;--gs:#b8963a;--lf:#1b3322;--ls:#5a9a6a}
.n{stroke-width:1.5}.p{fill:var(--pf);stroke:var(--ps)}.g{fill:var(--gf);stroke:var(--gs)}\
.l{fill:var(--lf);stroke:var(--ls)}
.t{font:500 13px 'IBM Plex Mono',ui-monospace,Menlo,Consolas,monospace;fill:var(--fg);\
text-anchor:middle}
.lb{font:12px 'IBM Plex Sans',system-ui,sans-serif;fill:var(--mut)}
.e{fill:none;stroke:var(--line);stroke-width:1.6;stroke-linejoin:round;marker-end:url(#ar)}\
.e.d{stroke-dasharray:6 5}"""


def _cy(index: int) -> int:
    return ROW0 + index * ROWP


def _shape(node: str, cy: int) -> str:
    kind = SHAPES.get(node, "proc")
    label = LABELS.get(node, node)
    if kind == "term":
        return (f'<circle cx="{X_CENTER}" cy="{cy}" r="24" class="n p"/>'
                f'<text x="{X_CENTER}" y="{cy + 4.5}" class="t">{label}</text>')
    x0, x1 = X_CENTER - NODE_W // 2, X_CENTER + NODE_W // 2
    top, bot = cy - NODE_H // 2, cy + NODE_H // 2
    if kind == "gate":
        pts = (f"{x0},{top + 20} {x0 + 14},{top} {x1 - 14},{top} "
               f"{x1},{top + 20} {x1 - 14},{bot} {x0 + 14},{bot}")
        return (f'<polygon points="{pts}" class="n g"/>'
                f'<text x="{X_CENTER}" y="{cy + 4.5}" class="t g">{label}</text>')
    rx = NODE_H // 2 if kind == "loop" else 8
    cls = "l" if kind == "loop" else "p"
    return (f'<rect x="{x0}" y="{top}" width="{NODE_W}" height="{NODE_H}" rx="{rx}" '
            f'class="n {cls}"/><text x="{X_CENTER}" y="{cy + 4.5}" class="t {cls}">{label}</text>')


def _spine_edges(positions: dict[str, int]) -> list[str]:
    out = []
    for a, b in zip(SPINE, SPINE[1:]):
        if (a, b) in SIDES:          # these are drawn as side routes instead
            continue
        out.append(f'<path d="M{X_CENTER},{positions[a] + NODE_H // 2 if a != "__start__" else positions[a] + 24} '
                   f'V{positions[b] - (NODE_H // 2 if b != "__end__" else 24)}" class="e"/>')
    return out


def _side_edges(positions: dict[str, int]) -> list[str]:
    out = []
    for (src, dst), (kind, label) in SIDES.items():
        label = label.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        sc, dc = positions[src], positions[dst]
        if kind == "left":
            x0 = X_CENTER - NODE_W // 2
            rail = X_LEFT if dst != "execute" else 100
            out.append(f'<path d="M{x0},{sc} H{rail} V{dc} H{x0}" class="e d"/>')
            out.append(f'<text x="{(x0 + rail) // 2}" y="{sc - 7}" class="lb" '
                       f'text-anchor="middle">{label}</text>')
        elif kind == "right" and src == "validate" and dst == "correct":
            x1 = X_CENTER + NODE_W // 2
            out.append(f'<path d="M{x1},{sc} H{x1 + 70}" class="e d"/>')
            out.append(f'<text x="{x1 + 35}" y="{sc - 6}" class="lb" '
                       f'text-anchor="middle">{label}</text>')
        elif kind == "right" and src == "correct":
            x1 = X_CENTER + NODE_W // 2
            cx = x1 + 140
            out.append(f'<rect x="{cx - 70}" y="{sc - NODE_H // 2}" width="140" '
                       f'height="{NODE_H}" rx="20" class="n l"/>'
                       f'<text x="{cx}" y="{sc + 4.5}" class="t l">correct</text>')
            out.append(f'<path d="M{cx},{sc - NODE_H // 2} V{dc} H{x1}" class="e"/>')
            out.append(f'<text x="{(cx + x1) // 2 + 5}" y="{dc - 8}" class="lb" '
                       f'text-anchor="middle">{label}</text>')
        elif kind == "right":       # validate -> smoke_test (stopped/exhausted)
            x1 = X_CENTER + NODE_W // 2
            rail = x1 + 35
            out.append(f'<path d="M{x1},{sc} H{rail} V{dc} H{x1}" class="e d"/>')
            out.append(f'<text x="{rail + 8}" y="{(sc + dc) // 2}" class="lb" '
                       f'text-anchor="start">{label}</text>')
        else:                        # abort -> __end__ down the far right
            x1 = X_CENTER + NODE_W // 2
            out.append(f'<path d="M{x1},{sc} H{X_ABORT} V{dc} H{X_CENTER + 26}" class="e d"/>')
            out.append(f'<text x="{(x1 + X_ABORT) // 2 + 90}" y="{sc - 8}" class="lb" '
                       f'text-anchor="middle">{label}</text>')
    return out


def build_svg() -> str:
    positions = {node: _cy(i) for i, node in enumerate(SPINE)}
    positions["correct"] = positions["validate"]   # drawn to the right, same row
    height = positions["__end__"] + 48
    width = X_ABORT + 60
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" style="background:transparent" aria-label="DALI onboarding flow">',
        f"<style>{STYLE}</style>",
        '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto"><path d="M0,1 L9,5 L0,9 z" fill="var(--line)"/>'
        "</marker></defs>",
    ]
    parts += _spine_edges(positions)
    parts += _side_edges(positions)
    parts += [_shape(node, positions[node]) for node in SPINE]
    parts.append("</svg>")
    return "".join(parts) + "\n"


def _verify_against_graph() -> None:
    """Fail loudly if the graph gained/lost a node or edge the layout misses."""
    from rag_ai_scientist import dali_onboard as ob

    g = ob.build_graph().get_graph()
    graph_nodes = [n for n in g.nodes]
    layout_nodes = set(SPINE) | {"correct"}
    if set(graph_nodes) != layout_nodes:
        missing = set(graph_nodes) - layout_nodes
        extra = layout_nodes - set(graph_nodes)
        raise SystemExit(f"flow changed - update SPINE. new={missing} gone={extra}")
    graph_edges = {(e.source, e.target) for e in g.edges}
    drawn = (set(zip(SPINE, SPINE[1:])) - set(SIDES) | set(SIDES)
             | {("validate", "correct"), ("correct", "execute")})
    if graph_edges != drawn:
        raise SystemExit(f"edges differ: graph-only={graph_edges - drawn} "
                         f"drawn-only={drawn - graph_edges}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="dali-flow-diagram",
                                     description="Render the DALI flow SVG from the graph.")
    parser.add_argument("--out", default="dali_flow.svg", help="Output .svg path.")
    parser.add_argument("--check", action="store_true",
                        help="Only verify the layout still matches the graph.")
    args = parser.parse_args(argv)
    _verify_against_graph()
    if args.check:
        print("layout matches build_graph()")
        return 0
    svg = build_svg()
    Path(args.out).write_text(svg, encoding="utf-8")
    print(f"wrote {args.out} (sha256 {hashlib.sha256(svg.encode()).hexdigest()[:12]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

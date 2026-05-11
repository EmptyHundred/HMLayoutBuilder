"""Render a town YAML to an image.

Usage:
    python -m towngen.visualize town.yaml --out town.png
    python -m towngen.visualize town.yaml --show
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List


WARD_COLORS = {
    "Market":         "#f6d86b",
    "Temple":         "#c7a0ff",
    "Administration": "#ff9b7a",
    "Patriciate":     "#e8b4b8",
    "Merchant":       "#ffd093",
    "Craftsmen":      "#c9e4ca",
    "Gate":           "#b0b0b0",
    "Military":       "#a0afc7",
    "Slum":           "#9a8478",
    "Park":           "#86c78f",
    "Farm":           "#e6d5a0",
    "Hamlet":         "#d8c99a",
    "Castle":         "#8b6b5a",
    "Ward":           "#e8e0c9",  # unnamed countryside
    None:             "#f0ebd8",
}

WATER_COLOR   = "#a7c7e7"
BG_COLOR      = "#f3ecd0"
WALL_COLOR    = "#4a3f35"
TOWER_COLOR   = "#2e2721"
GATE_COLOR    = "#c0392b"
STREET_COLOR  = "#5a4634"
ROAD_COLOR    = "#7a6548"
BUILDING_FILL = "#d7c6a8"
BUILDING_EDGE = "#6b5744"
PLAZA_COLOR   = "#e6d79a"
CITADEL_COLOR = "#9a8a78"


def _close(poly: List[List[float]]) -> List[List[float]]:
    if not poly:
        return poly
    if poly[0] != poly[-1]:
        return poly + [poly[0]]
    return poly


def _draw_poly(ax, poly, **kwargs):
    from matplotlib.patches import Polygon as MplPoly

    if len(poly) < 3:
        return
    patch = MplPoly(poly, closed=True, **kwargs)
    ax.add_patch(patch)


def render(data: Dict[str, Any], ax) -> None:
    # --- background: countryside polygon per patch ---------------------
    for p in data.get("patches", []):
        ward = p.get("ward")
        color = WARD_COLORS.get(ward, WARD_COLORS["Ward"])
        _draw_poly(
            ax,
            p["polygon"],
            facecolor=color,
            edgecolor="#8a7b62",
            linewidth=0.4,
            zorder=1,
        )

    # --- plaza highlight -----------------------------------------------
    plaza = data.get("plaza")
    if plaza:
        _draw_poly(
            ax, plaza, facecolor=PLAZA_COLOR, edgecolor="#a8906a",
            linewidth=0.6, zorder=2,
        )

    # --- citadel polygon -----------------------------------------------
    citadel = data.get("citadel")
    if citadel:
        _draw_poly(
            ax, citadel["polygon"], facecolor=CITADEL_COLOR,
            edgecolor="#3d3329", linewidth=0.8, zorder=2,
        )

    # --- streets & roads underneath buildings --------------------------
    for street in data.get("arteries", []) or data.get("streets", []):
        xs = [v[0] for v in street]
        ys = [v[1] for v in street]
        ax.plot(xs, ys, color=STREET_COLOR, linewidth=1.6, zorder=3,
                solid_capstyle="round", solid_joinstyle="round")

    for road in data.get("roads", []):
        xs = [v[0] for v in road]
        ys = [v[1] for v in road]
        ax.plot(xs, ys, color=ROAD_COLOR, linewidth=1.0, zorder=3,
                linestyle=(0, (4, 2)), alpha=0.7)

    # --- per-patch buildings -------------------------------------------
    for p in data.get("patches", []):
        for b in p.get("buildings") or []:
            _draw_poly(
                ax, b, facecolor=BUILDING_FILL, edgecolor=BUILDING_EDGE,
                linewidth=0.4, zorder=4,
            )

    # --- citadel buildings + inner wall --------------------------------
    if citadel:
        for b in citadel.get("buildings") or []:
            _draw_poly(
                ax, b, facecolor=BUILDING_FILL, edgecolor=BUILDING_EDGE,
                linewidth=0.4, zorder=4,
            )
        inner_wall = citadel.get("wall")
        if inner_wall:
            wall_poly = _close(inner_wall["polygon"])
            xs = [v[0] for v in wall_poly]
            ys = [v[1] for v in wall_poly]
            ax.plot(xs, ys, color=WALL_COLOR, linewidth=2.0, zorder=5)
            for t in inner_wall.get("towers") or []:
                ax.plot(t[0], t[1], marker="s", markersize=4,
                        markerfacecolor=TOWER_COLOR,
                        markeredgecolor=TOWER_COLOR, zorder=6)
            for g in inner_wall.get("gates") or []:
                ax.plot(g[0], g[1], marker="o", markersize=5,
                        markerfacecolor=GATE_COLOR,
                        markeredgecolor="#5c1a11", zorder=7)

    # --- outer wall ----------------------------------------------------
    wall = data.get("wall")
    if wall:
        wall_poly = _close(wall["polygon"])
        xs = [v[0] for v in wall_poly]
        ys = [v[1] for v in wall_poly]
        ax.plot(xs, ys, color=WALL_COLOR, linewidth=2.4, zorder=5)
        for t in wall.get("towers") or []:
            ax.plot(t[0], t[1], marker="s", markersize=5,
                    markerfacecolor=TOWER_COLOR,
                    markeredgecolor=TOWER_COLOR, zorder=6)
        for g in wall.get("gates") or []:
            ax.plot(g[0], g[1], marker="o", markersize=6,
                    markerfacecolor=GATE_COLOR,
                    markeredgecolor="#5c1a11", zorder=7)


def _attach_hover(fig, ax, data: Dict[str, Any]) -> None:
    """Wire mouse-motion events so patches highlight and show a tooltip on hover."""
    from matplotlib.path import Path as MplPath
    from matplotlib.patches import Polygon as MplPoly

    # Collect (label, description, Path, patch_info) for every hoverable region
    regions = []

    def _describe(p: Dict[str, Any]) -> str:
        lines = [f"Ward: {p.get('ward') or '(unassigned)'}"]
        flags = []
        if p.get("within_walls"):
            flags.append("within walls")
        if p.get("within_city"):
            flags.append("within city")
        if flags:
            lines.append(", ".join(flags))
        b = p.get("buildings") or []
        if b:
            lines.append(f"Buildings: {len(b)}")
        lines.append(f"Patch id: {p.get('id')}")
        return "\n".join(lines)

    for p in data.get("patches", []):
        poly = p["polygon"]
        if len(poly) < 3:
            continue
        regions.append({
            "path": MplPath(poly),
            "label": p.get("ward") or "Ward",
            "desc": _describe(p),
        })

    citadel = data.get("citadel")
    if citadel:
        poly = citadel["polygon"]
        regions.append({
            "path": MplPath(poly),
            "label": "Castle",
            "desc": (
                "Ward: Castle (citadel)\n"
                f"Buildings: {len(citadel.get('buildings') or [])}\n"
                f"Gates: {len((citadel.get('wall') or {}).get('gates') or [])}\n"
                f"Towers: {len((citadel.get('wall') or {}).get('towers') or [])}"
            ),
        })

    # Highlight overlay (updated per hover) and tooltip annotation
    highlight = MplPoly([[0, 0]], closed=True, facecolor="none",
                        edgecolor="#d94f2a", linewidth=2.0, zorder=9,
                        visible=False)
    ax.add_patch(highlight)

    tooltip = ax.annotate(
        "", xy=(0, 0), xytext=(14, 14), textcoords="offset points",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fffbe8",
                  edgecolor="#6a5a42", linewidth=0.8),
        fontsize=9, color="#3a2f22", zorder=10, visible=False,
    )

    current = {"idx": -1}

    def on_move(event):
        if event.inaxes is not ax or event.xdata is None:
            if current["idx"] != -1:
                highlight.set_visible(False)
                tooltip.set_visible(False)
                current["idx"] = -1
                fig.canvas.draw_idle()
            return

        x, y = event.xdata, event.ydata
        # Iterate in reverse so smaller/inner shapes (e.g. citadel) win over outer patches
        hit = -1
        for i in range(len(regions) - 1, -1, -1):
            if regions[i]["path"].contains_point((x, y)):
                hit = i
                break

        if hit == current["idx"]:
            if hit != -1:
                tooltip.xy = (x, y)
                fig.canvas.draw_idle()
            return

        current["idx"] = hit
        if hit == -1:
            highlight.set_visible(False)
            tooltip.set_visible(False)
        else:
            r = regions[hit]
            highlight.set_xy(r["path"].vertices)
            highlight.set_visible(True)
            tooltip.xy = (x, y)
            tooltip.set_text(r["desc"])
            tooltip.set_visible(True)
        fig.canvas.draw_idle()

    fig.canvas.mpl_connect("motion_notify_event", on_move)


def _make_legend(ax, data: Dict[str, Any]) -> None:
    from matplotlib.patches import Patch as LegendPatch

    present = set()
    for p in data.get("patches", []):
        present.add(p.get("ward"))
    if data.get("citadel"):
        present.add("Castle")

    handles = []
    for label in [
        "Market", "Temple", "Administration", "Patriciate", "Merchant",
        "Craftsmen", "Gate", "Military", "Slum", "Park", "Farm", "Hamlet",
        "Castle", "Ward",
    ]:
        if label in present:
            handles.append(
                LegendPatch(facecolor=WARD_COLORS[label], edgecolor="#6a5a42",
                            label=label)
            )
    if handles:
        ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0),
                  fontsize=8, frameon=False)


def visualize(yaml_path: str, out: str = None, show: bool = False,
              dpi: int = 150, size_inches: float = 10.0,
              legend: bool = True, title: bool = True,
              interactive: bool = False) -> None:
    import yaml
    import matplotlib.pyplot as plt

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    fig, ax = plt.subplots(figsize=(size_inches, size_inches))
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    render(data, ax)

    if interactive and show:
        _attach_hover(fig, ax, data)

    if legend:
        _make_legend(ax, data)

    if title:
        parts = [f"seed={data.get('seed')}", f"size={data.get('size')}"]
        ax.set_title(" · ".join(parts), fontsize=11, color="#3a2f22")

    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.margins(0.02)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.tight_layout()

    if out:
        fig.savefig(out, dpi=dpi, facecolor=BG_COLOR, bbox_inches="tight")
    if show:
        plt.show()
    if not show:
        plt.close(fig)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="towngen.visualize",
        description="Render a town YAML layout to an image.",
    )
    parser.add_argument("yaml", help="Path to the town YAML file")
    parser.add_argument("--out", default=None, help="Output image path (PNG/SVG/PDF)")
    parser.add_argument("--show", action="store_true", help="Display in a window")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--size", type=float, default=10.0,
                        help="Figure size in inches")
    parser.add_argument("--no-legend", action="store_true")
    parser.add_argument("--no-title", action="store_true")
    parser.add_argument("--interactive", action="store_true",
                        help="Enable hover tooltips (implies --show)")
    args = parser.parse_args(argv)

    if args.interactive:
        args.show = True
    if not args.out and not args.show:
        args.out = "town.png"

    visualize(
        args.yaml,
        out=args.out,
        show=args.show,
        dpi=args.dpi,
        size_inches=args.size,
        legend=not args.no_legend,
        title=not args.no_title,
        interactive=args.interactive,
    )
    if args.out:
        print(f"Wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
    "Harbour":        "#8fa3b5",
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
        if p.get("waterbody"):
            _draw_poly(
                ax,
                p["polygon"],
                facecolor=WATER_COLOR,
                edgecolor="#6a8ba6",
                linewidth=0.4,
                zorder=1,
            )
            continue
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

    # --- river ---------------------------------------------------------
    river = data.get("river")
    if river and river.get("course"):
        xs = [v[0] for v in river["course"]]
        ys = [v[1] for v in river["course"]]
        width = river.get("width", 4.0)
        # Draw as a thick line with a darker outline underneath
        ax.plot(xs, ys, color="#6a8ba6", linewidth=width * 1.6 + 2, zorder=2.3,
                solid_capstyle="round", solid_joinstyle="round")
        ax.plot(xs, ys, color=WATER_COLOR, linewidth=width * 1.6, zorder=2.4,
                solid_capstyle="round", solid_joinstyle="round")

    # --- bridges -------------------------------------------------------
    for b in data.get("bridges") or []:
        ax.plot(b[0], b[1], marker="D", markersize=5,
                markerfacecolor="#c0a068",
                markeredgecolor="#5c4428", zorder=5.5)

    # --- per-patch buildings -------------------------------------------
    for p in data.get("patches", []):
        for b in p.get("buildings") or []:
            _draw_poly(
                ax, b, facecolor=BUILDING_FILL, edgecolor=BUILDING_EDGE,
                linewidth=0.4, zorder=4,
            )
        # Harbour piers
        for pier in p.get("piers") or []:
            a, b = pier
            ax.plot([a[0], b[0]], [a[1], b[1]],
                    color="#6a5744", linewidth=1.6, zorder=4.5,
                    solid_capstyle="round")

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
    """Wire mouse-motion events so hovering shows a tooltip + highlight.

    Three kinds of targets are hoverable, ranked by priority (small wins):
      - **points** (gates, towers, bridges)         — priority 0
      - **polylines** (streets, roads, arteries,
                        river course, piers)        — priority 1
      - **polygon patches** (wards, citadel, water) — priority 2
    """
    import math
    from matplotlib.path import Path as MplPath
    from matplotlib.patches import Polygon as MplPoly

    targets: List[Dict[str, Any]] = []

    # --- points --------------------------------------------------------
    def _add_point(xy, kind: str, desc: str) -> None:
        targets.append({
            "kind": "point", "xy": (float(xy[0]), float(xy[1])),
            "priority": 0, "label": kind, "desc": desc,
        })

    wall = data.get("wall")
    if wall:
        for idx, g in enumerate(wall.get("gates") or []):
            _add_point(g, "Gate", f"City gate\nPosition: ({g[0]:.1f}, {g[1]:.1f})")
        for idx, t in enumerate(wall.get("towers") or []):
            _add_point(t, "Tower", f"Wall tower\nPosition: ({t[0]:.1f}, {t[1]:.1f})")

    citadel = data.get("citadel")
    if citadel:
        inner = citadel.get("wall") or {}
        for g in inner.get("gates") or []:
            _add_point(g, "Citadel gate",
                       f"Citadel gate\nPosition: ({g[0]:.1f}, {g[1]:.1f})")
        for t in inner.get("towers") or []:
            _add_point(t, "Citadel tower",
                       f"Citadel tower\nPosition: ({t[0]:.1f}, {t[1]:.1f})")

    for b in data.get("bridges") or []:
        _add_point(b, "Bridge",
                   f"Bridge (street × river crossing)\n"
                   f"Position: ({b[0]:.1f}, {b[1]:.1f})")

    # --- polylines -----------------------------------------------------
    def _add_polyline(pts, label: str, desc: str) -> None:
        if len(pts) < 2:
            return
        targets.append({
            "kind": "line",
            "pts": [(float(v[0]), float(v[1])) for v in pts],
            "priority": 1, "label": label, "desc": desc,
        })

    river = data.get("river")
    if river and river.get("course"):
        _add_polyline(
            river["course"], "River",
            f"River\nWidth: {river.get('width', '?')}\n"
            f"Bridges: {len(data.get('bridges') or [])}"
        )

    for i, s in enumerate(data.get("arteries") or []):
        _add_polyline(
            s, "Artery",
            f"Main street (artery #{i})\nSegments: {len(s) - 1}"
        )
    # Only fall back to individual streets/roads if arteries weren't computed
    if not (data.get("arteries") or []):
        for i, s in enumerate(data.get("streets") or []):
            _add_polyline(
                s, "Street",
                f"Street #{i}\nSegments: {len(s) - 1}"
            )
    for i, s in enumerate(data.get("roads") or []):
        _add_polyline(
            s, "Road",
            f"Outskirts road #{i}\nSegments: {len(s) - 1}"
        )

    # Harbour piers
    for p in data.get("patches") or []:
        for j, pier in enumerate(p.get("piers") or []):
            _add_polyline(
                pier, "Pier",
                f"Harbour pier (patch {p.get('id')}, #{j})"
            )

    # --- polygons (patches + citadel) ---------------------------------
    def _describe_patch(p: Dict[str, Any]) -> str:
        if p.get("waterbody"):
            label = "Water"
        else:
            label = p.get("ward") or "(unassigned)"
        lines = [f"Ward: {label}"]
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
        piers = p.get("piers") or []
        if piers:
            lines.append(f"Piers: {len(piers)}")
        lines.append(f"Patch id: {p.get('id')}")
        return "\n".join(lines)

    for p in data.get("patches", []):
        poly = p["polygon"]
        if len(poly) < 3:
            continue
        if p.get("waterbody"):
            label = "Water"
        else:
            label = p.get("ward") or "Ward"
        targets.append({
            "kind": "polygon",
            "path": MplPath(poly), "vertices": poly,
            "priority": 2, "label": label,
            "desc": _describe_patch(p),
        })

    if citadel:
        targets.append({
            "kind": "polygon",
            "path": MplPath(citadel["polygon"]),
            "vertices": citadel["polygon"],
            "priority": 2, "label": "Castle",
            "desc": (
                "Ward: Castle (citadel)\n"
                f"Buildings: {len(citadel.get('buildings') or [])}\n"
                f"Gates: {len((citadel.get('wall') or {}).get('gates') or [])}\n"
                f"Towers: {len((citadel.get('wall') or {}).get('towers') or [])}"
            ),
        })

    # --- pixel-to-data threshold (re-computed each hover) -------------
    def _px_to_data(px: float) -> float:
        """How many data units per screen pixel in this axes?"""
        trans = ax.transData.inverted()
        a = trans.transform((0, 0))
        b = trans.transform((px, 0))
        return abs(b[0] - a[0])

    def _point_seg_dist_sq(px, py, ax_, ay_, bx_, by_):
        dx, dy = bx_ - ax_, by_ - ay_
        seg_len2 = dx * dx + dy * dy
        if seg_len2 == 0:
            return (px - ax_) ** 2 + (py - ay_) ** 2
        t = max(0.0, min(1.0, ((px - ax_) * dx + (py - ay_) * dy) / seg_len2))
        qx, qy = ax_ + dx * t, ay_ + dy * t
        return (px - qx) ** 2 + (py - qy) ** 2

    # --- highlight artists --------------------------------------------
    from matplotlib.lines import Line2D

    poly_highlight = MplPoly([[0, 0]], closed=True, facecolor="none",
                             edgecolor="#d94f2a", linewidth=2.0, zorder=9,
                             visible=False)
    ax.add_patch(poly_highlight)
    line_highlight = Line2D([], [], color="#d94f2a", linewidth=2.5,
                            zorder=9.5, visible=False)
    ax.add_line(line_highlight)
    point_highlight = Line2D([], [], color="#d94f2a", marker="o",
                             markersize=10, markerfacecolor="none",
                             markeredgewidth=2, zorder=9.8, visible=False,
                             linestyle="")
    ax.add_line(point_highlight)

    tooltip = ax.annotate(
        "", xy=(0, 0), xytext=(14, 14), textcoords="offset points",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#fffbe8",
                  edgecolor="#6a5a42", linewidth=0.8),
        fontsize=9, color="#3a2f22", zorder=10, visible=False,
    )

    current = {"idx": -1}

    def _hide_all():
        poly_highlight.set_visible(False)
        line_highlight.set_visible(False)
        point_highlight.set_visible(False)
        tooltip.set_visible(False)

    def on_move(event):
        if event.inaxes is not ax or event.xdata is None:
            if current["idx"] != -1:
                _hide_all()
                current["idx"] = -1
                fig.canvas.draw_idle()
            return

        x, y = event.xdata, event.ydata

        # Pixel thresholds converted to data units
        point_radius = _px_to_data(10)
        line_radius = _px_to_data(6)
        point_r_sq = point_radius * point_radius
        line_r_sq = line_radius * line_radius

        best_idx = -1
        best_priority = 99
        best_dist = float("inf")

        for i, t in enumerate(targets):
            if t["priority"] > best_priority:
                continue
            if t["kind"] == "point":
                px_, py_ = t["xy"]
                d2 = (px_ - x) ** 2 + (py_ - y) ** 2
                if d2 <= point_r_sq and (
                    t["priority"] < best_priority or d2 < best_dist
                ):
                    best_idx = i
                    best_priority = t["priority"]
                    best_dist = d2
            elif t["kind"] == "line":
                # Early out if too far — cheap bbox test
                pts = t["pts"]
                d2_min = float("inf")
                for k in range(len(pts) - 1):
                    ax_, ay_ = pts[k]
                    bx_, by_ = pts[k + 1]
                    # Quick rejection
                    if (min(ax_, bx_) - line_radius > x or
                        max(ax_, bx_) + line_radius < x or
                        min(ay_, by_) - line_radius > y or
                        max(ay_, by_) + line_radius < y):
                        continue
                    d2 = _point_seg_dist_sq(x, y, ax_, ay_, bx_, by_)
                    if d2 < d2_min:
                        d2_min = d2
                if d2_min <= line_r_sq and (
                    t["priority"] < best_priority or d2_min < best_dist
                ):
                    best_idx = i
                    best_priority = t["priority"]
                    best_dist = d2_min
            else:  # polygon
                if best_priority < 2:
                    continue  # already have a more specific hit
                if t["path"].contains_point((x, y)):
                    # Keep the most recently-added polygon (smaller/inner wins)
                    best_idx = i
                    best_priority = 2
                    best_dist = 0

        if best_idx == current["idx"]:
            if best_idx != -1:
                tooltip.xy = (x, y)
                fig.canvas.draw_idle()
            return

        current["idx"] = best_idx
        if best_idx == -1:
            _hide_all()
        else:
            t = targets[best_idx]
            _hide_all()
            if t["kind"] == "polygon":
                poly_highlight.set_xy(t["vertices"])
                poly_highlight.set_visible(True)
            elif t["kind"] == "line":
                xs = [v[0] for v in t["pts"]]
                ys = [v[1] for v in t["pts"]]
                line_highlight.set_data(xs, ys)
                line_highlight.set_visible(True)
            elif t["kind"] == "point":
                point_highlight.set_data([t["xy"][0]], [t["xy"][1]])
                point_highlight.set_visible(True)
            tooltip.xy = (x, y)
            tooltip.set_text(t["desc"])
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
        "Craftsmen", "Gate", "Military", "Slum", "Park", "Harbour",
        "Farm", "Hamlet", "Castle", "Ward",
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

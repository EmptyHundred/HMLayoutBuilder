"""Convert a generated Model into a plain dict / YAML string."""

from __future__ import annotations

from typing import Any, Dict, List

from .model import Model
from .point import Point
from .polygon import Polygon


def _pt(p: Point) -> List[float]:
    return [round(p.x, 4), round(p.y, 4)]


def _poly(p: Polygon) -> List[List[float]]:
    return [_pt(v) for v in p]


def to_dict(model: Model) -> Dict[str, Any]:
    from . import random_ as rnd

    result: Dict[str, Any] = {
        "seed": rnd.get_seed(),
        "size": model.n_patches,
        "center": _pt(model.center),
        "city_radius": round(model.city_radius, 4),
    }

    # Walls (outer boundary + optional real wall)
    if model.wall is not None:
        result["wall"] = {
            "polygon": _poly(model.wall.shape),
            "towers": [_pt(t) for t in model.wall.towers],
            "gates": [_pt(g) for g in model.wall.gates],
        }
    else:
        result["wall"] = None

    # City silhouette regardless of walls
    result["border"] = _poly(model.border.shape) if model.border is not None else []

    # Citadel
    if model.citadel is not None and model.citadel.ward is not None:
        castle = model.citadel.ward
        citadel_data: Dict[str, Any] = {
            "polygon": _poly(model.citadel.shape),
            "buildings": [_poly(g) for g in castle.geometry],
        }
        # Castle has its own wall
        inner_wall = getattr(castle, "wall", None)
        if inner_wall is not None:
            citadel_data["wall"] = {
                "polygon": _poly(inner_wall.shape),
                "towers": [_pt(t) for t in inner_wall.towers],
                "gates": [_pt(g) for g in inner_wall.gates],
            }
        result["citadel"] = citadel_data
    else:
        result["citadel"] = None

    # Plaza
    if model.plaza is not None:
        result["plaza"] = _poly(model.plaza.shape)
    else:
        result["plaza"] = None

    # Streets / roads (model.arteries contains the smoothed, deduped network)
    result["streets"] = [_poly(s) for s in model.streets]
    result["roads"] = [_poly(r) for r in model.roads]
    result["arteries"] = [_poly(a) for a in model.arteries]

    # Water features
    if model.river_course:
        result["river"] = {
            "course": [_pt(v) for v in model.river_course],
            "width": round(model.river_width, 4),
        }
    else:
        result["river"] = None

    if model.bridges:
        result["bridges"] = [_pt(p) for p in model.bridges]
    else:
        result["bridges"] = []

    result["coast"] = bool(model.coast_needed)

    # Patches + ward buildings
    patches_out: List[Dict[str, Any]] = []
    for i, patch in enumerate(model.patches):
        if patch is model.citadel:
            continue  # citadel already emitted separately
        entry: Dict[str, Any] = {
            "id": i,
            "polygon": _poly(patch.shape),
            "within_city": patch.within_city,
            "within_walls": patch.within_walls,
            "waterbody": bool(patch.waterbody),
            "ward": patch.ward.get_label() if patch.ward is not None else None,
        }
        if patch.ward is not None and patch.ward.geometry:
            entry["buildings"] = [_poly(g) for g in patch.ward.geometry]
        # Harbour piers
        if patch.ward is not None and getattr(patch.ward, "piers", None):
            entry["piers"] = [
                [_pt(a), _pt(b)] for a, b in patch.ward.piers
            ]
        patches_out.append(entry)
    result["patches"] = patches_out

    return result


def to_yaml(model: Model) -> str:
    try:
        import yaml
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "PyYAML is required for YAML output. Install it with `pip install pyyaml`."
        ) from e

    return yaml.safe_dump(to_dict(model), sort_keys=False, default_flow_style=None)

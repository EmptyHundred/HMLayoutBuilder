"""Port of com.watabou.towngenerator.building.Cutter."""

from __future__ import annotations

import math
from typing import List, Optional

from . import geomutils as gu
from .point import Point
from .polygon import Polygon


def bisect(
    poly: Polygon,
    vertex: Point,
    ratio: float = 0.5,
    angle: float = 0.0,
    gap: float = 0.0,
) -> List[Polygon]:
    nxt = poly.next(vertex)

    p1 = gu.interpolate(vertex, nxt, ratio)
    d = nxt.subtract(vertex)

    cos_b = math.cos(angle)
    sin_b = math.sin(angle)
    vx = d.x * cos_b - d.y * sin_b
    vy = d.y * cos_b + d.x * sin_b
    p2 = Point(p1.x - vy, p1.y + vx)

    return poly.cut(p1, p2, gap)


def radial(
    poly: Polygon, center: Optional[Point] = None, gap: float = 0.0
) -> List[Polygon]:
    if center is None:
        center = poly.centroid

    sectors: List[Polygon] = []

    def _emit(v0: Point, v1: Point) -> None:
        sector = Polygon([center, v0, v1])
        if gap > 0:
            sector = sector.shrink([gap / 2, 0, gap / 2])
        sectors.append(sector)

    poly.for_edge(_emit)
    return sectors


def semi_radial(
    poly: Polygon, center: Optional[Point] = None, gap: float = 0.0
) -> List[Polygon]:
    if center is None:
        centroid = poly.centroid
        center = min(poly, key=lambda v: Point.distance(v, centroid))

    gap = gap / 2
    sectors: List[Polygon] = []

    def _emit(v0: Point, v1: Point) -> None:
        if v0 is center or v1 is center:
            return
        sector = Polygon([center, v0, v1])
        if gap > 0:
            d = [
                gap if poly.find_edge(center, v0) == -1 else 0,
                0,
                gap if poly.find_edge(v1, center) == -1 else 0,
            ]
            sector = sector.shrink(d)
        sectors.append(sector)

    poly.for_edge(_emit)
    return sectors


def ring(poly: Polygon, thickness: float) -> List[Polygon]:
    slices = []

    def _collect(v1: Point, v2: Point) -> None:
        v = v2.subtract(v1)
        n = v.rotate90().norm(thickness)
        slices.append({"p1": v1.add(n), "p2": v2.add(n), "len": v.length})

    poly.for_edge(_collect)
    slices.sort(key=lambda s: s["len"])

    peel: List[Polygon] = []
    p = poly
    for s in slices:
        halves = p.cut(s["p1"], s["p2"])
        p = halves[0]
        if len(halves) == 2:
            peel.append(halves[1])

    return peel

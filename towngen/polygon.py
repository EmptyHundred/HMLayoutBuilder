"""Port of com.watabou.geom.Polygon.

Polygon subclasses list[Point] — in Haxe it was `abstract Polygon(Array<Point>)`.
"""

from __future__ import annotations

import math
from typing import Callable, List, Optional

from . import geomutils as gu
from . import mathutils as mu
from .point import Point

DELTA = 1e-6


class Polygon(list):
    def __init__(self, vertices: Optional[List[Point]] = None) -> None:
        if vertices is None:
            super().__init__()
        else:
            super().__init__(list(vertices))

    # --- construction helpers -------------------------------------------
    def copy(self) -> "Polygon":
        return Polygon(list(self))

    def set(self, other: "Polygon") -> None:
        for i in range(len(other)):
            self[i].set(other[i])

    # --- geometric measurements -----------------------------------------
    @property
    def square(self) -> float:
        v1 = self[-1]
        v2 = self[0]
        s = v1.x * v2.y - v2.x * v1.y
        for i in range(1, len(self)):
            v1 = v2
            v2 = self[i]
            s += v1.x * v2.y - v2.x * v1.y
        return s * 0.5

    @property
    def perimeter(self) -> float:
        total = 0.0
        n = len(self)
        for i in range(n):
            total += Point.distance(self[i], self[(i + 1) % n])
        return total

    @property
    def compactness(self) -> float:
        p = self.perimeter
        return 4 * math.pi * self.square / (p * p)

    @property
    def center(self) -> Point:
        c = Point()
        for v in self:
            c.add_eq(v)
        c.scale_eq(1 / len(self))
        return c

    @property
    def centroid(self) -> Point:
        x = 0.0
        y = 0.0
        a = 0.0
        n = len(self)
        for i in range(n):
            v0 = self[i]
            v1 = self[(i + 1) % n]
            f = gu.cross(v0.x, v0.y, v1.x, v1.y)
            a += f
            x += (v0.x + v1.x) * f
            y += (v0.y + v1.y) * f
        s6 = 1 / (3 * a)
        return Point(s6 * x, s6 * y)

    # --- membership / identity ------------------------------------------
    def contains(self, v: Point) -> bool:
        for el in self:
            if el is v:
                return True
        return False

    def index_of(self, v: Point, start: int = 0) -> int:
        for i in range(start, len(self)):
            if self[i] is v:
                return i
        return -1

    def last_index_of(self, v: Point) -> int:
        for i in range(len(self) - 1, -1, -1):
            if self[i] is v:
                return i
        return -1

    def remove(self, v) -> None:  # type: ignore[override]
        idx = self.index_of(v)
        if idx != -1:
            self.pop(idx)

    # --- iteration helpers ----------------------------------------------
    def for_edge(self, f: Callable[[Point, Point], None]) -> None:
        n = len(self)
        for i in range(n):
            f(self[i], self[(i + 1) % n])

    def for_segment(self, f: Callable[[Point, Point], None]) -> None:
        for i in range(len(self) - 1):
            f(self[i], self[i + 1])

    # --- transformations -------------------------------------------------
    def offset(self, p: Point) -> None:
        for v in self:
            v.offset(p.x, p.y)

    def rotate(self, a: float) -> None:
        c = math.cos(a)
        s = math.sin(a)
        for v in self:
            nx = v.x * c - v.y * s
            ny = v.y * c + v.x * s
            v.set_to(nx, ny)

    # --- convexity -------------------------------------------------------
    def is_convex_vertex_i(self, i: int) -> bool:
        n = len(self)
        v0 = self[(i + n - 1) % n]
        v1 = self[i]
        v2 = self[(i + 1) % n]
        return gu.cross(v1.x - v0.x, v1.y - v0.y, v2.x - v1.x, v2.y - v1.y) > 0

    def is_convex_vertex(self, v1: Point) -> bool:
        v0 = self.prev(v1)
        v2 = self.next(v1)
        return gu.cross(v1.x - v0.x, v1.y - v0.y, v2.x - v1.x, v2.y - v1.y) > 0

    def is_convex(self) -> bool:
        return all(self.is_convex_vertex(v) for v in self)

    # --- smoothing / simplification -------------------------------------
    def smooth_vertex_i(self, i: int, f: float = 1.0) -> Point:
        n = len(self)
        v = self[i]
        prev = self[(i + n - 1) % n]
        nxt = self[(i + 1) % n]
        return Point(
            (prev.x + v.x * f + nxt.x) / (2 + f),
            (prev.y + v.y * f + nxt.y) / (2 + f),
        )

    def smooth_vertex(self, v: Point, f: float = 1.0) -> Point:
        prev = self.prev(v)
        nxt = self.next(v)
        return Point(prev.x + v.x * f + nxt.x, prev.y + v.y * f + nxt.y).scale(
            1 / (2 + f)
        )

    def distance(self, p: Point) -> float:
        v0 = self[0]
        d = Point.distance(v0, p)
        for i in range(1, len(self)):
            v1 = self[i]
            d1 = Point.distance(v1, p)
            if d1 < d:
                v0 = v1  # noqa: F841  — matches original (bug? but preserved)
                d = d1
        return d

    def smooth_vertex_eq(self, f: float = 1.0) -> "Polygon":
        n = len(self)
        result = Polygon()
        v1 = self[n - 1]
        v2 = self[0]
        for i in range(n):
            v0 = v1
            v1 = v2
            v2 = self[(i + 1) % n]
            result.append(
                Point(
                    (v0.x + v1.x * f + v2.x) / (2 + f),
                    (v0.y + v1.y * f + v2.y) / (2 + f),
                )
            )
        return result

    def filter_short(self, threshold: float) -> "Polygon":
        result = Polygon([self[0]])
        i = 1
        v0 = self[0]
        while i < len(self):
            v1 = self[i]
            i += 1
            while Point.distance(v0, v1) < threshold and i < len(self):
                v1 = self[i]
                i += 1
            result.append(v1)
            v0 = v1
        return result

    # --- insetting / buffering ------------------------------------------
    def inset(self, p1: Point, d: float) -> None:
        i1 = self.index_of(p1)
        n = len(self)
        i0 = i1 - 1 if i1 > 0 else n - 1
        p0 = self[i0]
        i2 = i1 + 1 if i1 < n - 1 else 0
        p2 = self[i2]
        i3 = i2 + 1 if i2 < n - 1 else 0
        p3 = self[i3]

        v0 = p1.subtract(p0)
        v1 = p2.subtract(p1)
        v2 = p3.subtract(p2)

        cos = v0.dot(v1) / v0.length / v1.length
        z = v0.x * v1.y - v0.y * v1.x
        denom = math.sqrt(1 - cos * cos) if abs(cos) < 1 else DELTA
        t = d / denom
        if z > 0:
            t = min(t, v0.length * 0.99)
        else:
            t = min(t, v1.length * 0.5)
        t *= mu.sign(z)
        self[i1] = p1.subtract(v0.norm(t))

        cos = v1.dot(v2) / v1.length / v2.length
        z = v1.x * v2.y - v1.y * v2.x
        denom = math.sqrt(1 - cos * cos) if abs(cos) < 1 else DELTA
        t = d / denom
        if z > 0:
            t = min(t, v2.length * 0.99)
        else:
            t = min(t, v1.length * 0.5)
        self[i2] = p2.add(v2.norm(t))

    def inset_all(self, d: List[float]) -> "Polygon":
        p = Polygon(self)
        for i in range(len(p)):
            if d[i] != 0:
                p.inset(p[i], d[i])
        return p

    def inset_eq(self, d: float) -> None:
        for v in list(self):
            self.inset(v, d)

    def buffer(self, d: List[float]) -> "Polygon":
        # Build a polygon (possibly invalid) with offset edges
        q = Polygon()
        idx = [0]

        def _push_edge(v0: Point, v1: Point) -> None:
            dd = d[idx[0]]
            idx[0] += 1
            if dd == 0:
                q.append(v0)
                q.append(v1)
            else:
                v = v1.subtract(v0)
                nrm = v.rotate90().norm(dd)
                q.append(v0.add(nrm))
                q.append(v1.add(nrm))

        self.for_edge(_push_edge)

        # Resolve self-intersections
        last_edge = 0
        while True:
            was_cut = False
            n = len(q)
            for i in range(last_edge, n - 2):
                last_edge = i
                p11 = q[i]
                p12 = q[i + 1]
                x1 = p11.x
                y1 = p11.y
                dx1 = p12.x - x1
                dy1 = p12.y - y1
                j_max = n if i > 0 else n - 1
                for j in range(i + 2, j_max):
                    p21 = q[j]
                    p22 = q[j + 1] if j < n - 1 else q[0]
                    x2 = p21.x
                    y2 = p21.y
                    dx2 = p22.x - x2
                    dy2 = p22.y - y2
                    t = gu.intersect_lines(x1, y1, dx1, dy1, x2, y2, dx2, dy2)
                    if (
                        t is not None
                        and t.x > DELTA
                        and t.x < 1 - DELTA
                        and t.y > DELTA
                        and t.y < 1 - DELTA
                    ):
                        pn = Point(x1 + dx1 * t.x, y1 + dy1 * t.x)
                        q.insert(j + 1, pn)
                        q.insert(i + 1, pn)
                        was_cut = True
                        break
                if was_cut:
                    break
            if not was_cut:
                break

        # Pick the largest connected component
        regular = list(range(len(q)))
        best_part: Optional[Polygon] = None
        best_sq = float("-inf")

        while regular:
            indices: List[int] = []
            start = regular[0]
            i = start
            while True:
                indices.append(i)
                regular.remove(i)
                nxt = (i + 1) % len(q)
                v = q[nxt]
                next1 = q.index_of(v)
                if next1 == nxt:
                    next1 = q.last_index_of(v)
                i = nxt if next1 == -1 else next1
                if i == start:
                    break

            part = Polygon([q[k] for k in indices])
            s = part.square
            if s > best_sq:
                best_part = part
                best_sq = s

        assert best_part is not None
        return best_part

    def buffer_eq(self, d: float) -> "Polygon":
        return self.buffer([d for _ in self])

    def shrink(self, d: List[float]) -> "Polygon":
        q = Polygon(self)
        idx = [0]

        def _shrink_edge(v1: Point, v2: Point) -> None:
            dd = d[idx[0]]
            idx[0] += 1
            if dd > 0:
                v = v2.subtract(v1)
                nrm = v.rotate90().norm(dd)
                nonlocal_q = q_wrapper[0]
                q_wrapper[0] = nonlocal_q.cut(v1.add(nrm), v2.add(nrm), 0)[0]

        q_wrapper = [q]
        self.for_edge(_shrink_edge)
        return q_wrapper[0]

    def shrink_eq(self, d: float) -> "Polygon":
        return self.shrink([d for _ in self])

    def peel(self, v1: Point, d: float) -> "Polygon":
        i1 = self.index_of(v1)
        i2 = 0 if i1 == len(self) - 1 else i1 + 1
        v2 = self[i2]

        v = v2.subtract(v1)
        nrm = v.rotate90().norm(d)

        return self.cut(v1.add(nrm), v2.add(nrm), 0)[0]

    def simplify(self, n: int) -> None:
        length = len(self)
        while length > n:
            best = 0
            min_m = float("inf")
            b = self[length - 1]
            c = self[0]
            for i in range(length):
                a = b
                b = c
                c = self[(i + 1) % length]
                m = abs(a.x * (b.y - c.y) + b.x * (c.y - a.y) + c.x * (a.y - b.y))
                if m < min_m:
                    best = i
                    min_m = m
            self.pop(best)
            length -= 1

    # --- edges / neighbors ----------------------------------------------
    def find_edge(self, a: Point, b: Point) -> int:
        idx = self.index_of(a)
        if idx != -1 and self[(idx + 1) % len(self)] is b:
            return idx
        return -1

    def next(self, a: Point) -> Point:
        return self[(self.index_of(a) + 1) % len(self)]

    def prev(self, a: Point) -> Point:
        n = len(self)
        return self[(self.index_of(a) + n - 1) % n]

    def vector(self, v: Point) -> Point:
        return self.next(v).subtract(v)

    def vector_i(self, i: int) -> Point:
        j = 0 if i == len(self) - 1 else i + 1
        return self[j].subtract(self[i])

    def borders(self, other: "Polygon") -> bool:
        n1 = len(self)
        n2 = len(other)
        for i in range(n1):
            j = other.index_of(self[i])
            if j != -1:
                nxt = self[(i + 1) % n1]
                if nxt is other[(j + 1) % n2] or nxt is other[(j + n2 - 1) % n2]:
                    return True
        return False

    def get_bounds(self) -> tuple:
        minx = maxx = self[0].x
        miny = maxy = self[0].y
        for v in self:
            if v.x < minx:
                minx = v.x
            if v.x > maxx:
                maxx = v.x
            if v.y < miny:
                miny = v.y
            if v.y > maxy:
                maxy = v.y
        return (minx, miny, maxx, maxy)

    # --- splitting / cutting --------------------------------------------
    def split(self, p1: Point, p2: Point) -> List["Polygon"]:
        return self.split_i(self.index_of(p1), self.index_of(p2))

    def split_i(self, i1: int, i2: int) -> List["Polygon"]:
        if i1 > i2:
            i1, i2 = i2, i1
        return [
            Polygon(list(self[i1 : i2 + 1])),
            Polygon(list(self[i2:]) + list(self[: i1 + 1])),
        ]

    def cut(self, p1: Point, p2: Point, gap: float = 0) -> List["Polygon"]:
        x1 = p1.x
        y1 = p1.y
        dx1 = p2.x - x1
        dy1 = p2.y - y1

        n = len(self)
        edge1 = 0
        ratio1 = 0.0
        edge2 = 0
        ratio2 = 0.0
        count = 0

        for i in range(n):
            v0 = self[i]
            v1 = self[(i + 1) % n]
            x2 = v0.x
            y2 = v0.y
            dx2 = v1.x - x2
            dy2 = v1.y - y2

            t = gu.intersect_lines(x1, y1, dx1, dy1, x2, y2, dx2, dy2)
            if t is not None and t.y >= 0 and t.y <= 1:
                if count == 0:
                    edge1 = i
                    ratio1 = t.x
                elif count == 1:
                    edge2 = i
                    ratio2 = t.x
                count += 1

        if count == 2:
            point1 = p1.add(p2.subtract(p1).scale(ratio1))
            point2 = p1.add(p2.subtract(p1).scale(ratio2))

            half1 = Polygon(list(self[edge1 + 1 : edge2 + 1]))
            half1.insert(0, point1)
            half1.append(point2)

            half2 = Polygon(list(self[edge2 + 1 :]) + list(self[: edge1 + 1]))
            half2.insert(0, point2)
            half2.append(point1)

            if gap > 0:
                half1 = half1.peel(point2, gap / 2)
                half2 = half2.peel(point1, gap / 2)

            v = self.vector_i(edge1)
            if gu.cross(dx1, dy1, v.x, v.y) > 0:
                return [half1, half2]
            return [half2, half1]

        return [Polygon(self)]

    def interpolate(self, p: Point) -> List[float]:
        dd = []
        total = 0.0
        for v in self:
            d = 1 / Point.distance(v, p)
            total += d
            dd.append(d)
        return [d / total for d in dd]

    # --- factories -------------------------------------------------------
    @staticmethod
    def rect(w: float = 1.0, h: float = 1.0) -> "Polygon":
        return Polygon(
            [
                Point(-w / 2, -h / 2),
                Point(w / 2, -h / 2),
                Point(w / 2, h / 2),
                Point(-w / 2, h / 2),
            ]
        )

    @staticmethod
    def regular(n: int = 8, r: float = 1.0) -> "Polygon":
        pts = []
        for i in range(n):
            a = i / n * math.pi * 2
            pts.append(Point(r * math.cos(a), r * math.sin(a)))
        return Polygon(pts)

    @staticmethod
    def circle(r: float = 1.0) -> "Polygon":
        return Polygon.regular(16, r)

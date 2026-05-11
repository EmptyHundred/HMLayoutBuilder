"""Port of com.watabou.geom.Voronoi — Bowyer-Watson incremental Delaunay + its dual.

Preserves Point identity throughout: shared vertices between neighbouring
regions (patches) are the same Point instance, which downstream code relies on.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .point import Point


class Triangle:
    __slots__ = ("p1", "p2", "p3", "c", "r")

    def __init__(self, p1: Point, p2: Point, p3: Point) -> None:
        # Orient CCW
        s = (
            (p2.x - p1.x) * (p2.y + p1.y)
            + (p3.x - p2.x) * (p3.y + p2.y)
            + (p1.x - p3.x) * (p1.y + p3.y)
        )
        self.p1 = p1
        if s > 0:
            self.p2 = p2
            self.p3 = p3
        else:
            self.p2 = p3
            self.p3 = p2

        # Circumcircle
        x1 = (self.p1.x + self.p2.x) / 2
        y1 = (self.p1.y + self.p2.y) / 2
        x2 = (self.p2.x + self.p3.x) / 2
        y2 = (self.p2.y + self.p3.y) / 2

        dx1 = self.p1.y - self.p2.y
        dy1 = self.p2.x - self.p1.x
        dx2 = self.p2.y - self.p3.y
        dy2 = self.p3.x - self.p2.x

        tg1 = dy1 / dx1 if dx1 != 0 else float("inf")
        if tg1 == float("inf"):
            t2 = (x1 - x2) / dx2 if dx2 != 0 else 0
        else:
            t2 = ((y1 - y2) - (x1 - x2) * tg1) / (dy2 - dx2 * tg1)

        self.c = Point(x2 + dx2 * t2, y2 + dy2 * t2)
        self.r = Point.distance(self.c, self.p1)

    def has_edge(self, a: Point, b: Point) -> bool:
        return (
            (self.p1 is a and self.p2 is b)
            or (self.p2 is a and self.p3 is b)
            or (self.p3 is a and self.p1 is b)
        )


class Region:
    __slots__ = ("seed", "vertices")

    def __init__(self, seed: Point) -> None:
        self.seed = seed
        self.vertices: List[Triangle] = []

    def sort_vertices(self) -> "Region":
        import functools

        self.vertices.sort(key=functools.cmp_to_key(self._compare_angles))
        return self

    def center(self) -> Point:
        c = Point()
        for v in self.vertices:
            c.add_eq(v.c)
        c.scale_eq(1 / len(self.vertices))
        return c

    def borders(self, r: "Region") -> bool:
        n1 = len(self.vertices)
        n2 = len(r.vertices)
        for i in range(n1):
            try:
                j = r.vertices.index(self.vertices[i])
            except ValueError:
                continue
            return self.vertices[(i + 1) % n1] is r.vertices[(j + n2 - 1) % n2]
        return False

    def _compare_angles(self, v1: Triangle, v2: Triangle) -> int:
        x1 = v1.c.x - self.seed.x
        y1 = v1.c.y - self.seed.y
        x2 = v2.c.x - self.seed.x
        y2 = v2.c.y - self.seed.y

        if x1 >= 0 and x2 < 0:
            return 1
        if x2 >= 0 and x1 < 0:
            return -1
        if x1 == 0 and x2 == 0:
            return 1 if y2 > y1 else -1

        cross = x2 * y1 - x1 * y2
        if cross == 0:
            return 0
        return -1 if cross < 0 else 1


class Voronoi:
    def __init__(
        self, minx: float, miny: float, maxx: float, maxy: float
    ) -> None:
        self.triangles: List[Triangle] = []

        c1 = Point(minx, miny)
        c2 = Point(minx, maxy)
        c3 = Point(maxx, miny)
        c4 = Point(maxx, maxy)
        self.frame: List[Point] = [c1, c2, c3, c4]
        self.points: List[Point] = [c1, c2, c3, c4]
        self.triangles.append(Triangle(c1, c2, c3))
        self.triangles.append(Triangle(c2, c3, c4))

        self._regions: Dict[Point, Region] = {
            p: self._build_region(p) for p in self.points
        }
        self._regions_dirty = False

    def add_point(self, p: Point) -> None:
        to_split = [tr for tr in self.triangles if Point.distance(p, tr.c) < tr.r]
        if not to_split:
            return

        self.points.append(p)

        a: List[Point] = []
        b: List[Point] = []
        for t1 in to_split:
            e1 = e2 = e3 = True
            for t2 in to_split:
                if t2 is t1:
                    continue
                if e1 and t2.has_edge(t1.p2, t1.p1):
                    e1 = False
                if e2 and t2.has_edge(t1.p3, t1.p2):
                    e2 = False
                if e3 and t2.has_edge(t1.p1, t1.p3):
                    e3 = False
                if not (e1 or e2 or e3):
                    break
            if e1:
                a.append(t1.p1)
                b.append(t1.p2)
            if e2:
                a.append(t1.p2)
                b.append(t1.p3)
            if e3:
                a.append(t1.p3)
                b.append(t1.p1)

        index = 0
        while True:
            self.triangles.append(Triangle(p, a[index], b[index]))
            # find where a[i] == b[index]
            try:
                index = a.index(b[index])
            except ValueError:
                break
            if index == 0:
                break

        for tr in to_split:
            self.triangles.remove(tr)

        self._regions_dirty = True

    def _build_region(self, p: Point) -> Region:
        r = Region(p)
        for tr in self.triangles:
            if tr.p1 is p or tr.p2 is p or tr.p3 is p:
                r.vertices.append(tr)
        return r.sort_vertices()

    @property
    def regions(self) -> Dict[Point, Region]:
        if self._regions_dirty:
            self._regions = {p: self._build_region(p) for p in self.points}
            self._regions_dirty = False
        return self._regions

    def _is_real(self, tr: Triangle) -> bool:
        return not (
            any(fp is tr.p1 for fp in self.frame)
            or any(fp is tr.p2 for fp in self.frame)
            or any(fp is tr.p3 for fp in self.frame)
        )

    def triangulation(self) -> List[Triangle]:
        return [tr for tr in self.triangles if self._is_real(tr)]

    def partitioning(self) -> List[Region]:
        result: List[Region] = []
        for p in self.points:
            r = self.regions[p]
            if all(self._is_real(v) for v in r.vertices):
                result.append(r)
        return result

    def get_neighbours(self, r1: Region) -> List[Region]:
        return [r2 for r2 in self.regions.values() if r1.borders(r2)]

    @staticmethod
    def relax(voronoi: "Voronoi", to_relax: Optional[List[Point]] = None) -> "Voronoi":
        regions = voronoi.partitioning()
        points = list(voronoi.points)
        for p in voronoi.frame:
            points.remove(p)

        if to_relax is None:
            to_relax = voronoi.points
        for r in regions:
            if any(p is r.seed for p in to_relax):
                points.remove(r.seed)
                points.append(r.center())

        return Voronoi.build(points)

    @staticmethod
    def build(vertices: List[Point]) -> "Voronoi":
        minx = miny = 1e10
        maxx = maxy = -1e9
        for v in vertices:
            if v.x < minx:
                minx = v.x
            if v.y < miny:
                miny = v.y
            if v.x > maxx:
                maxx = v.x
            if v.y > maxy:
                maxy = v.y
        dx = (maxx - minx) * 0.5
        dy = (maxy - miny) * 0.5

        voronoi = Voronoi(minx - dx / 2, miny - dy / 2, maxx + dx / 2, maxy + dy / 2)
        for v in vertices:
            voronoi.add_point(v)
        return voronoi

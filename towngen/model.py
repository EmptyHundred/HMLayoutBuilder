"""Port of com.watabou.towngenerator.building.Model."""

from __future__ import annotations

import math
from typing import List, Optional

from . import mathutils as mu
from . import random_ as rnd
from .curtain_wall import CurtainWall
from .patch import Patch
from .point import Point
from .polygon import Polygon
from .segment import Segment
from .topology import Topology
from .voronoi import Voronoi
from .wards import (
    AdministrationWard,
    Cathedral,
    CraftsmenWard,
    Castle,
    Farm,
    GateWard,
    Hamlet,
    Market,
    MerchantWard,
    MilitaryWard,
    Park,
    PatriciateWard,
    Slum,
    Ward,
)


WARDS = [
    CraftsmenWard, CraftsmenWard, MerchantWard, CraftsmenWard, CraftsmenWard, Cathedral,
    CraftsmenWard, CraftsmenWard, CraftsmenWard, CraftsmenWard, CraftsmenWard,
    CraftsmenWard, CraftsmenWard, CraftsmenWard, AdministrationWard, CraftsmenWard,
    Slum, CraftsmenWard, Slum, PatriciateWard, Market,
    Slum, CraftsmenWard, CraftsmenWard, CraftsmenWard, Slum,
    CraftsmenWard, CraftsmenWard, CraftsmenWard, MilitaryWard, Slum,
    CraftsmenWard, Park, PatriciateWard, Market, MerchantWard,
]


class Model:
    instance: Optional["Model"] = None

    def __init__(
        self,
        n_patches: int = -1,
        seed: int = -1,
        require_citadel: bool = True,
        require_walls: bool = True,
    ) -> None:
        # Always seed: explicit seed if > 0, otherwise time-based via rnd.reset(-1)
        rnd.reset(seed)

        self.n_patches = n_patches if n_patches != -1 else 15
        self._require_citadel = require_citadel
        self._require_walls = require_walls

        # Size 6 is "small town" in the original Watabou generator, and smaller
        # layouts can't reliably fit both walls and a citadel. Fail fast with a
        # helpful message instead of grinding through 100 doomed retries.
        min_size = 6 if (require_walls and require_citadel) else 5 if (require_walls or require_citadel) else 4
        if self.n_patches < min_size:
            raise ValueError(
                f"n_patches={self.n_patches} is too small. Minimum is "
                f"{min_size} (walls_required={require_walls}, "
                f"citadel_required={require_citadel}). Use --no-walls and/or "
                f"--no-citadel to allow smaller towns down to size 4."
            )

        self.topology: Optional[Topology] = None
        self.patches: List[Patch] = []
        self.waterbody: List[Patch] = []
        self.inner: List[Patch] = []
        self.citadel: Optional[Patch] = None
        self.plaza: Optional[Patch] = None
        self.center: Point = Point(0, 0)
        self.border: Optional[CurtainWall] = None
        self.wall: Optional[CurtainWall] = None
        self.city_radius: float = 0.0
        self.gates: List[Point] = []
        self.arteries: List[Polygon] = []
        self.streets: List[Polygon] = []
        self.roads: List[Polygon] = []

        # Retry until build succeeds (matches Haxe do/while). Re-roll the
        # plaza/citadel/walls flags on every attempt so we don't get stuck on
        # a combination that's impossible for the requested n_patches.
        attempts = 0
        while True:
            attempts += 1
            if attempts > 100:
                raise RuntimeError("Town generation failed after 100 attempts")
            self.plaza_needed = rnd.rand_bool()
            self.citadel_needed = True if self._require_citadel else rnd.rand_bool()
            self.walls_needed = True if self._require_walls else rnd.rand_bool()
            try:
                self._build()
                Model.instance = self
                return
            except Exception:
                Model.instance = None
                continue

    # -------------------------------------------------------------------
    def _build(self) -> None:
        self.streets = []
        self.roads = []
        self.patches = []
        self.inner = []
        self.plaza = None
        self.citadel = None
        self.wall = None
        self.border = None
        self.gates = []
        self.arteries = []

        self._build_patches()
        self._optimize_junctions()
        self._build_walls()
        self._build_streets()
        self._create_wards()
        self._build_geometry()

    # -------------------------------------------------------------------
    def _build_patches(self) -> None:
        sa = rnd.rand_float() * 2 * math.pi
        points: List[Point] = []
        for i in range(self.n_patches * 8):
            a = sa + math.sqrt(i) * 5
            r = 0 if i == 0 else 10 + i * (2 + rnd.rand_float())
            points.append(Point(math.cos(a) * r, math.sin(a) * r))

        voronoi = Voronoi.build(points)

        # Relax central wards a few times
        for _ in range(3):
            to_relax = [voronoi.points[j] for j in range(3)]
            to_relax.append(voronoi.points[self.n_patches])
            voronoi = Voronoi.relax(voronoi, to_relax)

        voronoi.points.sort(key=lambda p: p.length)
        regions = voronoi.partitioning()

        self.patches = []
        self.inner = []

        count = 0
        for r in regions:
            patch = Patch.from_region(r)
            self.patches.append(patch)

            if count == 0:
                self.center = min(patch.shape, key=lambda p: p.length)
                if self.plaza_needed:
                    self.plaza = patch
            elif count == self.n_patches and self.citadel_needed:
                self.citadel = patch
                self.citadel.within_city = True

            if count < self.n_patches:
                patch.within_city = True
                patch.within_walls = self.walls_needed
                self.inner.append(patch)

            count += 1

    # -------------------------------------------------------------------
    def _build_walls(self) -> None:
        reserved = list(self.citadel.shape) if self.citadel is not None else []

        self.border = CurtainWall(self.walls_needed, self, self.inner, reserved)
        if self.walls_needed:
            self.wall = self.border
            self.wall.build_towers()

        radius = self.border.get_radius()
        self.patches = [
            p for p in self.patches if p.shape.distance(self.center) < radius * 3
        ]

        self.gates = list(self.border.gates)

        if self.citadel is not None:
            castle = Castle(self, self.citadel)
            castle.wall.build_towers()
            self.citadel.ward = castle

            if self.citadel.shape.compactness < 0.75:
                raise RuntimeError("Bad citadel shape!")

            self.gates = self.gates + list(castle.wall.gates)

    # -------------------------------------------------------------------
    @staticmethod
    def find_circumference(wards: List[Patch]) -> Polygon:
        if not wards:
            return Polygon()
        if len(wards) == 1:
            return Polygon(list(wards[0].shape))

        A: List[Point] = []
        B: List[Point] = []

        for w1 in wards:
            def _check(a: Point, b: Point, w1=w1) -> None:
                outer_edge = True
                for w2 in wards:
                    if w2.shape.find_edge(b, a) != -1:
                        outer_edge = False
                        break
                if outer_edge:
                    A.append(a)
                    B.append(b)

            w1.shape.for_edge(_check)

        result = Polygon()
        index = 0
        while True:
            result.append(A[index])
            try:
                # identity search: find i such that A[i] is B[index]
                target = B[index]
                new_idx = -1
                for i in range(len(A)):
                    if A[i] is target:
                        new_idx = i
                        break
                if new_idx == -1:
                    raise RuntimeError("Broken circumference")
                index = new_idx
            except Exception:
                break
            if index == 0:
                break

        return result

    # -------------------------------------------------------------------
    def patch_by_vertex(self, v: Point) -> List[Patch]:
        return [p for p in self.patches if p.shape.contains(v)]

    # -------------------------------------------------------------------
    def _build_streets(self) -> None:
        def smooth_street(street: List[Point]) -> None:
            poly = Polygon(street)
            smoothed = poly.smooth_vertex_eq(3)
            for i in range(1, len(street) - 1):
                street[i].set(smoothed[i])

        self.topology = Topology(self)

        for gate in self.gates:
            if self.plaza is not None:
                end = min(self.plaza.shape, key=lambda v: Point.distance(v, gate))
            else:
                end = self.center

            street = self.topology.build_path(gate, end, self.topology.outer)
            if street is not None:
                self.streets.append(Polygon(street))

                if any(g is gate for g in self.border.gates):
                    direction = gate.norm(1000)
                    start = None
                    dist = float("inf")
                    for p in self.topology.node2pt.values():
                        d = Point.distance(p, direction)
                        if d < dist:
                            dist = d
                            start = p

                    if start is not None:
                        road = self.topology.build_path(
                            start, gate, self.topology.inner
                        )
                        if road is not None:
                            self.roads.append(Polygon(road))
            else:
                raise RuntimeError("Unable to build a street!")

        self._tidy_up_roads()

        for a in self.arteries:
            smooth_street(list(a))

    # -------------------------------------------------------------------
    def _tidy_up_roads(self) -> None:
        segments: List[Segment] = []

        def cut2segments(street: Polygon) -> None:
            v1 = street[0]
            for i in range(1, len(street)):
                v0 = v1
                v1 = street[i]

                if (
                    self.plaza is not None
                    and self.plaza.shape.contains(v0)
                    and self.plaza.shape.contains(v1)
                ):
                    continue

                exists = False
                for seg in segments:
                    if seg.start is v0 and seg.end is v1:
                        exists = True
                        break
                if not exists:
                    segments.append(Segment(v0, v1))

        for street in self.streets:
            cut2segments(street)
        for road in self.roads:
            cut2segments(road)

        self.arteries = []
        while segments:
            seg = segments.pop()
            attached = False
            for a in self.arteries:
                if a[0] is seg.end:
                    a.insert(0, seg.start)
                    attached = True
                    break
                if a[-1] is seg.start:
                    a.append(seg.end)
                    attached = True
                    break
            if not attached:
                self.arteries.append(Polygon([seg.start, seg.end]))

    # -------------------------------------------------------------------
    def _optimize_junctions(self) -> None:
        patches_to_optimize: List[Patch] = (
            list(self.inner)
            if self.citadel is None
            else list(self.inner) + [self.citadel]
        )

        wards2clean: List[Patch] = []
        for w in patches_to_optimize:
            index = 0
            while index < len(w.shape):
                v0 = w.shape[index]
                v1 = w.shape[(index + 1) % len(w.shape)]

                if v0 is not v1 and Point.distance(v0, v1) < 8:
                    for w1 in self.patch_by_vertex(v1):
                        if w1 is w:
                            continue
                        idx1 = w1.shape.index_of(v1)
                        if idx1 != -1:
                            w1.shape[idx1] = v0
                        wards2clean.append(w1)

                    v0.add_eq(v1)
                    v0.scale_eq(0.5)

                    w.shape.remove(v1)
                index += 1

        for w in wards2clean:
            i = 0
            while i < len(w.shape):
                v = w.shape[i]
                dup = w.shape.index_of(v, i + 1)
                while dup != -1:
                    w.shape.pop(dup)
                    dup = w.shape.index_of(v, i + 1)
                i += 1

    # -------------------------------------------------------------------
    def _create_wards(self) -> None:
        unassigned = list(self.inner)
        if self.plaza is not None:
            self.plaza.ward = Market(self, self.plaza)
            unassigned = [p for p in unassigned if p is not self.plaza]

        # Gate wards
        for gate in self.border.gates:
            for patch in self.patch_by_vertex(gate):
                if (
                    patch.within_city
                    and patch.ward is None
                    and rnd.rand_bool(0.2 if self.wall is None else 0.5)
                ):
                    patch.ward = GateWard(self, patch)
                    unassigned = [p for p in unassigned if p is not patch]

        wards = list(WARDS)
        for _ in range(len(wards) // 10):
            idx = rnd.rand_int(0, len(wards) - 1)
            wards[idx], wards[idx + 1] = wards[idx + 1], wards[idx]

        while unassigned:
            ward_cls = wards.pop(0) if wards else Slum
            has_rating = "rate_location" in ward_cls.__dict__

            if not has_rating:
                best_patch = None
                while True:
                    candidate = unassigned[rnd.rand_int(0, len(unassigned))]
                    if candidate.ward is None:
                        best_patch = candidate
                        break
            else:
                rate_func = ward_cls.rate_location
                def score(patch: Patch, rate_func=rate_func, ward_cls=ward_cls) -> float:
                    if patch.ward is not None:
                        return float("inf")
                    return rate_func(self, patch)

                best_patch = min(unassigned, key=score)

            best_patch.ward = ward_cls(self, best_patch)
            unassigned = [p for p in unassigned if p is not best_patch]

        # Outskirts
        if self.wall is not None:
            for gate in self.wall.gates:
                if rnd.rand_bool(1 / (self.n_patches - 5)):
                    continue
                for patch in self.patch_by_vertex(gate):
                    if patch.ward is None:
                        patch.within_city = True
                        patch.ward = GateWard(self, patch)

        self.city_radius = 0.0
        for patch in self.patches:
            if patch.within_city:
                for v in patch.shape:
                    self.city_radius = max(self.city_radius, v.length)
            elif patch.ward is None:
                # Countryside: farms on compact plots, hamlets on some of the rest,
                # open land everywhere else.
                if rnd.rand_bool(0.2) and patch.shape.compactness >= 0.7:
                    patch.ward = Farm(self, patch)
                elif rnd.rand_bool(0.35):
                    patch.ward = Hamlet(self, patch)
                else:
                    patch.ward = Ward(self, patch)

    # -------------------------------------------------------------------
    def _build_geometry(self) -> None:
        for patch in self.patches:
            if patch.ward is not None:
                patch.ward.create_geometry()

    # -------------------------------------------------------------------
    def get_neighbour(self, patch: Patch, v: Point) -> Optional[Patch]:
        nxt = patch.shape.next(v)
        for p in self.patches:
            if p.shape.find_edge(nxt, v) != -1:
                return p
        return None

    def get_neighbours(self, patch: Patch) -> List[Patch]:
        return [p for p in self.patches if p is not patch and p.shape.borders(patch.shape)]

    def is_enclosed(self, patch: Patch) -> bool:
        if not patch.within_city:
            return False
        if patch.within_walls:
            return True
        return all(p.within_city for p in self.get_neighbours(patch))

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
    Harbour,
    Market,
    MerchantWard,
    MilitaryWard,
    Park,
    PatriciateWard,
    Slum,
    Ward,
)


def _convex_hull(points: List[tuple]) -> List[tuple]:
    """Andrew's monotone chain. Input/output: list of (x, y) tuples, CCW."""
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _point_in_hull(x: float, y: float, hull: List[tuple]) -> bool:
    """True if (x, y) is on the inside (left) of every CCW hull edge."""
    n = len(hull)
    for i in range(n):
        ax, ay = hull[i]
        bx, by = hull[(i + 1) % n]
        cross = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        if cross < -1e-9:
            return False
    return True


def _clamp_to_hull(inside: "Point", outside: "Point", hull: List[tuple]):
    """Return the Point where the segment (inside -> outside) first crosses
    the hull boundary. Returns None if no crossing is found.
    """
    from .point import Point as _P
    n = len(hull)
    best = None
    best_t = 2.0
    for i in range(n):
        ax, ay = hull[i]
        bx, by = hull[(i + 1) % n]
        ix, iy = _line_intersect(inside.x, inside.y, outside.x, outside.y, ax, ay, bx, by)
        # Parameterise along (inside -> outside)
        seg_dx = outside.x - inside.x
        seg_dy = outside.y - inside.y
        seg_len2 = seg_dx * seg_dx + seg_dy * seg_dy
        if seg_len2 == 0:
            continue
        t = ((ix - inside.x) * seg_dx + (iy - inside.y) * seg_dy) / seg_len2
        if 0 <= t <= 1 and t < best_t:
            # Also check the intersection lies on the hull edge, not just the line
            edge_dx = bx - ax
            edge_dy = by - ay
            edge_len2 = edge_dx * edge_dx + edge_dy * edge_dy
            if edge_len2 == 0:
                continue
            u = ((ix - ax) * edge_dx + (iy - ay) * edge_dy) / edge_len2
            if -1e-6 <= u <= 1 + 1e-6:
                best_t = t
                best = _P(ix, iy)
    return best


def _line_intersect(p1x, p1y, p2x, p2y, ax, ay, bx, by):
    """Intersection of segment (p1->p2) with the infinite line (a->b)."""
    dx1 = p2x - p1x
    dy1 = p2y - p1y
    dx2 = bx - ax
    dy2 = by - ay
    denom = dx1 * dy2 - dy1 * dx2
    if denom == 0:
        return (p2x, p2y)
    t = ((ax - p1x) * dy2 - (ay - p1y) * dx2) / denom
    return (p1x + t * dx1, p1y + t * dy1)


def _clip_polygon_to_hull(subject: list, hull: List[tuple], protected_ids: set):
    """Sutherland-Hodgman: clip ``subject`` (list[Point]) against each CCW
    hull edge. Protected vertices are kept as-is (same Point instance);
    replacement vertices are fresh Point objects.
    """
    output = list(subject)
    n = len(hull)
    for i in range(n):
        if not output:
            break
        ax, ay = hull[i]
        bx, by = hull[(i + 1) % n]
        # Inside test: cross >= 0 (left side of the edge for CCW hulls).
        def is_inside(v):
            if id(v) in protected_ids:
                return True
            cross = (bx - ax) * (v.y - ay) - (by - ay) * (v.x - ax)
            return cross >= -1e-9

        new_output = []
        prev = output[-1]
        prev_in = is_inside(prev)
        for curr in output:
            curr_in = is_inside(curr)
            if curr_in:
                if not prev_in:
                    ix, iy = _line_intersect(prev.x, prev.y, curr.x, curr.y, ax, ay, bx, by)
                    new_output.append(Point(ix, iy))
                new_output.append(curr)
            elif prev_in:
                ix, iy = _line_intersect(prev.x, prev.y, curr.x, curr.y, ax, ay, bx, by)
                new_output.append(Point(ix, iy))
            prev = curr
            prev_in = curr_in
        output = new_output
    return output


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
        walls: Optional[bool] = True,
        citadel: Optional[bool] = True,
        coast: Optional[bool] = None,
        river: Optional[bool] = None,
        # Back-compat aliases (kept for callers using the older names).
        require_citadel: Optional[bool] = None,
        require_walls: Optional[bool] = None,
    ) -> None:
        # Always seed: explicit seed if > 0, otherwise time-based via rnd.reset(-1)
        rnd.reset(seed)

        self.n_patches = n_patches if n_patches != -1 else 15

        # Back-compat: old `require_walls=False` meant "optional (random)".
        # Users asking for no walls should pass `walls=False`.
        if require_walls is not None and walls is True:
            walls = None if require_walls is False else True
        if require_citadel is not None and citadel is True:
            citadel = None if require_citadel is False else True

        # None = randomise, True/False = force.
        self._walls_override = walls
        self._citadel_override = citadel
        self._coast_override = coast
        self._river_override = river

        # Size 6 is "small town" in the original Watabou generator, and smaller
        # layouts can't reliably fit both walls and a citadel. Fail fast with a
        # helpful message instead of grinding through 100 doomed retries.
        # Only count a feature toward the minimum if it MUST be present.
        walls_req = walls is True
        citadel_req = citadel is True
        min_size = 6 if (walls_req and citadel_req) else 5 if (walls_req or citadel_req) else 4
        if self.n_patches < min_size:
            raise ValueError(
                f"n_patches={self.n_patches} is too small. Minimum is "
                f"{min_size} (walls_required={walls_req}, "
                f"citadel_required={citadel_req}). Pass walls=False and/or "
                f"citadel=False to allow smaller towns down to size 4."
            )

        # Water features — populated during _build_patches / _carve_river
        self.coast_needed: bool = False
        self.river_needed: bool = False
        self.shore: List[Point] = []  # outline of the coast on the land side
        self.river_course: List[Point] = []  # polyline of the river centerline
        self.river_width: float = 0.0
        self.bridges: List[Point] = []
        self.headland: bool = False  # convex bulge of land vs concave bay

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
            if attempts > 200:
                raise RuntimeError("Town generation failed after 200 attempts")
            self.plaza_needed = rnd.rand_bool()
            self.citadel_needed = (
                rnd.rand_bool() if self._citadel_override is None
                else bool(self._citadel_override)
            )
            self.walls_needed = (
                rnd.rand_bool() if self._walls_override is None
                else bool(self._walls_override)
            )
            self.coast_needed = (
                rnd.rand_bool(0.5) if self._coast_override is None else self._coast_override
            )
            self.river_needed = (
                rnd.rand_bool(0.4) if self._river_override is None else self._river_override
            )
            # Reset per-attempt water state
            self.shore = []
            self.river_course = []
            self.bridges = []
            self.headland = False
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

        # Build the topology graph. The river needs it to route through the
        # city, but we defer tagging river patches as water until AFTER
        # streets are built — otherwise the water exclusion can isolate
        # gates from the plaza on small / constrained maps.
        self.topology = Topology(self)
        if self.river_needed and not self.coast_needed:
            self._carve_river()

        self._build_streets()
        # Now that streets have been routed, tag city patches the river
        # actually cuts through as waterbody (strips their ward/buildings).
        if self.river_course:
            self._tag_river_patches()
        self._create_wards()
        if self.coast_needed or self.river_needed:
            self._add_harbours()
        if self.river_course:
            self._find_bridges()
        self._clip_to_hull()
        self._drop_isolated_patches()
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

        # Build patches in distance-from-center order
        all_patches: List[Patch] = []
        for r in regions:
            p = Patch.from_region(r)
            all_patches.append(p)
        self.patches = all_patches

        # --- Coast: tag faraway patches on one side of a tilted parabola ---
        if self.coast_needed:
            # Parabola: a*(x')^2 + b + y' < 0 where (x', y') is the rotated frame
            # Port of Watabou's formula. With a river also, a is much smaller
            # (softer curve) and always >= 0 so we don't get a peninsula.
            if self.river_needed:
                a = rnd.normal() * 0.03
            else:
                a = rnd.normal() * 0.04 - 0.01
            b = 20 + rnd.rand_float() * 40
            t = rnd.rand_float() * 2 * math.pi
            cost = math.cos(t)
            sint = math.sin(t)
            for p in self.patches:
                c = p.shape.center
                x_rot = c.x * cost + c.y * sint
                y_rot = c.x * sint - c.y * cost
                if a * x_rot * x_rot + b + y_rot < 0:
                    p.waterbody = True
            self.headland = a < 0

        # --- Inner selection: skip water, take first n_patches land cells ---
        count = 0
        land_count = 0
        for p in all_patches:
            if count == 0:
                self.center = min(p.shape, key=lambda pt: pt.length)
                # The center patch is forced to land even if parabola says water
                p.waterbody = False
                if self.plaza_needed:
                    self.plaza = p

            if p.waterbody:
                count += 1
                continue

            if land_count == self.n_patches and self.citadel_needed:
                self.citadel = p
                p.within_city = True
            elif land_count < self.n_patches:
                p.within_city = True
                p.within_walls = self.walls_needed
                self.inner.append(p)

            land_count += 1
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
        visited: set = set()
        while True:
            if index in visited:
                # Non-simple chain (duplicate edges or a branch) — bail instead
                # of spinning forever.
                raise RuntimeError("Non-simple circumference chain")
            visited.add(index)
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

        # Topology is already built in _build() before the river was carved.
        # Collect A* exclude list of vertices that belong to water patches,
        # so streets never cross the river. Gates/plaza/citadel vertices are
        # kept reachable even if they happen to sit on a water-patch corner.
        gate_ids = {id(g) for g in self.gates}
        plaza_ids = set()
        if self.plaza is not None:
            plaza_ids = {id(v) for v in self.plaza.shape}
        citadel_ids = set()
        if self.citadel is not None:
            citadel_ids = {id(v) for v in self.citadel.shape}
        reachable_ids = gate_ids | plaza_ids | citadel_ids

        water_nodes: List = []
        for p in self.patches:
            if not p.waterbody:
                continue
            for v in p.shape:
                if id(v) in reachable_ids:
                    continue
                node = self.topology.pt2node.get(id(v))
                if node is not None and node not in water_nodes:
                    water_nodes.append(node)

        for gate in self.gates:
            if self.plaza is not None:
                # Pick the nearest plaza corner that ISN'T the gate itself,
                # otherwise the "street" collapses to a single point and the
                # gate has no visible street connecting it to the plaza.
                candidates = [v for v in self.plaza.shape if v is not gate]
                if candidates:
                    end = min(candidates, key=lambda v: Point.distance(v, gate))
                else:
                    end = self.center
            else:
                end = self.center

            # Streets avoid outer-ring nodes AND water-patch nodes.
            street_exclude = list(self.topology.outer) + water_nodes
            street = self.topology.build_path(gate, end, street_exclude)
            if street is not None and len(street) >= 2:
                self.streets.append(Polygon(street))
            elif street is None:
                raise RuntimeError("Unable to build a street!")
            # else: degenerate length-1 path — gate was already at destination;
            # skip drawing a street but still build the outbound road below.

            if any(g is gate for g in self.border.gates):
                direction = gate.norm(1000)
                start = None
                dist = float("inf")
                for node, p in self.topology.node2pt.items():
                    if node in water_nodes:
                        continue
                    d = Point.distance(p, direction)
                    if d < dist:
                        dist = d
                        start = p

                if start is not None:
                    # Roads avoid inner-city nodes. They may cross water
                    # (rendered as a bridge) since going around a river with
                    # only outer countryside patches is often impossible.
                    road_exclude = list(self.topology.inner)
                    road = self.topology.build_path(start, gate, road_exclude)
                    if road is not None and len(road) >= 2:
                        self.roads.append(Polygon(road))

        self._tidy_up_roads()

        for a in self.arteries:
            smooth_street(list(a))

    # -------------------------------------------------------------------
    def _tidy_up_roads(self) -> None:
        segments: List[Segment] = []

        gate_ids = {id(g) for g in self.gates}

        def cut2segments(street: Polygon) -> None:
            v1 = street[0]
            for i in range(1, len(street)):
                v0 = v1
                v1 = street[i]

                # Drop segments that run entirely inside the plaza (those are
                # the implicit plaza pavement, not a road). But keep segments
                # that touch a gate, so the gate-to-plaza-corner street is
                # preserved when the gate happens to be a plaza vertex.
                if (
                    self.plaza is not None
                    and self.plaza.shape.contains(v0)
                    and self.plaza.shape.contains(v1)
                    and id(v0) not in gate_ids
                    and id(v1) not in gate_ids
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

        # Merge arteries that terminate on plaza corners — the plaza is the
        # implicit connector between streets entering from different gates.
        # Without this, short gate-to-plaza streets stay as standalone arteries
        # that visually appear disconnected from the main street network.
        if self.plaza is not None:
            plaza_ids = {id(v) for v in self.plaza.shape}

            def on_plaza(v: Point) -> bool:
                return id(v) in plaza_ids

            merged = True
            while merged:
                merged = False
                for i in range(len(self.arteries)):
                    for j in range(i + 1, len(self.arteries)):
                        a = self.arteries[i]
                        b = self.arteries[j]
                        pairs = [
                            (a[0], b[0], "a0_b0"),
                            (a[0], b[-1], "a0_bn"),
                            (a[-1], b[0], "an_b0"),
                            (a[-1], b[-1], "an_bn"),
                        ]
                        for va, vb, mode in pairs:
                            if va is vb:
                                continue
                            if not (on_plaza(va) and on_plaza(vb)):
                                continue
                            # Merge b into a with a plaza-connector segment
                            if mode == "a0_b0":
                                a[:] = list(reversed(b)) + list(a)
                            elif mode == "a0_bn":
                                a[:] = list(b) + list(a)
                            elif mode == "an_b0":
                                a[:] = list(a) + list(b)
                            else:  # an_bn
                                a[:] = list(a) + list(reversed(b))
                            del self.arteries[j]
                            merged = True
                            break
                        if merged:
                            break
                    if merged:
                        break

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
            if patch.waterbody:
                continue  # no wards on water
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
    def _carve_river(self) -> None:
        """Carve a river polyline from one side of the map, through the city,
        out the opposite side.

        Pragmatic port of Canal.regularRiver from the JS bundle: pick a source
        and mouth on the outer periphery on opposite sides of the center, then
        route the path through the Voronoi patch graph via a central waypoint.
        The river is allowed to pass through the city (across walls/gates).
        """
        if self.topology is None:
            return

        # Nodes that A* cannot traverse (walls + citadel, minus gates).
        blocked_ids = self.topology._blocked_ids

        def reachable(v: Point) -> bool:
            nid = id(v)
            if nid in blocked_ids:
                return False
            node = self.topology.pt2node.get(nid)
            return node is not None and len(node.links) > 0

        # Outer periphery candidates — vertices on patches outside the city
        # that are reachable (not on walls / blocked).
        periphery = [
            v for p in self.patches for v in p.shape
            if not p.within_city and reachable(v)
        ]
        if len(periphery) < 4:
            return

        center = self.center

        # Farthest point from the center, then the point most opposite it
        source = max(periphery, key=lambda v: Point.distance(v, center))
        source_dir = Point(source.x - center.x, source.y - center.y)
        mouth = max(
            periphery,
            key=lambda v: -(
                ((v.x - center.x) * source_dir.x
                 + (v.y - center.y) * source_dir.y)
                / max(Point.distance(v, center), 1e-6)
            ),
        )

        # Route via a central waypoint so the river goes through town, not
        # around it. Try vertices of the central patch in random order until
        # we find one that's reachable.
        central_patch = self.inner[0] if self.inner else None
        if central_patch is None:
            return
        candidate_waypoints = [v for v in central_patch.shape if reachable(v)]
        if not candidate_waypoints:
            # Fall back to vertices of other inner patches
            for p in self.inner[1:]:
                candidate_waypoints.extend(v for v in p.shape if reachable(v))
        if not candidate_waypoints:
            return
        waypoint = candidate_waypoints[rnd.rand_int(0, len(candidate_waypoints))]

        # Do not exclude inner nodes — the river IS allowed through the city.
        # The walls' blocked-points list already prevents pathing through a
        # solid wall; it can still pass through gates which is the intended
        # behaviour for a river under a water gate.
        first_half = self.topology.build_path(source, waypoint)
        second_half = self.topology.build_path(waypoint, mouth)

        path = None
        if first_half and second_half and len(first_half) + len(second_half) >= 4:
            # Find the earliest point where second_half re-crosses first_half.
            # Ports the JS Canal.regularRiver merge: course = c2[:i] + c1[j:]
            # where c2[i] == c1[j]. This cuts out any redundant loop around
            # the center waypoint.
            first_ids = {id(v): idx for idx, v in enumerate(first_half)}
            for i, v in enumerate(second_half):
                j = first_ids.get(id(v))
                if j is not None:
                    path = second_half[:i] + first_half[j:]
                    # Reverse so it flows source -> mouth
                    path.reverse()
                    break
            # If no overlap found, just concatenate — imperfect but river still
            # passes through the center.
            if path is None:
                path = first_half + second_half[1:]

        if path is None or len(path) < 3:
            # Last resort: route around the city.
            path = self.topology.build_path(
                source, mouth, exclude=list(self.topology.inner)
            )
            if not path or len(path) < 3:
                return

        # Smooth the river centerline
        poly = Polygon(path)
        smoothed = poly.smooth_vertex_eq(3)
        for i in range(1, len(path) - 1):
            path[i] = Point(smoothed[i].x, smoothed[i].y)

        self.river_course = path
        self.river_width = 3.0 + rnd.rand_float() * 2.0
        # NOTE: _tag_river_patches is now called by _build() AFTER _build_streets,
        # so streets can still route through the city without being blocked by
        # yet-to-be-tagged water patches.

    def _tag_river_patches(self) -> None:
        """Flag patches the river crosses as waterbody.

        A patch is crossed if:
          - the river centerline passes within `patch_radius * 0.6` of its
            centroid, OR
          - any river vertex lies geometrically inside the patch polygon.

        City and citadel patches are also eligible — a river routed through the
        city is allowed, but patches it cuts through should become water (not
        keep their ward + buildings).
        """
        if not self.river_course:
            return

        def pt_seg_dist(px, py, ax, ay, bx, by):
            dx, dy = bx - ax, by - ay
            seg_len2 = dx * dx + dy * dy
            if seg_len2 == 0:
                return math.hypot(px - ax, py - ay)
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len2))
            return math.hypot(px - (ax + dx * t), py - (ay + dy * t))

        def point_in_poly(x: float, y: float, poly) -> bool:
            # Ray cast
            inside = False
            n = len(poly)
            j = n - 1
            for i in range(n):
                xi, yi = poly[i].x, poly[i].y
                xj, yj = poly[j].x, poly[j].y
                if ((yi > y) != (yj > y)) and (
                    x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi
                ):
                    inside = not inside
                j = i
            return inside

        for p in self.patches:
            # Skip the citadel — losing the citadel breaks too much geometry.
            if p is self.citadel:
                continue

            c = p.shape.center

            # 1) Centroid-based proximity test
            min_dist = float("inf")
            for i in range(len(self.river_course) - 1):
                a = self.river_course[i]
                b = self.river_course[i + 1]
                d = pt_seg_dist(c.x, c.y, a.x, a.y, b.x, b.y)
                if d < min_dist:
                    min_dist = d
            r = max(Point.distance(c, v) for v in p.shape) * 0.6
            hit = min_dist < r

            # 2) Any river vertex physically inside the patch polygon
            if not hit:
                for rv in self.river_course:
                    if point_in_poly(rv.x, rv.y, p.shape):
                        hit = True
                        break

            if hit:
                # Never demote the plaza (breaks too much) or a patch whose
                # loss would leave fewer than half the requested inner count.
                if p is self.plaza:
                    continue
                if p.within_city and len(self.inner) <= max(3, self.n_patches // 2):
                    continue
                p.waterbody = True
                p.within_city = False
                p.within_walls = False
                if p in self.inner:
                    self.inner.remove(p)
                # Also clear any ward already assigned
                p.ward = None

    # -------------------------------------------------------------------
    def _find_bridges(self) -> None:
        """Detect arteries that cross the river; record the intersection points.

        Only record a bridge if the street segment's endpoints connect two
        distinct LAND regions. A crossing in the middle of water (e.g. street
        vertices both inside waterbody patches, or both vertices isolated from
        any city/countryside patch) is not a real bridge — just a rendering
        coincidence.
        """
        if not self.river_course:
            return

        def seg_intersect(p1, p2, p3, p4):
            x1, y1 = p1.x, p1.y
            x2, y2 = p2.x, p2.y
            x3, y3 = p3.x, p3.y
            x4, y4 = p4.x, p4.y
            denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            if denom == 0:
                return None
            t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
            u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
            if 0 <= t <= 1 and 0 <= u <= 1:
                return Point(x1 + t * (x2 - x1), y1 + t * (y2 - y1))
            return None

        def water_patches_at(v: Point) -> set:
            """IDs of every water patch that has v as a corner."""
            return {
                id(p) for p in self.patches
                if p.waterbody and any(pv is v for pv in p.shape)
            }

        def land_patches_at(v: Point) -> set:
            return {
                id(p) for p in self.patches
                if not p.waterbody and any(pv is v for pv in p.shape)
            }

        self.bridges = []
        for street in list(self.arteries) + list(self.streets) + list(self.roads):
            for i in range(len(street) - 1):
                a, b = street[i], street[i + 1]
                for j in range(len(self.river_course) - 1):
                    r1, r2 = self.river_course[j], self.river_course[j + 1]
                    pt = seg_intersect(a, b, r1, r2)
                    if pt is None:
                        continue
                    # A real bridge connects two DIFFERENT land regions.
                    # Require both endpoints to touch land, AND require no
                    # shared land patch — if any single land patch contains
                    # both endpoints, the segment runs along that patch's
                    # boundary (beside the water) rather than bridging across.
                    la, lb = land_patches_at(a), land_patches_at(b)
                    if not la or not lb:
                        break
                    if la & lb:  # share at least one land patch
                        break
                    self.bridges.append(pt)
                    break

    # -------------------------------------------------------------------
    def _add_harbours(self) -> None:
        """Give one waterfront inner patch a Harbour ward if possible.

        Prefer a land patch whose longest water-facing edge is long enough
        to host at least one pier.
        """
        def waterfront_length(patch: Patch) -> float:
            """Longest edge of `patch` that borders a water patch."""
            best = 0.0
            for i in range(len(patch.shape)):
                v0 = patch.shape[i]
                v1 = patch.shape[(i + 1) % len(patch.shape)]
                nb = self.get_neighbour(patch, v0)
                if nb is not None and nb.waterbody:
                    d = Point.distance(v0, v1)
                    if d > best:
                        best = d
            return best

        # Wards that have specific spatial purposes — never overwrite them
        # with a Harbour, even if their patch happens to border water.
        protected_ward_types = (Market, Cathedral, Castle)

        candidates = []
        seen_ids = set()
        for wp in self.patches:
            if not wp.waterbody:
                continue
            for n in self.get_neighbours(wp):
                if n.waterbody or not n.within_city or n is self.citadel:
                    continue
                if isinstance(n.ward, protected_ward_types) or n is self.plaza:
                    continue
                if id(n) in seen_ids:
                    continue
                seen_ids.add(id(n))
                candidates.append(n)

        if not candidates:
            return

        # Prefer patches with a substantial waterfront (>= 3 units = at least
        # one pier) AND no existing special ward.
        def score(c: Patch) -> tuple:
            wf = waterfront_length(c)
            is_open = c.ward is None
            return (wf >= 3.0, is_open, wf)

        candidates.sort(key=score, reverse=True)
        chosen = candidates[0]
        if waterfront_length(chosen) < 3.0:
            return
        chosen.ward = Harbour(self, chosen)

    # -------------------------------------------------------------------
    def _clip_to_hull(self) -> None:
        """Cap peripheral spikes by clipping all patches to the convex hull
        of "reasonable" vertices.

        A vertex is reasonable if it belongs to a city / water / citadel
        patch, OR sits within ``spike_factor * city_radius`` of the center
        (i.e. not a Voronoi outlier). We compute the convex hull of those
        vertices and Sutherland-Hodgman-clip every countryside patch against
        each hull edge. Spiky vertices are replaced by hull-edge
        intersection points, giving the map an irregular polygonal boundary.
        """
        if self.city_radius <= 0:
            return

        spike_factor = 2.5
        limit_sq = (self.city_radius * spike_factor) ** 2
        cx, cy = self.center.x, self.center.y

        # Collect hull candidate points — every vertex that isn't a spike.
        # Only load-bearing vertices are unconditionally kept (city, citadel,
        # border, wall); everything else — including river course points and
        # countryside vertices — is kept only if within the spike cutoff.
        points: List[tuple] = []
        for p in self.patches:
            always_keep = p.within_city or p is self.citadel
            for v in p.shape:
                dx, dy = v.x - cx, v.y - cy
                if always_keep or dx * dx + dy * dy <= limit_sq:
                    points.append((v.x, v.y))
        for v in self.river_course:
            dx, dy = v.x - cx, v.y - cy
            if dx * dx + dy * dy <= limit_sq:
                points.append((v.x, v.y))
        if self.border is not None:
            for v in self.border.shape:
                points.append((v.x, v.y))

        if len(points) < 3:
            return
        hull = _convex_hull(points)
        if len(hull) < 3:
            return

        # Clip every non-city, non-citadel patch (including waterbody patches)
        # against the hull. We mutate patch.shape in place but replace any
        # far-out vertex with a fresh Point instance — protected load-bearing
        # vertices are preserved by identity.
        protected_ids: set = set()
        for p in self.patches:
            if p.within_city or p is self.citadel:
                for v in p.shape:
                    protected_ids.add(id(v))
        # River course points are protected only if they're within the hull
        # radius; spiky river endpoints will be trimmed by the clipper.
        for v in self.river_course:
            dx, dy = v.x - cx, v.y - cy
            if dx * dx + dy * dy <= limit_sq:
                protected_ids.add(id(v))
        if self.border is not None:
            for v in self.border.shape:
                protected_ids.add(id(v))
        if self.wall is not None:
            for v in self.wall.shape:
                protected_ids.add(id(v))

        for patch in self.patches:
            if patch.within_city or patch is self.citadel:
                continue
            # Skip patches entirely inside the hull — common case
            if all(_point_in_hull(v.x, v.y, hull) for v in patch.shape):
                continue
            clipped = _clip_polygon_to_hull(list(patch.shape), hull, protected_ids)
            if clipped and len(clipped) >= 3:
                patch.shape.clear()
                patch.shape.extend(clipped)

        # Trim the river course and every street polyline so they don't
        # shoot out past the hull. A polyline is kept up to its first exit,
        # with the exit point clamped to the hull edge.
        def _trim_polyline(points: List[Point]) -> List[Point]:
            if not points:
                return points
            out: List[Point] = []
            prev_inside = _point_in_hull(points[0].x, points[0].y, hull)
            if prev_inside:
                out.append(points[0])
            for i in range(1, len(points)):
                prev = points[i - 1]
                curr = points[i]
                curr_inside = _point_in_hull(curr.x, curr.y, hull)
                if curr_inside:
                    if not prev_inside:
                        # Entered the hull — add entry point
                        clamp = _clamp_to_hull(prev, curr, hull)
                        if clamp is not None:
                            out.append(clamp)
                    out.append(curr)
                elif prev_inside:
                    # Exited the hull — add exit point and stop
                    clamp = _clamp_to_hull(prev, curr, hull)
                    if clamp is not None:
                        out.append(clamp)
                    break
                prev_inside = curr_inside
            return out

        if self.river_course:
            trimmed = _trim_polyline(self.river_course)
            if len(trimmed) >= 2:
                self.river_course = trimmed

        def _trim_list(plist: List[Polygon]) -> List[Polygon]:
            result: List[Polygon] = []
            for poly in plist:
                t = _trim_polyline(list(poly))
                if len(t) >= 2:
                    result.append(Polygon(t))
            return result

        self.streets = _trim_list(self.streets)
        self.roads = _trim_list(self.roads)
        self.arteries = _trim_list(self.arteries)

        # Drop bridge markers that fell outside the hull after trimming.
        if self.bridges:
            self.bridges = [
                b for b in self.bridges if _point_in_hull(b.x, b.y, hull)
            ]

    # -------------------------------------------------------------------
    def _drop_isolated_patches(self) -> None:
        """Remove peripheral patches that became disconnected from the main
        cluster after the hull clip.

        Voronoi outliers can lose all (or all but one) of their neighbouring
        edges when the hull clip moves shared vertices, leaving them as
        floating patches that look like detached islands. We BFS from the
        city center patch over the patch-adjacency graph and drop any patch
        that's not reachable, OR that's reachable only through a single edge
        (likely-incidental overlap). City and citadel patches are always
        kept.
        """
        if not self.patches:
            return

        # Build patch adjacency: two patches are connected if they share at
        # least one full edge (any two consecutive vertices).
        def patches_share_edge(a: Patch, b: Patch) -> bool:
            sa = a.shape
            sb = b.shape
            for i in range(len(sa)):
                v0 = sa[i]
                v1 = sa[(i + 1) % len(sa)]
                # Look for the reverse edge (b's CCW match) on patch b
                for j in range(len(sb)):
                    u0 = sb[j]
                    u1 = sb[(j + 1) % len(sb)]
                    if u0 is v1 and u1 is v0:
                        return True
            return False

        # Adjacency map
        adj: dict = {id(p): [] for p in self.patches}
        for i, a in enumerate(self.patches):
            for b in self.patches[i + 1 :]:
                if patches_share_edge(a, b):
                    adj[id(a)].append(b)
                    adj[id(b)].append(a)

        # Find a seed: prefer the central patch (first inner patch), else
        # the patch closest to the center.
        seed = None
        if self.inner:
            seed = self.inner[0]
        else:
            seed = min(
                self.patches,
                key=lambda p: Point.distance(p.shape.center, self.center),
            )
        if seed is None:
            return

        # BFS over the connectivity graph
        reachable: set = set()
        queue = [seed]
        reachable.add(id(seed))
        while queue:
            curr = queue.pop()
            for nb in adj[id(curr)]:
                if id(nb) not in reachable:
                    reachable.add(id(nb))
                    queue.append(nb)

        # Always keep city/citadel patches even if the connectivity test
        # missed them somehow.
        for p in self.patches:
            if p.within_city or p is self.citadel:
                reachable.add(id(p))

        before = len(self.patches)
        self.patches = [p for p in self.patches if id(p) in reachable]
        if len(self.patches) < before:
            # Also drop any inner-tracking references that might dangle
            self.inner = [p for p in self.inner if id(p) in reachable]

    # -------------------------------------------------------------------
    def _build_geometry(self) -> None:
        for patch in self.patches:
            if patch.waterbody:
                continue  # water patches draw as water, no buildings
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

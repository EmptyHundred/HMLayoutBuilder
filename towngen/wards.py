"""Port of com.watabou.towngenerator.wards.* — base Ward + 12 subclasses."""

from __future__ import annotations

import math
from typing import List, Optional, TYPE_CHECKING

from . import cutter
from . import geomutils as gu
from . import random_ as rnd
from .curtain_wall import CurtainWall
from .point import Point
from .polygon import Polygon

if TYPE_CHECKING:
    from .model import Model
    from .patch import Patch


# -------- base -----------------------------------------------------------
class Ward:
    MAIN_STREET = 2.0
    REGULAR_STREET = 1.0
    ALLEY = 0.6

    LABEL = "Ward"

    def __init__(self, model: "Model", patch: "Patch") -> None:
        self.model = model
        self.patch = patch
        self.geometry: List[Polygon] = []

    def create_geometry(self) -> None:
        self.geometry = []

    def get_city_block(self) -> Polygon:
        inset_dist: List[float] = []
        inner = self.model.wall is None or self.patch.within_walls
        plaza_shape = self.model.plaza.shape if self.model.plaza is not None else None

        def _edge(v0: Point, v1: Point) -> None:
            if self.model.wall is not None and self.model.wall.borders_by(
                self.patch, v0, v1
            ):
                inset_dist.append(Ward.MAIN_STREET / 2)
                return

            on_street = False
            if inner and plaza_shape is not None and plaza_shape.find_edge(v1, v0) != -1:
                on_street = True
            if not on_street:
                for street in self.model.arteries:
                    if any(s is v0 for s in street) and any(s is v1 for s in street):
                        on_street = True
                        break

            if on_street:
                inset_dist.append(Ward.MAIN_STREET / 2)
            else:
                inset_dist.append(
                    (Ward.REGULAR_STREET if inner else Ward.ALLEY) / 2
                )

        self.patch.shape.for_edge(_edge)

        if self.patch.shape.is_convex():
            return self.patch.shape.shrink(inset_dist)
        return self.patch.shape.buffer(inset_dist)

    def filter_outskirts(self) -> None:
        populated_edges: List[dict] = []

        def add_edge(v1: Point, v2: Point, factor: float = 1.0) -> None:
            dx = v2.x - v1.x
            dy = v2.y - v1.y
            distances = {}
            max_v = None
            max_d = float("-inf")
            for v in self.patch.shape:
                if v is v1 or v is v2:
                    d = 0.0
                else:
                    d = gu.distance2line(v1.x, v1.y, dx, dy, v.x, v.y) * factor
                distances[id(v)] = d
                if d > max_d:
                    max_d = d
                    max_v = v
            populated_edges.append(
                {"x": v1.x, "y": v1.y, "dx": dx, "dy": dy, "d": distances[id(max_v)]}
            )

        def _each(v1: Point, v2: Point) -> None:
            on_road = False
            for street in self.model.arteries:
                if any(s is v1 for s in street) and any(s is v2 for s in street):
                    on_road = True
                    break
            if on_road:
                add_edge(v1, v2, 1.0)
            else:
                n = self.model.get_neighbour(self.patch, v1)
                if n is not None and n.within_city:
                    add_edge(v1, v2, 1.0 if self.model.is_enclosed(n) else 0.4)

        self.patch.shape.for_edge(_each)

        # Density per vertex
        gate_ids = {id(g) for g in self.model.gates}
        density: List[float] = []
        for v in self.patch.shape:
            if id(v) in gate_ids:
                density.append(1.0)
            else:
                all_within = all(
                    p.within_city for p in self.model.patch_by_vertex(v)
                )
                density.append(2 * rnd.rand_float() if all_within else 0.0)

        def _keep(building: Polygon) -> bool:
            min_dist = 1.0
            for edge in populated_edges:
                if edge["d"] == 0:
                    continue
                for v in building:
                    d = gu.distance2line(
                        edge["x"], edge["y"], edge["dx"], edge["dy"], v.x, v.y
                    )
                    dist = d / edge["d"]
                    if dist < min_dist:
                        min_dist = dist

            c = building.center
            weights = self.patch.shape.interpolate(c)
            p = 0.0
            for j in range(len(weights)):
                p += density[j] * weights[j]
            if p == 0:
                return False
            min_dist /= p
            return rnd.fuzzy(1) > min_dist

        self.geometry = [b for b in self.geometry if _keep(b)]

    def get_label(self) -> Optional[str]:
        return self.LABEL

    @staticmethod
    def rate_location(model: "Model", patch: "Patch") -> float:
        return 0.0

    # --- static helpers -------------------------------------------------
    @staticmethod
    def create_alleys(
        p: Polygon,
        min_sq: float,
        grid_chaos: float,
        size_chaos: float,
        empty_prob: float = 0.04,
        split: bool = True,
    ) -> List[Polygon]:
        v = [None]
        length = [-1.0]

        def _longest(p0: Point, p1: Point) -> None:
            ln = Point.distance(p0, p1)
            if ln > length[0]:
                length[0] = ln
                v[0] = p0

        p.for_edge(_longest)

        spread = 0.8 * grid_chaos
        ratio = (1 - spread) / 2 + rnd.rand_float() * spread

        angle_spread = (
            math.pi / 6 * grid_chaos * (0.0 if p.square < min_sq * 4 else 1.0)
        )
        b = (rnd.rand_float() - 0.5) * angle_spread

        halves = cutter.bisect(
            p, v[0], ratio, b, Ward.ALLEY if split else 0.0
        )

        buildings: List[Polygon] = []
        for half in halves:
            limit = min_sq * math.pow(2, 4 * size_chaos * (rnd.rand_float() - 0.5))
            if half.square < limit:
                if not rnd.rand_bool(empty_prob):
                    buildings.append(half)
            else:
                denom = rnd.rand_float() * rnd.rand_float()
                next_split = half.square > (min_sq / denom if denom > 0 else float("inf"))
                buildings.extend(
                    Ward.create_alleys(
                        half, min_sq, grid_chaos, size_chaos, empty_prob, next_split
                    )
                )
        return buildings

    @staticmethod
    def _find_longest_edge(poly: Polygon) -> Point:
        return min(poly, key=lambda v: -poly.vector(v).length)

    @staticmethod
    def create_ortho_building(
        poly: Polygon, min_block_sq: float, fill: float
    ) -> List[Polygon]:
        def slice_(p: Polygon, c1: Point, c2: Point) -> List[Polygon]:
            v0 = Ward._find_longest_edge(p)
            v1 = p.next(v0)
            v = v1.subtract(v0)

            ratio = 0.4 + rnd.rand_float() * 0.2
            p1 = gu.interpolate(v0, v1, ratio)

            if abs(gu.scalar(v.x, v.y, c1.x, c1.y)) < abs(
                gu.scalar(v.x, v.y, c2.x, c2.y)
            ):
                c = c1
            else:
                c = c2

            halves = p.cut(p1, p1.add(c))
            buildings: List[Polygon] = []
            for half in halves:
                lim = min_block_sq * math.pow(2, rnd.normal() * 2 - 1)
                if half.square < lim:
                    if rnd.rand_bool(fill):
                        buildings.append(half)
                else:
                    buildings.extend(slice_(half, c1, c2))
            return buildings

        if poly.square < min_block_sq:
            return [poly]
        c1 = poly.vector(Ward._find_longest_edge(poly))
        c2 = c1.rotate90()
        while True:
            blocks = slice_(poly, c1, c2)
            if blocks:
                return blocks


# -------- common (alley-based) -------------------------------------------
class CommonWard(Ward):
    def __init__(
        self,
        model: "Model",
        patch: "Patch",
        min_sq: float,
        grid_chaos: float,
        size_chaos: float,
        empty_prob: float = 0.04,
    ) -> None:
        super().__init__(model, patch)
        self.min_sq = min_sq
        self.grid_chaos = grid_chaos
        self.size_chaos = size_chaos
        self.empty_prob = empty_prob

    def create_geometry(self) -> None:
        block = self.get_city_block()
        self.geometry = Ward.create_alleys(
            block, self.min_sq, self.grid_chaos, self.size_chaos, self.empty_prob
        )
        if not self.model.is_enclosed(self.patch):
            self.filter_outskirts()


# -------- concrete wards -------------------------------------------------
class CraftsmenWard(CommonWard):
    LABEL = "Craftsmen"

    def __init__(self, model: "Model", patch: "Patch") -> None:
        super().__init__(
            model,
            patch,
            10 + 80 * rnd.rand_float() * rnd.rand_float(),
            0.5 + rnd.rand_float() * 0.2,
            0.6,
        )


class MerchantWard(CommonWard):
    LABEL = "Merchant"

    def __init__(self, model: "Model", patch: "Patch") -> None:
        super().__init__(
            model,
            patch,
            50 + 60 * rnd.rand_float() * rnd.rand_float(),
            0.5 + rnd.rand_float() * 0.3,
            0.7,
            0.15,
        )

    @staticmethod
    def rate_location(model: "Model", patch: "Patch") -> float:
        target = (
            model.plaza.shape.center if model.plaza is not None else model.center
        )
        return patch.shape.distance(target)


class GateWard(CommonWard):
    LABEL = "Gate"

    def __init__(self, model: "Model", patch: "Patch") -> None:
        super().__init__(
            model,
            patch,
            10 + 50 * rnd.rand_float() * rnd.rand_float(),
            0.5 + rnd.rand_float() * 0.3,
            0.7,
        )


class AdministrationWard(CommonWard):
    LABEL = "Administration"

    def __init__(self, model: "Model", patch: "Patch") -> None:
        super().__init__(
            model,
            patch,
            80 + 30 * rnd.rand_float() * rnd.rand_float(),
            0.1 + rnd.rand_float() * 0.3,
            0.3,
        )

    @staticmethod
    def rate_location(model: "Model", patch: "Patch") -> float:
        if model.plaza is not None:
            if patch.shape.borders(model.plaza.shape):
                return 0.0
            return patch.shape.distance(model.plaza.shape.center)
        return patch.shape.distance(model.center)


class PatriciateWard(CommonWard):
    LABEL = "Patriciate"

    def __init__(self, model: "Model", patch: "Patch") -> None:
        super().__init__(
            model,
            patch,
            80 + 30 * rnd.rand_float() * rnd.rand_float(),
            0.5 + rnd.rand_float() * 0.3,
            0.8,
            0.2,
        )

    @staticmethod
    def rate_location(model: "Model", patch: "Patch") -> float:
        rate = 0
        for p in model.patches:
            if p.ward is not None and p.shape.borders(patch.shape):
                if isinstance(p.ward, Park):
                    rate -= 1
                elif isinstance(p.ward, Slum):
                    rate += 1
        return float(rate)


class Slum(CommonWard):
    LABEL = "Slum"

    def __init__(self, model: "Model", patch: "Patch") -> None:
        super().__init__(
            model,
            patch,
            10 + 30 * rnd.rand_float() * rnd.rand_float(),
            0.6 + rnd.rand_float() * 0.4,
            0.8,
            0.03,
        )

    @staticmethod
    def rate_location(model: "Model", patch: "Patch") -> float:
        target = (
            model.plaza.shape.center if model.plaza is not None else model.center
        )
        return -patch.shape.distance(target)


class MilitaryWard(Ward):
    LABEL = "Military"

    def create_geometry(self) -> None:
        block = self.get_city_block()
        self.geometry = Ward.create_alleys(
            block,
            math.sqrt(block.square) * (1 + rnd.rand_float()),
            0.1 + rnd.rand_float() * 0.3,
            0.3,
            0.25,
        )

    @staticmethod
    def rate_location(model: "Model", patch: "Patch") -> float:
        if model.citadel is not None and model.citadel.shape.borders(patch.shape):
            return 0.0
        if model.wall is not None and model.wall.borders(patch):
            return 1.0
        return 0.0 if (model.citadel is None and model.wall is None) else float(
            "inf"
        )


class Cathedral(Ward):
    LABEL = "Temple"

    def create_geometry(self) -> None:
        block = self.get_city_block()
        if rnd.rand_bool(0.4):
            self.geometry = cutter.ring(block, 2 + rnd.rand_float() * 4)
        else:
            self.geometry = Ward.create_ortho_building(block, 50, 0.8)

    @staticmethod
    def rate_location(model: "Model", patch: "Patch") -> float:
        if model.plaza is not None and patch.shape.borders(model.plaza.shape):
            return -1 / patch.shape.square
        target = (
            model.plaza.shape.center if model.plaza is not None else model.center
        )
        return patch.shape.distance(target) * patch.shape.square


class Market(Ward):
    LABEL = "Market"

    def create_geometry(self) -> None:
        statue = rnd.rand_bool(0.6)
        offset = statue or rnd.rand_bool(0.3)

        v0 = v1 = None
        if statue or offset:
            length = -1.0

            def _longest(p0: Point, p1: Point) -> None:
                nonlocal v0, v1, length
                ln = Point.distance(p0, p1)
                if ln > length:
                    length = ln
                    v0 = p0
                    v1 = p1

            self.patch.shape.for_edge(_longest)

        if statue:
            obj = Polygon.rect(1 + rnd.rand_float(), 1 + rnd.rand_float())
            obj.rotate(math.atan2(v1.y - v0.y, v1.x - v0.x))
        else:
            obj = Polygon.circle(1 + rnd.rand_float())

        if offset:
            gravity = gu.interpolate(v0, v1)
            obj.offset(
                gu.interpolate(
                    self.patch.shape.centroid,
                    gravity,
                    0.2 + rnd.rand_float() * 0.4,
                )
            )
        else:
            obj.offset(self.patch.shape.centroid)

        self.geometry = [obj]

    @staticmethod
    def rate_location(model: "Model", patch: "Patch") -> float:
        for p in model.inner:
            if isinstance(p.ward, Market) and p.shape.borders(patch.shape):
                return float("inf")
        if model.plaza is not None:
            return patch.shape.square / model.plaza.shape.square
        return patch.shape.distance(model.center)


class Park(Ward):
    LABEL = "Park"

    def create_geometry(self) -> None:
        block = self.get_city_block()
        if block.compactness >= 0.7:
            self.geometry = cutter.radial(block, None, Ward.ALLEY)
        else:
            self.geometry = cutter.semi_radial(block, None, Ward.ALLEY)


class Farm(Ward):
    LABEL = "Farm"

    def create_geometry(self) -> None:
        housing = Polygon.rect(4, 4)
        idx = rnd.rand_int(0, len(self.patch.shape))
        pos = gu.interpolate(
            self.patch.shape[idx],
            self.patch.shape.centroid,
            0.3 + rnd.rand_float() * 0.4,
        )
        housing.rotate(rnd.rand_float() * math.pi)
        housing.offset(pos)
        self.geometry = Ward.create_ortho_building(housing, 8, 0.5)


class Hamlet(Ward):
    """A sparse rural cluster — 1-3 small cottages placed toward the centroid."""

    LABEL = "Hamlet"

    def create_geometry(self) -> None:
        n_cottages = rnd.rand_int(1, 4)  # 1..3
        centroid = self.patch.shape.centroid
        buildings = []
        for _ in range(n_cottages):
            w = 1.5 + rnd.rand_float() * 1.5
            h = 1.5 + rnd.rand_float() * 1.5
            cottage = Polygon.rect(w, h)
            cottage.rotate(rnd.rand_float() * math.pi)
            idx = rnd.rand_int(0, len(self.patch.shape))
            pos = gu.interpolate(
                self.patch.shape[idx], centroid, 0.4 + rnd.rand_float() * 0.4
            )
            cottage.offset(pos)
            buildings.append(cottage)
        self.geometry = buildings


class Castle(Ward):
    LABEL = "Castle"

    def __init__(self, model: "Model", patch: "Patch") -> None:
        super().__init__(model, patch)
        reserved = [
            v
            for v in patch.shape
            if any(not p.within_city for p in model.patch_by_vertex(v))
        ]
        self.wall = CurtainWall(True, model, [patch], reserved)

    def create_geometry(self) -> None:
        block = self.patch.shape.shrink_eq(Ward.MAIN_STREET * 2)
        self.geometry = Ward.create_ortho_building(
            block, math.sqrt(block.square) * 4, 0.6
        )

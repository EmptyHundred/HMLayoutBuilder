"""Port of com.watabou.towngenerator.building.CurtainWall."""

from __future__ import annotations

from typing import List, TYPE_CHECKING

from . import random_ as rnd
from .patch import Patch
from .point import Point
from .polygon import Polygon

if TYPE_CHECKING:
    from .model import Model


class CurtainWall:
    def __init__(
        self,
        real: bool,
        model: "Model",
        patches: List[Patch],
        reserved: List[Point],
    ) -> None:
        # NOTE: Haxe original forces `self.real = True` here. Preserve the bug to
        # match outputs — the `real` parameter does still gate logic below.
        self.real = True
        self.patches = patches

        if len(patches) == 1:
            self.shape: Polygon = patches[0].shape
        else:
            from .model import Model as M  # avoid circular at import time

            self.shape = M.find_circumference(patches)

            if real:
                smooth_factor = min(1.0, 40 / len(patches))
                reserved_ids = {id(p) for p in reserved}
                smoothed = Polygon(
                    [
                        v if id(v) in reserved_ids else self.shape.smooth_vertex(v, smooth_factor)
                        for v in self.shape
                    ]
                )
                # In-place mutation of shape vertices (match original .set semantics)
                for i in range(len(self.shape)):
                    self.shape[i].set(smoothed[i])

        self.segments: List[bool] = [True for _ in self.shape]

        self.gates: List[Point] = []
        self.towers: List[Point] = []
        self._build_gates(real, model, reserved)

    def _build_gates(
        self, real: bool, model: "Model", reserved: List[Point]
    ) -> None:
        self.gates = []
        reserved_ids = {id(p) for p in reserved}

        if len(self.patches) > 1:
            entrances = [
                v
                for v in self.shape
                if id(v) not in reserved_ids
                and sum(1 for p in self.patches if p.shape.contains(v)) > 1
            ]
        else:
            entrances = [v for v in self.shape if id(v) not in reserved_ids]

        if not entrances:
            raise RuntimeError("Bad walled area shape!")

        while True:
            index = rnd.rand_int(0, len(entrances))
            gate = entrances[index]
            self.gates.append(gate)

            if real:
                outer_wards = [
                    w
                    for w in model.patch_by_vertex(gate)
                    if not any(p is w for p in self.patches)
                ]
                if len(outer_wards) == 1:
                    outer = outer_wards[0]
                    if len(outer.shape) > 3:
                        wall_v = self.shape.next(gate).subtract(self.shape.prev(gate))
                        out = Point(wall_v.y, -wall_v.x)

                        def _rate(v: Point) -> float:
                            if self.shape.contains(v) or (id(v) in reserved_ids):
                                return float("-inf")
                            d = v.subtract(gate)
                            ln = d.length
                            if ln == 0:
                                return float("-inf")
                            return d.dot(out) / ln

                        farthest = max(outer.shape, key=_rate)
                        halves = outer.shape.split(gate, farthest)
                        new_patches = [Patch(list(half)) for half in halves]

                        # Replace outer in model.patches with new_patches (in order)
                        idx = -1
                        for i, pp in enumerate(model.patches):
                            if pp is outer:
                                idx = i
                                break
                        if idx != -1:
                            model.patches[idx : idx + 1] = new_patches

            # Remove neighbour entries so no gates are placed too close
            if index == 0:
                del entrances[0:2]
                if entrances:
                    entrances.pop()
            elif index == len(entrances) - 1:
                del entrances[index - 1 : index + 1]
                if entrances:
                    entrances.pop(0)
            else:
                del entrances[index - 1 : index + 2]

            if len(entrances) < 3:
                break

        if not self.gates:
            raise RuntimeError("Bad walled area shape!")

        if real:
            for gate in self.gates:
                gate.set(self.shape.smooth_vertex(gate))

    def build_towers(self) -> None:
        self.towers = []
        if not self.real:
            return
        n = len(self.shape)
        gate_ids = {id(g) for g in self.gates}
        for i in range(n):
            t = self.shape[i]
            if id(t) not in gate_ids and (
                self.segments[(i + n - 1) % n] or self.segments[i]
            ):
                self.towers.append(t)

    def get_radius(self) -> float:
        return max(v.length for v in self.shape)

    def borders_by(self, p: Patch, v0: Point, v1: Point) -> bool:
        patches_contains = any(q is p for q in self.patches)
        if patches_contains:
            index = self.shape.find_edge(v0, v1)
        else:
            index = self.shape.find_edge(v1, v0)
        if index != -1 and self.segments[index]:
            return True
        return False

    def borders(self, p: Patch) -> bool:
        within = any(q is p for q in self.patches)
        length = len(self.shape)
        for i in range(length):
            if not self.segments[i]:
                continue
            v0 = self.shape[i]
            v1 = self.shape[(i + 1) % length]
            if within:
                index = p.shape.find_edge(v0, v1)
            else:
                index = p.shape.find_edge(v1, v0)
            if index != -1:
                return True
        return False

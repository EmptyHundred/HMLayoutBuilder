"""Port of com.watabou.towngenerator.building.Topology."""

from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

from .graph import Graph, Node
from .point import Point

if TYPE_CHECKING:
    from .model import Model


class Topology:
    def __init__(self, model: "Model") -> None:
        self.model = model
        self.graph = Graph()
        self.pt2node: Dict[int, Node] = {}  # id(point) -> Node
        self.node2pt: Dict[Node, Point] = {}

        self.inner: List[Node] = []
        self.outer: List[Node] = []

        # Blocked points = walls + citadel walls, except gates
        blocked: List[Point] = []
        if model.citadel is not None:
            blocked.extend(model.citadel.shape)
        if model.wall is not None:
            blocked.extend(model.wall.shape)
        gate_ids = {id(g) for g in model.gates}
        self._blocked_ids = {id(p) for p in blocked if id(p) not in gate_ids}

        border = model.border.shape
        border_ids = {id(p) for p in border}

        for p in model.patches:
            within = p.within_city
            n = len(p.shape)
            v1 = p.shape[-1]
            n1 = self._process_point(v1)

            for i in range(n):
                v0 = v1
                v1 = p.shape[i]
                n0 = n1
                n1 = self._process_point(v1)

                if n0 is not None and id(v0) not in border_ids:
                    target = self.inner if within else self.outer
                    if n0 not in target:
                        target.append(n0)
                if n1 is not None and id(v1) not in border_ids:
                    target = self.inner if within else self.outer
                    if n1 not in target:
                        target.append(n1)

                if n0 is not None and n1 is not None:
                    n0.link(n1, Point.distance(v0, v1))

    def _process_point(self, v: Point) -> Optional[Node]:
        pid = id(v)
        if pid in self.pt2node:
            n = self.pt2node[pid]
        else:
            n = self.graph.add()
            self.pt2node[pid] = n
            self.node2pt[n] = v
        if pid in self._blocked_ids:
            return None
        return n

    def build_path(
        self,
        frm: Point,
        to: Point,
        exclude: Optional[List[Node]] = None,
    ) -> Optional[List[Point]]:
        start = self.pt2node.get(id(frm))
        goal = self.pt2node.get(id(to))
        if start is None or goal is None:
            return None
        path = self.graph.a_star(start, goal, exclude)
        if path is None:
            return None
        return [self.node2pt[n] for n in path]

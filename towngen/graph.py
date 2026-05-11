"""Port of com.watabou.geom.Graph — simple A* over a weighted graph."""

from __future__ import annotations

from typing import Dict, List, Optional


class Node:
    __slots__ = ("links",)

    def __init__(self) -> None:
        self.links: Dict["Node", float] = {}

    def link(self, node: "Node", price: float = 1.0, symmetrical: bool = True) -> None:
        self.links[node] = price
        if symmetrical:
            node.links[self] = price

    def unlink(self, node: "Node", symmetrical: bool = True) -> None:
        self.links.pop(node, None)
        if symmetrical:
            node.links.pop(self, None)

    def unlink_all(self) -> None:
        for node in list(self.links.keys()):
            self.unlink(node)


class Graph:
    def __init__(self) -> None:
        self.nodes: List[Node] = []

    def add(self, node: Optional[Node] = None) -> Node:
        if node is None:
            node = Node()
        self.nodes.append(node)
        return node

    def remove(self, node: Node) -> None:
        node.unlink_all()
        self.nodes.remove(node)

    def a_star(
        self,
        start: Node,
        goal: Node,
        exclude: Optional[List[Node]] = None,
    ) -> Optional[List[Node]]:
        closed_set: List[Node] = list(exclude) if exclude is not None else []
        open_set: List[Node] = [start]
        came_from: Dict[Node, Node] = {}
        g_score: Dict[Node, float] = {start: 0.0}

        while open_set:
            current = open_set.pop(0)
            if current is goal:
                return self._build_path(came_from, current)

            closed_set.append(current)
            cur_score = g_score[current]
            for neighbour, price in current.links.items():
                if neighbour in closed_set:
                    continue
                score = cur_score + price
                if neighbour not in open_set:
                    open_set.append(neighbour)
                elif score >= g_score.get(neighbour, float("inf")):
                    continue
                came_from[neighbour] = current
                g_score[neighbour] = score

        return None

    @staticmethod
    def _build_path(came_from: Dict[Node, Node], current: Node) -> List[Node]:
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        return path

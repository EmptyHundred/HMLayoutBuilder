"""Port of openfl.geom.Point + PointExtender.

Points use default object identity (__eq__/__hash__). This matches the Haxe
port, where shared vertices between neighboring polygons are represented by
the same Point instance. indexOf, contains, findEdge etc. all rely on this.
"""

from __future__ import annotations

import math


class Point:
    __slots__ = ("x", "y")

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)

    # --- core mutation / cloning -----------------------------------------
    def set(self, other: "Point") -> None:
        self.x = other.x
        self.y = other.y

    def set_to(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def clone(self) -> "Point":
        return Point(self.x, self.y)

    def copy(self) -> "Point":
        return Point(self.x, self.y)

    def offset(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    # --- arithmetic ------------------------------------------------------
    def add(self, other: "Point") -> "Point":
        return Point(self.x + other.x, self.y + other.y)

    def subtract(self, other: "Point") -> "Point":
        return Point(self.x - other.x, self.y - other.y)

    def scale(self, f: float) -> "Point":
        return Point(self.x * f, self.y * f)

    def add_eq(self, other: "Point") -> None:
        self.x += other.x
        self.y += other.y

    def sub_eq(self, other: "Point") -> None:
        self.x -= other.x
        self.y -= other.y

    def scale_eq(self, f: float) -> None:
        self.x *= f
        self.y *= f

    # --- measurements ----------------------------------------------------
    @property
    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def normalize(self, length: float = 1.0) -> None:
        l = self.length
        if l == 0:
            return
        k = length / l
        self.x *= k
        self.y *= k

    def norm(self, length: float = 1.0) -> "Point":
        p = self.clone()
        p.normalize(length)
        return p

    def atan(self) -> float:
        return math.atan2(self.y, self.x)

    def dot(self, other: "Point") -> float:
        return self.x * other.x + self.y * other.y

    def rotate90(self) -> "Point":
        return Point(-self.y, self.x)

    @staticmethod
    def distance(a: "Point", b: "Point") -> float:
        return math.hypot(a.x - b.x, a.y - b.y)

    # --- debug -----------------------------------------------------------
    def __repr__(self) -> str:
        return f"Point({self.x:.3f}, {self.y:.3f})"

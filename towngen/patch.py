from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from .point import Point
from .polygon import Polygon

if TYPE_CHECKING:
    from .voronoi import Region
    from .wards import Ward


class Patch:
    __slots__ = ("shape", "ward", "within_walls", "within_city", "waterbody")

    def __init__(self, vertices: List[Point]) -> None:
        self.shape: Polygon = Polygon(vertices)
        self.ward: Optional["Ward"] = None
        self.within_walls = False
        self.within_city = False
        self.waterbody = False

    @staticmethod
    def from_region(r: "Region") -> "Patch":
        return Patch([tr.c for tr in r.vertices])

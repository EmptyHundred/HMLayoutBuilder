"""Port of com.watabou.utils.Random — a minimal LCG matching the Haxe output."""

import time

_G = 48271
_N = 2147483647

_seed = 1


def reset(seed: int = -1) -> None:
    global _seed
    if seed != -1:
        _seed = seed
    else:
        _seed = int(time.time() * 1000) % _N
    if _seed <= 0:
        _seed = 1


def get_seed() -> int:
    return _seed


def _next() -> int:
    global _seed
    _seed = (_seed * _G) % _N
    return _seed


def rand_float() -> float:
    return _next() / _N


def normal() -> float:
    return (rand_float() + rand_float() + rand_float()) / 3.0


def rand_int(lo: int, hi: int) -> int:
    return int(lo + _next() / _N * (hi - lo))


def rand_bool(chance: float = 0.5) -> bool:
    return rand_float() < chance


def fuzzy(f: float = 1.0) -> float:
    if f == 0:
        return 0.5
    return (1 - f) / 2 + f * normal()

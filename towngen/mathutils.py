def gate(value: float, lo: float, hi: float) -> float:
    if value < lo:
        return lo
    return value if value < hi else hi


def sign(value: float) -> int:
    if value == 0:
        return 0
    return -1 if value < 0 else 1

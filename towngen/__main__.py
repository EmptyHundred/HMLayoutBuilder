"""CLI: python -m towngen --size 15 --seed 123 --out town.yaml"""

from __future__ import annotations

import argparse
import sys

from .model import Model
from .serialize import to_yaml


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="towngen",
        description="Generate a medieval town layout as YAML.",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=15,
        help="Number of inner patches (6=small town, 10=large town, 15=small city, 24=large city, 40=metropolis)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=-1,
        help="PRNG seed (omit or -1 for random)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="-",
        help="Output file path, or '-' for stdout",
    )
    parser.add_argument(
        "--no-citadel",
        dest="require_citadel",
        action="store_false",
        help="Make the citadel optional (random) instead of always present",
    )
    parser.add_argument(
        "--no-walls",
        dest="require_walls",
        action="store_false",
        help="Make walls optional (random) instead of always present",
    )
    parser.set_defaults(require_citadel=True, require_walls=True)
    args = parser.parse_args(argv)

    model = Model(
        n_patches=args.size,
        seed=args.seed,
        require_citadel=args.require_citadel,
        require_walls=args.require_walls,
    )
    y = to_yaml(model)

    if args.out == "-":
        sys.stdout.write(y)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(y)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

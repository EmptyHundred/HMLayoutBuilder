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
    parser.add_argument("--no-citadel", dest="citadel", action="store_false",
                        help="Force no citadel")
    parser.add_argument("--maybe-citadel", dest="citadel",
                        action="store_const", const=None,
                        help="Make the citadel random (50/50)")
    parser.add_argument("--no-walls", dest="walls", action="store_false",
                        help="Force no walls")
    parser.add_argument("--maybe-walls", dest="walls",
                        action="store_const", const=None,
                        help="Make walls random (50/50)")
    parser.add_argument("--coast", dest="coast", action="store_true", default=None,
                        help="Force a coastline")
    parser.add_argument("--no-coast", dest="coast", action="store_false",
                        help="Force no coastline")
    parser.add_argument("--river", dest="river", action="store_true", default=None,
                        help="Force a river through the city")
    parser.add_argument("--no-river", dest="river", action="store_false",
                        help="Force no river")
    parser.set_defaults(citadel=True, walls=True)
    args = parser.parse_args(argv)

    model = Model(
        n_patches=args.size,
        seed=args.seed,
        citadel=args.citadel,
        walls=args.walls,
        coast=args.coast,
        river=args.river,
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

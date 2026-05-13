"""One-shot: generate a town layout and open the interactive visualizer.

Usage:
    python generate_and_show.py
    python generate_and_show.py --size 24 --seed 42
    python generate_and_show.py --size 15 --out-yaml town.yaml --out-png town.png
    python generate_and_show.py --static          # save PNG, don't open window
"""

from __future__ import annotations

import argparse
import os
import sys

from towngen.model import Model
from towngen.serialize import to_yaml
from towngen.visualize import visualize


def _ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a town layout and visualize it."
    )
    parser.add_argument("--size", type=int, default=15,
                        help="Inner patches: 6=small town, 15=small city, 24=large city, 40=metropolis")
    parser.add_argument("--seed", type=int, default=-1,
                        help="PRNG seed (-1 for random)")
    parser.add_argument("--out-yaml", default="output/town.yaml",
                        help="Where to write the layout YAML (default: output/town.yaml)")
    parser.add_argument("--out-png", default="output/town.png",
                        help="Where to write the static PNG, only with --static (default: output/town.png)")
    parser.add_argument("--static", action="store_true",
                        help="Save a PNG instead of opening an interactive window")
    parser.add_argument("--no-hover", action="store_true",
                        help="Open window but disable hover tooltips")
    parser.add_argument("--no-citadel", dest="citadel", action="store_false",
                        help="Force no citadel")
    parser.add_argument("--maybe-citadel", dest="citadel", action="store_const",
                        const=None, help="Make the citadel random (50/50)")
    parser.add_argument("--no-walls", dest="walls", action="store_false",
                        help="Force no walls")
    parser.add_argument("--maybe-walls", dest="walls", action="store_const",
                        const=None, help="Make walls random (50/50)")
    parser.add_argument("--coast", dest="coast", action="store_true",
                        default=None,
                        help="Force a coastline")
    parser.add_argument("--no-coast", dest="coast", action="store_false",
                        help="Force no coastline")
    parser.add_argument("--river", dest="river", action="store_true",
                        default=None,
                        help="Force a river through the city")
    parser.add_argument("--no-river", dest="river", action="store_false",
                        help="Force no river")
    parser.set_defaults(citadel=True, walls=True)
    args = parser.parse_args(argv)

    # 1. Generate
    model = Model(
        n_patches=args.size,
        seed=args.seed,
        citadel=args.citadel,
        walls=args.walls,
        coast=args.coast,
        river=args.river,
    )
    _ensure_parent_dir(args.out_yaml)
    with open(args.out_yaml, "w", encoding="utf-8") as f:
        f.write(to_yaml(model))
    print(f"Wrote {args.out_yaml} (size={args.size}, seed={model and 'ok'})",
          file=sys.stderr)

    # 2. Visualize
    if args.static:
        _ensure_parent_dir(args.out_png)
        visualize(args.out_yaml, out=args.out_png, show=False)
        print(f"Wrote {args.out_png}", file=sys.stderr)
    else:
        visualize(args.out_yaml, show=True, interactive=not args.no_hover)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

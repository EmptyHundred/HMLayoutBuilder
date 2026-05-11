"""One-shot: generate a town layout and open the interactive visualizer.

Usage:
    python generate_and_show.py
    python generate_and_show.py --size 24 --seed 42
    python generate_and_show.py --size 15 --out-yaml town.yaml --out-png town.png
    python generate_and_show.py --static          # save PNG, don't open window
"""

from __future__ import annotations

import argparse
import sys

from towngen.model import Model
from towngen.serialize import to_yaml
from towngen.visualize import visualize


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a town layout and visualize it."
    )
    parser.add_argument("--size", type=int, default=15,
                        help="Inner patches: 6=small town, 15=small city, 24=large city, 40=metropolis")
    parser.add_argument("--seed", type=int, default=-1,
                        help="PRNG seed (-1 for random)")
    parser.add_argument("--out-yaml", default="town.yaml",
                        help="Where to write the layout YAML")
    parser.add_argument("--out-png", default="town.png",
                        help="Where to write the static PNG (only with --static)")
    parser.add_argument("--static", action="store_true",
                        help="Save a PNG instead of opening an interactive window")
    parser.add_argument("--no-hover", action="store_true",
                        help="Open window but disable hover tooltips")
    parser.add_argument("--no-citadel", dest="require_citadel",
                        action="store_false",
                        help="Citadel optional (random) instead of always present")
    parser.add_argument("--no-walls", dest="require_walls",
                        action="store_false",
                        help="Walls optional (random) instead of always present")
    parser.set_defaults(require_citadel=True, require_walls=True)
    args = parser.parse_args(argv)

    # 1. Generate
    model = Model(
        n_patches=args.size,
        seed=args.seed,
        require_citadel=args.require_citadel,
        require_walls=args.require_walls,
    )
    with open(args.out_yaml, "w", encoding="utf-8") as f:
        f.write(to_yaml(model))
    print(f"Wrote {args.out_yaml} (size={args.size}, seed={model and 'ok'})",
          file=sys.stderr)

    # 2. Visualize
    if args.static:
        visualize(args.out_yaml, out=args.out_png, show=False)
        print(f"Wrote {args.out_png}", file=sys.stderr)
    else:
        visualize(args.out_yaml, show=True, interactive=not args.no_hover)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

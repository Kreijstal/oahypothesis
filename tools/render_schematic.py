#!/usr/bin/env python3
"""Render an OpenAccess schematic or symbol cellview to SVG.

Usage:
    render_schematic.py FILE.oa [OUT.svg] [--search DIR]... [--cds-lib FILE]
                       [--depth N]

The cellview is decoded from the .oa file and every symbol instance is
resolved recursively through the search roots, so the drawing includes the
full schematic, not just bounding boxes:

  * figures (lines, arcs, polygons, rectangles, ellipses)
  * instance placement and orientation
  * label text, net names and notes
  * pins and terminals

If OUT.svg is omitted the SVG goes next to the input file.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oaparser.library import resolver_for
from oaparser.schematic import oa2svg, oa_native_svg as R


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="path to sch.oa / sym.oa")
    ap.add_argument("out", nargs="?", help="output SVG (default: alongside input)")
    ap.add_argument("--search", action="append", default=[],
                    help="library root to resolve master cellviews (repeatable)")
    ap.add_argument("--cds-lib", help="cds.lib to resolve libraries from")
    ap.add_argument("--depth", type=int, default=6, help="instance recursion depth")
    ap.add_argument("--title", help="drawing title")
    args = ap.parse_args(argv)

    dst = args.out or os.path.splitext(args.file)[0] + ".svg"
    resolver = resolver_for(args.file, cds_lib=args.cds_lib, search_dirs=args.search)

    prims, titles, skipped = [], {}, {}
    R.decode_cell(args.file, resolver, R.IDENTITY, 0, prims, titles, set(),
                  args.depth, None, skipped)

    unresolved = sum(1 for t in titles.values() if t.get("unresolved"))
    oa2svg.LAST_TITLES.clear()
    oa2svg.LAST_TITLES.update(titles)
    n = oa2svg.render(prims, dst, args.title or args.file)

    extra = f", {unresolved} unresolved master(s)" if unresolved else ""
    if skipped:
        extra += ", " + ", ".join(f"{c} {k}(s) skipped" for k, c in sorted(skipped.items()))
    print(f"{args.file}: {n} primitive(s){extra} -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

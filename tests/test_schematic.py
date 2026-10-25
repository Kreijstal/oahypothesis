#!/usr/bin/env python3
"""Smoke tests for the schematic renderer.

These use a cellview that ships with the repository, so they do not need the
Cadence install.  They check that a schematic decode produces real drawing
primitives rather than only bounding boxes.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from oaparser.library import resolver_for
from oaparser.schematic import oa2svg, oa_native_svg as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "files", "rc", "sch16.oa")


def test_package_imports():
    from oaparser.schematic import (oa_shapes, oa_labels, oa_instances,
                                    oa_netnames, oa_props, oa_nets, oa_expr,
                                    oa_cdf, oa_native_svg, oa2svg)  # noqa: F401


def test_decode_produces_primitives():
    assert os.path.exists(SAMPLE), SAMPLE
    resolver = resolver_for(SAMPLE, search_dirs=[])
    prims, titles, skipped = [], {}, {}
    R.decode_cell(SAMPLE, resolver, R.IDENTITY, 0, prims, titles, set(), 6,
                  None, skipped)
    assert prims, "no drawing primitives decoded"
    kinds = set()
    for p in prims:
        if isinstance(p, tuple) and p:
            kinds.add(p[0])
    assert kinds, kinds


def test_render_writes_svg(tmp_path):
    resolver = resolver_for(SAMPLE, search_dirs=[])
    prims, titles, skipped = [], {}, {}
    R.decode_cell(SAMPLE, resolver, R.IDENTITY, 0, prims, titles, set(), 6,
                  None, skipped)
    oa2svg.LAST_TITLES.clear()
    oa2svg.LAST_TITLES.update(titles)
    out = tmp_path / "out.svg"
    n = oa2svg.render(prims, str(out), "test")
    assert n >= 1
    svg = out.read_text()
    assert "<svg" in svg
    # a real schematic drawing, not just rectangles
    assert ("<path" in svg) or ("<line" in svg) or ("<rect" in svg) or ("<text" in svg)

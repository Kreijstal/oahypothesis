#!/usr/bin/env python3
"""Extract bounding-box figures from a .oa file and render them to SVG.

Unlike render_symbol.py this only trusts *validated* structure: a figure
bbox is the marker 0xC0000000 followed by four int32 (x1, y1, x2, y2).
See GROUND_TRUTH.md for how that was proven against a lef2oa-generated file.

Degenerate boxes are drawn as line segments (that is how single wire
segments appear); everything else is drawn as a rectangle outline.

The sheet frame (by far the largest box) is dropped by default so the
actual content is visible.

usage:
    render_boxes.py FILE.oa [out.svg] [--keep-frame] [--tables 0x10d,0x10e]
"""
import argparse
import struct
import sys

sys.path.insert(0, __file__.rsplit("/tools/", 1)[0])
from oaparser.format import OaFile

MARKER = 0xC0000000
MAX_COORD = 200000


def figures(oa, tables=None, keep_frame=False):
    out = []
    for e in oa.entries:
        if tables and e.id not in tables:
            continue
        tbl = oa.data[e.offset:e.offset + e.size]
        for i in range(0, len(tbl) - 20, 4):
            if struct.unpack_from("<I", tbl, i)[0] != MARKER:
                continue
            x1, y1, x2, y2 = struct.unpack_from("<iiii", tbl, i + 4)
            if not all(abs(v) < MAX_COORD for v in (x1, y1, x2, y2)):
                continue
            # a coordinate pair must be ordered; property tables that happen to
            # contain the marker usually fail this
            if x1 > x2 or y1 > y2:
                continue
            out.append((e.id, x1, y1, x2, y2))
    if not keep_frame and out:
        out.remove(max(out, key=lambda b: (b[3] - b[1]) * (b[4] - b[2])))
    return out


def render(figs, path, width=1200, height=900, pad=40):
    xs = [b[1] for b in figs] + [b[3] for b in figs]
    ys = [b[2] for b in figs] + [b[4] for b in figs]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    w = max(1, maxx - minx)
    h = max(1, maxy - miny)

    # uniform scale so the drawing is not distorted
    scale = min((width - 2 * pad) / w, (height - 2 * pad) / h)
    offx = pad + ((width - 2 * pad) - w * scale) / 2
    offy = pad + ((height - 2 * pad) - h * scale) / 2

    def sx(x):
        return offx + (x - minx) * scale

    def sy(y):
        return height - offy - (y - miny) * scale

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
           f'height="{height}" viewBox="0 0 {width} {height}">',
           f'<rect width="{width}" height="{height}" fill="white"/>']
    for tid, x1, y1, x2, y2 in figs:
        if x1 == x2 or y1 == y2:
            svg.append(f'<line x1="{sx(x1):.1f}" y1="{sy(y1):.1f}" '
                       f'x2="{sx(x2):.1f}" y2="{sy(y2):.1f}" '
                       f'stroke="#06c" stroke-width="2"/>')
        else:
            svg.append(f'<rect x="{sx(x1):.1f}" y="{sy(y2):.1f}" '
                       f'width="{sx(x2) - sx(x1):.1f}" '
                       f'height="{sy(y1) - sy(y2):.1f}" fill="none" '
                       f'stroke="#c00" stroke-width="1.5"/>')
    svg.append(f'<text x="10" y="20" font-family="sans-serif" font-size="13">'
               f'{len(figs)} figures, bbox x[{minx},{maxx}] y[{miny},{maxy}]</text>')
    svg.append('</svg>')
    open(path, 'w').write('\n'.join(svg))
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('oa')
    ap.add_argument('out', nargs='?')
    ap.add_argument('--keep-frame', action='store_true')
    ap.add_argument('--tables', help='comma separated hex table ids')
    a = ap.parse_args()

    tables = None
    if a.tables:
        tables = {int(t, 16) for t in a.tables.split(',') if t.strip()}

    oa = OaFile.open(a.oa)
    figs = figures(oa, tables, a.keep_frame)
    out = a.out or (a.oa + '.boxes.svg')
    render(figs, out)
    print(f"{len(figs)} figures -> {out}")


if __name__ == '__main__':
    main()

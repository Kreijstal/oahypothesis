#!/usr/bin/env python3
"""oa2svg.py -- render a schematic SVG from the dump produced by dump_oa.il.

    virtuoso -nograph < dump_oa.il        # -> balun.dump
    python3 oa2svg.py balun.dump out.svg

The dump carries *local* coordinates per cellview plus instance placement
(xy + orient); this script does the transform maths and the drawing. That split
keeps the SKILL side trivial and puts the geometry where it is easy to test.

Orientation support: R0 (verified here -- every instance in the test schematic
is R0), plus the usual R90/R180/R270/MX/MY/MYR90/MXR90. Only R0 has been
validated against a real design, so treat the others as unverified.
"""
import math
import sys
from collections import OrderedDict

# orient -> (a, b, c, d) such that (x, y) -> (a*x + b*y, c*x + d*y)
ORIENT = {
    "R0":     (1, 0, 0, 1),
    "R90":    (0, -1, 1, 0),
    "R180":   (-1, 0, 0, -1),
    "R270":   (0, 1, -1, 0),
    "MX":     (1, 0, 0, -1),
    "MY":     (-1, 0, 0, 1),
    "MXR90":  (0, 1, 1, 0),
    "MYR90":  (0, -1, -1, 0),
}


class CellView:
    def __init__(self, lib, cell, view):
        self.lib, self.cell, self.view = lib, cell, view
        self.shapes = []      # ("P", objtype, [pts]) | ("B", objtype, bbox) | ("T", ...)
        self.insts = []       # (name, lib, cell, view, x, y, orient)
        self.props = {}       # instance name -> {property: value}
        self.cvprops = {}     # cellview-level properties

    @property
    def key(self):
        return (self.lib, self.cell, self.view)


def parse(path):
    cells = OrderedDict()
    cur = None
    with open(path, "r", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            tag = line.split(" ", 1)[0]
            if tag == "CV":
                _, lib, cell, view = line.split()
                cur = CellView(lib, cell, view)
                cells.setdefault(cur.key, cur)      # first block wins
            elif tag == "P":
                _, ot, n, *nums = line.split()
                pts = [(float(nums[i]), float(nums[i + 1]))
                       for i in range(0, min(len(nums), 2 * int(n)), 2)]
                cur.shapes.append(("P", ot, pts))
            elif tag == "B":
                _, ot, x1, y1, x2, y2 = line.split()[:6]
                cur.shapes.append(("B", ot, (float(x1), float(y1), float(x2), float(y2))))
            elif tag == "T":
                parts = line.split(" ", 6)
                x, y, h = float(parts[1]), float(parts[2]), float(parts[3])
                just = parts[4].strip('"()') if len(parts) > 4 else ""
                lorient = parts[5].strip('"()') if len(parts) > 5 else ""
                text = parts[6] if len(parts) > 6 else ""
                cur.shapes.append(("T", text, x, y, h, just, lorient))
            elif tag == "PROP":
                parts = line.split(" ", 3)
                if len(parts) >= 4 and cur is not None:
                    cur.props.setdefault(parts[1], {})[parts[2]] = parts[3].strip('"')
            elif tag == "CVP":
                parts = line.split(" ", 2)
                if len(parts) >= 3 and cur is not None:
                    cur.cvprops[parts[1]] = parts[2].strip('"')
            elif tag == "I":
                _, name, lib, cell, view, x, y, orient = line.split()[:8]
                cur.insts.append((name, lib, cell, view,
                                  float(x), float(y), orient.strip('"')))
    return cells


LAST_TITLES = {}
LAST_CVPROPS = {}


def flatten(cells, key, mat, depth=0, out=None, seen=None, owner=None):
    """Collect absolute primitives for cellview `key` under affine matrix `mat`.

    mat is (a, b, c, d, tx, ty): (x, y) -> (a*x + b*y + tx, c*x + d*y + ty)

    Each emitted primitive carries its owning instance path as its last element
    (None for the root cellview), so a renderer can group them and attach a
    tooltip. The property dict for each owner path is collected in LAST_TITLES.
    """
    out = [] if out is None else out
    seen = set() if seen is None else seen
    if depth == 0:
        LAST_TITLES.clear()
        LAST_CVPROPS.clear()
        LAST_CVPROPS.update(cells[key].cvprops if key in cells else {})
    if depth > 12 or key in seen or key not in cells:
        return out
    seen = seen | {key}
    cv = cells[key]
    a, b, c, d, tx, ty = mat

    def tp(p):
        x, y = p
        return (a * x + b * y + tx, c * x + d * y + ty)

    for sh in cv.shapes:
        if sh[0] == "P":
            out.append(("P", sh[1], [tp(p) for p in sh[2]], owner))
        elif sh[0] == "B":
            x1, y1, x2, y2 = sh[2]
            p1, p2 = tp((x1, y1)), tp((x2, y2))
            out.append(("B", sh[1], (min(p1[0], p2[0]), min(p1[1], p2[1]),
                                     max(p1[0], p2[0]), max(p1[1], p2[1])), owner))
        elif sh[0] == "T":
            txt = sh[1] or ""
            # symbol masters carry CDF expressions as label text (cdsTerm(...),
            # cdsParam(...)); they are not display text, so skip them.
            if txt.startswith("cds"):
                continue
            # text is not mirrored, but it does rotate with the instance
            angle = math.degrees(math.atan2(c, a)) if (a or c) else 0.0
            lorient = sh[6] if len(sh) > 6 else ""
            digits = "".join(ch for ch in lorient if ch.isdigit())
            if digits:
                angle += float(digits)
            out.append(("T", txt, tp((sh[2], sh[3])), sh[4],
                        sh[5] if len(sh) > 5 else "", angle, owner))
    for (_n, lib, cell, view, ix, iy, orient) in cv.insts:
        path = f"{owner}/{_n}" if owner else _n
        LAST_TITLES[path] = cv.props.get(_n, {})
        oa, ob, oc, od = ORIENT.get(orient, (1, 0, 0, 1))
        # instance transform composes on the right: mat * orient, then translate
        na = a * oa + b * oc
        nb = a * ob + b * od
        nc = c * oa + d * oc
        nd = c * ob + d * od
        ntx = a * ix + b * iy + tx
        nty = c * ix + d * iy + ty
        flatten(cells, (lib, cell, view), (na, nb, nc, nd, ntx, nty),
                depth + 1, out, seen, path)
    return out


def _bbox(prims):
    xs, ys = [], []
    for p in prims:
        if p[0] == "P":
            xs += [q[0] for q in p[2]]
            ys += [q[1] for q in p[2]]
        elif p[0] == "B":
            xs += [p[2][0], p[2][2]]
            ys += [p[2][1], p[2][3]]
        else:
            xs.append(p[2][0])
            ys.append(p[2][1])
    return min(xs), min(ys), max(xs), max(ys)


def _draw(p, X, Y, s):
    """One primitive -> list of SVG element strings."""
    if p[0] == "P":
        coords = " ".join(f"{X(x):.2f},{Y(y):.2f}" for x, y in p[2])
        tag = "polygon" if p[1] == "polygon" and len(p[2]) > 2 else "polyline"
        return [f'<{tag} points="{coords}" fill="none" stroke="#1a1a1a" '
                f'stroke-width="1.6"/>']
    if p[0] == "A":
        import math as _m
        cx, cy, rx, ry, st, en = p[2]
        while en < st:
            en += 2 * _m.pi
        span = en - st
        large = 1 if span > _m.pi else 0
        x1 = cx + rx * _m.cos(st)
        y1 = cy + ry * _m.sin(st)
        x2 = cx + rx * _m.cos(en)
        y2 = cy + ry * _m.sin(en)
        # y is flipped on screen, so a CCW (increasing-angle) arc is sweep 0
        return [f'<path d="M {X(x1):.2f},{Y(y1):.2f} A {abs(rx*s):.2f},'
                f'{abs(ry*s):.2f} 0 {large} 0 {X(x2):.2f},{Y(y2):.2f}" '
                f'fill="none" stroke="#1a1a1a" stroke-width="1.6"/>']
    if p[0] == "B":
        x1, y1, x2, y2 = p[2]
        if p[1] == "ellipse":
            return [f'<ellipse cx="{X((x1+x2)/2):.2f}" cy="{Y((y1+y2)/2):.2f}" '
                    f'rx="{(x2-x1)*s/2:.2f}" ry="{(y2-y1)*s/2:.2f}" fill="none" '
                    f'stroke="#0a5" stroke-width="1.4"/>']
        if p[1] == "pin":
            # Cadence draws terminal markers as solid squares in its plots
            return [f'<rect x="{X(x1):.2f}" y="{Y(y2):.2f}" '
                    f'width="{(x2-x1)*s:.2f}" height="{(y2-y1)*s:.2f}" '
                    f'fill="#111" stroke="#111" stroke-width="1.0"/>']
        return [f'<rect x="{X(x1):.2f}" y="{Y(y2):.2f}" width="{(x2-x1)*s:.2f}" '
                f'height="{(y2-y1)*s:.2f}" fill="none" stroke="#06c" '
                f'stroke-width="1.4"/>']
    if p[0] == "T":
        txt = (p[1] or "").replace("&", "&amp;").replace("<", "&lt;")
        if not txt:
            return []
        just = p[4] if len(p) > 4 else ""
        angle = p[5] if len(p) > 5 else 0.0
        anchor = ("start" if "left" in just.lower()
                  else "end" if "right" in just.lower() else "middle")
        baseline = ("hanging" if "upper" in just.lower()
                    else "middle" if "center" in just.lower() else "alphabetic")
        x, y = X(p[2][0]), Y(p[2][1])
        rot = (f' transform="rotate({-angle:.2f} {x:.2f} {y:.2f})"'
               if abs(angle) > 1e-9 else "")
        size = max(8, p[3] * s)
        raw = (p[1] or "").replace("&", "&amp;").replace("<", "&lt;")
        if "\n" in raw:                 # multi-line note: one tspan per line
            lines = raw.split("\n")
            spans = [f'<tspan x="{x:.2f}"'
                     + (' dy="0"' if i == 0 else f' dy="{size*1.25:.1f}"')
                     + f'>{ln or " "}</tspan>'
                     for i, ln in enumerate(lines)]
            return [f'<text x="{x:.2f}" y="{y:.2f}"{rot} font-size="{size:.1f}" '
                    f'fill="#c00" text-anchor="{anchor}" '
                    f'dominant-baseline="{baseline}">{"".join(spans)}</text>']
        return [f'<text x="{x:.2f}" y="{y:.2f}"{rot} '
                f'font-size="{size:.1f}" fill="#c00" '
                f'text-anchor="{anchor}" dominant-baseline="{baseline}">{txt}</text>']
    return []


def render(prims, out_path, title="", tooltips=True):
    """Draw primitives. Primitives owned by an instance are wrapped in a <g>
    with a <title>, so hovering shows that instance's properties."""
    if not prims:
        raise SystemExit("nothing to draw")
    minx, miny, maxx, maxy = _bbox(prims)
    W, H, pad = 1200, 900, 40
    s = min((W - 2 * pad) / max(maxx - minx, 1e-9),
            (H - 2 * pad) / max(maxy - miny, 1e-9))
    ox = pad + ((W - 2 * pad) - (maxx - minx) * s) / 2
    oy = pad + ((H - 2 * pad) - (maxy - miny) * s) / 2

    def X(x):
        return ox + (x - minx) * s

    def Y(y):
        return H - (oy + (y - miny) * s)

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
           f'font-family="sans-serif">',
           f'<rect width="{W}" height="{H}" fill="white"/>',
           f'<text x="10" y="16" font-size="11" fill="#666">{title} — '
           f'{len(prims)} primitives — user units x[{minx:g},{maxx:g}] '
           f'y[{miny:g},{maxy:g}]</text>']

    # group by owning instance, keeping first-seen order
    order, groups = [], {}
    for p in prims:
        owner = p[-1] if p[-1:] and isinstance(p[-1], (str, type(None))) else None
        if owner not in groups:
            groups[owner] = []
            order.append(owner)
        groups[owner].append(p)

    for owner in order:
        body = []
        for p in groups[owner]:
            body += _draw(p, X, Y, s)
        if not body:
            continue
        if owner is None or not tooltips:
            svg += body
            continue
        props = LAST_TITLES.get(owner, {})
        lines = [owner] + [f"{k} = {v}" for k, v in props.items()]
        tip = "&#10;".join(l.replace("&", "&amp;").replace("<", "&lt;")
                           for l in lines)
        svg.append(f"<g><title>{tip}</title>")
        svg += body
        svg.append("</g>")
    if LAST_CVPROPS:
        kv = "; ".join(f"{k}={v}" for k, v in LAST_CVPROPS.items())
        kv = kv.replace("&", "&amp;").replace("<", "&lt;")
        svg.append(f"<desc>cellview properties: {kv}</desc>")
    svg.append("</svg>")
    with open(out_path, "w") as fh:
        fh.write("\n".join(svg))
    return len(prims)

if __name__ == "__main__":
    dump = sys.argv[1] if len(sys.argv) > 1 else "balun.dump"
    outp = sys.argv[2] if len(sys.argv) > 2 else "balun.svg"
    cells = parse(dump)
    root = next(iter(cells))
    prims = flatten(cells, root, (1, 0, 0, 1, 0, 0))
    n = render(prims, outp, title=f"{root[0]}/{root[1]}/{root[2]}")
    print(f"{len(cells)} cellviews, {len(prims)} primitives -> {outp}")

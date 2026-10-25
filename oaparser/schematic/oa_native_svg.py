#!/usr/bin/env python3
"""oa_native_svg.py -- render a schematic cellview to SVG using only our own
byte-level decoders. No Virtuoso, no SKILL, no oracle.

Instances are drawn by resolving their master cellview and recursing, so symbols
appear as symbols. Resolution uses oaparser.library.LibraryResolver: cds.lib
`DEFINE` lines, any --search directories, and the libraries sitting beside the
cellview being opened.

    python3 oa_native_svg.py balun.oa out.svg [title] [--search DIR] [--cds-lib F]
"""
import sys
import math
import struct

from . import oa2svg
from . import oa_instances
from . import oa_labels
from . import oa_netnames
from . import oa_expr
from . import oa_cdf
from .term_terms import terminals_from_labels
from . import oa_shapes
from oaparser.format import OaFile
from oaparser.library import resolver_for

DBU = 160.0
IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
MIRROR = {"MX": (1, 0, 0, -1), "MY": (-1, 0, 0, 1),
          "MXR90": (0, 1, 1, 0), "MYR90": (0, -1, -1, 0)}
ROT = {"R0": 0.0, "R90": 90.0, "R180": 180.0, "R270": 270.0}


def matrix_for(orient, x, y):
    """Instance transform: (a, b, c, d, tx, ty)."""
    base = MIRROR.get(orient) or oa2svg.ORIENT.get(orient, (1, 0, 0, 1))
    a, b, c, d = base
    return (a, b, c, d, x, y)


def apply(mat, pt):
    a, b, c, d, tx, ty = mat
    x, y = pt
    return (a * x + b * y + tx, c * x + d * y + ty)


def angle_of(mat):
    import math
    return math.degrees(math.atan2(mat[2], mat[0]))


def compose(outer, inner):
    """outer ∘ inner (apply inner first)."""
    ao, bo, co, do, txo, tyo = outer
    ai, bi, ci, di, txi, tyi = inner
    return (ao * ai + bo * ci,
            ao * bi + bo * di,
            co * ai + do * ci,
            co * bi + do * di,
            ao * txi + bo * tyi + txo,
            co * txi + do * tyi + tyo)



def _arc_bbox(cx, cy, rx, ry, st, en, n=64):
    xs, ys = [], []
    for k in range(n + 1):
        t = st + (en - st) * k / n
        xs.append(cx + rx * math.cos(t))
        ys.append(cy + ry * math.sin(t))
    return min(xs), min(ys), max(xs), max(ys)


def solve_end_angle(cx, cy, rx, ry, st, target):
    """Recover a truncated end angle from the arc figure's own bbox.

    The writer drops the final four bytes of the arc table, so the last end
    angle is lost.  The arc's bbox is stored separately and pins the sweep
    down (modulo 2*pi); validated on the transformer's arcs, where the solver
    returns the known end angle 1.8235 as 8.1064 (= 1.8235 + 2*pi).
    """
    best, best_d = None, 1e18
    t = st + 0.01
    while t <= st + 2 * math.pi:
        b = _arc_bbox(cx, cy, rx, ry, st, t)
        d = sum(abs(b[i] - target[i]) for i in range(4))
        if d < best_d:
            best, best_d = t, d
        t += 0.01
    if best is None:
        return None
    lo, hi = max(st, best - 0.01), min(st + 2 * math.pi, best + 0.01)
    t = lo
    while t <= hi:
        b = _arc_bbox(cx, cy, rx, ry, st, t, 128)
        d = sum(abs(b[i] - target[i]) for i in range(4))
        if d < best_d:
            best, best_d = t, d
        t += 0.0002
    return best if best_d < 0.02 else None

def decode_cell(path, resolver, mat, depth, out, titles, seen, limit, owner,
                skipped=None):
    if skipped is None:
        skipped = {}
    if depth > limit:
        return
    key = str(path)
    if key in seen:
        return
    seen = seen | {key}

    shapes = list(oa_shapes.decode(path))

    # The "instance" layer rect is the symbol's bounding box, not artwork.
    # Cadence's own plot does not draw it (gnd: rect ((-0.0625 -0.25)(0.0625 0))
    # is absent from the oracle plot, while the pin square IS drawn).  We have
    # not decoded the per-shape layer yet, so drop a rect only when it is
    # exactly the union bbox of the *device* figures around it - the defining
    # property of that shape.
    dev = [f["bbox"] for f in shapes
           if f["class"] in ("line", "polygon", "ellipse") and f.get("bbox")]
    content = None
    if dev:
        content = (min(b[0] for b in dev), min(b[1] for b in dev),
                   max(b[2] for b in dev), max(b[3] for b in dev))
    def is_instance_rect(f):
        b = f.get("bbox")
        if f["class"] != "rect" or not b or not content:
            return False
        if any(v is None for v in b):
            return False
        return all(abs(b[i] - content[i]) < 1e-6 for i in range(4))

    oa_file = oa_shapes.OaFile.open(str(path))
    # The symbol's instance-layer box is the one rect whose bbox is recorded in
    # table 0x010d (the cellview bbox record); pins and artwork are not.  Among
    # rects that match, the instance box is the largest.  Verified on
    # analogLib res/cap/ind/gnd/port/xfmr: Cadence never plots this box.
    inst_box = None
    try:
        _bo = getattr(oa_file, "byteorder", "<")
        _t = oa_file.table_bytes(0x010d) if oa_file.has(0x010d) else b""
        if _t:
            _cands = []
            for _f in shapes:
                if _f.get("class") != "rect" or not _f.get("bbox"):
                    continue
                if any(v is None for v in _f["bbox"]):
                    continue
                _pat = struct.pack(f"{_bo}4i",
                                   *[round(v * 160) for v in _f["bbox"]])
                if _t.find(_pat) >= 0:
                    _cands.append(tuple(_f["bbox"]))
            if _cands:
                inst_box = max(_cands, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    except Exception:
        inst_box = None

    _n_arc = sum(1 for _f in shapes if _f.get("class") == "arc")
    arc_recs = oa_shapes.arc_geometry(oa_file, _n_arc)
    arc_i = 0
    for f in shapes:
        cls, box, pts = f["class"], f["bbox"], f.get("points") or []
        if is_instance_rect(f):
            continue
        if inst_box is not None and cls == "rect" and box is not None and \
                all(v is not None for v in box) and \
                all(abs(box[i] - inst_box[i]) < 1e-9 for i in range(4)):
            continue                       # symbol instance box: never plotted
        if cls in ("label", "textDisplay"):
            continue                       # drawn from the label decoder
        if cls.startswith("0x"):
            try:
                # class nibble 9 is the text-object class; it is rendered from
                # the label table, so it is not an undecoded shape
                # 9 = text objects, 5 = the other text class (thin strips whose
                # strings come from the label tables, e.g. pllLib 'ctrl<N>')
                if (int(cls, 16) & 0x0F) in (5, 9):
                    continue
            except ValueError:
                pass
        if cls == "polygon" and pts:
            out.append(("P", "polygon", [apply(mat, p) for p in pts], owner))
            continue
        if box is None:
            continue
        x1, y1, x2, y2 = (v if v is not None else 0.0 for v in box)
        if cls == "line":
            out.append(("P", "line", [apply(mat, (x1, y1)),
                                      apply(mat, (x2, y2))], owner))
            continue
        corners = [apply(mat, c) for c in ((x1, y1), (x2, y1), (x2, y2), (x1, y2))]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        box2 = (min(xs), min(ys), max(xs), max(ys))
        if cls == "arc":
            rec = arc_recs[arc_i] if arc_i < len(arc_recs) else None
            arc_i += 1
            if rec and rec[1] is not None and rec[2] is None:
                (bx1, by1, bx2, by2), st, en = rec
                en = solve_end_angle((bx1 + bx2) / 2.0, (by1 + by2) / 2.0,
                                     (bx2 - bx1) / 2.0, (by2 - by1) / 2.0, st, box)
                rec = (rec[0], st, en)
            if rec and rec[1] is not None and rec[2] is not None:
                (bx1, by1, bx2, by2), st, en = rec
                cx, cy = (bx1 + bx2) / 2.0, (by1 + by2) / 2.0
                rx, ry = (bx2 - bx1) / 2.0, (by2 - by1) / 2.0
                while en < st:
                    en += 2 * math.pi
                # Sample the arc and push every point through the instance
                # transform.  Rotating only the start/end angles is valid for
                # circles but wrong for an ellipse under a 90/270 degree
                # rotation (the axes do not rotate with the parameter), which
                # turned rotated coils into spikes.
                steps = 24
                pts = []
                for _k in range(steps + 1):
                    _t = st + (en - st) * _k / steps
                    pts.append(apply(mat, (cx + rx * math.cos(_t),
                                           cy + ry * math.sin(_t))))
                out.append(("P", "line", pts, owner))
                continue
            skipped["arc"] = skipped.get("arc", 0) + 1
            continue
        elif cls == "pin":
            out.append(("B", "pin", box2, owner))
        elif cls == "0xb":
            # thin bar in the pin symbols (basic/iopin, ipin, opin): a pin marker
            out.append(("B", "pin", box2, owner))
        elif cls == "ellipse":
            out.append(("B", "ellipse", box2, owner))
        elif cls == "rect":
            out.append(("B", "rect", box2, owner))
        else:
            # Unknown shape class: count it rather than drawing its bounding
            # box, which used to put a large spurious rectangle on the sheet.
            skipped[cls] = skipped.get(cls, 0) + 1

    # Net labels: the schematic's textDisplays carry no literal text - they
    # name the net whose wire ends beside them.  Member 0x010f/0x0300 gives a
    # net index per figure and the names are in the heap in net-table order.
    net_ends = []
    try:
        net_by_fig = dict(oa_netnames.figure_names(str(path)))
        for _i, _f in enumerate(shapes):
            if _f.get("class") == "line" and _i in net_by_fig:
                _b = _f.get("bbox")
                if _b and all(v is not None for v in _b):
                    net_ends.append(((_b[0], _b[1]), net_by_fig[_i]))
                    net_ends.append(((_b[2], _b[3]), net_by_fig[_i]))
    except Exception:
        net_ends = []

    def _net_at(pt, tol=0.35):
        best, best_d = None, tol
        for q, nm in net_ends:
            d = ((q[0] - pt[0]) ** 2 + (q[1] - pt[1]) ** 2) ** 0.5
            if d < best_d:
                best, best_d = nm, d
        return best

    _labs = oa_labels.decode(path)
    if not _labs:
        try:
            _labs = oa_labels.decode_text_objects(path)
        except Exception:
            _labs = []
    for l in _labs:
        if not l["text"]:
            l = dict(l, text=_net_at((l["x"], l["y"])))
        if not l["text"]:
            continue
        ang = ROT.get(l["orient"], 0.0) + angle_of(mat)
        out.append(("T", l["text"], apply(mat, (l["x"], l["y"])),
                    l["height"] or 0.1, l["justify"], ang, owner))

    inst_list = list(oa_instances.decode(path))
    term_map = {}
    for _i in inst_list:
        _spec = _i.get("master")
        if _spec and _spec not in term_map:
            _t = resolver.resolve_spec(_spec) if _spec else None
            try:
                term_map[_spec] = (terminals_from_labels(oa_labels.symbol_labels(_t))
                                   if _t else [])
            except Exception:
                term_map[_spec] = []
    try:
        real_names = oa_instances.instance_names(
            oa_shapes.OaFile.open(str(path)), inst_list, term_map)
    except Exception:
        real_names = {}
    # If the writer-order walk did not cover every instance, its results are
    # not trustworthy for this file, and neither are parameter values (we have
    # no per-instance property decode).  In that case emit no instance-context
    # text at all rather than printing CDF defaults that may be wrong.
    names_ok = bool(inst_list) and len(real_names) >= len(inst_list)
    for i in inst_list:
        if i["x"] is None:
            continue
        child = matrix_for(i["orient"], i["x"], i["y"] or 0.0)
        spec = i["master"]
        target = resolver.resolve_spec(spec) if spec else None
        child_mat = compose(mat, child)
        if target and depth < limit:
            name = f"{owner}/{spec}" if owner else spec
            titles[name] = {"master": spec, "orient": i["orient"]}
            decode_cell(target, resolver, child_mat, depth + 1, out, titles,
                        seen, limit, name, skipped)
            # Symbol labels are evaluated text (cdsName(), cdsParam(n),
            # cdsTerm("X")).  Evaluate them in this instance's context; a
            # value of None means the context lacks that datum, so the label
            # is simply not drawn.
            try:
                sym = oa_labels.symbol_labels(target)
            except Exception:
                sym = []
            if sym:
                spec_parts = (spec or "").split(".")
                params = {}
                if target:
                    try:
                        import os as _os
                        cdf = oa_cdf.read_cell(
                            _os.path.dirname(_os.path.dirname(str(target))))
                        if cdf:
                            for _n in range(1, 8):
                                params[_n] = oa_cdf.param_display(cdf, _n)
                    except Exception:
                        params = {}
                if not names_ok:
                    params = {}
                ctx = {"params": params,
                       "cell": (spec_parts[1] if len(spec_parts) > 1 else None),
                       "name": (real_names.get(i.get("name"))
                                if names_ok else None),
                       "terminals": i.get("terminals") or {}}
                for box, expr in sym:
                    txt = oa_expr.evaluate(expr, ctx)
                    if not txt:
                        continue
                    bx1, by1, bx2, by2 = box
                    p = apply(child_mat, (bx1, by2))
                    h = abs(by2 - by1)
                    out.append(("T", str(txt), p, h, "leftLower", 0.0, name))
        else:
            p = apply(mat, (i["x"], i["y"] or 0.0))
            out.append(("B", "instance",
                        (p[0] - 0.05, p[1] - 0.05, p[0] + 0.05, p[1] + 0.05),
                        spec))
            if spec:
                titles[spec] = {"master": spec, "unresolved": True}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = sys.argv[1:]
    search, cds_lib, limit = [], None, 6
    for k, a in enumerate(opts):
        if a == "--search" and k + 1 < len(opts):
            search.append(opts[k + 1])
        if a == "--cds-lib" and k + 1 < len(opts):
            cds_lib = opts[k + 1]
        if a == "--depth" and k + 1 < len(opts):
            limit = int(opts[k + 1])
    if len(args) < 2:
        raise SystemExit(__doc__)
    src, dst = args[0], args[1]
    title = args[2] if len(args) > 2 else src

    resolver = resolver_for(src, cds_lib=cds_lib, search_dirs=search)
    prims, titles, skipped = [], {}, {}
    decode_cell(src, resolver, IDENTITY, 0, prims, titles, set(), limit, None, skipped)

    unresolved = sum(1 for t in titles.values() if t.get("unresolved"))
    oa2svg.LAST_TITLES.clear()
    oa2svg.LAST_TITLES.update(titles)
    n = oa2svg.render(prims, dst, title)
    extra = f", {unresolved} unresolved master(s)" if unresolved else ""
    if skipped:
        extra += ", " + ", ".join(f"{n} {k}(s) not decoded (skipped)"
                                   for k, n in sorted(skipped.items()))
    print(f"{src}: {n} primitive(s) decoded natively{extra} -> {dst}")


if __name__ == "__main__":
    main()

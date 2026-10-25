#!/usr/bin/env python3
"""oa_nets.py -- geometric connectivity engine for OA schematics.

Virtuoso's schematic editor derives nets from geometry: wire segments that share
an endpoint, or whose endpoint lies on another segment (a T junction), form one
net; a wire that reaches an instance terminal's pin also joins that terminal.
The authored result is what gets saved, but the same rule reproduces it, which
is what this module does.
"""
import math


def _segments(figs):
    """Axis-aligned wire segments from the decoded line figures."""
    out = []
    for f in figs:
        if f.get("class") != "line":
            continue
        x1, y1, x2, y2 = f["bbox"]
        out.append(((x1, y1), (x2, y2)))
    return out


def _on_segment(pt, seg, eps=0.0):
    (x1, y1), (x2, y2) = seg
    x, y = pt
    if abs(x1 - x2) <= eps:                 # vertical
        return abs(x - x1) <= eps and min(y1, y2) - eps <= y <= max(y1, y2) + eps
    if abs(y1 - y2) <= eps:                 # horizontal
        return abs(y - y1) <= eps and min(x1, x2) - eps <= x <= max(x1, x2) + eps
    return False


class _DSU:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra


def build(figs, terminals=(), eps=0.0):
    """Group wire segments into nets.

    terminals: iterable of (instance_name, terminal_name, (x, y)).
    Returns a list of dicts: {"figs": [seg...], "terms": [(inst, term)...]}.
    """
    segs = _segments(figs)
    dsu = _DSU(len(segs))
    for i, a in enumerate(segs):
        for j in range(i + 1, len(segs)):
            b = segs[j]
            if any(_on_segment(p, b, eps) for p in a) or \
               any(_on_segment(p, a, eps) for p in b):
                dsu.union(i, j)
    groups = {}
    for i, s in enumerate(segs):
        groups.setdefault(dsu.find(i), []).append(s)
    nets = [{"figs": v, "terms": []} for v in groups.values()]
    for inst, term, pt in terminals:
        for net in nets:
            if any(_on_segment(pt, s, eps) for s in net["figs"]):
                net["terms"].append((inst, term))
                break
    return nets


def decode(path, terminals=(), eps=0.0):
    from . import oa_shapes
    return build(oa_shapes.decode(path), terminals, eps)


# --- terminals -------------------------------------------------------------

def _pin_points(symbol_path, max_size=0.2):
    """Small rects in a symbol are its terminals; return their centres."""
    from . import oa_shapes
    out = []
    for f in oa_shapes.decode(symbol_path):
        if f.get("class") != "rect":
            continue
        x1, y1, x2, y2 = f["bbox"]
        if abs(x2 - x1) <= max_size and abs(y2 - y1) <= max_size:
            out.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0))
    return out


def _term_names(symbol_path):
    """[(label_position, terminal_name)] from the symbol's cdsTerm() labels."""
    from . import oa_labels
    from . import oa_expr
    import re
    out = []
    for box, expr in oa_labels.symbol_labels(symbol_path):
        m = re.fullmatch(r'cdsTerm\(\s*"([^"]+)"\s*\)', (expr or "").strip())
        if m:
            out.append((((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0),
                        m.group(1)))
    return out


def instance_terminals(path, resolver):
    """[(instance_name, terminal_name, sheet_point)] for a schematic."""
    from . import oa_instances
    from oa_native_svg import matrix_for, apply as _apply
    out = []
    for inst in oa_instances.decode(path):
        spec = inst.get("master")
        target = resolver.resolve_spec(spec) if spec else None
        if not target or inst.get("x") is None:
            continue
        pins = _pin_points(target)
        names = _term_names(target)
        mat = matrix_for(inst["orient"], inst["x"], inst["y"] or 0.0)
        for (px, py) in pins:
            name = None
            if names:
                name = min(names,
                           key=lambda np: (np[0][0] - px) ** 2 + (np[0][1] - py) ** 2)[1]
            out.append((inst.get("name"), name, _apply(mat, (px, py))))
    return out


def recover_positions(insts, figs, resolver):
    """Fill in instance coordinates the writer truncated.

    A truncated coordinate has no bytes left in the record, but the instance
    must still connect to the schematic: pick the candidate value (taken from
    the wire endpoint coordinates) that puts the most of its pins on a wire.
    """
    segs = _segments(figs)
    xs = sorted({p[0] for s in segs for p in s})
    ys = sorted({p[1] for s in segs for p in s})
    from oa_native_svg import matrix_for, apply as _apply
    fixed = []
    for inst in insts:
        x, y = inst.get("x"), inst.get("y")
        if x is not None and y is not None:
            fixed.append(inst)
            continue
        target = resolver.resolve_spec(inst.get("master") or "")
        pins = _pin_points(target) if target else []
        best, best_hits, ties = None, -1, 0
        cands = xs if x is None else ys
        for c in cands:
            xx = c if x is None else x
            yy = c if y is None else y
            mat = matrix_for(inst["orient"], xx, yy)
            hits = 0
            for p in pins:
                q = _apply(mat, p)
                if any(_on_segment(q, s) for s in segs):
                    hits += 1
            if hits > best_hits:
                best, best_hits = (xx, yy), hits
                ties = 0
            elif hits == best_hits:
                ties += 1
        if best and not ties:            # refuse to guess between equal fits
            inst = dict(inst, x=best[0], y=best[1])
        fixed.append(inst)
    return fixed

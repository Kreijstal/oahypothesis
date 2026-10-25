#!/usr/bin/env python3
"""oa_labels.py -- decode schematic label records straight from the .oa bytes.

Established by the one-field sweep (build_labsweep.il) and the columnar member
dump. Labels live in table 0x010f, member 0x030e, as 0xC0000000-separated
columns, one entry per label:

    column     layout                          meaning
    text       u32 width, then N values        string heap offset + 1
    height     u32 width, then N values        height in DBU + 1  (DBU = 160/user unit)
    origins    N x (i32 x, i32 y)              DBU, no +1
    justify    N bytes                         3*H + V, H: left0 center1 right2,
                                               V: upper0 center1 lower2
    orient     N bytes                         0 R0, 1 R90, 2 R180, 3 R270

A sentinel can occur inside the origin array by coincidence (a coordinate whose
bytes match 00 00 00 c0), so a raw split is wrong; segments whose length is not a
multiple of four are merged with the following one, which reconstructs the array.

    python3 oa_labels.py synth/labels2/schematic/sch.oa
    python3 oa_labels.py --json labels.json synth/labels2/schematic/sch.oa
"""
import json
import struct
import sys

from oaparser.format import OaFile, parse_base_tbl

from . import oa_shapes

SHAPE_TABLE = 0x010F
LABEL_MEMBERS = (0x030E, 0x0311)   # 0x030e = label, 0x0311 = textDisplay
DBU = 160.0
SENTINEL = b"\x00\x00\x00\xc0"

JUSTIFY = {3 * h + v: (h, v) for h in range(3) for v in range(3)}
H_NAMES = {0: "left", 1: "center", 2: "right"}
V_NAMES = {0: "upper", 1: "center", 2: "lower"}
ORIENT = {0: "R0", 1: "R90", 2: "R180", 3: "R270"}


def member_bytes(oa, table_id, member_id):
    if not oa.has(table_id):
        return None
    data = oa.table_bytes(table_id)
    bt = parse_base_tbl(data)
    if not bt:
        return None
    for i, off, size in zip(bt.ids, bt.offsets, bt.sizes):
        if i == member_id:
            return data[off:off + size]
    return None


def segments(chunk):
    """Split on sentinels, then re-join accidental splits."""
    raw, pos = [], 0
    while True:
        i = chunk.find(SENTINEL, pos)
        if i < 0:
            raw.append(chunk[pos:])
            break
        raw.append(chunk[pos:i])
        pos = i + 4
    out = []
    i = 0
    while i < len(raw):
        seg = raw[i]
        while len(seg) % 4 != 0 and i + 1 < len(raw):
            i += 1
            seg = seg + SENTINEL + raw[i]
        out.append(seg)
        i += 1
    return out


def as_ints(seg):
    return [struct.unpack_from("<i", seg, i)[0] for i in range(0, len(seg) - 3, 4)]


def raw_or_headed(seg, n, offsets, plus_one):
    """Return the column values for segment `seg` if it encodes n values
    either raw or behind a 4-byte width header; the +1 convention is optional."""
    for head in (4, 0):
        body = seg[head:]
        if len(body) < n:
            continue
        if head == 4:
            width = struct.unpack_from("<I", seg, 0)[0]
            if width not in (1, 2, 4):
                continue
        if head == 4 and width == 1:
            vals = list(body[:n])
        elif head == 4 and width == 2:
            vals = [struct.unpack_from("<H", body, i)[0] for i in range(0, 2 * n, 2)]
        else:
            vals = list(body[:n])
        if plus_one:
            if all((v - 1) in offsets for v in vals):
                return vals
        else:
            return vals
    return None


def decode_member(oa, chunk):
    if chunk is None or oa.string_table is None:
        return []
    segs = segments(chunk)
    offsets = set(oa.string_table.offsets)
    strings = oa.string_table

    best = None
    for si, seg in enumerate(segs):
        if len(seg) % 8 or len(seg) < 8:
            continue
        ints = as_ints(seg)
        if any(abs(v) > 1_000_000 for v in ints):
            continue
        n = len(seg) // 8
        for tj, tseg in enumerate(segs):
            if tj == si:
                continue
            text = raw_or_headed(tseg, n, offsets, plus_one=True)
            if text is None:
                continue
            # height column: the next segment after the text column
            height = None
            for hj in range(tj + 1, min(tj + 3, len(segs))):
                h = raw_or_headed(segs[hj], n, set(range(0, 10**6)), plus_one=False)
                if h is not None and all(0 < v <= 2000 for v in h):
                    height = [v - 1 for v in h]
                    break
            if height is None:
                continue
            origins = [(ints[k], ints[k + 1]) for k in range(0, len(ints), 2)]
            # justify / orient: the next two n-byte segments after the origins
            just = orient = None
            for j in range(si + 1, len(segs) - 1):
                vals = list(segs[j])
                nxt = list(segs[j + 1])
                if (len(vals) == n and len(nxt) == n and any(vals)
                        and all(v in JUSTIFY for v in vals)
                        and all(v in ORIENT for v in nxt)):
                    just, orient = vals, nxt
                    break
            if just is None:
                continue
            best = (n, text, height, origins, just, orient or [0] * n)
            break
        if best:
            break
    if not best:
        return []

    n, text, height, origins, just, orient = best
    labels = []
    for k in range(n):
        h, v = JUSTIFY.get(just[k], (1, 1))
        labels.append({
            "text": (None if all(v - 1 == 0 for v in text)
                     else strings.get_by_offset(text[k] - 1) if text[k] >= 1
                     else None),
            "x": origins[k][0] / DBU,
            "y": origins[k][1] / DBU,
            "height": height[k] / DBU,
            "justify": V_NAMES[v] + H_NAMES[h].capitalize(),
            "justify_code": just[k],
            "orient": ORIENT.get(orient[k], str(orient[k])),
        })
    return labels


def decode(path):
    oa = OaFile.open(path)
    for mid in LABEL_MEMBERS:
        labels = decode_member(oa, member_bytes(oa, SHAPE_TABLE, mid))
        if labels:
            return labels
    return []


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else "synth/labels2/schematic/sch.oa"
    labels = decode(path)
    print(f"{path}: {len(labels)} label(s) decoded from bytes")
    for l in labels:
        print(f"   {l['text']!r:14s} at ({l['x']:g},{l['y']:g}) h={l['height']:g} "
              f"{l['justify']} ({l['justify_code']}) {l['orient']}")
    if "--json" in sys.argv:
        out = sys.argv[sys.argv.index("--json") + 1]
        json.dump({"labels": labels}, open(out, "w"), indent=1)
        print("wrote", out)


if __name__ == "__main__":
    main()


SYMBOL_LABEL_MEMBER = 0x030F   # symbol cellviews use 0x030f, not 0x030e


def _text_column(oa, seg, n):
    """A column is: u32 width, then n values of that width (string offset+1)."""
    if len(seg) < 4:
        return None
    w = struct.unpack_from("<i", seg, 0)[0]
    if w not in (1, 2, 4):
        return None
    body = seg[4:]
    if len(body) < n * w:
        return None
    body = body[:n * w]          # trailing bytes are alignment padding
    offs = set(oa.string_table.offsets)
    vals = [int.from_bytes(body[k * w:(k + 1) * w], "little") for k in range(n)]
    if not all((v - 1) in offs for v in vals):
        return None
    return [oa.string_table.get_by_offset(v - 1) for v in vals]


def symbol_labels(path):
    """[(bbox, expression)] for a SYMBOL cellview.

    Symbol cells keep their labels in member 0x030f; the text column holds
    string offsets+1 which resolve to Cadence evaluated-text expressions
    (cdsName(), cdsParam(n), cdsTerm("X")) or to literal strings.  Positions
    come from the class-"label" figures in the ordinary bbox table.
    """
    from . import oa_shapes
    oa = OaFile.open(path)
    seg = oa_shapes.members(oa, SHAPE_TABLE).get(SYMBOL_LABEL_MEMBER)
    if not seg or oa.string_table is None:
        return []
    boxes = [f["bbox"] for f in oa_shapes.decode(path) if f["class"] == "label"]
    n = len(boxes)
    if not n:
        return []
    parts, i = [], 0
    while True:
        j = seg.find(SENTINEL, i)
        if j < 0:
            parts.append(seg[i:])
            break
        parts.append(seg[i:j])
        i = j + 4
    for part in parts:
        texts = _text_column(oa, part, n)
        if texts:
            return list(zip(boxes, texts))
    return []


def _segments(seg):
    parts, i = [], 0
    while True:
        j = seg.find(b"\x00\x00\x00\xc0", i)
        if j < 0:
            parts.append(seg[i:])
            return parts
        parts.append(seg[i:j])
        i = j + 4


def decode_text_objects(path):
    """Fallback decoder for cellviews whose labels use a 2-byte text column.

    `rfLib/ten_plexer` stores its text objects (class 0x9 / 0x2029) in member
    0x030e with the layout [header][u16 text refs][justify][int32 x,y pairs]
    [height]..., which the main decoder does not recognise.  Every reference is
    verified to resolve to a real heap string before anything is returned.
    """
    import struct as _s
    oa = OaFile.open(path)
    st = oa.string_table
    m = oa_shapes.members(oa, 0x010F)
    out = []
    for mid in (0x030E, 0x0311):
        seg = m.get(mid)
        if not seg:
            continue
        parts = _segments(seg)
        texts = None
        for p in parts:
            if len(p) < 8:
                continue
            for w in (2, 1):
                body = p[4:]
                if len(body) < w or len(body) % w:
                    continue
                vals = [_s.unpack_from(f"<{'H' if w == 2 else 'B'}", body, k)[0]
                        for k in range(0, len(body), w)]
                strs = []
                for v in vals:
                    t = None
                    if v:
                        try:
                            t = st.get_by_offset(v - 1)
                        except Exception:
                            t = None
                    strs.append(t)
                good = [t for t in strs if t]
                if len(good) >= 3 and len(good) >= len(strs) - 2:
                    texts = strs
                    break
            if texts:
                break
        if not texts:
            continue
        pts = None
        for p in parts:
            if len(p) < 16 or len(p) % 8:
                continue
            ints = [_s.unpack_from("<i", p, k)[0] for k in range(0, len(p) - 3, 4)]
            npts = len(ints) // 2
            # the origin array can be a couple of entries shorter than the text
            # array when the writer truncated it
            if npts >= 3 and abs(npts - len(texts)) <= 2:
                pts = [(ints[2 * k] / DBU, ints[2 * k + 1] / DBU)
                       for k in range(npts)]
                break
        if not pts:
            continue
        for (x, y), t in zip(pts, texts):
            if t:
                out.append({"text": t, "x": x, "y": y, "height": 0.0625,
                            "justify": "lowerLeft", "orient": "R0"})
    return out

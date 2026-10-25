#!/usr/bin/env python3
"""oa_netnames.py -- bind OA net names to nets.

Two facts, both verified against SKILL on analogLib/ideal_balun:

1. Member 0x010f/0x0300 of the schematic holds one net index per figure
   (0 = the figure is on no net, 1..N indexes the net table).
2. The net names sit in the string heap in the net table's order, immediately
   before the first instance name.

So figure -> net index -> name, and the connectivity engine supplies the rest.
"""
import sys

SENTINEL = b"\x00\x00\x00\xc0"


def _members(oa, tid):
    from . import oa_shapes
    return oa_shapes.members(oa, tid)


def figure_net_indices(oa):
    """One net index per figure, in figure order (0 = unconnected)."""
    seg = _members(oa, 0x010F).get(0x0300)
    if not seg:
        return []
    cut = seg.find(SENTINEL)
    if cut < 0:
        return []
    body = seg[cut + 8:]                 # skip marker + count
    return list(body)


def net_names(path):
    """Net names in net-table order."""
    from oaparser.format import OaFile
    oa = OaFile.open(path)
    st = oa.string_table
    seq = [st.get_by_offset(o) for o in st.offsets]
    cnt = _members(oa, 0x010D).get(0x0104) or b""
    n = int.from_bytes(cnt[:4], "little") if len(cnt) >= 4 else 0
    if not n:
        return []
    # the names are the last n strings before the first instance name; the
    # instance region starts at the first master spec
    from . import oa_instances
    insts = oa_instances.decode(path)
    if insts and insts[0].get("master") in seq:
        # the first instance NAME is the string just before its master spec
        first = seq.index(insts[0]["master"]) - 1
        return seq[first - n:first]
    return seq[-(n + 2):-2]


def figure_names(path):
    """[(figure_index, net_name)] for every figure that is on a net."""
    from oaparser.format import OaFile
    oa = OaFile.open(path)
    names = net_names(path)
    out = []
    for i, idx in enumerate(figure_net_indices(oa)):
        if 1 <= idx <= len(names):
            out.append((i, names[idx - 1]))
    return out

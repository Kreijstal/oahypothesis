#!/usr/bin/env python3
"""oa_expr.py -- evaluator for Cadence "evaluated text" label expressions.

Vendor symbol cellviews do not store label text as strings.  They store a
skill expression that Cadence evaluates in the context of the instance being
drawn.  The xfmr symbol's eight labels are, in file order:

    cdsTerm("P+")  cdsTerm("P-")  cdsTerm("S+")  cdsTerm("S-")
    cdsName()      cdsParam(2)    cdsParam(1)    cdsParam(3)

Context keys
    name       instance name                      -> cdsName()
    params     {int: value}  instance parameters   -> cdsParam(n)
    terminals  {"P+": name}  terminal names        -> cdsTerm("X")

Anything that is not a recognised call is returned as a literal.
"""
import re

_CALL = re.compile(
    r'cds\s*(Name|Param|Term)\s*\(\s*(?:"([^"]*)"|(-?\d+))?\s*\)\s*$')


def is_expression(text):
    return bool(text) and _CALL.match(text.strip()) is not None


def evaluate(expr, ctx=None):
    """Return the text for `expr` in context `ctx`, or None if unknowable."""
    ctx = ctx or {}
    if expr is None:
        return None
    text = expr.strip()
    if text == "[@cellName]":            # format string -> cellview cell name
        return ctx.get("cell")
    if text == "[@instanceName]":        # format string -> instance name
        return ctx.get("name")
    if text == "[@partName]":            # format string -> library part name
        return ctx.get("cell")
    m = _CALL.match(text)
    if not m:
        return expr                      # a literal string
    kind, sarg, narg = m.group(1), m.group(2), m.group(3)
    if kind == "Name":
        return ctx.get("name")
    if kind == "Param":
        if narg is None:
            return None
        params = ctx.get("params") or {}
        for key in (int(narg), str(narg)):
            if key in params:
                return params[key]
        return None
    if kind == "Term":
        if sarg is None:
            return None
        terms = ctx.get("terminals") or {}
        return terms.get(sarg)
    return None

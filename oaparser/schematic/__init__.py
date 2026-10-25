"""Schematic parsing and rendering for OpenAccess cellviews.

Layers, from the file up:

    oa_shapes    figures: bbox, class, arc/ellipse/polygon/line/rect geometry
    oa_labels    label tables and text objects (1-byte and 2-byte columns)
    oa_instances instance origins, orientations and master indices
    oa_netnames  net index per figure and net names
    oa_props     property tables
    oa_nets      connectivity (segments, terminals, pin points)
    oa_expr      label expressions (cdsName, cdsParam, cdsTerm, [@cellName])
    oa_cdf       cell CDF parameters (data.dm)
    oa_native_svg  recursive cellview -> primitives
    oa2svg       primitives -> SVG
"""
from . import (oa_shapes, oa_labels, oa_instances, oa_netnames, oa_props,
               oa_nets, oa_expr, oa_cdf, oa_native_svg, oa2svg)

__all__ = ["oa_shapes", "oa_labels", "oa_instances", "oa_netnames", "oa_props",
           "oa_nets", "oa_expr", "oa_cdf", "oa_native_svg", "oa2svg"]

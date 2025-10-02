"""
OA Parser - Binary file parsing utilities for OpenAccess format files
"""

from .binary_curator import BinaryCurator, Region, ClaimedRegion, UnclaimedRegion, NestedUnclaimedData
from .oa_renderer import render_report, render_regions_to_string, summarized_hex_dump

__all__ = [
    'BinaryCurator', 
    'Region', 
    'ClaimedRegion', 
    'UnclaimedRegion',
    'NestedUnclaimedData',
    'render_report',
    'render_regions_to_string',
    'summarized_hex_dump'
]

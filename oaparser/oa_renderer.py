"""
Rendering module for binary parsing results.

This module provides the "View" layer in the Model-View separation.
It takes structured region data and renders it in a human-readable format.
"""

from typing import List
from .binary_curator import Region, UnclaimedRegion, ClaimedRegion


def summarized_hex_dump(data: bytes, indent: str = "  "):
    """
    Creates a summarized hex dump that collapses long runs of identical bytes.
    
    Args:
        data: The byte data to dump
        indent: Indentation string for each line
    """
    if not data:
        return
    
    # Heuristic: A run is "long" if it's more than 2 full lines (32 bytes)
    LONG_RUN_THRESHOLD = 32
    
    i = 0
    while i < len(data):
        byte_val = data[i]
        run_length = 1
        while i + run_length < len(data) and data[i + run_length] == byte_val:
            run_length += 1
        
        if run_length >= LONG_RUN_THRESHOLD:
            print(f"{indent}[... {run_length} bytes of 0x{byte_val:02x} ...]")
            i += run_length
        else:
            # Print a standard 16-byte line
            end = min(i + 16, len(data))
            chunk = data[i:end]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            print(f"{indent}{i:04x}: {hex_part:<48} |{ascii_part}|")
            i += 16


def render_report(regions: List[Region], title: str = "Binary Analysis Report"):
    """
    Renders a complete report by walking through a list of Region objects.
    
    This is the "walker" or "renderer" that provides the View layer.
    It delegates the actual rendering of parsed values to the objects themselves
    via their __str__ methods.
    
    Args:
        regions: List of Region objects (ClaimedRegion and UnclaimedRegion)
        title: Optional title for the report
    """
    print(f"\n{title}")
    
    for region in regions:
        if isinstance(region, UnclaimedRegion):
            # Render unclaimed data with hex dump
            print(f"[UNCLAIMED DATA]  Offset: 0x{region.start:x}, Size: {region.size} bytes")
            summarized_hex_dump(region.raw_data, indent="  ")
            
        elif isinstance(region, ClaimedRegion):
            # Render claimed data in compact form
            parsed_str = str(region.parsed_value) if region.parsed_value is not None else ""
            print(f"[{region.name}]  Offset: 0x{region.start:x}, Size: {region.size} bytes  {parsed_str}")


def render_regions_to_string(regions: List[Region], title: str = "Binary Analysis Report") -> str:
    """
    Like render_report, but returns a string instead of printing.
    
    This is useful for tests and for cases where we need the output as a string.
    """
    lines = []
    lines.append(f"\n{title}")
    
    for region in regions:
        if isinstance(region, UnclaimedRegion):
            lines.append(f"[UNCLAIMED DATA]  Offset: 0x{region.start:x}, Size: {region.size} bytes")
            
            # Collect hex dump lines
            i = 0
            LONG_RUN_THRESHOLD = 32
            while i < len(region.raw_data):
                byte_val = region.raw_data[i]
                run_length = 1
                while i + run_length < len(region.raw_data) and region.raw_data[i + run_length] == byte_val:
                    run_length += 1
                
                if run_length >= LONG_RUN_THRESHOLD:
                    lines.append(f"  [... {run_length} bytes of 0x{byte_val:02x} ...]")
                    i += run_length
                else:
                    end = min(i + 16, len(region.raw_data))
                    chunk = region.raw_data[i:end]
                    hex_part = ' '.join(f'{b:02x}' for b in chunk)
                    ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
                    lines.append(f"  {i:04x}: {hex_part:<48} |{ascii_part}|")
                    i += 16
            
        elif isinstance(region, ClaimedRegion):
            parsed_str = str(region.parsed_value) if region.parsed_value is not None else ""
            lines.append(f"[{region.name}]  Offset: 0x{region.start:x}, Size: {region.size} bytes  {parsed_str}")
    
    return "\n".join(lines)

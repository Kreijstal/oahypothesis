"""
A small library for iterative reverse engineering of binary data blocks.

The core idea is to "curate" a byte array by claiming known structures.
The get_regions() method returns both the claimed structures and all the unclaimed
raw data in between, ensuring no data is ever hidden.

BINARY CURATOR PRINCIPLE - THE CARDINAL RULE:
============================================

Every byte claimed MUST be either interpreted OR asserted if the pattern is known.

THE WORST MISTAKE: Claiming data without printing it.

Example of WRONG usage:
    # BAD: Claims 716 bytes but only shows 2 values
    class TableHeader:
        def __str__(self):
            return f"Header ID: {self.header_id}, Pointers: {len(self.pointers)}"
    
    Output: "[Table Header] Size: 716 bytes Header ID: 4, Pointers: 89"
    ❌ 716 bytes claimed, but actual pointer data is HIDDEN!

Example of CORRECT usage:
    # GOOD: Shows all claimed data
    class TableHeader:
        def __str__(self):
            lines = [f"Header ID: {self.header_id}"]
            lines.append(f"Pointer Count: {len(self.pointers)}")
            for i, ptr in enumerate(self.pointers):
                lines.append(f"  [{i:03d}]: 0x{ptr:016x}")
            return "\\n".join(lines)
    
    Output: All 89 pointers are printed, accounting for all 716 bytes ✓

LOSSLESS DATA PHILOSOPHY:
========================

1. ALL claimed data must be printed or asserted
   - If you claim() a region, its __str__() must show the data
   - Arrays must print all elements (or summarize with clear counts)
   - Headers must print all fields

2. Repeated patterns can be summarized LOSSLESSLY
   - ✓ "0x00000000 x50" - clear and lossless
   - ✓ "Value 123 repeats 10 times" - lossless
   - ❌ "Header: 716 bytes" - data is hidden!

3. Unknown data should remain UNCLAIMED
   - Don't claim bytes you don't understand
   - get_regions() will automatically report UnclaimedRegion
   - This makes it obvious what needs reverse engineering

4. Assert known patterns explicitly
   - "Padding: 0x00 x24 (as expected)"
   - "Magic: 0x12345678 (validated)"
   - Make expectations visible in the output

This principle CANNOT be programmatically tested, but users and agents
must enforce it. Violating this rule defeats the purpose of reverse
engineering, which is to UNDERSTAND the data format.
"""

import struct
from dataclasses import dataclass, field
from typing import List, Any, Callable, Optional

# --- Base Region Class ---
@dataclass
class Region:
    """Base class for all regions in a binary block."""
    start: int
    size: int
    raw_data: bytes

    @property
    def end(self) -> int:
        return self.start + self.size

# --- Data Structure for an Unclaimed Region ---
@dataclass
class UnclaimedRegion(Region):
    """Stores information about a block of data that has not been identified."""
    pass

# --- Data Structure for Nested Unclaimed Data ---
@dataclass
class NestedUnclaimedData:
    """
    Represents unclaimed data within a claimed structure.
    This allows for partial understanding of complex records.
    """
    label: str  # e.g., "Unclaimed Payload", "Unknown Field @ 0x8"
    data: bytes
    description: Optional[str] = None  # Additional context
    
    def __str__(self):
        """Format nested unclaimed data with clear labeling."""
        lines = [f"[{self.label}] Size: {len(self.data)} bytes"]
        if self.description:
            lines.append(f"  Description: {self.description}")
        
        # Hex dump of the data (limited to first 256 bytes)
        if len(self.data) > 0:
            lines.append("  Hex dump:")
            display_size = min(len(self.data), 256)
            for i in range(0, display_size, 16):
                chunk = self.data[i:i+16]
                hex_part = ' '.join(f'{b:02x}' for b in chunk)
                ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
                lines.append(f"    {i:04x}: {hex_part:<48} |{ascii_part}|")
            
            if len(self.data) > 256:
                lines.append(f"    ... ({len(self.data) - 256} more bytes)")
        
        return "\n".join(lines)

# --- Data Structure for a Claimed Region ---
@dataclass
class ClaimedRegion(Region):
    """Stores information about a block of data that has been identified."""
    name: str
    parsed_value: Optional[Any] = None

# --- The Main Curator Class ---
class BinaryCurator:
    """
    Manages a block of binary data, allowing structures to be defined
    iteratively while keeping track of all unclaimed data.
    """
    def __init__(self, data: bytes):
        self.data = data
        self.cursor = 0
        self.regions: List[ClaimedRegion] = []

    def seek(self, offset: int):
        """Moves the internal cursor to an absolute offset."""
        if not (0 <= offset <= len(self.data)):
            raise ValueError(f"Seek offset {offset} is out of bounds (Size: {len(self.data)})")
        self.cursor = offset

    def skip(self, num_bytes: int):
        """Moves the internal cursor forward by a relative number of bytes."""
        self.seek(self.cursor + num_bytes)

    def claim(self, name: str, size: int, parser_func: Callable[[bytes], Any]):
        """
        Claims a block of bytes from the current cursor position as a known structure.

        Args:
            name: A human-readable name for this structure.
            size: The number of bytes to claim.
            parser_func: A function that takes the raw bytes of the claimed block 
                        and returns a parsed object. The object must have a __str__ 
                        method for rendering.
        
        IMPORTANT - BINARY CURATOR RULE:
            The object returned by parser_func MUST have a __str__() method that
            prints or interprets ALL the claimed bytes. Claiming bytes without
            printing them is the WORST mistake in binary reverse engineering.
            
            Example violations to avoid:
            - Claiming 716 bytes but only printing "Pointers: 89" ❌
            - Claiming an array but only printing its length ❌
            - Claiming a header but not showing all fields ❌
            
            Correct approach:
            - Print all array elements (or summarize: "0x00 x50") ✓
            - Print all header fields ✓
            - Show all interpreted data ✓
        """
        if self.cursor + size > len(self.data):
            raise ValueError(f"Cannot claim {size} bytes from offset {self.cursor}; not enough data.")

        start = self.cursor
        raw_chunk = self.data[start : start + size]
        
        try:
            parsed = parser_func(raw_chunk)
        except Exception as e:
            parsed = f"[PARSER ERROR: {e}]"

        region = ClaimedRegion(
            start=start,
            size=size,
            raw_data=raw_chunk,
            name=name,
            parsed_value=parsed
        )
        self.regions.append(region)
        self.cursor += size # Automatically advance the cursor

    def get_regions(self) -> List[Region]:
        """
        Returns a complete list of all regions (claimed and unclaimed) that covers
        the entire data block. This is the core of the "lossless" philosophy.
        
        Returns:
            A sorted list of Region objects (ClaimedRegion and UnclaimedRegion)
            that covers every byte from start to finish.
        """
        if not self.regions:
            # If nothing was claimed, the entire block is unclaimed
            return [UnclaimedRegion(
                start=0,
                size=len(self.data),
                raw_data=self.data
            )]
        
        # Sort claimed regions by start offset to handle out-of-order claims
        sorted_claimed = sorted(self.regions, key=lambda r: r.start)
        
        result: List[Region] = []
        last_end = 0
        
        for claimed in sorted_claimed:
            # Add any unclaimed region BEFORE this claimed region
            if claimed.start > last_end:
                result.append(UnclaimedRegion(
                    start=last_end,
                    size=claimed.start - last_end,
                    raw_data=self.data[last_end:claimed.start]
                ))
            
            # Add the claimed region
            result.append(claimed)
            last_end = claimed.end
        
        # Add any final unclaimed region at the end
        if last_end < len(self.data):
            result.append(UnclaimedRegion(
                start=last_end,
                size=len(self.data) - last_end,
                raw_data=self.data[last_end:]
            ))
        
        return result

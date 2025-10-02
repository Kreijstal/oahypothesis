"""
A small library for iterative reverse engineering of binary data blocks.

The core idea is to "curate" a byte array by claiming known structures.
The final report shows both the claimed structures and all the unclaimed
raw data in between, ensuring no data is ever hidden.
"""

import struct
from dataclasses import dataclass, field
from typing import List, Any, Callable, Optional

# --- Helper for Hex Dumping ---
def _hex_dump_lines(data: bytes, indent: str = "  ") -> List[str]:
    """Creates a list of formatted hex dump lines for a byte string."""
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
        lines.append(f"{indent}{i:04x}: {hex_part:<48} |{ascii_part}|")
    return lines

# --- Data Structure for a Claimed Region ---
@dataclass
class ClaimedRegion:
    """Stores information about a block of data that has been identified."""
    name: str
    start: int
    size: int
    raw_data: bytes
    parsed_value: Optional[Any] = None

    @property
    def end(self) -> int:
        return self.start + self.size

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

    def claim(self, name: str, size: int, parser_func: Optional[Callable[[bytes], Any]] = None):
        """
        Claims a block of bytes from the current cursor position as a known structure.

        Args:
            name: A human-readable name for this structure.
            size: The number of bytes to claim.
            parser_func: An optional function that takes the raw bytes of the
                         claimed block and returns a parsed, human-readable value.
        """
        if self.cursor + size > len(self.data):
            raise ValueError(f"Cannot claim {size} bytes from offset {self.cursor}; not enough data.")

        start = self.cursor
        raw_chunk = self.data[start : start + size]
        
        parsed = None
        if parser_func:
            try:
                parsed = parser_func(raw_chunk)
            except Exception as e:
                parsed = f"[PARSER ERROR: {e}]"

        region = ClaimedRegion(
            name=name,
            start=start,
            size=size,
            raw_data=raw_chunk,
            parsed_value=parsed
        )
        self.regions.append(region)
        self.cursor += size # Automatically advance the cursor

    def report(self) -> str:
        """
        Generates a complete report showing all claimed and unclaimed data blocks
        in order. This method is the core of the "lossless" philosophy.
        """
        lines = [f"--- Curated Binary Report (Total Size: {len(self.data)} bytes) ---"]
        
        if not self.regions:
            lines.append("\n[Unclaimed Data]")
            lines.append(f"  Offset: 0, Size: {len(self.data)} bytes")
            lines.extend(_hex_dump_lines(self.data))
            return "\n".join(lines)

        # Sort regions by start offset to handle out-of-order claims
        sorted_regions = sorted(self.regions, key=lambda r: r.start)
        
        last_end = 0
        for region in sorted_regions:
            # 1. Report any unclaimed data BEFORE this region
            if region.start > last_end:
                unclaimed_size = region.start - last_end
                lines.append("\n" + "="*50)
                lines.append(f"[Unclaimed Data]")
                lines.append(f"  Offset: 0x{last_end:x}, Size: {unclaimed_size} bytes")
                lines.extend(_hex_dump_lines(self.data[last_end:region.start]))

            # 2. Report the claimed region itself
            lines.append("\n" + "="*50)
            lines.append(f"[{region.name}]")
            lines.append(f"  Offset: 0x{region.start:x}, Size: {region.size} bytes")
            if region.parsed_value is not None:
                lines.append(f"  Parsed Value: {region.parsed_value}")
            lines.append(f"  Raw Hex: {' '.join(f'{b:02x}' for b in region.raw_data)}")
            
            last_end = region.end
        
        # 3. Report any final unclaimed data at the end of the block
        if last_end < len(self.data):
            final_unclaimed_size = len(self.data) - last_end
            lines.append("\n" + "="*50)
            lines.append(f"[Unclaimed Data]")
            lines.append(f"  Offset: 0x{last_end:x}, Size: {final_unclaimed_size} bytes")
            lines.extend(_hex_dump_lines(self.data[last_end:]))
            
        lines.append("\n" + "="*50)
        return "\n".join(lines)

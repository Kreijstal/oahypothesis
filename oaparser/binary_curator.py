"""
A small library for iterative reverse engineering of binary data blocks.

The core idea is to "curate" a byte array by claiming known structures.
The get_regions() method returns both the claimed structures and all the unclaimed
raw data in between, ensuring no data is ever hidden.
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

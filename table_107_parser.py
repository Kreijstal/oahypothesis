# table_107_parser.py
"""
Specialized parser for Table 0x107 (Object Edit Metadata).

This version correctly interprets a name pointer value of '0' as an instruction
to use the component's default name (e.g., "R0", "V0").
"""

import struct
from dataclasses import dataclass
from typing import List, Optional

from oaparser import BinaryCurator, Region

# --- Data Structures (For Schema Definition) ---

@dataclass
class InstanceSchema:
    """A simple data class to hold the known offsets for a component instance."""
    instance_name: str
    name_pointer_offset: int
    edit_count_offset: int

# --- The Parser Class ---

class Table107Parser:
    """
    Parser for Table 0x107 (Object Edit Metadata).
    """

    def __init__(self, data: bytes, string_list: Optional[List[str]] = None):
        if not isinstance(data, bytes):
            raise TypeError("Input data must be bytes.")
        self.data = data
        self.string_list = string_list if string_list else []
        self.curator = BinaryCurator(self.data)

        # Schema defining the component instances we know about.
        self.KNOWN_INSTANCES_SCHEMA = [
            InstanceSchema(
                instance_name="Resistor (R0)",
                name_pointer_offset=0x2b9,
                edit_count_offset=0x2e8
            ),
            InstanceSchema(
                instance_name="VDC Source (V0)",
                name_pointer_offset=0x2b0,
                # Placeholder until confirmed via diffs
                edit_count_offset=0x300
            ),
            InstanceSchema(
                instance_name="Capacitor (C0)",
                name_pointer_offset=0x2c1,
                # Placeholder until confirmed via diffs
                edit_count_offset=0x2f0
            )
        ]

    def _decode_name_pointer_value(self, value: int) -> Optional[int]:
        """Converts a raw byte value into a string table index."""
        if value < 1 or (value - 1) % 2 != 0:
            return None
        return ((value - 1) // 2) + 64

    # --- Parser Functions for `claim()` ---

    def _parse_name_pointer(self, raw_bytes: bytes) -> str:
        """
        Parses a 1-byte name pointer. Correctly interprets a value of 0
        as an indicator to use the default component name.
        """
        raw_val = raw_bytes[0]

        # This is the new, crucial logic.
        if raw_val == 0:
            return "Value: 0 (Default Name)"

        string_index = self._decode_name_pointer_value(raw_val)

        resolved_name = "???"
        if string_index is not None and 0 <= string_index < len(self.string_list):
            resolved_name = self.string_list[string_index]

        return f"Raw: {raw_val} (0x{raw_val:x}), String[{string_index}]: '{resolved_name}'"

    def _parse_version_counter(self, raw_bytes: bytes) -> str:
        """Parses a 4-byte little-endian version/edit counter."""
        raw_val = struct.unpack('<I', raw_bytes)[0]
        return f"Value: {raw_val} (0x{raw_val:x})"

    def parse(self) -> List[Region]:
        """
        Parses Table 0x107 by claiming only the individual, known fields.
        """
        # Iterate through each known component instance in our schema
        for instance in self.KNOWN_INSTANCES_SCHEMA:

            # --- Claim the 1-byte Name Pointer ---
            offset, size = instance.name_pointer_offset, 1
            if offset + size <= len(self.data):
                self.curator.seek(offset)
                self.curator.claim(
                    f"{instance.instance_name} - Name Pointer",
                    size,
                    self._parse_name_pointer
                )

            # --- Claim the 4-byte Edit Count ---
            offset, size = instance.edit_count_offset, 4
            if offset + size <= len(self.data):
                self.curator.seek(offset)
                self.curator.claim(
                    f"{instance.instance_name} - Edit Count",
                    size,
                    self._parse_version_counter
                )

        return self.curator.get_regions()

# table_b_parser.py - Focused parser for property list table 0xb
import struct

class TableBParser:
    """
    Parses Table 0xb based on the hypothesis that it contains a header,
    a record count, and a list of property records.

    Structure Hypothesis:
    - Header: 220 bytes (0xDC), contents not fully parsed.
    - Record Count: 4-byte little-endian uint at offset 0xDC.
    - Record List: An array of 4-byte records following the count.
    """

    def __init__(self, data):
        self.data = data
        self.records = []

    def parse(self):
        """
        Parses the table data according to the structured hypothesis.
        Returns a formatted string summary of the parsed data.
        """
        lines = [f"--- Parsed Structure of Table 0xb (Size: {len(self.data)} bytes) ---"]

        # 1. Validate size
        header_size = 220  # 0xDC
        count_offset = header_size
        records_offset = count_offset + 4

        if len(self.data) < records_offset:
            lines.append(f"  [ERROR] Table is too small ({len(self.data)} bytes) to contain a valid header and record count.")
            return "\n".join(lines)

        # 2. Parse Header and Record Count
        lines.append(f"\n[Header]")
        lines.append(f"  - Size: {header_size} bytes (0x0000 - 0x{header_size-1:04x})")
        lines.append(f"  - Note: Header is treated as an opaque block.")

        record_count = struct.unpack_from('<I', self.data, count_offset)[0]
        lines.append(f"\n[Metadata]")
        lines.append(f"  - Record Count at 0x{count_offset:04x}: {record_count}")

        # 3. Parse Record List
        lines.append(f"\n[Property Records]")
        lines.append(f"  - Location: 0x{records_offset:04x} -> end")
        lines.append(f"  - Record Size: 4 bytes")
        lines.append("-" * 40)

        expected_size = records_offset + (record_count * 4)
        if len(self.data) < expected_size:
            lines.append(f"  [WARNING] Data size ({len(self.data)}) is smaller than expected ({expected_size} bytes). Truncated list.")
            # Adjust record_count to what can actually be read
            record_count = (len(self.data) - records_offset) // 4


        for i in range(record_count):
            record_offset = records_offset + (i * 4)

            # Unpack the 4-byte record as a single integer
            record_val = struct.unpack_from('<I', self.data, record_offset)[0]
            
            # Also interpret the two 2-byte halves
            val_low = record_val & 0xFFFF
            val_high = (record_val >> 16) & 0xFFFF

            line = f"  - Record[{i:03d}] at 0x{record_offset:04x}: Full=0x{record_val:08x} (Low=0x{val_low:04x}, High=0x{val_high:04x})"
            lines.append(line)
            
            # Store the parsed record for potential external use
            self.records.append({
                "index": i,
                "offset": record_offset,
                "full_value": record_val,
                "low_word": val_low,
                "high_word": val_high
            })
        
        # 4. Report any trailing data
        trailing_data_start = records_offset + (record_count * 4)
        if trailing_data_start < len(self.data):
            trailing_size = len(self.data) - trailing_data_start
            lines.append(f"  [INFO] Found {trailing_size} unexpected trailing bytes at the end of the table.")

        return "\n".join(lines)

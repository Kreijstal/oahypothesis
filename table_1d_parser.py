# table_1d_parser.py - Parser for table directory 0x1d
import struct

class Table1dParser:
    """
    Parser for table 0x1d (Table Directory)
    
    This table contains an array of table IDs, acting as a directory
    or reference list of specific tables in the file.
    """
    
    def __init__(self, data):
        self.data = data
        self.table_ids = []
        
    def parse(self):
        """Parse the table directory with complete data dump"""
        if len(self.data) < 8:
            return f"Table Directory (0x1d): Too small ({len(self.data)} bytes)"
        
        lines = [f"Table Directory (0x1d): {len(self.data)} bytes"]
        lines.append("="*80)
        
        # Show complete hex dump first
        lines.append("\nComplete Binary Data:")
        lines.append("-"*80)
        for i in range(0, len(self.data), 16):
            chunk = self.data[i:i+16]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            lines.append(f"  {i:04x}: {hex_part:<48} |{ascii_part}|")
        
        # Parse as array of 64-bit table IDs
        lines.append("\n" + "="*80)
        lines.append("Parsed Structure:")
        lines.append("-"*80)
        
        if len(self.data) % 8 == 0:
            num_entries = len(self.data) // 8
            lines.append(f"\nTable ID Array: {num_entries} entries (64-bit values)")
            lines.append("")
            
            for i in range(num_entries):
                offset = i * 8
                table_id = struct.unpack('<Q', self.data[offset:offset+8])[0]
                self.table_ids.append(table_id)
                lines.append(f"  [{i:2d}] 0x{offset:04x}: Table 0x{table_id:x} ({table_id})")
            
            # Provide interpretation
            lines.append("\n" + "-"*80)
            lines.append("Interpretation:")
            lines.append("-"*80)
            lines.append("\nThis table acts as a directory listing specific tables.")
            lines.append("These table IDs reference other tables in the file:")
            
            # List known tables
            known_tables = {
                0x04: "Counter/Version",
                0x05: "Flag/Unused", 
                0x06: "Type/Count Pair",
                0x07: "Pointer Table",
                0x19: "Unknown Structure",
                0x1c: "Record Structure",
                0x1d: "Table Directory (self-reference)",
                0x25: "Unknown",
                0x2a: "Magic Number"
            }
            
            lines.append("")
            for table_id in self.table_ids:
                name = known_tables.get(table_id, "Unknown")
                lines.append(f"  → 0x{table_id:x}: {name}")
        else:
            lines.append(f"\nWarning: Size {len(self.data)} is not a multiple of 8")
            lines.append("Cannot parse as array of 64-bit values")
        
        return "\n".join(lines)

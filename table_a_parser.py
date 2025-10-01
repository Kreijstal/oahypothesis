# table_a_parser.py - Parser for string table 0xa
import struct

class TableAParser:
    """
    Parser for table 0xa (String Table)
    
    Hypothesis: The string table has a structure:
    - 16-byte header containing metadata
    - 4 bytes padding
    - String data as null-terminated strings
    
    The header format is: <I (type), I (num_entries), I (padding), I (padding)
    However, based on dump_string.py, it seems like we skip 20 bytes total
    to get to the string heap.
    """
    
    def __init__(self, data):
        self.data = data
        self.strings = []
        
    def parse(self):
        """Parse the string table and extract all strings"""
        if len(self.data) < 20:
            return f"String Table: Too small ({len(self.data)} bytes)"
        
        # Format the output
        lines = [f"String Table (0xa): {len(self.data)} bytes"]
        lines.append("="*80)
        
        # Show the 20-byte header in binary format
        lines.append("\nHeader (20 bytes):")
        header_data = self.data[:20]
        for i in range(0, 20, 16):
            chunk = header_data[i:i+16]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            lines.append(f"  {i:04x}: {hex_part:<48} |{ascii_part}|")
        
        # Parse header fields
        if len(self.data) >= 16:
            type_id, num_entries, pad1, pad2 = struct.unpack('<IIII', self.data[:16])
            lines.append(f"\n  Type ID: 0x{type_id:08x}")
            lines.append(f"  Number of entries: {num_entries} (0x{num_entries:x})")
            lines.append(f"  Padding1: 0x{pad1:08x}")
            lines.append(f"  Padding2: 0x{pad2:08x}")
            if len(self.data) >= 20:
                extra_pad = struct.unpack('<I', self.data[16:20])[0]
                lines.append(f"  Extra padding: 0x{extra_pad:08x}")
        
        # Skip the 20-byte header (16 bytes table info + 4 bytes padding)
        string_buffer = self.data[20:]
        
        lines.append(f"\nString Data ({len(string_buffer)} bytes):")
        lines.append("-"*80)
        
        # Extract all null-terminated strings
        current_offset = 0
        while current_offset < len(string_buffer):
            # Find the next null terminator
            try:
                null_pos = string_buffer.index(b'\0', current_offset)
            except ValueError:
                break
            
            # Decode the string
            string_data = string_buffer[current_offset:null_pos]
            
            # Skip empty strings
            if string_data:
                try:
                    decoded_string = string_data.decode('utf-8')
                    self.strings.append({
                        'offset': current_offset,
                        'string': decoded_string
                    })
                except UnicodeDecodeError:
                    self.strings.append({
                        'offset': current_offset,
                        'string': f'[DECODE ERROR: {string_data!r}]'
                    })
            
            current_offset = null_pos + 1
        
        lines.append(f"Total strings found: {len(self.strings)}")
        lines.append("")
        
        # Show ALL strings (no skipping)
        for i, entry in enumerate(self.strings):
            lines.append(f"  [{i:3d}] 0x{entry['offset']:04x}: '{entry['string']}'")
        
        return "\n".join(lines)

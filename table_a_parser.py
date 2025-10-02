# table_a_parser.py - Parser for string table 0xa
import struct
from oaparser import BinaryCurator

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
        
        curator = BinaryCurator(self.data)
        
        # Claim the 16-byte header
        def parse_header(data):
            type_id, num_entries, pad1, pad2 = struct.unpack('<IIII', data)
            lines = []
            lines.append(f"Type ID: 0x{type_id:08x}")
            lines.append(f"Number of entries: {num_entries} (0x{num_entries:x})")
            lines.append(f"Padding1: 0x{pad1:08x}")
            lines.append(f"Padding2: 0x{pad2:08x}")
            return "\n    ".join(lines)
        
        curator.claim("Header (16 bytes)", 16, parse_header)
        
        # Claim the 4-byte extra padding
        curator.claim("Extra Padding", 4, lambda d: f"0x{struct.unpack('<I', d)[0]:08x}")
        
        # Extract all null-terminated strings from remaining data
        string_buffer = self.data[20:]
        current_offset = 0
        string_regions = []
        
        while current_offset < len(string_buffer):
            # Find the next null terminator
            try:
                null_pos = string_buffer.index(b'\0', current_offset)
            except ValueError:
                break
            
            # Decode the string
            string_data = string_buffer[current_offset:null_pos]
            
            # Claim even empty strings to be lossless
            if string_data or null_pos - current_offset > 0:
                string_len = null_pos - current_offset + 1  # Include null terminator
                
                def make_parser(data):
                    try:
                        decoded = data.rstrip(b'\x00').decode('utf-8')
                        return f'"{decoded}"' if decoded else "(empty string)"
                    except UnicodeDecodeError:
                        return f'[DECODE ERROR: {data!r}]'
                
                curator.seek(20 + current_offset)
                curator.claim(f"String at 0x{current_offset:04x}", string_len, make_parser)
                
                # Store for later enumeration
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
        
        # Generate the report using BinaryCurator
        lines = [f"String Table (0xa): {len(self.data)} bytes"]
        lines.append("="*80)
        lines.append("")
        lines.append(curator.report())
        lines.append("")
        lines.append("="*80)
        lines.append(f"String Summary: {len(self.strings)} non-empty strings found")
        for i, entry in enumerate(self.strings):
            lines.append(f"  [{i:3d}] 0x{entry['offset']:04x}: '{entry['string']}'")
        
        return "\n".join(lines)

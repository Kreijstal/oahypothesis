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
        
        # Skip the 20-byte header (16 bytes table info + 4 bytes padding)
        string_buffer = self.data[20:]
        
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
        
        # Format the output
        lines = [f"String Table (0xa): {len(self.data)} bytes, {len(self.strings)} strings"]
        lines.append("="*80)
        
        # Show first 10 and last 10 strings
        show_count = 10
        if len(self.strings) <= show_count * 2:
            # Show all strings if there are few
            for i, entry in enumerate(self.strings):
                lines.append(f"  [{i:3d}] 0x{entry['offset']:04x}: '{entry['string']}'")
        else:
            # Show first 10
            for i in range(show_count):
                entry = self.strings[i]
                lines.append(f"  [{i:3d}] 0x{entry['offset']:04x}: '{entry['string']}'")
            
            lines.append(f"  ... ({len(self.strings) - 2*show_count} strings omitted) ...")
            
            # Show last 10
            for i in range(len(self.strings) - show_count, len(self.strings)):
                entry = self.strings[i]
                lines.append(f"  [{i:3d}] 0x{entry['offset']:04x}: '{entry['string']}'")
        
        return "\n".join(lines)

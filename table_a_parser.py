# table_a_parser.py - Parser for string table 0xa
import struct
from typing import List
from dataclasses import dataclass
from oaparser import BinaryCurator, Region

@dataclass
class StringTableHeader:
    """Header information for string table."""
    type_id: int
    num_entries: int
    pad1: int
    pad2: int
    
    def __str__(self):
        return f"Type: 0x{self.type_id:08x}, Entries: {self.num_entries}"

class TableAParser:
    """
    Parser for table 0xa (String Table)
    
    Hypothesis: The string table has a structure:
    - 16-byte header containing metadata
    - 4 bytes padding
    - String data as null-terminated strings
    """
    
    def __init__(self, data: bytes):
        self.data = data
        self.strings = []
        self.curator = BinaryCurator(self.data)
        
    def parse(self) -> List[Region]:
        """Parse the string table and return regions."""
        if len(self.data) < 20:
            # Return empty regions list for too-small data
            return self.curator.get_regions()
        
        # Claim the 16-byte header
        def parse_header(data):
            type_id, num_entries, pad1, pad2 = struct.unpack('<IIII', data)
            return StringTableHeader(type_id, num_entries, pad1, pad2)
        
        self.curator.claim("Header", 16, parse_header)
        
        # Claim the 4-byte extra padding
        self.curator.claim("Padding", 4, lambda d: f"0x{struct.unpack('<I', d)[0]:08x}")
        
        # Extract all null-terminated strings from remaining data
        string_buffer = self.data[20:]
        current_offset = 0
        
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
                
                def make_parser(sdata):
                    def parser(data):
                        try:
                            decoded = data.rstrip(b'\x00').decode('utf-8')
                            return f'"{decoded}"' if decoded else "(empty)"
                        except UnicodeDecodeError:
                            return f'[ERROR: {data!r}]'
                    return parser
                
                self.curator.seek(20 + current_offset)
                self.curator.claim(f"Str@0x{current_offset:04x}", string_len, make_parser(string_data))
                
                # Store for later enumeration
                if string_data:
                    try:
                        decoded_string = string_data.decode('utf-8')
                        self.strings.append({'offset': current_offset, 'string': decoded_string})
                    except UnicodeDecodeError:
                        self.strings.append({'offset': current_offset, 'string': f'[ERROR]'})
            
            current_offset = null_pos + 1
        
        return self.curator.get_regions()

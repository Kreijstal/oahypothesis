# table_1d_parser.py - Parser for table directory 0x1d
import struct
from dataclasses import dataclass
from oaparser import BinaryCurator, render_regions_to_string

@dataclass
class TableIdEntry:
    """Represents a single table ID entry in the directory."""
    index: int
    table_id: int
    name: str
    
    def __str__(self):
        return f"Table 0x{self.table_id:x} ({self.table_id}) - {self.name}"

class Table1dParser:
    """
    Parser for table 0x1d (Table Directory)
    
    This table contains an array of table IDs, acting as a directory
    or reference list of specific tables in the file.
    """
    
    # Known table names for interpretation
    KNOWN_TABLES = {
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
    
    def __init__(self, data):
        self.data = data
        self.table_ids = []
        
    def parse(self):
        """
        Parse the table directory and return a formatted string.
        
        Uses BinaryCurator to track regions and oa_renderer to format output.
        """
        if len(self.data) < 8:
            return f"Table Directory (0x1d): Too small ({len(self.data)} bytes)"
        
        curator = BinaryCurator(self.data)
        
        # Parse as array of 64-bit table IDs
        if len(self.data) % 8 == 0:
            num_entries = len(self.data) // 8
            
            for i in range(num_entries):
                # Parse this entry
                offset = i * 8
                table_id = struct.unpack('<Q', self.data[offset:offset+8])[0]
                self.table_ids.append(table_id)
                name = self.KNOWN_TABLES.get(table_id, "Unknown")
                
                # Create a parser function that returns a TableIdEntry object
                def make_parser(idx, tid, nm):
                    def parser(data):
                        return TableIdEntry(idx, tid, nm)
                    return parser
                
                curator.seek(offset)
                curator.claim(
                    f"Table ID [{i}]", 
                    8, 
                    make_parser(i, table_id, name)
                )
        
        # Get regions and render to string
        regions = curator.get_regions()
        report = render_regions_to_string(
            regions, 
            f"Table Directory (0x1d): {len(self.data)} bytes"
        )
        
        # Add warning if size isn't a multiple of 8
        if len(self.data) % 8 != 0:
            report += f"\n\nWarning: Size {len(self.data)} is not a multiple of 8\n"
            report += "Cannot fully parse as array of 64-bit values\n"
        
        return report

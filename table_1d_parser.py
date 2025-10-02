# table_1d_parser.py - Parser for table directory 0x1d
import struct
from dataclasses import dataclass
from typing import List
from oaparser import BinaryCurator, Region

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
    
    Uses BinaryCurator internally to produce a lossless list of regions.
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
    
    def __init__(self, data: bytes):
        self.data = data
        self.table_ids = []
        self.curator = BinaryCurator(self.data)
        
    def parse(self) -> List[Region]:
        """
        Parse the table directory and return a list of regions.
        
        Returns:
            List of Region objects (ClaimedRegion and UnclaimedRegion) representing
            the complete structure of the table.
        """
        # Parse as array of 64-bit table IDs
        if len(self.data) >= 8 and len(self.data) % 8 == 0:
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
                
                self.curator.seek(offset)
                self.curator.claim(
                    f"Table ID [{i}]", 
                    8, 
                    make_parser(i, table_id, name)
                )
        
        # Return the complete list of regions (claimed and unclaimed)
        return self.curator.get_regions()

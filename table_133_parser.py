# table_133_parser.py - Parser for Table 0x133
import struct
from dataclasses import dataclass, field
from typing import List
from oaparser import BinaryCurator, Region

@dataclass
class ParsedTable133:
    """
    A container for the parsed data from Table 0x133. This version treats
    the entire table as a single integer array to avoid hiding any data.
    """
    int_array: List[int] = field(default_factory=list)
    separator_index: int = -1
    found_counter: int = -1
    counter_index: int = -1
    counter_found: bool = False

class Table133Parser:
    """
    Parses the ENTIRE Table 0x133 as a flat array of 32-bit integers.
    It identifies the location of the 0xFFFFFFFF separator and then applies a
    heuristic to find a plausible "Structural Change Counter".
    """
    def __init__(self, data: bytes):
        self.data = data
        self.parsed_data = ParsedTable133()
        self.curator = BinaryCurator(self.data)

    def parse(self) -> List[Region]:
        # Parse the ENTIRE table into integers and claim each
        int_array = []
        cursor = 0
        index = 0
        
        while cursor <= len(self.data) - 4:
            val = struct.unpack_from('<I', self.data, cursor)[0]
            int_array.append(val)
            
            # Determine if this is a special value
            if val == 0xffffffff:
                label = f"Int[{index}]SEP"
            elif index > 0 and int_array[index-1] == 1 and 1 < val < 1000:
                label = f"Int[{index}]CNT"
            else:
                label = f"Int[{index}]"
            
            self.curator.seek(cursor)
            self.curator.claim(
                label,
                4,
                lambda d, v=val: f"{v} (0x{v:x})"
            )
            
            cursor += 4
            index += 1
        
        self.parsed_data.int_array = int_array

        # Find the separator's index within the complete array
        try:
            self.parsed_data.separator_index = int_array.index(0xffffffff)
        except ValueError:
            self.parsed_data.separator_index = -1

        # Apply the heuristic to find the counter
        self._find_counter()

        return self.curator.get_regions()

    def _find_counter(self):
        """
        Heuristically searches the integer array for the structural change counter.
        """
        arr = self.parsed_data.int_array
        for i in range(len(arr) - 1):
            # The pattern is: the integer 1, followed by a plausible counter value.
            if arr[i] == 1 and (1 < arr[i+1] < 1000):
                self.parsed_data.counter_index = i + 1
                self.parsed_data.found_counter = arr[i+1]
                self.parsed_data.counter_found = True
                return

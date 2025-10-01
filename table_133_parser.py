
# table_133_parser.py (Corrected Version 3 - Full Data Dump)
import struct
from dataclasses import dataclass, field
from typing import List

def format_full_int_array(int_array: List[int], separator_index: int) -> str:
    """
    Creates a string representation of the ENTIRE integer array, summarizing
    repeats and visually marking the separator's location.
    """
    if not int_array:
        return "  - (Array is empty)"

    lines = []
    last_num = None
    repeat_count = 0
    start_index = 0

    for i, num in enumerate(int_array):
        # Check if the current index is where the separator was found
        if i == separator_index:
            # First, print the last sequence of numbers before the separator
            if last_num is not None:
                line = f"  - Index[{start_index:03d}]: {last_num} (0x{last_num:x})"
                lines.append(line)
                if repeat_count > 1:
                    lines.append(f"      (Repeats {repeat_count} times)")

            # Now, print the separator marker itself
            lines.append("\n  ==================================================")
            lines.append(f"  --- SEPARATOR (0xffffffff) FOUND AT INDEX {i} ---")
            lines.append("  ==================================================\n")

            # Reset tracking for the numbers after the separator
            last_num = None
            repeat_count = 0
            continue # Skip to the next number

        if num == last_num:
            repeat_count += 1
        else:
            if last_num is not None:
                line = f"  - Index[{start_index:03d}]: {last_num} (0x{last_num:x})"
                lines.append(line)
                if repeat_count > 1:
                    lines.append(f"      (Repeats {repeat_count} times)")
            last_num = num
            repeat_count = 1
            start_index = i

    # Handle the very last number(s) in the list
    if last_num is not None:
        line = f"  - Index[{start_index:03d}]: {last_num} (0x{last_num:x})"
        lines.append(line)
        if repeat_count > 1:
            lines.append(f"      (Repeats {repeat_count} times)")

    return "\n".join(lines)


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

    def __str__(self):
        output = "[Full Integer Array Dump of Entire Table]\n"
        output += f"  - Parsed a total of {len(self.int_array)} 32-bit integers.\n"
        output += "--------------------------------------------------\n"
        output += format_full_int_array(self.int_array, self.separator_index)
        output += "\n--------------------------------------------------\n"

        if self.counter_found:
            context_start = max(0, self.counter_index - 4)
            context_end = min(len(self.int_array), self.counter_index + 4)
            context = self.int_array[context_start:context_end]

            output += (f"\n[Hypothesis Section]\n"
                       f"  Based on the full data dump above, a plausible candidate for the\n"
                       f"  Structural Change Counter has been located.\n"
                       f"  - Counter Value: {self.found_counter}\n"
                       f"  - Found at Index:  {self.counter_index}\n"
                       f"  - Local Context: ... {context} ...\n")
        else:
            output += "\n[Hypothesis Section]\n  - A plausible Structural Change Counter was not found.\n"

        return output

class Table133Parser:
    """
    Parses the ENTIRE Table 0x133 as a flat array of 32-bit integers.
    It identifies the location of the 0xFFFFFFFF separator and then applies a
    heuristic to find a plausible "Structural Change Counter".
    """
    def __init__(self, data: bytes):
        self.data = data
        self.parsed_data = ParsedTable133()

    def parse(self):
        # 1. Parse the ENTIRE table into a single integer array
        int_array = []
        cursor = 0
        while cursor <= len(self.data) - 4:
            val = struct.unpack_from('<I', self.data, cursor)[0]
            int_array.append(val)
            cursor += 4
        self.parsed_data.int_array = int_array

        # 2. Find the separator's index within the complete array
        try:
            self.parsed_data.separator_index = int_array.index(0xffffffff)
        except ValueError:
            self.parsed_data.separator_index = -1 # Not found

        # 3. Apply the heuristic to find the counter
        self._find_counter()

        return self.parsed_data

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


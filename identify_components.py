import os
import glob
import struct
import difflib

# --- Helper Functions ---
def hex_dump(data):
    """Creates a formatted hex dump of a byte string, similar to xxd."""
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
        lines.append(f"{i:08x}: {hex_part:<48} |{ascii_part}|")
    return lines

# --- Core Parser Class ---
class ParsedOaFile:
    """
    A comprehensive container for an .oa file's data, storing both high-level
    semantic information and the raw byte data of every table.
    """
    def __init__(self, filepath):
        self.filepath = os.path.basename(filepath)
        self.table_metadata = {} # id -> {offset, size}
        self.table_data = {}     # id -> raw_bytes
        self.strings = []
        self.save_counter = -1

        try:
            self._parse()
        except Exception as e:
            print(f"[ERROR] Failed to parse {self.filepath}: {e}")

    def _parse(self):
        """Parses the .oa file and loads all table data into memory."""
        with open(self.filepath, 'rb') as f:
            header = f.read(24)
            _, _, _, _, _, used = struct.unpack('<IHHQII', header)

            ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))

            for i in range(used):
                self.table_metadata[ids[i]] = {'offset': offsets[i], 'size': sizes[i]}
                if offsets[i] != 0xffffffffffffffff and sizes[i] > 0:
                    f.seek(offsets[i])
                    self.table_data[ids[i]] = f.read(sizes[i])

            if 0xa in self.table_data:
                string_heap = self.table_data[0xa][16:]
                current_offset = 0
                while current_offset < len(string_heap):
                    try:
                        null_pos = string_heap.index(b'\0', current_offset)
                        string_data = string_heap[current_offset:null_pos]
                        if string_data:
                            self.strings.append(string_data.decode('utf-8', 'ignore'))
                        current_offset = null_pos + 1
                    except ValueError:
                        break

            if 0x1 in self.table_data and len(self.table_data[0x1]) >= 0x64 + 4:
                self.save_counter = struct.unpack_from('<I', self.table_data[0x1], 0x64)[0]

# --- Main Diffing Logic ---
def print_full_diff(old_file, new_file):
    """
    Compares two ParsedOaFile objects and prints a complete report including
    both semantic and byte-level differences.
    """
    print("\n" + "#"*80)
    print(f"### Diffing '{old_file.filepath}' (OLD) vs. '{new_file.filepath}' (NEW) ###")
    print("#"*80)

    # --- Part 1: Semantic Diff ---
    print("\n======================= SEMANTIC CHANGES =======================")

    # Metadata
    print("\n[Metadata Changes]")
    if old_file.save_counter != new_file.save_counter:
        print(f"  - Save Counter incremented: {old_file.save_counter} -> {new_file.save_counter}")
    else:
        print("  - Save Counter is identical.")

    # Schema
    old_tables = set(old_file.table_metadata.keys())
    new_tables = set(new_file.table_metadata.keys())
    added = new_tables - old_tables
    removed = old_tables - new_tables

    print("\n[Schema (Table List) Changes]")
    if added:
        print(f"  - Tables ADDED: {', '.join(hex(t) for t in sorted(list(added)))}")
    if removed:
        print(f"  - Tables REMOVED: {', '.join(hex(t) for t in sorted(list(removed)))}")
    if not added and not removed:
        print("  - No change in the set of tables.")

    # String Timeline
    print("\n[String Timeline Changes]")
    str_diff = list(difflib.unified_diff(old_file.strings, new_file.strings, lineterm=''))

    change_found = False
    for line in str_diff:
        if line.startswith(('+', '-')) and not line.startswith(('+++', '---')):
            print(f"  {line}")
            change_found = True
    if not change_found:
         print("  - No changes to the string timeline.")

    # --- Part 2: Byte-Level Diff ---
    print("\n======================= BYTE-LEVEL DIFFS =======================")

    all_table_ids = sorted(list(old_tables | new_tables))
    diff_found = False

    for table_id in all_table_ids:
        old_data = old_file.table_data.get(table_id, b'')
        new_data = new_file.table_data.get(table_id, b'')

        if old_data != new_data:
            diff_found = True
            print(f"\n--- Diff for Table 0x{table_id:x} ---")

            old_dump = hex_dump(old_data)
            new_dump = hex_dump(new_data)

            hex_diff = list(difflib.unified_diff(old_dump, new_dump, fromfile=old_file.filepath, tofile=new_file.filepath, lineterm=''))

            # Print only relevant lines from the diff output
            for line in hex_diff:
                if not line.startswith(('---', '+++', '@@')):
                    print(line)

    if not diff_found:
        print("\nNo byte-level differences found in any table data.")


if __name__ == '__main__':
    oa_files = sorted(glob.glob('sch*.oa'))
    if not oa_files:
        print("Error: No 'sch*.oa' files found in this directory.")
        sys.exit(1)

    print(f"Found {len(oa_files)} .oa files to compare chronologically.")

    parsed_files = [ParsedOaFile(f) for f in oa_files]

    for i in range(len(parsed_files) - 1):
        print_full_diff(parsed_files[i], parsed_files[i+1])

    print("\n" + "#"*80)
    print("### End of Report ###")
    print("#"*80)

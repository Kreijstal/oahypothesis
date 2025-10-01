import os
import glob
import struct
import difflib

class ParsedOaFile:
    """
    A container for the semantically meaningful data we can reliably extract
    from an .oa file, ignoring the noisy, shifting offsets of raw table data.
    """
    def __init__(self, filepath):
        self.filepath = os.path.basename(filepath)
        self.tables = {}
        self.strings = []
        self.save_counter = -1

        try:
            self._parse()
        except Exception as e:
            print(f"[ERROR] Failed to parse {self.filepath}: {e}")

    def _parse(self):
        """
        Parses the .oa file to extract only the high-value, stable information:
        the list of tables and the chronological string timeline.
        """
        with open(self.filepath, 'rb') as f:
            # 1. Read the header and table directory to get table locations.
            header = f.read(24)
            _, _, _, _, _, used = struct.unpack('<IHHQII', header)

            ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))

            for i in range(used):
                self.tables[ids[i]] = {'offset': offsets[i], 'size': sizes[i]}

            # 2. Specifically parse the String Table (0xa) for its timeline.
            # This is the most important semantic data in the file.
            if 0xa in self.tables:
                info = self.tables[0xa]
                f.seek(info['offset'])
                table_a_data = f.read(info['size'])

                # The string "heap" starts after the 16-byte internal header.
                string_heap = table_a_data[16:]

                current_offset = 0
                while current_offset < len(string_heap):
                    try:
                        null_pos = string_heap.index(b'\0', current_offset)
                        string_data = string_heap[current_offset:null_pos]
                        if string_data:
                            self.strings.append(string_data.decode('utf-8', 'ignore'))
                        current_offset = null_pos + 1
                    except ValueError:
                        break # No more strings

            # 3. "Cheat" by grabbing a known save counter from Table 0x1.
            # We know from diffs that a reliable counter exists at offset 0x64
            # within this table's data.
            if 0x1 in self.tables:
                info = self.tables[0x1]
                f.seek(info['offset'])
                table_1_data = f.read(info['size'])
                if len(table_1_data) >= 0x64 + 4:
                    self.save_counter = struct.unpack_from('<I', table_1_data, 0x64)[0]

def print_semantic_diff(old_file, new_file):
    """
    Compares two ParsedOaFile objects and prints a human-readable,
    semantic diff report.
    """
    print("\n" + "="*80)
    print(f"--- Diffing '{old_file.filepath}' (OLD) vs. '{new_file.filepath}' (NEW) ---")
    print("="*80)

    # 1. Compare Metadata
    print("\n[Metadata Changes]")
    if old_file.save_counter != new_file.save_counter:
        print(f"  - Save Counter incremented: {old_file.save_counter} -> {new_file.save_counter}")
    else:
        print("  - Save Counter is identical.")

    # 2. Compare the file "schema" (which tables are present)
    old_tables = set(old_file.tables.keys())
    new_tables = set(new_file.tables.keys())

    added = new_tables - old_tables
    removed = old_tables - new_tables

    if added or removed:
        print("\n[Schema (Table List) Changes]")
        if added:
            print(f"  - Tables ADDED: {', '.join(hex(t) for t in sorted(list(added)))}")
        if removed:
            print(f"  - Tables REMOVED: {', '.join(hex(t) for t in sorted(list(removed)))}")

    # 3. Compare the most important part: the string timeline
    print("\n[String Timeline Changes]")

    diff = list(difflib.unified_diff(
        old_file.strings,
        new_file.strings,
        fromfile=old_file.filepath,
        tofile=new_file.filepath,
        lineterm=''
    ))

    if not diff:
        print("  - No changes to the string timeline.")
        return

    # Print only the lines with actual changes for clarity
    change_found = False
    for line in diff:
        if line.startswith(('+', '-')) and not line.startswith(('+++', '---')):
            print(f"  {line}")
            change_found = True

    if not change_found:
         print("  - No changes to the string timeline.")


if __name__ == '__main__':
    # Find all .oa files in the current directory
    oa_files = sorted(glob.glob('*.oa'))

    if len(oa_files) < 2:
        print("Error: Found fewer than two .oa files in this directory. Nothing to compare.")
        sys.exit(1)

    print(f"Found {len(oa_files)} .oa files to compare chronologically.")

    # Parse all files first
    parsed_files = [ParsedOaFile(f) for f in oa_files]

    # Compare each file to the next one in the sequence
    for i in range(len(parsed_files) - 1):
        print_semantic_diff(parsed_files[i], parsed_files[i+1])

    print("\n" + "="*80)
    print("--- End of Report ---")
    print("="*80)

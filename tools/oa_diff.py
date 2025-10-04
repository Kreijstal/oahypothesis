import struct
import sys
import difflib

# Helper function to format data into a hex view similar to `xxd`
def hex_dump(data, prefix=''):
    """Creates a formatted hex dump of a byte string."""
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
        lines.append(f"{prefix}{i:08x}: {hex_part:<48} |{ascii_part}|")
    return lines

class OaFile:
    """A simple container to parse and hold the table structure of an .oa file."""
    def __init__(self, filepath):
        self.filepath = filepath
        self.tables = {}
        try:
            with open(filepath, 'rb') as f:
                # Read the 24-byte preface
                header = f.read(24)
                _, _, _, _, _, used = struct.unpack('<IHHQII', header)

                # Read the table directory (IDs, Offsets, Sizes)
                ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))

                # Store table info in a dictionary keyed by ID for easy lookup
                for i in range(used):
                    # Skip tables with invalid offsets
                    if offsets[i] != 0xffffffffffffffff:
                        self.tables[ids[i]] = {'offset': offsets[i], 'size': sizes[i], 'data': None}

                # Read the raw data for each table
                for table_id, info in self.tables.items():
                    f.seek(info['offset'])
                    info['data'] = f.read(info['size'])

        except Exception as e:
            print(f"Error parsing {filepath}: {e}", file=sys.stderr)
            sys.exit(1)

def diff_oa_tables(file_old_path, file_new_path):
    """Compares and diffs the tables of two .oa files."""
    print(f"--- Comparing {file_old_path} (OLD) with {file_new_path} (NEW) ---\n")
    oa_old = OaFile(file_old_path)
    oa_new = OaFile(file_new_path)

    # Get a sorted, unique list of all table IDs present in either file
    all_ids = sorted(list(set(oa_old.tables.keys()) | set(oa_new.tables.keys())))

    for table_id in all_ids:
        table_old = oa_old.tables.get(table_id)
        table_new = oa_new.tables.get(table_id)

        if table_old == table_new:
            continue # Skip identical tables (both metadata and data)

        print(f"[*] Found differences in Table ID 0x{table_id:x}")
        print("="*60)

        # Print metadata comparison
        old_offset = f"0x{table_old['offset']:x}" if table_old else "N/A"
        old_size = table_old['size'] if table_old else "N/A"
        new_offset = f"0x{table_new['offset']:x}" if table_new else "N/A"
        new_size = table_new['size'] if table_new else "N/A"

        print(f"  Metadata OLD: Offset={old_offset}, Size={old_size}")
        print(f"  Metadata NEW: Offset={new_offset}, Size={new_size}\n")

        # Get data for diffing
        data_old = table_old.get('data', b'') if table_old else b''
        data_new = table_new.get('data', b'') if table_new else b''

        if data_old == data_new:
            print("  NOTE: Table data is identical, only offset/size metadata changed.\n")
            continue

        # Generate and print the side-by-side hex diff
        dump_old = hex_dump(data_old)
        dump_new = hex_dump(data_new)

        diff = difflib.unified_diff(dump_old, dump_new, fromfile='OLD', tofile='NEW', lineterm='')
        print("  --- Hex Data Diff ---")
        for line in diff:
            # Skip the '---' and '+++' header lines from difflib for cleaner output
            if line.startswith('---') or line.startswith('+++') or line.startswith('@@'):
                continue
            print(f"  {line}")
        print("\n")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: python3 {sys.argv[0]} <old_oa_file> <new_oa_file>")
        sys.exit(1)

    diff_oa_tables(sys.argv[1], sys.argv[2])

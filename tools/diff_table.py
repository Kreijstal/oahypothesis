import sys
import struct
import os
import difflib

# --- Helper function for clean hex dumps ---
def get_hex_dump_lines(data):
    """Creates a complete, formatted hex dump of a byte string as a list of lines."""
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
        lines.append(f"{i:08x}: {hex_part:<48} |{ascii_part}|")
    return lines

# --- Helper function for uint32_t array view ---
def get_int32_view_lines(data):
    """
    Parses a byte array as a flat list of 32-bit unsigned little-endian integers
    and returns the view as a list of formatted strings.
    """
    lines = []
    # Ensure data is padded to be a multiple of 4 bytes for a clean array view
    padding = len(data) % 4
    if padding != 0:
        data += b'\x00' * (4 - padding)

    num_integers = len(data) // 4
    for i in range(num_integers):
        offset = i * 4
        chunk = data[offset:offset+4]
        value = struct.unpack('<I', chunk)[0]
        hex_bytes_str = chunk.hex(' ')
        lines.append(f"Index {i:04d} | Offset 0x{offset:04x}:  {hex_bytes_str:<12} ->  Value: {value} (0x{value:x})")
    return lines

class OaTableExtractor:
    """A helper class to parse an OA file and extract a single table's data."""
    def __init__(self, filepath):
        self.filepath = filepath

    def get_table_data(self, table_id_hex):
        """Finds and returns the raw byte data for a given table ID."""
        table_id = int(table_id_hex, 16)
        try:
            with open(self.filepath, 'rb') as f:
                header = f.read(24)
                _, _, _, _, _, used = struct.unpack('<IHHQII', header)

                ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))

                for i in range(used):
                    if ids[i] == table_id:
                        if offsets[i] == 0xffffffffffffffff:
                            return None
                        f.seek(offsets[i])
                        return f.read(sizes[i])
        except FileNotFoundError:
            return None # Gracefully handle missing files
        except Exception as e:
            print(f"An error occurred while parsing {self.filepath}: {e}", file=sys.stderr)
            return None
        return None

def diff_specific_table(table_id_hex, file_old, file_new):
    """
    Extracts the same table from two files and prints both a focused hex diff
    and a uint32_t array diff.
    """
    print("#"*80)
    print(f"### Performing Dual-View Biopsy on Table {table_id_hex} ###")
    print(f"### Comparing '{os.path.basename(file_old)}' vs. '{os.path.basename(file_new)}' ###")
    print("#"*80 + "\n")

    try:
        extractor_old = OaTableExtractor(file_old)
        extractor_new = OaTableExtractor(file_new)

        data_old = extractor_old.get_table_data(table_id_hex)
        data_new = extractor_new.get_table_data(table_id_hex)

        if data_old is None:
            print(f"Table {table_id_hex} not found or is inactive in '{file_old}'.")
            return
        if data_new is None:
            print(f"Table {table_id_hex} not found or is inactive in '{file_new}'.")
            return

        if data_old == data_new:
            print("No byte-level differences found in this table.")
            return

        # --- 1. Hex Dump Diff ---
        print("-" * 32 + " Hex Dump Diff " + "-" * 31)
        hex_lines_old = get_hex_dump_lines(data_old)
        hex_lines_new = get_hex_dump_lines(data_new)
        hex_diff = list(difflib.unified_diff(hex_lines_old, hex_lines_new, n=1, lineterm=''))
        for line in hex_diff[3:]: # Skip header lines
            print(line)
        print("-" * 80 + "\n")

        # --- 2. uint32_t Array Diff ---
        print("-" * 29 + " uint32_t Array Diff " + "-" * 29)
        int_lines_old = get_int32_view_lines(data_old)
        int_lines_new = get_int32_view_lines(data_new)
        int_diff = list(difflib.unified_diff(int_lines_old, int_lines_new, n=1, lineterm=''))
        for line in int_diff[3:]: # Skip header lines
            print(line)
        print("-" * 80)


    except FileNotFoundError as e:
        print(f"ERROR: File not found - {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def dump_specific_table(filepath, table_id_hex):
    """Extracts and prints the full hex content of a single table."""
    print("\n" + "#"*80)
    print(f"### Full Hex Dump for Table {table_id_hex} in file '{os.path.basename(filepath)}' ###")
    print("#"*80 + "\n")

    try:
        extractor = OaTableExtractor(filepath)
        data = extractor.get_table_data(table_id_hex)

        if data is None:
            print(f"Table {table_id_hex} not found or is inactive in '{filepath}'.")
            return

        print(f"Table Size: {len(data)} bytes")
        print("-" * 80)
        # Re-create the full hex dump string for printing
        print("\n".join(get_hex_dump_lines(data)))
        print("-" * 80)

    except FileNotFoundError as e:
        print(f"ERROR: File not found - {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == '__main__':
    # --- Argument Parsing ---
    args = sys.argv[1:]
    show_full_dump = False

    if '--full' in args:
        show_full_dump = True
        args.remove('--full')

    if len(args) < 2 or len(args) > 3:
        print("Usage:")
        print("  For dumping a full table from a single file:")
        print("    python3 table_tool.py <table_id_hex> <file.oa> --full")
        print("\n  For diffing a table between two files (shows both hex and uint32 diffs):")
        print("    python3 table_tool.py <table_id_hex> <old_file.oa> <new_file.oa>")
        print("\n  For diffing AND dumping the new file's table:")
        print("    python3 table_tool.py <table_id_hex> <old_file.oa> <new_file.oa> --full")
        sys.exit(1)

    table_id = args[0]

    # --- Mode Dispatch ---
    # Single file mode (must have --full)
    if len(args) == 2:
        if not show_full_dump:
            print("Error: For a single file, you must use the --full flag to dump its content.")
            sys.exit(1)
        dump_specific_table(args[1], table_id)

    # Two file mode (diff, with optional full dump)
    elif len(args) == 3:
        file_old = args[1]
        file_new = args[2]
        diff_specific_table(table_id, file_old, file_new)
        if show_full_dump:
            dump_specific_table(file_new, table_id)

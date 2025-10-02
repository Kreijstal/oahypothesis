# parser.py (Enhanced with String Resolution)
import sys
import struct

# Import the specialized parsers
from table_c_parser import HypothesisParser
from table_133_parser import Table133Parser
from table_a_parser import TableAParser
from table_b_parser import TableBParser
from table_1d_parser import Table1dParser
from table_1_parser import Table1Parser
from table_107_parser import Table107Parser

# Import rendering utilities
from oaparser import render_report, render_regions_to_string

# --- Generic Dump Utilities ---

def generate_hex_dump(data: bytes, table_id: int):
    """Creates a complete, formatted hex dump for a given table's data."""
    header = f"--- Hex Dump for Table 0x{table_id:x} (Size: {len(data)} bytes) ---"
    if not any(data):
        return f"{header}\n  - (Table is entirely zero-filled)"
    lines = [header]
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
        lines.append(f"  {i:08x}: {hex_part:<48} |{ascii_part}|")
    return "\n".join(lines)

def generate_int_array_dump(data: bytes, table_id: int):
    """Treats the table's data as a flat int32 array and produces a summarized dump."""
    header = f"--- int32[] Dump for Table 0x{table_id:x} (Size: {len(data)} bytes) ---"
    lines = [header]
    padding = len(data) % 4
    if padding != 0:
        data += b'\x00' * (4 - padding)
    if not data:
        lines.append("  - (Table is empty)")
        return "\n".join(lines)
    int_array = [struct.unpack_from('<I', data, i)[0] for i in range(0, len(data), 4)]
    last_num, repeat_count, start_index = None, 0, 0
    for i, num in enumerate(int_array):
        if num == last_num:
            repeat_count += 1
        else:
            if last_num is not None:
                lines.append(f"  - Index[{start_index:03d}]: {last_num} (0x{last_num:x})")
                if repeat_count > 1: lines.append(f"      (Repeats {repeat_count} times)")
            last_num, repeat_count, start_index = num, 1, i
    if last_num is not None:
        lines.append(f"  - Index[{start_index:03d}]: {last_num} (0x{last_num:x})")
        if repeat_count > 1: lines.append(f"      (Repeats {repeat_count} times)")
    return "\n".join(lines)

# --- Main Execution ---

if __name__ == '__main__':
    args = sys.argv[1:]

    # --- Argument Parsing ---
    dump_hex = '--hexdump' in args
    if dump_hex: args.remove('--hexdump')

    dump_int = '--intarray' in args
    if dump_int: args.remove('--intarray')

    if len(args) != 1:
        print("Usage: python3 parser.py [--hexdump | --intarray] <oa_file>")
        print("\n  Decodes Tables 0xa, 0xb, 0x1d, 0xc, 0x107, and 0x133 by default.")
        print("  Table 0xc now resolves string references from Table 0xa.")
        print("  Table 0x107 now resolves name pointers using the formula: index = (value - 1) // 2 + 46")
        print("  Use flags to dump all OTHER tables in a raw format.")
        sys.exit(1)

    filepath = args[0]
    print(f"--- Running Enhanced Parser on: {filepath} ---")

    try:
        with open(filepath, 'rb') as f:
            # Read header and table directory
            header = f.read(24)
            _, _, _, _, _, used = struct.unpack('<IHHQII', header)
            ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))

            # FIRST PASS: Extract string table and parse it
            string_table_data = None
            string_list = []
            for i in range(used):
                if ids[i] == 0x0a:
                    f.seek(offsets[i])
                    string_table_data = f.read(sizes[i])
                    # Parse string table into list of strings
                    pos = 0
                    while pos < len(string_table_data):
                        end = string_table_data.find(b'\x00', pos)
                        if end == -1:
                            break
                        string_list.append(string_table_data[pos:end].decode('utf-8', errors='replace'))
                        pos = end + 1
                    break

            # SECOND PASS: Parse all tables
            for i in range(used):
                table_id = ids[i]
                offset = offsets[i]
                size = sizes[i]

                if offset == 0xffffffffffffffff or size == 0:
                    continue

                # --- Specialized Parsers ---
                if table_id == 0x01:
                    print("\n--- Table 0x1 (Global Metadata) ---")
                    f.seek(offset)
                    parser = Table1Parser(f.read(size))
                    regions = parser.parse()
                    render_report(regions, f"Global Metadata: {size} bytes")

                elif table_id == 0x0a:
                    print("\n--- Table 0xa (String Table) ---")
                    f.seek(offset)
                    parser = TableAParser(f.read(size))
                    regions = parser.parse()
                    render_report(regions, f"String Table: {size} bytes")

                elif table_id == 0x0b:
                    print("\n--- Table 0xb (Property List) ---")
                    f.seek(offset)
                    parser = TableBParser(f.read(size))
                    regions = parser.parse()
                    render_report(regions, f"Property List: {size} bytes")

                elif table_id == 0x1d:
                    print("\n--- Table 0x1d (Table Directory) ---")
                    f.seek(offset)
                    parser = Table1dParser(f.read(size))
                    regions = parser.parse()
                    render_report(regions, f"Table Directory: {size} bytes")

                elif table_id == 0x0c:
                    print("\n--- Table 0xc (Netlist Data) ---")
                    f.seek(offset)
                    # Pass string table data to enable string resolution
                    parser = HypothesisParser(f.read(size), string_table_data)
                    regions = parser.parse()
                    render_report(regions, f"Netlist Data: {size} bytes")

                elif table_id == 0x107:
                    print("\n--- Table 0x107 (Object Edit Metadata) ---")
                    f.seek(offset)
                    # Pass string list to enable name pointer resolution
                    parser = Table107Parser(f.read(size), string_list)
                    regions = parser.parse()
                    render_report(regions, f"Object Edit Metadata: {size} bytes")

                elif table_id == 0x133:
                    print("\n--- Table 0x133 ---")
                    f.seek(offset)
                    parser = Table133Parser(f.read(size))
                    regions = parser.parse()
                    render_report(regions, f"Table 0x133: {size} bytes")

                # --- Generic Dumpers (if flags are used) ---
                elif dump_hex:
                    f.seek(offset)
                    print("\n" + generate_hex_dump(f.read(size), table_id))

                elif dump_int:
                    f.seek(offset)
                    print("\n" + generate_int_array_dump(f.read(size), table_id))

    except FileNotFoundError:
        print(f"ERROR: File not found at '{filepath}'")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()

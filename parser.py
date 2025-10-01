# parser.py (Focused Tool Version)
import sys
import struct
import types

# Import the specialized, hypothetical parsers we trust
from table_c_parser import HypothesisParser
from table_133_parser import Table133Parser
from table_a_parser import TableAParser
from table_b_parser import TableBParser
from table_1d_parser import Table1dParser

# --- Generic Dump Utilities ---

def generate_hex_dump(data: bytes, table_id: int):
    """
    Creates a complete, formatted hex dump for a given table's data.
    If the data is entirely zero-filled, it prints a summary instead.
    """
    header = f"--- Hex Dump for Table 0x{table_id:x} (Size: {len(data)} bytes) ---"

    # Check if the table is zero-filled by seeing if any byte is non-zero
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
    """
    Treats the table's data as a flat int32 array and produces a summarized dump.
    """
    header = f"--- int32[] Dump for Table 0x{table_id:x} (Size: {len(data)} bytes) ---"
    lines = [header]

    # Pad data with nulls if it's not a multiple of 4 bytes
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
        print("\n  Decodes Tables 0xa, 0xb, 0x1d, 0xc, and 0x133 by default.")
        print("  All parsers show complete binary data (no hidden/skipped data).")
        print("  Use flags to dump all OTHER tables in a raw format.")
        sys.exit(1)

    filepath = args[0]
    print(f"--- Running Focused Parser on: {filepath} ---")

    try:
        with open(filepath, 'rb') as f:
            # Read header and table directory
            header = f.read(24)
            _, _, _, _, _, used = struct.unpack('<IHHQII', header)
            ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))

            # --- Main Dispatch Loop ---
            for i in range(used):
                table_id = ids[i]
                offset = offsets[i]
                size = sizes[i]

                if offset == 0xffffffffffffffff or size == 0:
                    continue

                # --- Specialized Parsers ---
                if table_id == 0x0a:
                    print("\n--- Parsed Structure of Table 0xa (String Table) ---")
                    f.seek(offset)
                    parser = TableAParser(f.read(size))
                    print(parser.parse())
                
                elif table_id == 0x0b:
                    print("\n--- Parsed Structure of Table 0xb (Property List) ---")
                    f.seek(offset)
                    parser = TableBParser(f.read(size))
                    print(parser.parse())
                
                elif table_id == 0x1d:
                    print("\n--- Parsed Structure of Table 0x1d (Table Directory) ---")
                    f.seek(offset)
                    parser = Table1dParser(f.read(size))
                    print(parser.parse())
                
                elif table_id == 0x0c:
                    print("\n--- Parsed Structure of Table 0x0c ---")
                    f.seek(offset)
                    parser = HypothesisParser(f.read(size))
                    parser.parse()
                    for record in parser.records:
                        print(record)

                elif table_id == 0x133:
                    print("\n--- Parsed Structure of Table 0x133 ---")
                    f.seek(offset)
                    parser = Table133Parser(f.read(size))
                    print(parser.parse())

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

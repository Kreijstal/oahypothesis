import struct
import sys
import difflib

# Import the intelligent parsers for all tables
from table_c_parser import HypothesisParser
from table_a_parser import TableAParser
from table_b_parser import TableBParser
from table_1d_parser import Table1dParser
from table_133_parser import Table133Parser
from table_1_parser import Table1Parser

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

        except FileNotFoundError:
            print(f"Error: File not found at {filepath}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error parsing {filepath}: {e}", file=sys.stderr)
            sys.exit(1)

def diff_oa_tables(file_old_path, file_new_path):
    """
    Compares the tables of two .oa files. For Table 0xc, it performs a
    structured, semantic diff. For all other tables, it performs a
    standard hex-level diff.
    """
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

        data_old = table_old.get('data', b'') if table_old else b''
        data_new = table_new.get('data', b'') if table_new else b''

        if data_old == data_new:
            print("  NOTE: Table data is identical, only offset/size metadata changed.\n")
            continue

        # --- SPECIALIZED DIFF FOR TABLE 0x1 ---
        if table_id == 0x1:
            print("  --- Structured Diff for Table 0x1 (Global Metadata) ---")
            parser_old = Table1Parser(data_old)
            parser_new = Table1Parser(data_new)
            lines_old = parser_old.parse().split('\n')
            lines_new = parser_new.parse().split('\n')

            diff = difflib.unified_diff(lines_old, lines_new, fromfile='OLD', tofile='NEW', lineterm='')
            
            diff_lines = list(diff)[2:] # Skip the ---/+++ file headers
            if not diff_lines:
                 print("  NOTE: Parsed structure is identical.")
            else:
                for line in diff_lines:
                    print(f"  {line}")
            print("\n")
            continue

        # --- SPECIALIZED DIFF FOR TABLE 0xa ---
        if table_id == 0xa:
            print("  --- Structured Diff for Table 0xa (String Table) ---")
            parser_old = TableAParser(data_old)
            parser_new = TableAParser(data_new)
            lines_old = parser_old.parse().split('\n')
            lines_new = parser_new.parse().split('\n')

            diff = difflib.unified_diff(lines_old, lines_new, fromfile='OLD', tofile='NEW', lineterm='')
            
            diff_lines = list(diff)[2:]
            if not diff_lines:
                 print("  NOTE: Parsed structure is identical.")
            else:
                for line in diff_lines:
                    print(f"  {line}")
            print("\n")
            continue

        # --- SPECIALIZED DIFF FOR TABLE 0xb ---
        if table_id == 0xb:
            print("  --- Structured Diff for Table 0xb (Property List) ---")
            parser_old = TableBParser(data_old)
            parser_new = TableBParser(data_new)
            lines_old = parser_old.parse().split('\n')
            lines_new = parser_new.parse().split('\n')

            diff = difflib.unified_diff(lines_old, lines_new, fromfile='OLD', tofile='NEW', lineterm='')
            
            diff_lines = list(diff)[2:]
            if not diff_lines:
                 print("  NOTE: Parsed structure is identical.")
            else:
                for line in diff_lines:
                    print(f"  {line}")
            print("\n")
            continue

        # --- SPECIALIZED DIFF FOR TABLE 0x1d ---
        if table_id == 0x1d:
            print("  --- Structured Diff for Table 0x1d (Table Directory) ---")
            parser_old = Table1dParser(data_old)
            parser_new = Table1dParser(data_new)
            lines_old = parser_old.parse().split('\n')
            lines_new = parser_new.parse().split('\n')

            diff = difflib.unified_diff(lines_old, lines_new, fromfile='OLD', tofile='NEW', lineterm='')
            
            diff_lines = list(diff)[2:]
            if not diff_lines:
                 print("  NOTE: Parsed structure is identical.")
            else:
                for line in diff_lines:
                    print(f"  {line}")
            print("\n")
            continue

        # --- SPECIALIZED DIFF FOR TABLE 0x133 ---
        if table_id == 0x133:
            print("  --- Structured Diff for Table 0x133 ---")
            parser_old = Table133Parser(data_old)
            parser_new = Table133Parser(data_new)
            lines_old = parser_old.parse().split('\n')
            lines_new = parser_new.parse().split('\n')

            diff = difflib.unified_diff(lines_old, lines_new, fromfile='OLD', tofile='NEW', lineterm='')
            
            diff_lines = list(diff)[2:]
            if not diff_lines:
                 print("  NOTE: Parsed structure is identical.")
            else:
                for line in diff_lines:
                    print(f"  {line}")
            print("\n")
            continue

        # --- SPECIALIZED DIFF FOR TABLE 0xc ---
        if table_id == 0xc:
            print("  --- Structured Diff for Table 0xc (Netlist Data) ---")
            parser_old = HypothesisParser(data_old)
            parser_old.parse()
            lines_old = [str(r) for r in parser_old.records]

            parser_new = HypothesisParser(data_new)
            parser_new.parse()
            lines_new = [str(r) for r in parser_new.records]

            diff = difflib.unified_diff(lines_old, lines_new, fromfile='OLD', tofile='NEW', lineterm='')
            
            # Print the resulting structured diff
            diff_lines = list(diff)[2:] # Skip the ---/+++ file headers
            if not diff_lines:
                 print("  NOTE: Parsed structure is identical, but raw byte-level differences may exist.")
            else:
                for line in diff_lines:
                    # Add extra indentation to fit our report format
                    print(f"  {line}")
            print("\n")
            continue # Skip the generic hex diff for this table

        # --- GENERIC HEX DIFF FOR ALL OTHER TABLES ---
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
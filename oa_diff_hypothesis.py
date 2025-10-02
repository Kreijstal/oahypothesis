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
from table_107_parser import Table107Parser
from oaparser import render_regions_to_string

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
            regions_old = parser_old.parse()
            regions_new = parser_new.parse()
            lines_old = render_regions_to_string(regions_old, "").split('\n')
            lines_new = render_regions_to_string(regions_new, "").split('\n')

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
            regions_old = parser_old.parse()
            regions_new = parser_new.parse()
            lines_old = render_regions_to_string(regions_old, "").split('\n')
            lines_new = render_regions_to_string(regions_new, "").split('\n')

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
            regions_old = parser_old.parse()
            regions_new = parser_new.parse()
            lines_old = render_regions_to_string(regions_old, "").split('\n')
            lines_new = render_regions_to_string(regions_new, "").split('\n')

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
            regions_old = parser_old.parse()
            regions_new = parser_new.parse()
            lines_old = render_regions_to_string(regions_old, "").split('\n')
            lines_new = render_regions_to_string(regions_new, "").split('\n')

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
            regions_old = parser_old.parse()
            regions_new = parser_new.parse()
            lines_old = render_regions_to_string(regions_old, "").split('\n')
            lines_new = render_regions_to_string(regions_new, "").split('\n')

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
            
            # Get string table for string resolution
            string_table_old = oa_old.tables.get(0xa, {}).get('data')
            string_table_new = oa_new.tables.get(0xa, {}).get('data')
            
            parser_old = HypothesisParser(data_old, string_table_old)
            parser_old.parse()
            
            parser_new = HypothesisParser(data_new, string_table_new)
            parser_new.parse()
            
            # For diffing, we want to show only the actual changes in content,
            # not spurious differences caused by offset shifts.
            # Strategy: For each record, extract its "signature" (type + key fields)
            # and match records by signature, then show differences in matched records.
            
            def get_record_signature(record):
                """Get a signature that identifies the record type and key content"""
                record_type = type(record).__name__
                if hasattr(record, 'property_value_id'):
                    return (record_type, record.property_value_id)
                elif hasattr(record, 'timestamp_val'):
                    return (record_type, 'timestamp')
                elif hasattr(record, 'record_type'):
                    # NetUpdateRecord - use first few bytes of payload as signature
                    payload_sig = record.unparsed_data[:min(16, len(record.unparsed_data))]
                    return (record_type, payload_sig)
                elif hasattr(record, 'value'):
                    return (record_type, record.value)
                elif hasattr(record, 'data'):
                    # Generic record - use first few bytes as signature
                    data_sig = record.data[:min(16, len(record.data))]
                    return (record_type, data_sig)
                else:
                    return (record_type, str(record)[:50])
            
            # Parse to get regions
            from oaparser.binary_curator import ClaimedRegion
            regions_old = parser_old.parse()
            regions_new = parser_new.parse()
            
            # Extract records from regions
            records_old = []
            for region in regions_old:
                if isinstance(region, ClaimedRegion) and region.parsed_value:
                    records_old.append(region.parsed_value)
            
            records_new = []
            for region in regions_new:
                if isinstance(region, ClaimedRegion) and region.parsed_value:
                    records_new.append(region.parsed_value)
            
            # Build signature maps
            old_by_sig = {}
            for i, r in enumerate(records_old):
                sig = get_record_signature(r)
                if sig not in old_by_sig:
                    old_by_sig[sig] = []
                old_by_sig[sig].append((i, r))
            
            new_by_sig = {}
            for i, r in enumerate(records_new):
                sig = get_record_signature(r)
                if sig not in new_by_sig:
                    new_by_sig[sig] = []
                new_by_sig[sig].append((i, r))
            
            # Find matching and non-matching records
            changes = []
            
            # Check for removed records
            for sig, old_records in old_by_sig.items():
                if sig not in new_by_sig:
                    for idx, rec in old_records:
                        changes.append(('removed', idx, rec, None))
            
            # Check for added records
            for sig, new_records in new_by_sig.items():
                if sig not in old_by_sig:
                    for idx, rec in new_records:
                        changes.append(('added', None, None, rec))
            
            # Check for modified records (same signature but different content)
            for sig in set(old_by_sig.keys()) & set(new_by_sig.keys()):
                old_recs = old_by_sig[sig]
                new_recs = new_by_sig[sig]
                
                # Match records one-to-one
                for i in range(max(len(old_recs), len(new_recs))):
                    old_rec = old_recs[i] if i < len(old_recs) else None
                    new_rec = new_recs[i] if i < len(new_recs) else None
                    
                    if old_rec and new_rec:
                        old_str = str(old_rec[1])
                        new_str = str(new_rec[1])
                        # Normalize offsets for comparison
                        import re
                        old_str = re.sub(r' at 0x[0-9a-f]+', ' at [offset]', old_str)
                        old_str = re.sub(r'Offset 0x[0-9a-f]+:', 'Offset:', old_str)
                        new_str = re.sub(r' at 0x[0-9a-f]+', ' at [offset]', new_str)
                        new_str = re.sub(r'Offset 0x[0-9a-f]+:', 'Offset:', new_str)
                        
                        if old_str != new_str:
                            changes.append(('modified', old_rec[0], old_rec[1], new_rec[1]))
                    elif old_rec:
                        changes.append(('removed', old_rec[0], old_rec[1], None))
                    elif new_rec:
                        changes.append(('added', None, None, new_rec[1]))
            
            # Sort changes by old index (for removed/modified) or by type
            changes.sort(key=lambda x: (x[0], x[1] if x[1] is not None else 9999))
            
            if not changes:
                print("  NOTE: Parsed structure is identical.")
            else:
                for change_type, old_idx, old_rec, new_rec in changes:
                    if change_type == 'removed':
                        print(f"  [-] Record {old_idx}: {type(old_rec).__name__} removed")
                    elif change_type == 'added':
                        print(f"  [+] New record: {type(new_rec).__name__} added")
                    elif change_type == 'modified':
                        print(f"  [~] Record {old_idx}: {type(old_rec).__name__} modified")
                        # Show detailed diff for modified records
                        old_str = str(old_rec)
                        new_str = str(new_rec)
                        # Normalize offsets
                        import re
                        old_str = re.sub(r' at 0x[0-9a-f]+', ' at [offset]', old_str)
                        old_str = re.sub(r'Offset 0x[0-9a-f]+:', 'Offset:', old_str)
                        new_str = re.sub(r' at 0x[0-9a-f]+', ' at [offset]', new_str)
                        new_str = re.sub(r'Offset 0x[0-9a-f]+:', 'Offset:', new_str)
                        
                        old_lines = old_str.split('\n')
                        new_lines = new_str.split('\n')
                        diff = difflib.unified_diff(old_lines, new_lines, lineterm='')
                        diff_lines = list(diff)[2:]  # Skip headers
                        if diff_lines:
                            for line in diff_lines[:20]:  # Limit to first 20 lines
                                print(f"      {line}")
                            if len(diff_lines) > 20:
                                print(f"      ... ({len(diff_lines) - 20} more lines)")
            
            print("\n")
            continue # Skip the generic hex diff for this table

        # --- SPECIALIZED DIFF FOR TABLE 0x107 ---
        if table_id == 0x107:
            print("  --- Structured Diff for Table 0x107 (Object Edit Metadata) ---")
            
            # Get string table for string resolution
            string_table_old = oa_old.tables.get(0xa, {}).get('data')
            string_table_new = oa_new.tables.get(0xa, {}).get('data')
            
            # Parse string tables into lists
            def parse_strings(data):
                if not data:
                    return []
                strings = []
                pos = 0
                while pos < len(data):
                    end = data.find(b'\x00', pos)
                    if end == -1:
                        break
                    strings.append(data[pos:end].decode('utf-8', errors='replace'))
                    pos = end + 1
                return strings
            
            strings_old = parse_strings(string_table_old)
            strings_new = parse_strings(string_table_new)
            
            parser_old = Table107Parser(data_old, strings_old)
            parser_new = Table107Parser(data_new, strings_new)
            
            from oaparser.binary_curator import ClaimedRegion
            regions_old = parser_old.parse()
            regions_new = parser_new.parse()
            
            # Extract claimed regions and compare
            claimed_old = [(r.name, r.parsed_value) for r in regions_old if isinstance(r, ClaimedRegion)]
            claimed_new = [(r.name, r.parsed_value) for r in regions_new if isinstance(r, ClaimedRegion)]
            
            changes_found = False
            for (name_old, val_old), (name_new, val_new) in zip(claimed_old, claimed_new):
                if name_old != name_new:
                    print(f"  [!] Region name mismatch: '{name_old}' vs '{name_new}'")
                    changes_found = True
                elif str(val_old) != str(val_new):
                    print(f"  [~] {name_old}:")
                    print(f"      OLD: {val_old}")
                    print(f"      NEW: {val_new}")
                    changes_found = True
            
            if not changes_found:
                print("  NOTE: No changes in claimed regions.")
            
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
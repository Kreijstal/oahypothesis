import struct
import sys

def parse_string_table_deep_dive(filepath):
    """
    Parses a Cadence .oa file, focusing on the internal structure of the
    string table (ID 0xa) to find the Logical ID -> Offset lookup map.
    """
    print(f"--- Deep Dive into String Table (0xa) for: {filepath} ---\n")
    try:
        with open(filepath, 'rb') as f:
            # 1. Find the offset and size of Table 0xa from the main directory
            header = f.read(24)
            _, _, _, _, _, used = struct.unpack('<IHHQII', header)

            if used == 0:
                print("No tables found.")
                return

            ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))

            string_table_info = None
            for i in range(used):
                if ids[i] == 0xa:
                    string_table_info = {'offset': offsets[i], 'size': sizes[i]}
                    break

            if not string_table_info:
                print("ERROR: String Table (ID 0xa) not found.")
                return

            # 2. Seek to the table and parse its internal structure
            f.seek(string_table_info['offset'])

            # 2a. Parse the 16-byte table header
            # We theorize this is: <I (type), I (num_entries), I (padding), I (padding)
            table_header = struct.unpack('<IIII', f.read(16))
            num_entries = table_header[1]
            print(f"Table Header: Found {num_entries} entries in the lookup map.")

            # 2b. Parse the Lookup Map itself
            # We theorize each entry is 8 bytes: <I (logical_id), I (physical_offset)
            lookup_map = []
            for _ in range(num_entries):
                entry = struct.unpack('<II', f.read(8))
                lookup_map.append({'id': entry[0], 'offset': entry[1]})
            
            # The current file position is the start of the string data heap
            heap_start_pos = f.tell()
            
            # 3. Print the results, connecting all three pieces of information
            print("\n" + "="*80)
            print(f"{'Index':<8} {'Logical ID':<15} {'Physical Offset':<20} {'String'}")
            print("="*80)

            for i, entry in enumerate(lookup_map):
                logical_id = entry['id']
                physical_offset = entry['offset']

                # Seek to the string's physical location and read it
                f.seek(heap_start_pos + physical_offset)
                
                string_bytes = []
                while True:
                    byte = f.read(1)
                    if not byte or byte == b'\0':
                        break
                    string_bytes.append(byte)
                
                decoded_string = b''.join(string_bytes).decode('utf-8', 'replace')

                # Highlight the key entries we've seen in our analysis
                highlight = ""
                if logical_id in [0x0736, 0x0760, 0x078c, 0x07ec]:
                    highlight = "  <--- FOUND IT!"

                print(f"{i:<8} 0x{logical_id:<12x} 0x{physical_offset:<17x} '{decoded_string}'{highlight}")

    except FileNotFoundError:
        print(f"ERROR: File not found at '{filepath}'")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f"Usage: python3 {sys.argv[0]} <oa_file>")
        sys.exit(1)

    parse_string_table_deep_dive(sys.argv[1])
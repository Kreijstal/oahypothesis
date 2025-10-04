import struct
import sys

def dump_string_table(filepath):
    """
    Parses a Cadence .oa file and dumps the contents of the string table (ID 0xa).
    """
    print(f"--- Dumping String Table (0xa) for: {filepath} ---\n")
    try:
        with open(filepath, 'rb') as f:
            # 1. Read the 24-byte preface to find the table directory size
            header = f.read(24)
            _, _, _, _, _, used = struct.unpack('<IHHQII', header)

            if used == 0:
                print("No tables found in the directory.")
                return

            # 2. Read the entire table directory to find Table 0xa
            ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
            sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))

            string_table_info = None
            for i in range(used):
                if ids[i] == 0xa:
                    string_table_info = {'offset': offsets[i], 'size': sizes[i]}
                    break

            if not string_table_info:
                print("ERROR: String Table (ID 0xa) not found in the file.")
                return

            # 3. Seek to the string table and read its contents
            f.seek(string_table_info['offset'])
            
            # The string table has a 20-byte header of its own we need to skip
            # (4x 4-byte integers for table_info + 4 bytes of padding)
            table_header = f.read(20)
            
            string_buffer = f.read(string_table_info['size'] - 20)

            # 4. Iterate through the buffer and print null-terminated strings
            current_offset = 0
            string_index = 0
            print(f"{'Index':<10} {'Offset (Hex)':<15} {'String'}")
            print("="*60)

            while current_offset < len(string_buffer):
                # Find the next null terminator
                try:
                    null_pos = string_buffer.index(b'\0', current_offset)
                except ValueError:
                    # No more null terminators
                    break

                # Decode the string
                string_data = string_buffer[current_offset:null_pos]
                
                # Some offsets might be empty strings due to alignment/padding
                if not string_data:
                    current_offset = null_pos + 1
                    continue
                
                try:
                    decoded_string = string_data.decode('utf-8')
                    print(f"{string_index:<10} 0x{current_offset:<12x} '{decoded_string}'")
                except UnicodeDecodeError:
                    print(f"{string_index:<10} 0x{current_offset:<12x} [DECODE ERROR: {string_data!r}]")

                string_index += 1
                current_offset = null_pos + 1


    except FileNotFoundError:
        print(f"ERROR: File not found at '{filepath}'")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f"Usage: python3 {sys.argv[0]} <oa_file>")
        sys.exit(1)

    dump_string_table(sys.argv[1])
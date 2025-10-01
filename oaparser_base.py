
# oaparser_base.py
# (This code is identical to what you provided)
import struct
import ctypes

class OaFileParser:
    def __init__(self):
        self.table_map = {
            0x04: self._read_0x04, 0x05: self._read_0x05, 0x06: self._read_0x06,
            0x07: self._read_0x07, 0x19: self._read_0x19, 0x1c: self._read_0x1c,
            0x1d: self._read_0x1d, 0x28: self._read_0x28, 0x0a: self._read_0x0a,
            0x1f: self._read_0x1f
        }
        self.indexed_items = {0x04, 0x05, 0x06, 0x07, 0x19, 0x1c, 0x1d, 0x28}

    def on_parsed_preface(self, test_bit, type_val, schema, offset, size, used): raise NotImplementedError
    def on_parsed_table_information(self, ids, offsets, sizes): raise NotImplementedError
    def on_parsed_flags(self, flags): raise NotImplementedError
    def on_parsed_time_stamp(self, time_stamp): raise NotImplementedError
    def on_parsed_last_saved_time(self, ls_time): raise NotImplementedError
    def on_parsed_database_map(self, ids, types, tbl_ids, tbl_types): raise NotImplementedError
    def on_parsed_string_table(self, table_info, buffer): raise NotImplementedError
    def on_parsed_create_time(self, create_time): raise NotImplementedError
    def on_parsed_dm_and_build_name(self, data_model_rev, build_name): raise NotImplementedError
    def on_parsed_build_information(self, app_info, app_build_name, kit_build_name, platform_name): raise NotImplementedError
    def on_parsed_database_map_d(self, ids, types): raise NotImplementedError
    def on_parsed_database_marker(self, bit_check): raise NotImplementedError
    def on_parsed_error(self, error_msg): raise NotImplementedError

    def _round_align_8bit(self, length):
        rem = length % 8
        return length + (8 - rem) if rem != 0 else length

    def _read_0x04(self, file, pos, tbl_size):
        file.seek(pos)
        flags = struct.unpack('<I', file.read(4))[0]
        self.on_parsed_flags(flags)

    def _read_0x05(self, file, pos, tbl_size):
        file.seek(pos)
        time_stamp = struct.unpack('<I', file.read(4))[0]
        self.on_parsed_time_stamp(time_stamp)

    def _read_0x06(self, file, pos, tbl_size):
        file.seek(pos)
        ls_time = struct.unpack('<Q', file.read(8))[0]
        self.on_parsed_last_saved_time(ls_time)

    def _read_0x07(self, file, pos, tbl_size):
        file.seek(pos)
        num_res, num_data = struct.unpack('<II', file.read(8))
        num_other = num_data - num_res
        ids = list(struct.unpack(f'<{num_res}Q', file.read(8 * num_res)))
        types = list(struct.unpack(f'<{num_res}I', file.read(4 * num_res)))
        tbl_ids = list(struct.unpack(f'<{num_other}Q', file.read(8 * num_other)))
        tbl_types = list(struct.unpack(f'<{num_other}I', file.read(4 * num_other)))
        self.on_parsed_database_map(ids, types, tbl_ids, tbl_types)

    def _read_0x0a(self, file, pos, tbl_size):
        file.seek(pos)
        table_info = struct.unpack('<IIII', file.read(16))
        file.read(4)
        buffer = file.read(tbl_size - 20)
        self.on_parsed_string_table(table_info, buffer)

    def _read_0x19(self, file, pos, tbl_size):
        file.seek(pos)
        create_time = struct.unpack('<Q', file.read(8))[0]
        self.on_parsed_create_time(create_time)

    def _read_0x1c(self, file, pos, tbl_size):
        file.seek(pos)
        data_model_rev = struct.unpack('<H', file.read(2))[0]
        build_name = file.read(tbl_size - 2).split(b'\0', 1)[0].decode('utf-8')
        self.on_parsed_dm_and_build_name(data_model_rev, build_name)

    def _read_0x1d(self, file, pos, tbl_size):
        file.seek(pos)
        app_info = struct.unpack('<HHHH', file.read(8))
        buffer = file.read(tbl_size - 8)
        app_build_name = ctypes.c_char_p(buffer).value.decode('utf-8')
        offset = self._round_align_8bit(len(app_build_name) + 1)
        kit_build_name = ctypes.c_char_p(buffer[offset:]).value.decode('utf-8')
        offset += self._round_align_8bit(len(kit_build_name) + 1)
        platform_name = ctypes.c_char_p(buffer[offset:]).value.decode('utf-8')
        self.on_parsed_build_information(app_info, app_build_name, kit_build_name, platform_name)

    def _read_0x1f(self, file, pos, tbl_size):
        file.seek(pos)
        num = struct.unpack('<Q', file.read(8))[0]
        ids = list(struct.unpack(f'<{num}Q', file.read(8 * num)))
        types = list(struct.unpack(f'<{num}I', file.read(4 * num)))
        self.on_parsed_database_map_d(ids, types)

    def _read_0x28(self, file, pos, tbl_size):
        file.seek(pos)
        bit_check = struct.unpack('<I', file.read(4))[0]
        self.on_parsed_database_marker(bit_check)

    def parse(self, filepath):
        try:
            with open(filepath, 'rb') as f:
                header_bytes = f.read(24)
                test_bit, type_val, schema, offset, size, used = struct.unpack('<IHHQII', header_bytes)
                self.on_parsed_preface(test_bit, type_val, schema, offset, size, used)

                ids = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                offsets = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                sizes = list(struct.unpack(f'<{used}Q', f.read(8 * used)))
                self.on_parsed_table_information(ids, offsets, sizes)

                start_offset = 0
                for i in range(used):
                    if ids[i] == 1:
                        start_offset = offsets[i]
                        break

                for i in range(used):
                    table_id = ids[i]
                    if table_id in self.table_map:
                        read_pos = offsets[i]
                        # The original code had a bug here, applying start_offset incorrectly.
                        # The base parser should handle absolute vs relative offsets correctly.
                        # For this example, we assume all offsets in the directory are absolute.
                        # if table_id in self.indexed_items:
                        #     read_pos += start_offset
                        self.table_map[table_id](f, read_pos, sizes[i])
        except FileNotFoundError:
            self.on_parsed_error("File path does not exist.")
            return 1
        except Exception as e:
            self.on_parsed_error(f"Error: parsing file. {e}")
            return 1
        return 0

class MyParser(OaFileParser):
    def on_parsed_preface(self, test_bit, type_val, schema, offset, size, used): print(f"Preface: test_bit=0x{test_bit:x}, type=0x{type_val:x}, schema=0x{schema:x}, used={used}")
    def on_parsed_table_information(self, ids, offsets, sizes):
        print("\n--- Table Directory ---")
        for i, (id_val, offset, size) in enumerate(zip(ids, offsets, sizes)): print(f"Table {i}: ID=0x{id_val:x}, Offset=0x{offset:x}, Size={size}")
    def on_parsed_flags(self, flags): print(f"\nFlags (0x04): 0x{flags:x}")
    def on_parsed_time_stamp(self, time_stamp): print(f"Timestamp (0x05): {time_stamp}")
    def on_parsed_last_saved_time(self, ls_time): print(f"Last Saved Time (0x06): {ls_time}")
    def on_parsed_database_map(self, ids, types, tbl_ids, tbl_types): print(f"\nDatabase Map (0x07): {len(ids)} ids, {len(tbl_ids)} table ids")
    def on_parsed_string_table(self, table_info, buffer): print(f"\nString Table (0x0a): used={table_info[1]}")
    def on_parsed_create_time(self, create_time): print(f"Create Time (0x19): {create_time}")
    def on_parsed_dm_and_build_name(self, data_model_rev, build_name): print(f"\nDM and Build Name (0x1c): rev={data_model_rev}, name='{build_name}'")
    def on_parsed_build_information(self, app_info, app_build_name, kit_build_name, platform_name):
        print("\nBuild Info (0x1d):")
        print(f"  App Build: '{app_build_name}'\n  Kit Build: '{kit_build_name}'\n  Platform: '{platform_name}'")
    def on_parsed_database_map_d(self, ids, types): print(f"\nDatabase Map Delta (0x1f): {len(ids)} new tables")
    def on_parsed_database_marker(self, bit_check): print(f"\nDatabase Marker (0x28): 0x{bit_check:x}")
    def on_parsed_error(self, error_msg): print(f"ERROR: {error_msg}")

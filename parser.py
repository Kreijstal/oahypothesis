# parser.py
import sys
import types
from oaparser_base import MyParser
from table_c_parser import HypothesisParser

def on_parsed_table_c(self, records):
    """
    This will be our new callback method. It prints the structured results
    from the HypothesisParser.
    """
    print("\n--- Hypothesis Parse of Table 0x0c ---")
    if not records:
        print("  (No records parsed or parser failed)")
        return
    for record in records:
        print(record)

def _read_0x0c(self, file, pos, tbl_size):
    """
    This is our new handler function for Table 0xc. It matches the signature
    expected by the OaFileParser's table_map.
    """
    file.seek(pos)
    table_c_data = file.read(tbl_size)

    c_parser = HypothesisParser(table_c_data)
    c_parser.parse()

    # Call the callback method we attached to the instance.
    self.on_parsed_table_c(c_parser.records)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f"Usage: python3 {sys.argv[0]} <oa_file>")
        sys.exit(1)

    # 1. Create an instance of the standard parser.
    #    It already knows how to parse and print all the original tables.
    parser = MyParser()

    # 2. Dynamically "monkey-patch" the new callback method onto the INSTANCE.
    #    This binds the function to the instance, giving it access to 'self'.
    parser.on_parsed_table_c = types.MethodType(on_parsed_table_c, parser)

    # 3. Register our new handler in the instance's table_map.
    #    This tells the main parse loop to call our function when it sees table 0xc.
    parser.table_map[0x0c] = types.MethodType(_read_0x0c, parser)

    # 4. Run the parser. It will now execute all original handlers PLUS our new one.
    parser.parse(sys.argv[1])

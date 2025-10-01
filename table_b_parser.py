# table_b_parser.py - Parser for property list table 0xb
import struct

class TableBParser:
    """
    Parser for table 0xb (Property List Table)
    
    Hypothesis based on analysis:
    - Header section with type and offsets
    - Array of 64-bit values (IDs or offsets)
    - Property data section
    - List of property IDs/references
    
    This table appears to store property assignments and their values.
    """
    
    def __init__(self, data):
        self.data = data
        
    def parse(self):
        """Parse the property list table with complete data dump"""
        if len(self.data) < 8:
            return f"Property List Table (0xb): Too small ({len(self.data)} bytes)"
        
        lines = [f"Property List Table (0xb): {len(self.data)} bytes"]
        lines.append("="*80)
        
        # Show complete hex dump first
        lines.append("\nComplete Binary Data:")
        lines.append("-"*80)
        for i in range(0, len(self.data), 16):
            chunk = self.data[i:i+16]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            lines.append(f"  {i:04x}: {hex_part:<48} |{ascii_part}|")
        
        # Parse header
        lines.append("\n" + "="*80)
        lines.append("Parsed Structure:")
        lines.append("-"*80)
        
        if len(self.data) >= 16:
            type_id = struct.unpack('<I', self.data[0:4])[0]
            pad1 = struct.unpack('<I', self.data[4:8])[0]
            offset1 = struct.unpack('<I', self.data[8:12])[0]
            pad2 = struct.unpack('<I', self.data[12:16])[0]
            
            lines.append(f"\nHeader (offset 0x0000-0x000f):")
            lines.append(f"  Type ID: {type_id} (0x{type_id:08x})")
            lines.append(f"  Padding: {pad1} (0x{pad1:08x})")
            lines.append(f"  Data section offset: {offset1} (0x{offset1:04x})")
            lines.append(f"  Padding: {pad2} (0x{pad2:08x})")
            
            # Parse array section (appears to be 64-bit values)
            if len(self.data) >= offset1:
                lines.append(f"\nArray Section (offset 0x0010-0x{offset1-1:04x}):")
                num_entries = (offset1 - 16) // 8
                lines.append(f"  Number of 64-bit entries: {num_entries}")
                
                for i in range(num_entries):
                    offset = 16 + i * 8
                    if offset + 8 <= len(self.data):
                        val = struct.unpack('<Q', self.data[offset:offset+8])[0]
                        lines.append(f"  [{i:2d}] 0x{offset:04x}: {val:20d} (0x{val:016x})")
                
                # Parse data section
                if offset1 < len(self.data):
                    lines.append(f"\nData Section (offset 0x{offset1:04x}-end):")
                    data_section = self.data[offset1:]
                    
                    # Look for patterns - appears to be counts followed by arrays
                    pos = 0
                    if len(data_section) >= 8:
                        count1 = struct.unpack('<I', data_section[0:4])[0]
                        count2 = struct.unpack('<I', data_section[4:8])[0]
                        lines.append(f"  Count1: {count1} (0x{count1:x})")
                        lines.append(f"  Count2: {count2} (0x{count2:x})")
                        
                        pos = 8
                        # Parse following data as array of values
                        lines.append(f"\n  Remaining data as bytes:")
                        idx = 0
                        while pos < len(data_section):
                            if pos + 1 <= len(data_section):
                                b = data_section[pos]
                                if b != 0 or idx < 20:  # Show non-zero or first 20 bytes
                                    lines.append(f"    [{idx:3d}] 0x{offset1+pos:04x}: 0x{b:02x} ({b})")
                                elif b == 0 and idx >= 20:
                                    # Count consecutive zeros
                                    zero_count = 0
                                    temp_pos = pos
                                    while temp_pos < len(data_section) and data_section[temp_pos] == 0:
                                        zero_count += 1
                                        temp_pos += 1
                                    if zero_count > 1:
                                        lines.append(f"    ... {zero_count} zero bytes ...")
                                        pos = temp_pos - 1
                                        idx = temp_pos - pos - 1 + idx
                                pos += 1
                                idx += 1
                        
                        # Also try parsing as 16-bit values at the end
                        lines.append(f"\n  Last section as 16-bit values:")
                        # The property IDs seem to be at the end
                        prop_start = len(data_section) - 32  # Last ~32 bytes
                        if prop_start > 0:
                            for i in range(prop_start, len(data_section), 2):
                                if i + 2 <= len(data_section):
                                    val = struct.unpack('<H', data_section[i:i+2])[0]
                                    if val != 0:
                                        lines.append(f"    0x{offset1+i:04x}: 0x{val:04x} ({val})")
        
        return "\n".join(lines)

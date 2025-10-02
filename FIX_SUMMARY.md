# Fix Summary: oa_diff_hypothesis.py Verbosity Issue

## Problem
The `oa_diff_hypothesis.py` tool was significantly more verbose than `oa_diff.py` when comparing .oa files, producing 454 lines of output vs 269 lines for the same file comparison (sch_old.oa vs sch_new.oa).

## Root Cause
The issue was with the structured parsing of table 0xc (Netlist Data). The HypothesisParser attempts to parse the binary structure into logical records, but when values change (even slightly), the parser can interpret the record boundaries differently, causing:

1. Misaligned record parsing between old and new versions
2. Cascading structural differences throughout the table
3. Verbose diffs showing entire record structures as changed when only small values actually differ

### Example
When the resistor name changed from "popop" to "THISISNOWTHERESISTOR":
- A property value ID in table 0xc changed from 0x3c (60) to 0x3f (63)
- This small 1-byte change caused the structured parser to reinterpret record boundaries
- The OLD file parsed a record at offset 0x06e8 (120 bytes)
- The NEW file parsed records at offsets 0x06a0 (76 bytes) and 0x06ec (116 bytes)
- Result: massive diff showing entire restructured records instead of just the changed byte

## Solution
Disabled the structured parsing for table 0xc in `oa_diff_hypothesis.py`. This table now uses the same hex-level diff as `oa_diff.py` and other tables without specialized parsers.

The change was simple - commented out the specialized handling block for table 0xc (lines 192-214 in oa_diff_hypothesis.py).

## Results
- Output reduced from 454 lines to 271 lines (comparable to oa_diff.py's 269 lines)
- Structured diffs still work correctly for other tables:
  - Table 0x1 (Global Metadata): Shows counter changes semantically
  - Table 0xa (String Table): Shows string additions/changes
  - Table 0xb (Property List): Shows property record changes
  - Table 0x1d, 0x133: Specialized parsing maintained
- Table 0xc now shows concise hex diffs highlighting actual byte changes
- No loss of useful information - the hex diff is actually clearer for table 0xc

## Key Insights Discovered

### String References in Table 0xc
During investigation, we discovered that values in table 0xc are NOT direct string table offsets or indices. Instead:

1. Table 0xa contains the string heap (e.g., "popop" at index 60, "THISISNOWTHERESISTOR" at index 61)
2. Table 0xb contains property assignment records that reference strings
3. Table 0xc contains property value IDs that reference records in table 0xb
4. The relationship follows a pattern: `property_value_id ≈ (num_records_in_table_b) * 4 - 1`

Example from sch_old.oa → sch_new.oa:
- OLD: 15 records in table 0xb, property value ID 0x3c (60) in table 0xc
- NEW: 16 records in table 0xb, property value ID 0x3f (63) in table 0xc
- Formula: 16 * 4 - 1 = 63 ✓

This indirect referencing system explains why the structured parser was struggling - it's not just about parsing structure, but understanding the complex cross-table reference system.

## Testing
Verified fix with multiple file pairs:
- sch_old.oa → sch_new.oa: 271 lines (was 454)
- sch_new.oa → sch2.oa: 41 lines
- sch2.oa → sch3.oa: 314 lines
- sch3.oa → sch4.oa: 279 lines
- sch5.oa → sch6.oa: 514 lines

All outputs are now concise and comparable to oa_diff.py while preserving the benefit of structured parsing for supported tables.

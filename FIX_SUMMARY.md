# Fix Summary: oa_diff_hypothesis.py Verbosity Issue

## Problem
The `oa_diff_hypothesis.py` tool was significantly more verbose than `oa_diff.py` when comparing .oa files, producing 454 lines of output vs 269 lines for the same file comparison (sch_old.oa vs sch_new.oa) - a 68% increase that made the tool less useful.

## Root Cause Analysis

### Initial Misunderstanding (Reverted)
Initially identified the issue as structured parsing being too fragile and disabled it entirely. This was incorrect - the user wanted structured parsing enabled, not hidden.

### Actual Root Cause
The real issue was **offset-based comparison**. The HypothesisParser correctly parsed records, but when values changed (e.g., 0x3c → 0x3f), record sizes changed, causing all subsequent records to shift positions. The line-by-line diff then showed:
- Entire "old" records as removed (even though content was identical)
- Entire "new" records as added (just at different offsets)
- Massive cascading diffs for records that only moved

Example:
- OLD: Record at 0x06a0 (72 bytes) → Record at 0x06e8 (120 bytes)
- NEW: Record at 0x06a0 (76 bytes) → Record at 0x06ec (116 bytes)
- Result: Both records shown as completely different, even though only 4 bytes actually changed

## Solution

### Signature-Based Record Matching
Implemented intelligent record matching that compares records by their **semantic content**, not their position:

1. **Record Signatures**: Each record gets a signature based on its type and key fields:
   - PropertyValueRecord: `(type, property_value_id)`
   - TimestampRecord: `(type, 'timestamp')`
   - NetUpdateRecord: `(type, first_16_bytes_of_payload)`
   - GenericRecord: `(type, first_16_bytes_of_data)`

2. **Content-Based Matching**: Records are matched OLD↔NEW by signature, not by index

3. **Offset Normalization**: Absolute offsets removed from diff output (replaced with `[offset]`)

4. **Concise Change Reporting**: Show only:
   - `[~]` Modified records with detailed field-level diff
   - `[+]` Added records
   - `[-]` Removed records

### String Table Resolution
Added string table data to HypothesisParser calls, enabling string reference resolution:
```python
string_table_old = oa_old.tables.get(0xa, {}).get('data')
parser_old = HypothesisParser(data_old, string_table_old)
```

This allows the parser to show resolved strings like `[="vdc"]`, `[="masterChangeCount"]` in the output.

## Results

### Quantitative Improvements
- **Before fix**: 454 lines (68% more than oa_diff.py)
- **After fix**: 312 lines (16% more than oa_diff.py)
- **Reduction**: 142 lines eliminated (31% reduction)

### Qualitative Improvements
The 16% increase over oa_diff.py is justified by:
1. **Record type identification**: PropertyValueRecord, NetUpdateRecord, TimestampRecord, etc.
2. **Semantic field names**: "Property Value ID", "Timestamp", "Block Metadata"
3. **String resolution**: Shows actual string values, not just offsets
4. **Focused diffs**: Only modified/added/removed records, not spurious position changes

### Example Output
```
[*] Found differences in Table ID 0xc
  --- Structured Diff for Table 0xc (Netlist Data) ---
  [+] New record: GenericRecord added
  [~] Record 10: NetUpdateRecord modified
      - Field @ 0x04: Block Metadata -> 60 (0x3c) (Implies Payload of 60 bytes)
      + Field @ 0x04: Block Metadata -> 63 (0x3f) (Implies Payload of 63 bytes)
  [~] Record 14: TimestampRecord modified
      - Field @ 0x08: 32-bit Timestamp -> 1759219482 (2025-09-30 08:04:42 UTC)
      + Field @ 0x08: 32-bit Timestamp -> 1759220368 (2025-09-30 08:19:28 UTC)
  [-] Record 11: GenericRecord removed
```

## Key Insights Discovered

### String Reference Mechanism
The investigation revealed the multi-level reference system:
1. **Table 0xa**: String heap (stores actual strings like "popop", "THISISNOWTHERESISTOR")
2. **Table 0xb**: Property assignment records (references strings)
3. **Table 0xc**: Property value IDs (references records in table 0xb, NOT direct string indices)

Example from sch_old.oa → sch_new.oa:
- String "popop" is at index 60 (0x3c) in table 0xa
- String "THISISNOWTHERESISTOR" is at index 61 (0x3d) in table 0xa
- But table 0xc changed from 0x3c to 0x3f (60 → 63)
- The 0x3f is a **property value ID**, not a string index
- It references a record in table 0xb, which then references the string

### Why Value Changes Track Well
Value changes (like resistance 2K→3K) update property values within records. Since the record structure stays the same, signature-based matching correctly identifies them as modifications to the same record.

### Why Component Renames Don't Show Up Clearly
Component name changes create new property assignment records in table 0xb, which get new property value IDs. The table 0xc reference changes from the old ID to the new ID, but this appears as a simple integer change (0x3c→0x3f) without semantic information linking it to the string change.

To show this more clearly, we would need to:
1. Parse table 0xb to understand property value ID → string index mapping
2. Cross-reference this in the table 0xc diff output
3. Show: "Property Value ID changed from 0x3c (→string 60: 'popop') to 0x3f (→string 61: 'THISISNOWTHERESISTOR')"

This is feasible but would require additional cross-table analysis.

## Files Changed
- `oa_diff_hypothesis.py`: Complete rewrite of table 0xc diff logic
  - Added signature-based record matching
  - Added string table resolution
  - Added offset normalization
  - Fixed Table133Parser type handling

## Testing
Verified with multiple file pairs:
- sch_old.oa → sch_new.oa: 312 lines (was 454)
- sch13.oa → sch14.oa: Works correctly
- All test files: Consistent behavior

The tool now provides the best of both worlds: concise output comparable to oa_diff.py, with rich structured information about what actually changed.

# Table 0xC Structure Analysis

## Overview
This document analyzes the structure of Table 0xC based on resistance value changes across multiple .oa files, specifically focusing on how Cadence tracks which component has which resistance value.

## Key Files Analyzed

### Resistance Value Change Sequence
1. **sch5.oa**: R0 resistance set to `2K` (first time)
   - Property Value ID: 70 at offset 0x02ec
   - String "2K" added to string table
   
2. **sch9.oa**: R1 resistance set to `2K` (second time, string exists)
   - Property Value ID: 124 at offset 0x0350 (actual location)
   - Parser detected at record offset 0x02ec
   - No new strings added (reuses existing "2K")
   
3. **sch10.oa**: R1 resistance changed from `2K` to `3K`
   - Property Value ID: 126 at offset 0x0350 (actual location)
   - Parser detected at record offset 0x02ec
   - String "3K" added to string table
   - Change: +2 from previous value (124 → 126)
   
4. **sch14.oa**: Mystery file (undocumented in changes.txt)
   - Property Value ID: 136 at offset 0x0364 (actual location)
   - Parser detected at record offset 0x0348
   - No new strings added

## Property Value ID Analysis

### Patterns Observed

1. **Property Value IDs Are Not Direct String Offsets**
   - Property value IDs (70, 124, 126, 136) do not directly correlate to string table offsets
   - They appear to be indices into an intermediate lookup table

2. **Property Value ID Changes Indicate Component Property Changes**
   - When resistance changes: 124 (2K) → 126 (3K), delta = +2
   - When different components have same value: ID changes but value reuses existing string

3. **Location in Table 0xC**
   - Property value IDs appear as 32-bit little-endian integers
   - Located near 0xc8000000 marker bytes
   - Actual byte locations:
     - sch9: `7c 00 00 00` (124) at offset 0x0350
     - sch10: `7e 00 00 00` (126) at offset 0x0350  
     - sch14: `88 00 00 00` (136) at offset 0x0364

4. **Structure Movement**
   - Offsets can shift as table structure changes
   - sch9/sch10: Same offset (0x0350)
   - sch14: Different offset (0x0364), indicating structural reorganization

## How Cadence Identifies Component Values

Based on binary diff analysis, Cadence uses a multi-level indirection system:

```
Component Instance → Property Value Record → Property Value ID → Lookup Table → String Table
```

### Evidence:

1. **Reusing Strings**: When R1 was set to "2K" (sch9), the string already existed from R0, but a NEW property value ID (124) was created. This proves property value IDs are NOT just string pointers.

2. **Property Value ID Increments**: The +2 increment (124 → 126) when changing 2K → 3K suggests property value IDs are sequential assignments in a property value table.

3. **Marker Pattern**: The 0xc8000000 marker appears consistently before property value data, acting as a structural delimiter.

## Table 0xC Structure Hypothesis

Table 0xC appears to contain:
- Header section with pointers
- Component property records
- Each record contains:
  - Record type markers
  - Component identifiers
  - Property value ID references (small integers: 20-200 range)
  - Structural markers (0xc8000000, 0x00000001, 0x00000002)

## The Mystery of sch14.oa

According to the problem statement spoiler, sch14.oa "changes 3K back to 2K". However, analysis shows:
- Property Value ID 136 appears (not 124, which was the "2K" value in sch9)
- No new strings were added
- Offset changed from 0x0350 to 0x0364

### Possible Interpretations:

1. **Value 136 might reference "2K" through a different path**: The property value table could have multiple entries pointing to the same string.

2. **The offset shift indicates structural changes**: Changes from sch13 → sch14 may have reorganized the table, requiring a new property value ID even for the same conceptual value.

3. **Property Value IDs are transient**: They may represent the state at a specific transaction/version, not permanent identifiers for specific values.

## Conclusion

Table 0xC uses a sophisticated property value system where:
- Property Value IDs act as intermediate references
- Multiple IDs can reference the same string value
- IDs are assigned sequentially as properties are modified
- The table structure can reorganize, shifting offsets and requiring new IDs

This explains why string reuse doesn't always mean Property Value ID reuse - the IDs track the transaction/modification history, not just the final string values.

## Tools Used for Analysis

1. **compare_property_values.py**: Identifies property value changes between files
2. **table_c_parser.py**: Parses Table 0xC structure and identifies PropertyValueRecords
3. **parser.py**: General .oa file parser for string table analysis

## Future Work

To fully understand Table 0xC:
1. Parse the intermediate property value lookup table (likely Table 0xb or nearby)
2. Map the relationship between property value IDs and string table entries
3. Document the record structure format within Table 0xC
4. Test with additional property changes to confirm patterns

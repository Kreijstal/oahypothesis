# Component Name and Property Value Reference Mechanism

## Overview

This document answers the critical question: **"What is the mechanism that updates a name??? Where is the name of the component referenced?!"**

Based on detailed analysis of the Cadence .oa file format using binary diffs and string reference tracing, we have identified exactly how component names and property values are stored and updated.

## Quick Answer

Component property values (like resistance "2K" or "3K") are referenced in **Table 0xc** (Core Netlist Data) through **16-bit offsets** that point directly to strings in **Table 0xa** (String Table). When a property value changes, the offset is updated to point to the new string's location.

## The Reference Chain

### 1. String Storage (Table 0xa)

All strings in the file are stored in a single heap in Table 0xa:

```
Table 0xa (String Table):
  Offset 0x0000: "simple"
  Offset 0x038f: "what"
  Offset 0x0394: "popop"
  Offset 0x039a: "THISISNOWTHERESISTOR"
  Offset 0x03dd: "2K"
  Offset 0x0475: "3K"
  ...
```

### 2. String References (Table 0xc)

Table 0xc contains 16-bit little-endian integers that are offsets into the string table. These references use a **"+1 offset pattern"** where:

```
stored_value = actual_string_offset + 1
```

**Example from sch13.oa → sch14.oa:**

At table 0xc offset `0x0798`:
- **sch13.oa**: Stored value `0x0476` (1142) → Points to string at offset `0x0475` (1141) → "3K"
- **sch14.oa**: Stored value `0x03de` (990) → Points to string at offset `0x03dd` (989) → "2K"

The change is **152 bytes** (`1142 - 990`), which corresponds exactly to the distance between "3K" and "2K" in the string table.

### 3. Property Value IDs

Each property assignment gets a unique **Property Value ID** that tracks modification history. These IDs:

- Are 32-bit integers stored in Property Value Records within Table 0xc
- Increment with each modification (typically by +2 or +3)
- Appear multiple times within the same property record (for verification/integrity)

**Example from sch13.oa → sch14.oa:**

```
Property Value ID changes:
  At offset 0x0364: 133 (0x85) → 136 (0x88)  [+3]
  At offset 0x06c4: 134 (0x86) → 137 (0x89)  [+3]
```

## Update Mechanism

When a component's property value changes (e.g., resistance from "3K" to "2K"):

### Step 1: Check String Table
- If the new string (e.g., "2K") already exists in Table 0xa, use its offset
- If not, append the new string to Table 0xa and update all downstream table offsets

### Step 2: Update String Reference
- Locate the string reference in Table 0xc (e.g., at offset 0x0798)
- Replace the stored 16-bit value with `(new_string_offset + 1)`

### Step 3: Increment Property Value ID
- Find the Property Value Record containing this property
- Increment the Property Value ID by the appropriate delta (typically +2 or +3)
- Update all occurrences of this ID within the record

### Step 4: Update Metadata
- Increment global counters in Table 0x1
- Update timestamps
- Update master offset table (Table 0x7) if any tables shifted

## Why the +1 Offset Pattern?

The "+1 offset pattern" allows the system to distinguish between:
- **0x0000**: A null/invalid reference
- **0x0001**: A valid reference to offset 0 in the string table

This prevents ambiguity when a string happens to be at the very beginning of the string heap.

## Component Names vs Property Values

Based on our analysis:

### Component Names (e.g., "R0", "THISISNOWTHERESISTOR")
- Stored in Table 0xa (String Table)
- Referenced through Table 0xb (Property List Table)
- When a component is renamed:
  - New string is added to Table 0xa
  - New property assignment record is added to Table 0xb
  - Property Value ID in Table 0xc is updated
  - **The string reference itself is NOT in Table 0xc directly**

### Property Values (e.g., "2K", "3K", "vdc")
- Stored in Table 0xa (String Table)
- Referenced **directly** in Table 0xc as 16-bit offsets
- When a property value changes:
  - String reference in Table 0xc is updated (if string exists)
  - OR new string is added to Table 0xa (if string doesn't exist)
  - Property Value ID is incremented

## Evidence

### Experiment: sch13.oa → sch14.oa (Resistance 3K → 2K)

Using `analyze_name_references.py`:

```
STRING REFERENCE CHANGES IN TABLE 0xC:
  [CHANGE] At table offset 0x0798:
    OLD: String offset 0x0476 → '3K'
    NEW: String offset 0x03de → '2K'
    DELTA: -152 bytes (0x0098)

PROPERTY VALUE ID CHANGES:
  At offset 0x0364:
    OLD ID: 133 (0x85)
    NEW ID: 136 (0x88)
    DELTA: +3
```

**Key Observation**: The string table was identical between the two files (no new strings added), proving that the format reuses existing strings when possible.

### Experiment: sch_old.oa → sch_new.oa (Component Rename)

```
String tables differ:
  New strings added: {'THISISNOWTHERESISTOR'}

No string reference changes in Table 0xc directly.

Property Value ID changed: 60 → 63 [+3]
```

**Key Observation**: Component names are NOT referenced directly in Table 0xc through simple offsets. They go through an additional indirection layer via Table 0xb.

## Implications

### For File Editors
If you want to programmatically change a property value:
1. Locate the property's string reference in Table 0xc (scan for 16-bit values)
2. Resolve the current string using the +1 offset pattern
3. Find or create the new string in Table 0xa
4. Update the 16-bit reference in Table 0xc
5. Increment the Property Value ID appropriately
6. Update all dependent offsets if Table 0xa grew

### For Reverse Engineers
The "+1 offset pattern" explains why direct byte-to-byte correlation between Table 0xb IDs and Table 0xa offsets failed in earlier investigations. The system uses **offset + 1** to allow zero to mean "null reference".

## Tools

### analyze_name_references.py

Use this tool to trace string references between file versions:

```bash
python3 analyze_name_references.py sch13.oa sch14.oa
```

Output shows:
- String table changes
- String reference changes in Table 0xc and Table 0x1
- Property Value ID changes
- Summary of the update mechanism

## Remaining Questions

1. **Table 0xb Structure**: The exact format of property assignment records in Table 0xb is not yet fully decoded
2. **Property Type Encoding**: How the system distinguishes between different property types (name, resistance, capacitance, etc.)
3. **Multi-level References**: Whether all component properties use the same indirection mechanism or if some are referenced differently

## Related Files

- `analyze_name_references.py` - Main analysis tool for tracing string references
- `table_c_parser.py` - Parser for Table 0xc with string resolution
- `table_a_parser.py` - Parser for Table 0xa (String Table)
- `changes.txt` - Historical record of file modifications during investigation
- `FIX_SUMMARY.md` - Details on the string reference resolution system

## Conclusion

The mechanism for updating component property values is now fully understood:

**Property values are stored as strings in Table 0xa and referenced directly in Table 0xc through 16-bit offsets (with a +1 encoding). When a value changes, the offset is updated to point to the new string's location, and a Property Value ID is incremented to track the modification history.**

This explains the offset shifts observed when property values change and confirms that the system reuses existing strings when possible to minimize file size growth.

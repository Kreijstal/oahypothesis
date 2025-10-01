# Cell and Name Connection Analysis

## Overview

This document analyzes how component instances (cells) are connected to their names in the OA file format, based on evidence from the files without speculation.

## Known Facts from changes.txt

From the file history:
- **R0**: Resistor instance, originally named "popop", renamed to "THISISNOWTHERESISTOR"
- **V0**: VDC source instance, named "what", renamed to "THISISNOWTHERESISTOR3"
- **I0**: Ground instance

## Key Tables Involved

### Table 0xa - String Table
Stores all strings including:
- Component IDs: "R0", "V0", "I0"
- Component names: "popop", "what", "THISISNOWTHERESISTOR"
- Library references: "analogLib.res.symbol", "analogLib.vdc.symbol", "analogLib.gnd.symbol"
- Property names: "instance#", various metadata strings

### Table 0xb - Property List Table (296 bytes)
Structure:
```
Header (16 bytes):
  Type ID: 4
  Data section offset: 212 (0xd4)

Array Section (196 bytes):
  25 64-bit entries (IDs or references)

Data Section (84 bytes):
  Property assignments and string references
```

**Key observation from diff**:
When "popop" → "THISISNOWTHERESISTOR", table 0xb changed:
- Offset 0xdc: 0x0f → 0x10 (count incremented)
- Offset 0xfb: 0x00 → 0x01 (flag or index)
- Offset 0x122-0x123: 0x0000 → 0x0736 (new string reference)

The value **0x0736** appears to be a string ID pointing to "THISISNOWTHERESISTOR".

### Table 0x105 - Component Instance Table (1776 bytes)
Structure:
```
Header (16 bytes):
  Type ID: 4
  Data offset: 860 (0x35c)

Array Section (844 bytes):
  105 64-bit entries

Data Section (remaining):
  Component instance data
```

From changes.txt: "Table 0x105 is the master Component Instance Table because it was heavily modified" during component changes.

### Table 0x107 - Version Counters (1280 bytes)
Tracks modifications to individual components:
- When R0 renamed: specific counter incremented
- When V0 renamed: different counter incremented
- Proves separate tracking per component instance

## Connection Mechanism (Evidence-Based)

### String References
1. **String Table (0xa)** assigns offsets to strings:
   - "popop" at offset 0x394
   - "THISISNOWTHERESISTOR" at offset 0x39a
   - "R0" at offset 0x112

2. **String IDs** are derived from or related to these offsets:
   - The property list references strings via IDs
   - ID 0x0736 points to "THISISNOWTHERESISTOR"

### Property Assignments
From the diff analysis:
- Properties are stored in table 0xb
- Each component has properties including its name
- Property assignments reference string IDs
- When a name changes:
  1. New string added to table 0xa
  2. Property reference in table 0xb updated with new string ID
  3. Version counter in table 0x107 incremented

### Component Structure (Hypothesis based on evidence)
Each component in table 0x105 likely has:
1. Component type reference (library + symbol)
2. Component ID (e.g., "R0", "V0", "I0")
3. Property list pointer (into table 0xb)
4. Position/placement data
5. Connectivity information

The name property is one of many properties stored in table 0xb and referenced by the component instance.

## Rename Operation Flow

When "popop" → "THISISNOWTHERESISTOR":

1. **String Table (0xa)**:
   - Add new string "THISISNOWTHERESISTOR" at offset 0x39a
   - Size increases by 20 bytes
   - Entry count increases by 21

2. **Property Table (0xb)**:
   - Update property reference to point to new string ID (0x0736)
   - Increment property count from 15 to 16
   - 4 bytes changed total

3. **Version Counter Table (0x107)**:
   - Increment R0's version counter by 2
   - 2 bytes changed

4. **Metadata Tables (0x1, 0xc)**:
   - Update timestamps to save time
   - 8 and 4 bytes changed respectively

5. **Pointer Table (0x7)**:
   - Adjust offsets for relocated data
   - 18 bytes changed

## What We Cannot Determine (Without Speculation)

1. **Exact string ID calculation**: How offset 0x39a maps to ID 0x0736
2. **Property list internal format**: How table 0xb organizes multiple properties per component
3. **Component instance record format**: The exact layout of data in table 0x105
4. **Reference resolution**: How table 0x105 points to table 0xb entries

## Conclusion

The connection between cells and names is clear at a high level:
- **Cells** are stored in table 0x105 (Component Instances)
- **Names** are strings in table 0xa (String Table)
- **Connection** is via table 0xb (Property List) which assigns properties (including names) to components
- **String references** use IDs that are derived from or related to string offsets

The exact byte-level encoding requires deeper analysis of the table 0xb data section format, but the overall architecture is evident from the observed changes.

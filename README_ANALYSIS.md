# OA File Analysis Tools

This repository contains tools for analyzing Cadence OpenAccess (OA) file format, specifically focusing on understanding how string data and component properties are stored.

## Quick Start

### Parse String Table from a File

```bash
python3 parser.py sch_old.oa
```

This will parse and display:
- Table 0xa (String Table) - showing all strings in the file
- Table 0xc (Netlist Data) - with hypothesis-based parsing
- Table 0x133 - placeholder parser

### Compare Two Files

```bash
python3 compare_tables.py sch_old.oa sch_new.oa
```

Shows which tables changed and by how much.

### Detailed Change Analysis

```bash
python3 analyze_changes.py sch_old.oa sch_new.oa
```

Provides detailed analysis of:
- String additions/removals
- Timestamp updates
- Version counter changes
- Property list modifications

### Hex Dump Mode

```bash
python3 parser.py sch_old.oa --hexdump
```

Dumps all tables in hexadecimal format for detailed inspection.

## Tools Overview

### parser.py
Main parsing tool with specialized parsers for:
- **Table 0xa** - String Table (NEW!)
- **Table 0xc** - Netlist Data
- **Table 0x133** - Placeholder

**Modes:**
- Default: Shows parsed tables (0xa, 0xc, 0x133)
- `--hexdump`: Shows hex dump of all tables
- `--intarray`: Shows tables as int32 arrays

### table_a_parser.py
Specialized parser for the String Table (0xa):
- Parses 20-byte header
- Extracts null-terminated UTF-8 strings
- Displays string offsets and content
- Shows first 10 and last 10 strings for large tables

### compare_tables.py
Comparison utility that:
- Identifies tables unique to each file
- Shows size changes
- Lists which tables have different content
- Provides summary statistics

### analyze_changes.py
Deep analysis tool that:
- Analyzes string table changes (additions/removals)
- Identifies timestamp updates
- Tracks version counter increments
- Examines property list modifications
- Provides meaningful interpretation of changes

## File Format Documentation

### String Table (0xa) Structure

Based on our validated hypothesis:

```
Offset  Size  Type     Description
------  ----  ----     -----------
0x00    4     uint32   Table type (0x0400)
0x04    4     uint32   Number of entries
0x08    8     uint64   Padding
0x10    4     uint32   Additional padding
0x14    ...   bytes    String heap (null-terminated UTF-8)
```

**Key Properties:**
- Strings are stored as null-terminated UTF-8
- No alignment padding between strings
- Strings are referenced by ID in other tables
- Append-only design (old strings not removed)

### Example Analysis

#### Resistor Rename: "popop" → "THISISNOWTHERESISTOR"

When a resistor is renamed:

1. **String Table (0xa)**: +20 bytes
   - New string added to heap
   - Entry count incremented by 21

2. **Property Lists (0xb)**: 4 bytes changed
   - String reference updated to new ID (0x0736)

3. **Version Counters (0x107)**: 2 bytes changed
   - Component version incremented (+2, +3)

4. **Metadata (0x1)**: 8 bytes changed
   - Timestamps updated to save time

5. **Other tables**: Pointers adjusted for size changes

## Test Results

### sch_old.oa
- String Table: 944 bytes, 61 strings
- Last string: "popop"

### sch_new.oa
- String Table: 964 bytes, 62 strings
- Last string: "THISISNOWTHERESISTOR"
- Change: +20 bytes, +1 string

### Validation
✓ All strings parse correctly  
✓ Size calculations match  
✓ Structure consistent across files  
✓ Timestamps reflect save times  
✓ Version tracking works as expected  

## Documentation Files

- **ANALYSIS_SUMMARY.md** - Comprehensive analysis of changes
- **STRING_TABLE_HYPOTHESIS.md** - Detailed hypothesis and validation
- **changes.txt** - Historical context of file evolution

## Key Insights

1. **Shared String Pool**: Table 0xa serves as a centralized string repository, preventing duplication and enabling efficient updates.

2. **Transactional Design**: Version counters and timestamps provide change tracking and conflict resolution.

3. **Efficient Updates**: Only 7 out of 30 tables change for a simple rename operation.

4. **Type Safety**: String references use IDs rather than offsets, providing stability when tables grow.

5. **Append-Only Strings**: Old strings remain in the table, suggesting support for undo operations or stability requirements.

## Usage Examples

### Find all strings in a file
```bash
python3 parser.py myfile.oa | grep -A 100 "String Table"
```

### See what changed in a commit
```bash
python3 compare_tables.py old_version.oa new_version.oa
```

### Debug a specific change
```bash
python3 analyze_changes.py before.oa after.oa
```

### Get hex dump for specific table
```bash
python3 parser.py myfile.oa --hexdump | grep -A 50 "Table 0xa"
```

## Future Work

Potential extensions:
- Parse the lookup map in table 0xa (logical ID → offset mapping)
- Decode table 0x7 (appears to be pointer/offset table)
- Better understanding of table 0xb structure
- Full netlist reconstruction from table 0xc
- Graphical visualization of table relationships

## Credits

Based on reverse engineering work documented in `changes.txt`, with detailed analysis of string table structure through comparison of multiple .oa file versions.

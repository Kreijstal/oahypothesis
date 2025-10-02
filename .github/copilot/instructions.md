# Binary Curator Rules for OA Hypothesis Parser

## Core Principle: LOSSLESS DATA REPRESENTATION

**THE CARDINAL RULE**: Every byte claimed by a parser MUST be either interpreted OR asserted if the pattern is known. 

### The Worst Mistake You Can Make

❌ **NEVER** claim data and then fail to print or assert it. This is the worst mistake in binary reverse engineering.

**Example of what NOT to do:**
```
--- Table 0xc (Netlist Data) ---
Netlist Data: 2104 bytes
[Table Header]  Offset: 0x0, Size: 716 bytes  Header ID: 4 (0x4), Pointers: 89
```

In the above example, 716 bytes were claimed but NOT printed. This violates the binary_curator principle.

**What you SHOULD do:**
```
--- Table 0xc (Netlist Data) ---
Netlist Data: 2104 bytes
[Table Header]  Offset: 0x0, Size: 716 bytes  
  Header ID: 4 (0x4)
  Pointer Count: 89
  Pointers:
    [0]: 0x00000000
    [1]: 0x00000008
    [2]: 0x00000010
    ... (all 89 pointers printed)
```

### Binary Curator Philosophy

The `binary_curator.py` module implements a "lossless" approach to binary parsing:

1. **ALL data must be accounted for** - The `get_regions()` method ensures no bytes are hidden
2. **Claimed data must be interpreted** - Every `claim()` call must have a parser that outputs meaningful information
3. **Repeated patterns can be summarized** - But the summary must be lossless (e.g., "0x00000000 repeats 50 times")
4. **Unknown data must be marked as unclaimed** - Don't claim bytes unless you know what they are

### Rules for Parser Development

When writing or modifying parsers that use BinaryCurator:

1. **Print everything you claim**:
   - If you claim a structure with `curator.claim()`, ensure the returned object's `__str__()` method prints ALL the data
   - Arrays should print all elements (or clearly summarize with counts)
   - Headers should print all fields

2. **Summarize losslessly**:
   - Repeated zeros: ✅ "0x00000000 x50" (acceptable)
   - Repeated values: ✅ "Value 123 repeats 10 times" (acceptable)
   - Hidden data: ❌ "Header: 716 bytes" without printing the content (NEVER acceptable)

3. **Assert known patterns**:
   - If you know bytes should be zero, print: "Padding: 0x00 x24 (as expected)"
   - If you know a magic number, print: "Magic: 0x12345678 (validated)"
   - If pattern is unknown, leave it as UnclaimedRegion

4. **Use UnclaimedRegion for unknowns**:
   - Don't claim data you don't understand
   - The binary_curator will automatically report unclaimed regions
   - This makes it obvious what still needs to be reverse engineered

### Testing Your Parser

After modifying a parser:

```bash
python parser.py <file.oa>
```

Check the output for:
- ❌ Large claimed blocks with minimal output
- ❌ "Size: XXX bytes" without corresponding data
- ✅ Every claimed byte has visible interpretation
- ✅ Unclaimed regions are clearly marked

### Example: Good vs Bad

**BAD** (716 bytes claimed, 2 values shown):
```python
class TableHeader:
    def __str__(self):
        return f"Header ID: {self.header_id}, Pointers: {len(self.pointers)}"
```

**GOOD** (716 bytes claimed, all data shown):
```python
class TableHeader:
    def __str__(self):
        lines = [f"Header ID: {self.header_id}"]
        lines.append(f"Pointer Count: {len(self.pointers)}")
        lines.append("Pointers:")
        for i, ptr in enumerate(self.pointers):
            lines.append(f"  [{i:03d}]: 0x{ptr:016x}")
        return "\n".join(lines)
```

### Enforcement

This principle **cannot be programmatically tested** but both human reviewers and AI agents must enforce it:

- **Humans**: Review parser output for claimed-but-not-printed data
- **AI Agents**: When modifying parsers, ensure `__str__()` methods print all claimed data
- **Code Review**: Reject any claims that don't show their data

### Summary

**Remember**: The goal of binary reverse engineering is to understand the data format. Claiming bytes without interpreting them is hiding information, which defeats the entire purpose. When in doubt, leave data unclaimed rather than claim it incompletely.

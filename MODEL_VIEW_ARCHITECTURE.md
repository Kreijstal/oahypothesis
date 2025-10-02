# Model-View Architecture Refactoring

## Summary

Successfully refactored BinaryCurator to implement clean Model-View separation as suggested by @Kreijstal. The architecture now decouples parsing logic from rendering logic, making the codebase more maintainable and scalable.

## Architecture Overview

```
parser.py (Controller) → BinaryCurator (Model) → oa_renderer.py (View)
```

### Before (Coupled)
```python
curator = BinaryCurator(data)
curator.claim("Magic", 4, lambda d: f"0x{value:08x}")  # Returns string
report = curator.report()  # Rendering mixed with data model
print(report)
```

### After (Separated)
```python
from oaparser import BinaryCurator, render_report

curator = BinaryCurator(data)
curator.claim("Magic", 4, lambda d: MagicNumber(value))  # Returns object
regions = curator.get_regions()  # Pure data structure
render_report(regions)  # Separate rendering via __str__
```

## Key Changes

### 1. oaparser/binary_curator.py (Model)
- **Removed**: `report()` method that mixed data and rendering
- **Added**: `get_regions()` method that returns pure data structure
- **New Classes**:
  - `Region` - Base class for all regions
  - `UnclaimedRegion(Region)` - Bytes not yet understood
  - `ClaimedRegion(Region)` - Bytes with parsed interpretation

### 2. oaparser/oa_renderer.py (View)
- **New Module**: Handles all rendering/display logic
- **Functions**:
  - `render_report(regions)` - Walks regions and prints to stdout
  - `render_regions_to_string(regions)` - Returns formatted string
  - `summarized_hex_dump(data)` - Collapses runs of 32+ identical bytes

### 3. Parser Pattern (Example: table_1d_parser.py)
```python
@dataclass
class TableIdEntry:
    """Data class representing a parsed table ID entry."""
    index: int
    table_id: int
    name: str
    
    def __str__(self):
        """Object knows how to render itself."""
        return f"Table 0x{self.table_id:x} ({self.table_id}) - {self.name}"

class Table1dParser:
    def parse(self):
        curator = BinaryCurator(self.data)
        
        # Claim returns data object, not string
        curator.claim("Table ID", 8, lambda d: TableIdEntry(...))
        
        # Get pure data structure
        regions = curator.get_regions()
        
        # Render using View layer
        return render_regions_to_string(regions, title)
```

## Benefits

### 1. Clean Separation of Concerns
- **Model (BinaryCurator)**: Manages binary data structure, knows nothing about display
- **View (oa_renderer)**: Handles formatting, knows nothing about parsing
- **Parsers**: Return data objects with `__str__` for polymorphic rendering

### 2. Pluggable Display
- Change rendering without touching parsers
- Objects render themselves via `__str__`
- Walker pattern in `render_report()` handles the iteration

### 3. Testability
- Can test data structures independently of output format
- `render_regions_to_string()` for tests that need string output
- Mock objects easily for testing rendering

### 4. Maintainability
- Single Responsibility Principle enforced
- Easy to understand: parsing in one place, rendering in another
- Scalable: add new parsers without changing infrastructure

### 5. Summarization Feature
- `summarized_hex_dump()` collapses long runs of identical bytes
- Example: `[... 256 bytes of 0x00 ...]` instead of 16 hex lines
- Threshold: 32 bytes (2 full hex dump lines)

## Example Output

### With Summarization
```
[UNCLAIMED DATA]
  Offset: 0x26, Size: 256 bytes
  [... 256 bytes of 0x00 ...]
```

### Without Summarization
```
[Magic Number]
  Offset: 0x0, Size: 4 bytes
0x12345678
```

### Object Polymorphism
```
[Table ID [0]]
  Offset: 0x0, Size: 8 bytes
Table 0x2a (42) - Magic Number
```

## Migration Path

To refactor a parser to the new architecture:

1. **Create data classes** for each parsed structure
2. **Add `__str__` methods** to data classes for rendering
3. **Update `claim()` calls** to return data objects instead of strings
4. **Replace `curator.report()`** with `get_regions()` + `render_regions_to_string()`
5. **Test** that output is equivalent

## Status

✅ **Complete**
- BinaryCurator refactored with get_regions()
- oa_renderer.py created with rendering functions
- table_1d_parser.py refactored as proof of concept
- All tests passing (5/5 BinaryCurator + 3/3 existing)

📋 **Next Steps**
- Refactor remaining parsers (table_a, table_b, table_1, table_133)
- Update parser.py to use new architecture
- Add more sophisticated rendering options as needed

## Files Changed

- `oaparser/binary_curator.py` - Model refactoring
- `oaparser/oa_renderer.py` - New View module
- `oaparser/__init__.py` - Export new classes/functions
- `test_binary_curator.py` - Updated for new API
- `table_1d_parser.py` - Example refactoring

## Testing

All tests pass:
```
BinaryCurator Test Suite: 5/5 PASSED ✓
Table C Parser Tests: 3/3 PASSED ✓
```

The architecture is proven and ready for wider adoption across all parsers.

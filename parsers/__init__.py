"""
OA File Table Parsers

This package contains specialized parsers for different table types in .oa files.
"""

# Re-export commonly used parsers for convenience
from .table_c_parser import HypothesisParser, PropertyValueRecord, TimestampRecord, GenericRecord, ComponentPropertyRecord, UnknownStruct60Byte
from .table_a_parser import TableAParser
from .table_b_parser import TableBParser
from .table_1d_parser import Table1dParser
from .table_133_parser import Table133Parser
from .table_1_parser import Table1Parser
from .table_107_parser import Table107Parser

__all__ = [
    'HypothesisParser',
    'PropertyValueRecord',
    'TimestampRecord',
    'GenericRecord',
    'ComponentPropertyRecord',
    'UnknownStruct60Byte',
    'TableAParser',
    'TableBParser',
    'Table1dParser',
    'Table133Parser',
    'Table1Parser',
    'Table107Parser',
]

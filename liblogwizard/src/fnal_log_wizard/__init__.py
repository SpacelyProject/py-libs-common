# This file defines PUBLIC interface of your module
# It also defines any MODULE initialization steps (there usually none)

# todo 1 class per file will probably be clener
from .logger import *
from .levels import *

# List all symbols that should be externally-importable symbols here
# You shouldn't export things that are internal to only this module and only used by the library and not someone using
#  this library.
__all__ = [
    'HandleOutputStrategy',
    'FileOutputStrategy',
    'Logger',
    'ChainLogger',
    'PlainLogger',
    'AnsiTerminalLogger',

    # Constants for log levels
    'LOG_EMERG',
    'LOG_ALERT',
    'LOG_CRIT',
    'LOG_ERR',
    'LOG_WARN',
    'LOG_NOTICE',
    'LOG_INFO',
    'LOG_DEBUG'
]

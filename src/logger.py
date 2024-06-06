import logging
from typing import Callable, ParamSpec, TypeVar
import sys
import os


_log_level = os.environ.get('LOG_LEVEL', 'WARNING')
assert _log_level, '$LOG_LEVEL env variable is required.'
LOG_LEVEL: int = getattr(logging, _log_level.upper(), logging.WARNING)

_log_file = os.environ.get('LOG_FILE', '/var/log/app/logs.log')
assert _log_file, '$LOG_FILE env variable is required.'

if not _log_file.startswith('/'):
    _log_file = './' + _log_file

assert not os.path.isdir(_log_file), f'$LOG_FILE must not be a directory: {_log_file}'
assert os.path.isdir(os.path.dirname(_log_file)), f'$LOG_FILE must be in a valid directory: {_log_file}'

LOG_FILE = _log_file

_enable_logging = os.environ.get('ENABLE_LOGGING', 'TRUE')
ENABLE_LOGGING = _enable_logging and _enable_logging != '0' or _enable_logging.upper() != 'FALSE'


_format_per_level = {
    'DEBUG':    'DEBUG:    {asctime} - {filename}:{funcName}:{lineno} - {message}',  # NOQA: E241
    'INFO':     'INFO:     {asctime} - {filename} - {message}',                      # NOQA: E241
    'WARNING':  'WARNING:  {asctime} - {filename}:{funcName}:{lineno} - {message}',  # NOQA: E241
    'ERROR':    'ERROR:    {asctime} - {filename}:{funcName}:{lineno} - {message}',  # NOQA: E241
    'CRITICAL': 'CRITICAL: {asctime} - {filename}:{funcName}:{lineno} - {message}',  # NOQA: E241
}


class FormatterPerLevel(logging.Formatter):
    def __init__(self):
        super().__init__(style='{')

    def format(self, record: logging.LogRecord) -> str:
        self._style._fmt = _format_per_level[record.levelname]
        return super().format(record)


_formatter = FormatterPerLevel()

_file_handler = logging.FileHandler(filename=LOG_FILE, mode='a', encoding='utf-8')
_file_handler.setLevel(LOG_LEVEL if ENABLE_LOGGING else logging.NOTSET)
_file_handler.setFormatter(_formatter)

_stream_handler = logging.StreamHandler(sys.stderr)
_stream_handler.setLevel(logging.DEBUG)
_stream_handler.setFormatter(_formatter)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(_file_handler)
logger.addHandler(_stream_handler)


Params = ParamSpec('Params')
ReturnType = TypeVar('ReturnType')


def log_exception(func: Callable[Params, ReturnType]) -> Callable[Params, ReturnType]:
    def wrapper(*args: Params.args, **kwargs: Params.kwargs) -> ReturnType:
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception('Exception caught from logging decorator.')
            raise

    return wrapper

import os
from typing import TypeVar
import dotenv

dotenv.load_dotenv('.env')

if os.path.isfile('/run/secrets/app_secrets'):
    dotenv.load_dotenv('/run/secrets/app_secrets')

from logger import log_exception, logger  # NOQA: E402


T = TypeVar('T', str, int, bool)


@log_exception
def get_env(type_: type[T], key: str, default: str | None = None) -> T:
    value = os.environ.get(key, default)

    assert value is not None, f'${key} env variable is required.'

    wrong_type_error = TypeError(f'Wrong type for ${key}, must be "{type_}".')

    if type_ is bool:
        if not value:
            return type_(False)

        if not value.isnumeric():
            raise wrong_type_error

        return type_(int(value))

    if type_ is int:
        if not value.isnumeric():
            raise wrong_type_error

        return type_(value)

    return type_(value)


SPOTIFY_API_SEARCH_URL = get_env(str, 'SPOTIFY_API_SEARCH_URL')
SPOTIFY_API_TOKEN_URL = get_env(str, 'SPOTIFY_API_TOKEN_URL')
SPOTIFY_API_CLIENT_ID = get_env(str, 'SPOTIFY_API_CLIENT_ID')
SPOTIFY_API_CLIENT_SECRET = get_env(str, 'SPOTIFY_API_CLIENT_SECRET')

FFMPEG_PATH = get_env(str, 'FFMPEG_PATH', '/usr/bin/ffmpeg')

MOCK_MODE = get_env(bool, 'MOCK_MODE', '0')
if MOCK_MODE:
    logger.warning('$MOCK_MODE set to True. Using mock data instead.')

CACHE_PATH = get_env(str, 'CACHE_PATH', 'cache.json')

from typing import Any
from logger import logger
from datetime import datetime, timedelta, timezone
import json
import settings


CacheItem = tuple[Any, int]


class CacheStorage:
    def __init__(self, cache_path: str | None = None, item_lifetime: timedelta = timedelta(seconds=10)) -> None:
        self.cache_path: str = cache_path or settings.CACHE_PATH
        self.mem_cache: dict[str, CacheItem] = {}
        self.item_lifetime: timedelta = item_lifetime

    def _has_expired(self, item: CacheItem) -> bool:
        return datetime.now(timezone.utc).timestamp() > item[1]

    def _create_item(self, value: Any) -> CacheItem:
        new_expiration = datetime.now(timezone.utc) + self.item_lifetime
        return (value, int(new_expiration.timestamp()))

    def get_item(self, key: str) -> Any | None:
        if key in self.mem_cache:
            item = self.mem_cache[key]

            if not self._has_expired(item):
                return item

        item: CacheItem | None = None
        try:
            with open(self.cache_path) as fp:
                cache: dict[str, Any] = json.load(fp)
                item = cache.get(key)

        except (FileNotFoundError, json.JSONDecodeError) as error:
            logger.debug(f'Error loading {self.cache_path}: {error}')

        if item is None:
            return

        if self._has_expired(item):
            return None

        return item[0]

    def set_item(self, key: str, value: Any) -> None:
        item = self._create_item(value)
        try:
            with open(self.cache_path, 'r+') as fp:
                cache: dict[str, Any] = json.load(fp)
                cache[key] = item
                fp.seek(0)
                json.dump(cache, fp)
                fp.truncate()

        except (FileNotFoundError, json.JSONDecodeError) as error:
            logger.debug(f'Error loading {self.cache_path}: {error}')

            with open(self.cache_path, 'w') as fp:
                json.dump({key: item}, fp)

            logger.debug('New cache file created.')

        self.mem_cache[key] = item

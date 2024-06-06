# FastAPI
from fastapi.responses import FileResponse
from fastapi import Depends, FastAPI, Query
from pydantic import ValidationError
from starlette.background import BackgroundTask

# Pytube
import pytube  # type: ignore[reportMissingTypeStubs]
import pytube.exceptions  # type: ignore[reportMissingTypeStubs]

# EyeD3
from eyed3.id3.frames import ImageFrame  # type: ignore[reportMissingTypeStubs]
from eyed3.id3.tag import Tag  # type: ignore[reportMissingTypeStubs]

# Utils
from typing import Annotated, Literal
import httpx
from urllib.parse import unquote as url_decode
import asyncio
import tempfile
import os
import time
import json

# App
from cache_storage import CacheStorage
from logger import log_exception, logger
import settings
from utils import (
    VideoSearchResult,
    TrackMetadata,
    PartialTrackMetadata,
    search_track_metadata_options,
    download_youtube_video,
    convert_mp4_to_mp3
)


def get_cache_storage() -> CacheStorage:
    return cache_storage


CacheStorageDep = Annotated[CacheStorage, Depends(get_cache_storage)]


app = FastAPI(title='Mobile Music Downloader API')
cache_storage = CacheStorage()


@log_exception
@app.get('/ping')
async def ping() -> Literal['pong!']:
    return 'pong!'


@log_exception
@app.get('/search/video', response_model=list[VideoSearchResult], description='Search YouTube videos.')
async def search_videos(cache: CacheStorageDep, query: Annotated[str, Query(description='The value must be urlencoded.')]) -> list[VideoSearchResult]:
    if settings.MOCK_MODE:
        await asyncio.sleep(2)
        with open('mock.json') as fp:
            return json.load(fp)['videos']

    query = url_decode(query.strip())
    cache_key = 'search_video_' + query.lower()

    cached_result: list[dict[str, str]] | None = cache.get_item(cache_key)
    if cached_result is not None:
        try:
            return [
                VideoSearchResult.model_validate(result)
                for result in cached_result
            ]
        except ValidationError:
            pass

    search = pytube.Search(query)

    results: list[pytube.YouTube] | None = search.results

    if not results:
        return []

    final_results = [
        VideoSearchResult(
            video_id=result.video_id,
            watch_url=result.watch_url,
            title=result.title,
            author=result.author,
            thumbnail_url=sorted(
                result.vid_info['videoDetails']['thumbnail']['thumbnails'],  # type: ignore
                key=lambda t: t['width'] * t['height'],  # type: ignore
                reverse=True
            )[0]['url'].split('?', 1)[0]
        )
        for result in results
    ]
    cache.set_item(cache_key, [result.model_dump() for result in final_results])
    return final_results


@log_exception
@app.get(
    '/search/track',
    response_model=list[TrackMetadata],
    description='Search for tracks\' metadata using the Spotify API. All query parameter values must be urlencoded.'
)
async def search_tracks(
    cache: CacheStorageDep,
    title: Annotated[str, Query()],
    artist: Annotated[str, Query()],
    album: Annotated[str | None, Query()] = None,
) -> list[TrackMetadata]:
    if settings.MOCK_MODE:
        await asyncio.sleep(2)
        with open('mock.json') as fp:
            return json.load(fp)['tracks']

    partial_metadata = PartialTrackMetadata(
        title=url_decode(title),
        artist=url_decode(artist),
        album=url_decode(album) if album else None,
    )
    track_metadata_options = await search_track_metadata_options(partial_metadata, cache)
    return track_metadata_options


@log_exception
@app.get(
    '/download',
    response_class=FileResponse,
    description='Downloads a YouTube video\'s audio as mp3 with the passed metadata. All query parameter values must be urlencoded.',
    responses={
        '200': {
            'description': 'Successful Response',
            'content': {
                'audio/mpeg': {}
            }
        },
        '404': {
            'description': 'Video Not Found',
            'content': {
                'application/json': {
                    'example': 'No video found with ID <video_id>'
                }
            }
        }
    }
)
def download_video_as_mp3(
    video_id: Annotated[str, Query()],
    title: Annotated[str, Query()],
    artist: Annotated[str, Query()],
    album: Annotated[str, Query()],
    album_cover_url: Annotated[str, Query()]
) -> FileResponse:
    if settings.MOCK_MODE:
        time.sleep(4)
        return FileResponse('mock.mp3')

    video_id = url_decode(video_id)

    metadata = TrackMetadata(
        title=url_decode(title),
        artist=url_decode(artist),
        album=url_decode(album),
        album_cover_url=url_decode(album_cover_url)
    )

    tmp_mp4_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
    tmp_mp4_file.close()

    tmp_mp3_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
    tmp_mp3_file.close()

    def remove_tmp_files() -> None:
        os.remove(tmp_mp4_file.name)
        os.remove(tmp_mp3_file.name)

    try:
        download_youtube_video(video_id, tmp_mp4_file.name)

        convert_mp4_to_mp3(mp4_filepath=tmp_mp4_file.name, mp3_filepath=tmp_mp3_file.name)

        tag = Tag()

        tag.title = metadata.title
        tag.artist = metadata.artist
        tag.album = metadata.album

        response = httpx.get(metadata.album_cover_url)

        if response.status_code not in range(200, 300):
            logger.error(f'Could not fetch album cover. HTTP code: {response.status_code}')

        tag.images.set(  # type: ignore[reportOptionalMemberAccess]
            img_data=response.read(),
            type_=ImageFrame.FRONT_COVER,
            mime_type='image/jpeg',
            description=f'{metadata.album} Front Cover'
        )

        # Some music players doesn't recognize the artist when the track doesn't have the "lyrics" tag
        tag.lyrics.set(text='', description='', lang=b'   ')  # type: ignore[reportOptionalMemberAccess]

        tag.save(filename=tmp_mp3_file.name)

        return FileResponse(tmp_mp3_file.name, media_type='audio/mpeg', background=BackgroundTask(remove_tmp_files))

    except Exception:
        logger.exception('Exception downloading youtube track.')
        remove_tmp_files()
        raise

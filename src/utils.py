# FastAPI
import subprocess
from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator
from pydantic.alias_generators import to_camel

# Pytube
import pytube  # type: ignore[reportMissingTypeStubs]
import pytube.exceptions  # type: ignore[reportMissingTypeStubs]

# Utils
from urllib.parse import quote as url_encode
import httpx
from datetime import datetime, timezone
import os

# App
from logger import logger
from cache_storage import CacheStorage
import settings


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True
    )


class VideoSearchResult(CamelModel):
    video_id: str
    watch_url: str
    title: str
    author: str
    thumbnail_url: str


class PartialTrackMetadata(BaseModel):
    title: str
    artist: str
    album: str | None


class TrackMetadata(CamelModel):
    title: str
    artist: str
    album: str
    album_cover_url: str


class SpotifyAlbumImage(BaseModel):
    url: str
    height: int
    width: int


class SpotifyAlbum(BaseModel):
    name: str
    images: list[SpotifyAlbumImage]


class SpotifyArtist(BaseModel):
    name: str


class SpotifyTrack(BaseModel):
    name: str
    album: SpotifyAlbum
    artists: list[SpotifyArtist]


class SpotifyTracksResult(BaseModel):
    total: int
    items: list[SpotifyTrack]


class SpotifySearchResponse(BaseModel):
    tracks: SpotifyTracksResult


class SpotifyAPIToken(BaseModel):
    token: str
    expires_at: int

    @field_validator('expires_at')
    @classmethod
    def validate_expiration_timestamp(cls, expires_at: int) -> int:
        if expires_at <= datetime.now(timezone.utc).timestamp():
            raise ValueError('Token has expired.')

        return expires_at


async def get_spotify_api_token(cache: CacheStorage | None = None) -> str | None:
    SPOTIFY_API_TOKEN_CACHE_KEY = 'spotify_api_token'

    if cache is not None:
        try:
            cached_token = SpotifyAPIToken.model_validate(cache.get_item(SPOTIFY_API_TOKEN_CACHE_KEY))
            logger.debug('Spotify token retrieved from cache.')

            return cached_token.token
        except ValidationError:
            pass

    async with httpx.AsyncClient() as client:
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        content = f'grant_type=client_credentials&client_id={settings.SPOTIFY_API_CLIENT_ID}&client_secret={settings.SPOTIFY_API_CLIENT_SECRET}'

        response = await client.post(settings.SPOTIFY_API_TOKEN_URL, headers=headers, content=content)

    data = response.json()

    if 'error' in data:
        logger.error('Error fetching a new spotify access token. Error:', data['error'])
        return

    token = SpotifyAPIToken(
        token=data['access_token'],
        expires_at=int(datetime.now(timezone.utc).timestamp()) + int(data['expires_in'])
    )

    if cache:
        cache.set_item(SPOTIFY_API_TOKEN_CACHE_KEY, token.model_dump())

    logger.info('Fetched new Spotify access token.')
    return token.token


async def search_track_metadata_options(partial_metadata: PartialTrackMetadata, cache: CacheStorage | None = None) -> list[TrackMetadata]:
    cache_key = str(partial_metadata).lower()

    if cache:
        try:
            cached_metadata: list[dict[str, str]] | None = cache.get_item(cache_key)
            if cached_metadata is not None:
                return [
                    TrackMetadata.model_validate(data)
                    for data in cached_metadata
                ]
        except ValidationError:
            pass

    query = partial_metadata.title + ' ' + partial_metadata.artist

    filters = f'track:{partial_metadata.title} artist:{partial_metadata.artist}'

    if partial_metadata.album:
        filters += f' album:{partial_metadata.album}'

    q = url_encode((query + ' ' + filters).replace(' ', '%20'))

    token = await get_spotify_api_token(cache)

    if token is None:
        logger.error('Could not retrieve spotify access token.')
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    async with httpx.AsyncClient() as client:
        headers = {
            'Authorization': f'Bearer {token}'
        }
        response = await client.get(settings.SPOTIFY_API_SEARCH_URL + f'?q={q}&type=track&limit=10', headers=headers)
        logger.debug('Spotify search done.')

    if response.status_code not in range(200, 300):
        logger.error(f'Error fetching the track metadata. HTTP code: {response.status_code}')
        return []

    try:
        data = SpotifySearchResponse.model_validate(response.json())
    except ValidationError:
        logger.error('Spotify search response with an unexpected format.')
        return []

    metadata_options = [
        TrackMetadata(
            artist=' & '.join(artist.name for artist in track.artists),
            title=track.name,
            album=track.album.name,
            album_cover_url=track.album.images[0].url  # sorted in non-increasing order
        )
        for track in data.tracks.items
    ]

    if cache:
        value = [model.model_dump() for model in metadata_options]
        cache.set_item(cache_key, value)

    return metadata_options


def download_youtube_video(video_id: str, filepath: str) -> None:
    if not os.path.isfile(filepath):
        raise IOError(f'`filepath` must be a valid filepath: {filepath}')

    try:
        audio_stream = pytube.YouTube.from_id(video_id).streams.get_audio_only('mp4')

        if not audio_stream:
            raise pytube.exceptions.VideoUnavailable(video_id)

    except pytube.exceptions.VideoUnavailable:
        logger.debug(f'Youtube video with ID {video_id} not found.')
        raise HTTPException(status.HTTP_404_NOT_FOUND, f'No video found with ID {video_id}')

    logger.debug(f'Downloading audio track: {audio_stream}')
    audio_stream.download(
        output_path=os.path.dirname(filepath),
        filename=os.path.basename(filepath),
        skip_existing=False,
        max_retries=3
    )


def convert_mp4_to_mp3(mp4_filepath: str, mp3_filepath: str) -> None:
    if not mp4_filepath.endswith('.mp4') or not os.path.isfile(mp4_filepath):
        raise IOError('`mp4_filepath` must be an existing file with the ".mp4" extension:', mp4_filepath)

    if not mp3_filepath.endswith('.mp3') or not os.path.isfile(mp3_filepath):
        raise IOError('`mp3_filepath` must be an existing file with the ".mp3" extension:', mp3_filepath)

    process = subprocess.run(
        f'{settings.FFMPEG_PATH} -i {mp4_filepath} -ab 320k -y {mp3_filepath}'.split(' '),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if process.returncode != 0:
        raise Exception('Could not convert mp4 to mp3.')

    logger.debug('Successfully converted mp4 to mp3.')

import asyncio
import datetime

from fastapi import Request, APIRouter
from fastapi.security import OAuth2PasswordBearer
from fastapi.encoders import jsonable_encoder
from slowapi.util import get_remote_address
from slowapi import Limiter

from app.internal.Youtube.youtube_api_wrapper import youtube_client

from app.internal.errors.global_exceptions import InvalidBody
from app.internal.errors.youtube_exceptions import YoutubeInfoExtractorError

from app.internal.utilities.auth import require_valid_token
from app.utils.loggers import base_logger as logger
from app.internal.utilities.task import task_manager

import app.connectors as connectors

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# ------------------ ROUTEURS ---------------------- #


@router.get("/api/youtube/search/{gameID}")
@require_valid_token
async def get_matching_video(request: Request, gameID: int) -> dict:
    logger.info("Searching best matching data from Source 1 for game ID [%s].", gameID)

    game_data = await connectors.iris_query_wrapper.get_base_game_data(gameID)

    if game_data is None:
        raise YoutubeInfoExtractorError(
            "Game not found in database", error_http_code=404
        )
    game_name = game_data.get("name")
    release_date: datetime.date = game_data.get("first_release_date")

    res = await youtube_client.video_match(game_name, release_date)

    return {"data": res}


@router.get("/api/youtube/chapters/")
@require_valid_token
async def get_chapters(
    request: Request,
    gameID: str,
    mediaID: str,
    mediaType: str,
) -> dict:
    if mediaType == "video":
        res = await youtube_client.get_video_chapters(mediaID, gameID)
    elif mediaType == "playlist":
        res = await youtube_client.get_playlist_chapters(mediaID, gameID)
    else:
        raise InvalidBody("mediaType must be either video or playlist")

    return {"data": res}


@router.get("/api/youtube/download/video/{videoID}")
@require_valid_token
async def download_video(request: Request, videoID: str) -> dict:
    task = task_manager.create_task(
        "download-audio", "boolean", "Downloading audio [%s]" % videoID
    )
    task.add_object_id("video_id", videoID)

    loop = asyncio.get_event_loop()
    loop.create_task(youtube_client.download_video(videoID, task.complete_task))

    return jsonable_encoder(task.toDict())


@router.get("/api/youtube/download/playlist/{playlistID}")
@require_valid_token
async def download_playlist(request: Request, playlistID: str) -> dict:
    task = task_manager.create_task(
        "download-playlist", "boolean", "Downloading playlist [%s]" % playlistID
    )
    task.add_object_id("playlist_id", playlistID)

    loop = asyncio.get_event_loop()
    loop.create_task(youtube_client.download_playlist(playlistID, task.complete_task))

    return jsonable_encoder(task.toDict())


@router.get("/api/youtube/chapters/align")
@require_valid_token
async def align_chapter(
    request: Request, videoID: str, computeGraph: bool = False
) -> dict:
    chapters = await youtube_client.align_chapters(videoID, computeGraph)

    return {"data": chapters}


@router.get("/api/youtube/audio/format/{media_id}")
@require_valid_token
async def format_audio(request: Request, media_id: str) -> dict:
    game_id, album_id, tracks = await youtube_client.format_audio(media_id)

    await connectors.iris_query_wrapper.add_game_tracks(game_id, album_id, tracks, media_id)

    return {"data": "OK"}

from fastapi import Depends, Request, APIRouter
from fastapi.security import OAuth2PasswordBearer
from slowapi.util import get_remote_address
from slowapi import Limiter
import json

from app.clients.igdb_cli import IGDB
from app.clients.iris_cli import iris
from app.clients.s1_cli import s1
from app.utils.errors import raiseNoGameFound, raiseNoChapterFound
from app.utils.auth import admin_auth
from app.utils.loggers import base_logger

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

IGDB_cli = IGDB()
iris_cli = iris()
s1_cli = s1()


@router.get("/matching_games")
@limiter.limit("60/minute")
def get_best_matching_games(request: Request, game: str, token: str = Depends(oauth2_scheme)) -> dict:
    # Get the best matching games from the IGDB API

    admin_auth(token)

    base_logger.info("Searching matching games for input [%s].", game)

    res = IGDB_cli.matching_games(game)

    return {"data": res}


@router.post("/new_game")
@limiter.limit("60/minute")
def push_new_game(request: Request, gameID: int, token: str = Depends(oauth2_scheme)) -> dict:
    # Push a new game to the database

    admin_auth(token)

    base_logger.info("Obtaining the metadata of the game ID [%s].", gameID)

    game_data = IGDB_cli.new_game(gameID)

    base_logger.info(
        "Pushing metadata of the game ID [%s] to database.", gameID)

    iris_cli.push_new_game(game_data)

    base_logger.info("Game ID [%s] - Push successfull to database.", gameID)

    return {"data": game_data}


@router.delete("/del/game")
@limiter.limit("60/minute")
def delete_game(request: Request, gameID: int, token: str = Depends(oauth2_scheme)) -> None:
    # Delete a game from the database

    admin_auth(token)

    iris_cli.del_game(gameID)

    base_logger.info("Deleted Game ID [%s].", gameID)


@router.get("/s1/match")
@limiter.limit("60/minute")
def get_matching_video(request: Request, gameID: int, token: str = Depends(oauth2_scheme)) -> dict:
    # Get the best matching video from the Source 1 API

    admin_auth(token)

    base_logger.info(
        "Searching best matching data from Source 1 for game ID [%s].", gameID)

    try:
        name = iris_cli.getGameName(gameID)
        res = s1_cli.best_video_match(name)

        return {"data": res}
    except:
        base_logger.error(
            "No matching game found in database for ID [%s].", gameID)
        raiseNoGameFound(gameID)


@router.get("/s1/chapter")
@limiter.limit("60/minute")
def get_chapter_s1(request: Request, videoID: str, token: str = Depends(oauth2_scheme)) -> dict:
    # Get the chapter data from the Source 1

    admin_auth(token)

    base_logger.info(
        "Obtaining the chapter data from Source 1 for video ID [%s].", videoID)
    chapters = s1_cli.get_chapter(videoID)
    if chapters == []:
        raiseNoChapterFound(videoID)

    # Save chapter data in a file
    file_path = f"/bacchus/chapters/{videoID}.json"
    with open(file_path, "w") as f:
        f.write(json.dumps(chapters))

    return {"data": chapters}


@router.get("/s1/download")
@limiter.limit("60/minute")
async def get_download_s1(request: Request, vidID: str, gameID: int, token: str = Depends(oauth2_scheme)) -> dict:
    # Download the audio data from the Source 1

    admin_auth(token)

    base_logger.info(
        "Downloading audio data from Source 1 for game ID [%s].", gameID)
    audio_duration: int = s1_cli.downloader(vidID, gameID)

    # Correction of audio timestamps
    s1_cli.fix_audio_timestamp(gameID, vidID)

    return {"data": {"audio_duration": audio_duration}}


@router.get("/s1/format_file")
@limiter.limit("60/minute")
def get_file_format_s1(request: Request, gameID: int, vidID: str, token: str = Depends(oauth2_scheme)) -> dict:
    # Format the audio data from the Source 1

    admin_auth(token)

    base_logger.info(
        "Formating audio data from Source 1 for game ID [%s].", gameID)

    # Get the chapter data from the file
    file_path = f"/bacchus/chapters/{vidID}.json"
    with open(file_path, "r") as f:
        chapters = json.loads(f.read())

    s1_cli.full_audio_format(gameID, chapters)

    return {"data": 'tracklist'}

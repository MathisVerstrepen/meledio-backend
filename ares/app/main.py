# type: ignore

from fastapi import FastAPI, Depends, Request, Path, Query
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import redis
import json
import time
import logging.handlers
from timeit import default_timer as timer

from app.clients.igdb_cli import IGDB
from app.clients.iris_cli import iris, iris_user
from app.clients.s1_cli import s1
from app.utils.errors import raiseNoGameFound, raiseNoChapterFound, raiseNoUserFound, raiseAuthFailed

from dotenv import load_dotenv
load_dotenv()

limiter = Limiter(key_func=get_remote_address)
ares = FastAPI()
ares.state.limiter = limiter
ares.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# Init Redis connections
r_glob = redis.Redis(host="atlas", port=6379, db=1, password=os.getenv("REDIS_SECRET"))
r_games = redis.Redis(host="atlas", port=6379, db=0, password=os.getenv("REDIS_SECRET"))
r_users = redis.Redis(host="atlas", port=6379, db=2, password=os.getenv("REDIS_SECRET"))

# Init API clients
IGDB_cli = IGDB()
iris_cli = iris()
s1_cli = s1()

f = open('./app/schema.json')
db_schema: dict = json.load(f)

origins = ["*"]
ares.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import app.utils.loggers
base_logger = app.utils.loggers.base_logger


def admin_auth(token: str):
    if token != os.getenv("ARES_TOKEN"):
        raiseAuthFailed()


@ares.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(f"{process_time:0.4f} sec")
    return response


@ares.get("/matching_games")
def get_best_matching_games(game: str, token: str = Depends(oauth2_scheme)) -> dict:
    # Get the best matching games from the IGDB API
    
    admin_auth(token)

    base_logger.info("Searching matching games for input [%s].", game)

    res = IGDB_cli.matching_games(game)

    return {"data": res}


@ares.post("/new_game")
@limiter.limit("60/minute")
def push_new_game(request: Request, gameID: int, token: str = Depends(oauth2_scheme)) -> dict:
    # Push a new game to the database
    
    admin_auth(token)

    base_logger.info("Obtaining the metadata of the game ID [%s].", gameID)

    game_data = IGDB_cli.new_game(gameID)

    base_logger.info("Pushing metadata of the game ID [%s] to database.", gameID)

    iris_cli.push_new_game(game_data)

    base_logger.info("Game ID [%s] - Push successfull to database.", gameID)

    return {"data": game_data}


@ares.delete("/del/game")
@limiter.limit("60/minute")
def delete_game(request: Request, gameID: int, token: str = Depends(oauth2_scheme)) -> None:
    # Delete a game from the database
    
    admin_auth(token)

    iris_cli.del_game(gameID)

    base_logger.info("Deleted Game ID [%s].", gameID)


@ares.get("/s1/match")
@limiter.limit("60/minute")
def get_matching_video(request: Request, gameID: int, token: str = Depends(oauth2_scheme)) -> dict:
    # Get the best matching video from the Source 1 API
    
    admin_auth(token)

    base_logger.info("Searching best matching data from Source 1 for game ID [%s].", gameID)
    
    try:
        name = iris_cli.getGameName(gameID)
        res = s1_cli.best_video_match(name)
        
        return {"data": res}
    except:
        base_logger.error("No matching game found in database for ID [%s].", gameID)
        raiseNoGameFound(gameID)


@ares.get("/s1/chapter")
@limiter.limit("60/minute")
def get_chapter_s1(request: Request, videoID: str, token: str = Depends(oauth2_scheme)) -> dict:
    # Get the chapter data from the Source 1
    
    admin_auth(token)

    base_logger.info("Obtaining the chapter data from Source 1 for video ID [%s].", videoID)    
    chapters = s1_cli.get_chapter(videoID)
    if chapters == []:
        raiseNoChapterFound(videoID)
    
    # Save chapter data in a file
    file_path = f"/bacchus/chapters/{videoID}.json"
    with open(file_path, "w") as f:
        f.write(json.dumps(chapters))
    
    return {"data": chapters}


@ares.get("/s1/download")
@limiter.limit("60/minute")
async def get_download_s1(request: Request, vidID: str, gameID: int, token: str = Depends(oauth2_scheme)) -> dict:
    # Download the audio data from the Source 1
    
    admin_auth(token)

    base_logger.info("Downloading audio data from Source 1 for game ID [%s].", gameID)
    audio_duration: int = s1_cli.downloader(vidID, gameID)
    
    # Correction of audio timestamps
    s1_cli.fix_audio_timestamp(gameID, vidID)

    return {"data": {"audio_duration": audio_duration}}


@ares.get("/s1/format_file")
@limiter.limit("60/minute")
def get_file_format_s1(request: Request, gameID: int, vidID: str, token: str = Depends(oauth2_scheme)) -> dict:
    # Format the audio data from the Source 1
    
    admin_auth(token)

    base_logger.info("Formating audio data from Source 1 for game ID [%s].", gameID)
    
    # Get the chapter data from the file
    file_path = f"/bacchus/chapters/{vidID}.json"
    with open(file_path, "r") as f:
        chapters = json.loads(f.read())
        
    s1_cli.full_audio_format(gameID, chapters)

    return {"data": 'tracklist'}


@ares.get("/r1/new")
# @limiter.limit("5/minute")
async def add_new_user_redis(userData: object) -> None:
    print(userData)

    userData = json.loads(userData)
    userData["is_admin"] = False
    iris_user_cli = iris_user()
    exist = iris_user_cli.get_user_exist(userData["id"])

    if exist:
        r_users.json().set(userData["id"], "$", userData)
    else:
        raiseNoUserFound(userData["id"])

    return {}


@ares.get("/r1/get")
def get_user_redis(data: object) -> None:
    data = json.loads(data)
    elements = data["el"]

    iris_user_cli = iris_user()
    exist = iris_user_cli.get_user_exist(data["id"])

    if exist:
        r_res = r_users.json().get(data["id"], f"${elements}")
        res = {elements[i]: r_res[i] for i in range(len(r_res))}

    else:
        raiseNoUserFound(data["id"])

    return {"data": res}


@ares.get("/v1/game")
# @limiter.limit("60/minute")
async def get_game_data(request: Request, gID: int, labels: list[str] = Query(default=['base']), debug: bool = False,
                        forceDB: bool = False) -> dict:
    fData = {}
    debugData = {}

    for label in labels:
        if label == 'base':
            start = timer()
            res = iris_cli.get_base_game_data(gID, forceDB)
            end = timer()
            fData['base'] = res
            if debug: debugData['base'] = (end - start) * 1000

        elif label in ['artworks', 'cover', 'screenshots']:
            start = timer()
            res = iris_cli.get_media_game_data(gID, label)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end - start) * 1000

        elif label == 'alternative_name':
            start = timer()
            res = iris_cli.get_alternative_name_game_data(gID)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end - start) * 1000

        elif label == 'album':
            start = timer()
            res = iris_cli.get_album_game_data(gID, forceDB)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end - start) * 1000

        elif label == 'involved_companies':
            start = timer()
            res = iris_cli.get_involved_companies_game_data(gID)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end - start) * 1000

        elif label in ['dlcs', 'expansions', 'expanded_games', 'similar_games', 'standalone_expansions']:
            start = timer()
            res = iris_cli.get_extra_content_game_data(gID, label)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end - start) * 1000

        elif label == 'genre':
            start = timer()
            res = iris_cli.get_genre_game_data(gID)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end - start) * 1000

        elif label == 'theme':
            start = timer()
            res = iris_cli.get_theme_game_data(gID)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end - start) * 1000

        elif label == 'keyword':
            start = timer()
            res = iris_cli.get_keyword_game_data(gID)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end - start) * 1000

    return {"debug_data": debugData, "gameID": gID, "data": fData}


@ares.get("/v1/game/random/{limit}")
# @limiter.limit("60/minute")
async def get_random_games(request: Request, labels: list[str] = Query(default=['base']),
                        limit: int = Path(0, title="Number of random games", gt=0, le=1000), debug: bool = False,
                        forceDB: bool = False) -> dict:
    # base_logger.info(labels)
    data = []
    randID: list = iris_cli.getRandomCompleteGameIDs(limit)
    for gameID in randID:
        data.append(await get_game_data(request, gameID[0], labels, debug, forceDB))

    return {"data": data}


@ares.get("/v1/game/top/rating/{limit}")
# @limiter.limit("60/minute")
async def get_top_rated_games(request: Request, labels: list[str] = Query(default=['base']),
                            limit: int = Path(0, title="Number of top rating games", gt=0, le=1000),
                            debug: bool = False, forceDB: bool = False) -> dict:
    # base_logger.info(labels)
    data = []
    topRateIDs: list = iris_cli.getTopRatedGameIDs(limit)
    for gameID in topRateIDs:
        data.append(await get_game_data(request, gameID[0], labels, debug, forceDB))

    return {"data": data}


@ares.get("/v1/collection/top/{limit}")
# @limiter.limit("60/minute")
async def get_top_rated_collection(request: Request, labels: list[str] = Query(default=['base']),
                                limit: int = Path(0, title="Number of top rating collection", gt=0, le=1000),
                                debug: bool = False, forceDB: bool = False) -> dict:
    # base_logger.info(labels)
    data = {}
    topRateIDs: list = iris_cli.getTopRatedCollectionIDs(limit)

    for gameID, collectionID, collectionName in topRateIDs:
        data.setdefault(collectionID, {})['collectionName'] = collectionName
        data[collectionID].setdefault('gameData', []).append(
            await get_game_data(request, gameID, labels, debug, forceDB))

    return {"data": data}


@ares.get("/v1/collection/{collectionID}")
# @limiter.limit("60/minute")
async def get_collection_by_id(request: Request, labels: list[str] = Query(default=['base']),
                            collectionID: int = Path(0, title="Collection ID"), debug: bool = False,
                            forceDB: bool = False) -> dict:
    base_logger.info(labels)
    collectionData: list = iris_cli.getCollectionData(collectionID)
    collectionGameID: list = iris_cli.getGameIDofCollection(collectionID)

    data = {
        "collection": {
            "name": collectionData[0],
            "slug": collectionData[1]
        },
        "games": {}
    }
    base_logger.info(data)
    for game in collectionGameID:
        data["games"][game[0]] = await get_game_data(request, game[0], labels, debug, forceDB)

    return {"data": data}


@ares.get("/v1/game/search/{searchText}")
# @limiter.limit("60/minute")
async def get_collection_by_id(request: Request, searchText: str = Path(0, title="Search game text"),
                            debug: bool = False) -> dict:
    searchResults = iris_cli.searchGameByName(searchText)

    return {"data": searchResults}

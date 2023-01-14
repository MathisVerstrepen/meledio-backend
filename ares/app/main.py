from fastapi import FastAPI, Depends, HTTPException, status, Request, Path, Query
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import redis
import json
import time
import logging
from timeit import default_timer as timer

from app.functions.IGDB import IGDB
from app.functions.iris import iris, iris_user
from app.functions.s1 import s1
from dotenv import load_dotenv

load_dotenv()

limiter = Limiter(key_func=get_remote_address)
ares = FastAPI()
ares.state.limiter = limiter
ares.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

r_glob = redis.Redis(host="atlas", port=6379, db=1, password=os.getenv("REDIS_SECRET"))
r_games = redis.Redis(host="atlas", port=6379, db=0, password=os.getenv("REDIS_SECRET"))
r_users = redis.Redis(host="atlas", port=6379, db=2, password=os.getenv("REDIS_SECRET"))

iris_cli = iris(r_glob, r_games)

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

logging.basicConfig(
    filename="app/logs/ares.log",
    encoding="utf-8",
    level=logging.INFO,
    format="%(asctime)s -- %(levelname)s -- %(message)s",
)


def auth(token: str) -> None:
    if token != os.getenv("ARES_TOKEN"):
        logging.info("%s fail logging", token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def raiseNoGameFound(gameID: int) -> None:
    logging.error("No matching game found in database for ID [%s].", gameID)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No matching game found in database for ID {gameID}",
    )


def raiseNoChapterFound(gameID: int) -> None:
    logging.error("No chapter found in database for ID [%s].", gameID)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No chapter found in database for gameID {gameID}",
    )


def raiseNoUserFound(userID: int) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No user found in database for userID {userID}",
    )


@ares.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(f"{process_time:0.4f} sec")
    return response


@ares.get("/matching_games")
def get_best_matching_games(game: str, token: str = Depends(oauth2_scheme)) -> dict:

    auth(token)

    logging.info("Searching matching games for input [%s].", game)

    IGDB_client = IGDB(r_glob)
    res = IGDB_client.matching_games(game)

    return {"data": res["data"]}


@ares.post("/new_game")
@limiter.limit("60/minute")
def push_new_game(request: Request, gameID: int, token: str = Depends(oauth2_scheme)) -> dict:

    auth(token)

    logging.info("Obtaining the metadata of the game ID [%s].", gameID)
 
    IGDB_cli = IGDB(r_glob)
    game_data = IGDB_cli.new_game(gameID)

    logging.info("Pushing metadata of the game ID [%s] to database.", gameID)

    iris_cli = iris(r_glob, r_games)
    iris_cli.push_new_game(game_data["data"])

    logging.info("Game ID [%s] - Push successfull to database.", gameID)

    return {"data": game_data["data"]}


@ares.delete("/del/game")
@limiter.limit("60/minute")
def delete_game(request: Request, gameID: int, token: str = Depends(oauth2_scheme)) -> None:

    auth(token)

    iris_cli = iris(r_glob, r_games)
    iris_cli.del_game(gameID)

    logging.info("Deleted Game ID [%s].", gameID)


@ares.get("/s1/match")
@limiter.limit("60/minute")
def get_best_matching_games_s1(request: Request, gameID: int, token: str = Depends(oauth2_scheme)) -> dict:

    auth(token)

    logging.info("Searching best matching data from Source 1 for game ID [%s].", gameID)

    res_name = r_games.json().get(f"g:{gameID}", "$.name")
    if res_name:
        res_s1_match = r_games.json().get(f"g:{gameID}", "$.s1.match") 
        if not res_s1_match:
            s1_client = s1()
            res = s1_client.best_match(res_name[0])
            logging.info("Pushing Source 1 data for game ID [%s] to cache.", gameID)

            r_games.json().set(f"g:{gameID}", f"$.s1", {})
            r_games.json().set(f"g:{gameID}", f"$.s1.match", res)
        else:
            logging.info("Source 1 data for game ID [%s] already in database.", gameID)
            res = res_s1_match[0]
    else:
        raiseNoGameFound(gameID)

    return {"data": res}


@ares.get("/s1/chapter")
@limiter.limit("60/minute")
def get_chapter_s1(request: Request, id: str, gameID: int, token: str = Depends(oauth2_scheme)) -> dict:

    auth(token)

    logging.info("Searching chapters for data from Source 1 for game ID [%s].", gameID)

    res_name = r_games.json().get(f"g:{gameID}", "$.name")
    if res_name:
        res_s1_chapter = r_games.json().get(f"g:{gameID}", "$.s1.chapter")
        res_s1_chapter = False
        if not res_s1_chapter:
            s1_client = s1()
            res = s1_client.get_chapter(id)
            logging.info(
                "Pushing Source 1 chapters for game ID [%s] to cache.", gameID
            )
            r_games.json().set(f"g:{gameID}", "$.s1.videoID", id)
            r_games.json().set(f"g:{gameID}", "$.s1.chapter", res)
        else:
            logging.info(
                "Source 1 chapters for game ID [%s] already in database.", gameID
            )
            res = res_s1_chapter[0]
    else:
        raiseNoGameFound(gameID)

    return {"data": res}


@ares.get("/s1/download")
@limiter.limit("60/minute")
async def get_download_s1(request: Request, vidID: str, gameID: int, token: str = Depends(oauth2_scheme)) -> None:

    auth(token)

    logging.info("Downloading audio data from Source 1 for game ID [%s].", gameID)

    res_s1_chapter = r_games.json().get(f"g:{gameID}", "$.s1.chapter")
    if res_s1_chapter:

        s1_cli = s1()
        vid_dur: list = s1_cli.downloader(vidID, gameID)
    else:
        raiseNoChapterFound(gameID)

    return {"data": {"vid_dur": vid_dur}}


@ares.get("/s1/format_file")
@limiter.limit("60/minute")
async def get_file_format_s1(request: Request, gameID: int, vid_dur: int, token: str = Depends(oauth2_scheme)) -> None:

    auth(token)

    logging.info("Formating audio data from Source 1 for game ID [%s].", gameID)

    res_s1_chapter = r_games.json().get(f"g:{gameID}", "$.s1.chapter")

    s1_cli = s1()
    tracklist: list = s1_cli.file_formater(
        gameID, res_s1_chapter[0], vid_dur, r_games
    )

    return {"data": tracklist}


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
async def get_game_data(request: Request, gID: int, labels: list[str] = Query(default=['base']), debug: bool = False, forceDB: bool = False) -> dict:
    
    fData = {}
    debugData = {}

    for label in labels:
        if (label == 'base'):
            start = timer()
            res = iris_cli.get_base_game_data(gID, forceDB)
            end = timer()
            fData['base'] = res
            if debug: debugData['base'] = (end-start)*1000

        elif (label in ['artworks', 'cover', 'screenshots']):
            start = timer()
            res = iris_cli.get_media_game_data(gID, label)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end-start)*1000
            
        elif (label == 'alternative_name'):
            start = timer()
            res = iris_cli.get_alternative_name_game_data(gID)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end-start)*1000
            
        elif (label == 'album'):
            start = timer()
            res = iris_cli.get_album_game_data(gID, forceDB)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end-start)*1000
            
        elif (label == 'involved_companies'):
            start = timer()
            res = iris_cli.get_involved_companies_game_data(gID)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end-start)*1000
            
        elif (label in ['dlcs', 'expansions', 'expanded_games', 'similar_games', 'standalone_expansions']):
            start = timer()
            res = iris_cli.get_extra_content_game_data(gID, label)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end-start)*1000

        elif (label == 'genre'):
            start = timer()
            res = iris_cli.get_genre_game_data(gID)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end-start)*1000
            
        elif (label == 'theme'):
            start = timer()
            res = iris_cli.get_theme_game_data(gID)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end-start)*1000
            
        elif (label == 'keyword'):
            start = timer()
            res = iris_cli.get_keyword_game_data(gID)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end-start)*1000
            
    return {"debug_data": debugData, "gameID": gID, "data": fData}

@ares.get("/v1/game/random/{limit}")
# @limiter.limit("60/minute")
async def get_random_games(request: Request, labels: list[str] = Query(default=['base']), limit: int = Path(0, title="Number of random games", gt=0, le=1000), debug: bool = False, forceDB: bool = False) -> dict:
    
    # logging.info(labels)
    data = []
    randID: list = iris_cli.getRandomCompleteGameIDs(limit)
    for gameID in randID:
        data.append(await get_game_data(request, gameID[0], labels, debug, forceDB))
    
    return {"data": data}

@ares.get("/v1/game/rating/{limit}")
# @limiter.limit("60/minute")
async def get_top_rated_games(request: Request, labels: list[str] = Query(default=['base']), limit: int = Path(0, title="Number of top rating games", gt=0, le=1000), debug: bool = False, forceDB: bool = False) -> dict:
    
    # logging.info(labels)
    data = []
    topRateIDs: list = iris_cli.getTopRatedGameIDs(limit)
    for gameID in topRateIDs:
        data.append(await get_game_data(request, gameID[0], labels, debug, forceDB))
    
    return {"data": data}

@ares.get("/v1/game/collection/top/{limit}")
# @limiter.limit("60/minute")
async def get_top_rated_collection(request: Request, labels: list[str] = Query(default=['base']), limit: int = Path(0, title="Number of top rating collection", gt=0, le=1000), debug: bool = False, forceDB: bool = False) -> dict:
    
    # logging.info(labels)
    data = {}
    topRateIDs: list = iris_cli.getTopRatedCollectionIDs(limit)
    
    for gameID, collectionID, collectionName in topRateIDs:
        data.setdefault(collectionID, {})['collectionName'] = collectionName
        data[collectionID].setdefault('gameData', []).append(await get_game_data(request, gameID, labels, debug, forceDB))

    return {"data": data}

@ares.get("/v1/game/collection/{collectionID}")
# @limiter.limit("60/minute")
async def get_collection_by_id(request: Request, labels: list[str] = Query(default=['base']), collectionID: int = Path(0, title="Collection ID"), debug: bool = False, forceDB: bool = False) -> dict:
    
    logging.info(labels)
    collectionData: list = iris_cli.getCollectionData(collectionID)
    collectionGameID: list = iris_cli.getGameIDofCollection(collectionID)
    
    data = {
        "collection" : {
            "name": collectionData[0],
            "slug": collectionData[1]
        },
        "games" : {}
    }
    logging.info(data)
    for game in collectionGameID:
        data["games"][game[0]] = await get_game_data(request, game[0], labels, debug, forceDB)

    return {"data": data}

@ares.get("/v1/game/search/{searchText}")
# @limiter.limit("60/minute")
async def get_collection_by_id(request: Request, searchText: str = Path(0, title="Search game text"), debug: bool = False) -> dict:
    
    searchResults = iris_cli.searchGameByName(searchText)
    
    return {"data": searchResults}
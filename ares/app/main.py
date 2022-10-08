from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
import os
import redis
import json
import time
import logging

from app.functions.IGDB import IGDB
from app.functions.iris import iris, iris_user
from app.functions.s1 import s1
from dotenv import load_dotenv
load_dotenv()

ares = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

r_glob = redis.Redis(host='atlas', port=6379, db=0,
                     password=os.getenv('REDIS_SECRET'))
r_games = redis.Redis(host='atlas', port=6379, db=1,
                      password=os.getenv('REDIS_SECRET'))
r_users = redis.Redis(host='atlas', port=6379, db=2,
                      password=os.getenv('REDIS_SECRET'))

origins = ["*"]
ares.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(filename='app/logs/ares.log', encoding='utf-8', level=logging.DEBUG, format='%(asctime)s -- %(levelname)s -- %(message)s')


def auth(token: str) -> None:
    if (token != os.getenv('ARES_TOKEN')):
        logging.debug('%s fail logging', token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def raiseNoGameFound(gameID: int) -> None:
    logging.error('No matching game found in database for ID [%s].', gameID)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No matching game found in database for ID {gameID}"
    )


def raiseNoChapterFound(gameID: int) -> None:
    logging.error('No chapter found in database for ID [%s].', gameID)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No chapter found in database for gameID {gameID}"
    )

def raiseNoUserFound(userID: int) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No user found in database for userID {userID}"
    )

@ares.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(f'{process_time:0.4f} sec')
    return response


@ares.get("/matching_games")
def get_best_matching_games(game: str, token: str = Depends(oauth2_scheme)) -> dict:

    auth(token)
    
    logging.debug('Searching matching games for input [%s].', game)

    IGDB_client = IGDB(r_glob)
    res = IGDB_client.matching_games(game)

    return {"data": res['data']}


@ares.post("/new_game")
def push_new_game(gameID: int, token: str = Depends(oauth2_scheme)) -> dict:

    auth(token)
    
    logging.debug('Obtaining the metadata of the game ID [%s].', gameID)

    IGDB_cli = IGDB(r_glob)
    game_data = IGDB_cli.new_game(gameID)
    
    logging.debug('Pushing metadata of the game ID [%s] to database.', gameID)

    iris_cli = iris(r_glob, r_games)
    iris_cli.push_new_game(game_data['data'])
    
    logging.debug('Game ID [%s] - Push successfull to database.', gameID)

    return {"data": game_data['data']}


@ares.delete("/del/game")
def push_new_game(gameID: int, token: str = Depends(oauth2_scheme)) -> None:

    auth(token)

    iris_cli = iris(r_glob, r_games)
    iris_cli.del_game(gameID)
    
    logging.debug('Deleted Game ID [%s].', gameID)


@ares.get("/s1/match")
def get_best_matching_games_s1(gameID: int, token: str = Depends(oauth2_scheme)) -> dict:
 
    auth(token)
    
    logging.debug('Searching best matching data from Source 1 for game ID [%s].', gameID)

    res_name = r_games.json().get(gameID, '$.name')
    if res_name:
        res_s1_match = r_games.json().get(gameID, '$.s1.match')
        if not res_s1_match:
            s1_client = s1()
            res = s1_client.best_match(res_name[0])
            logging.debug('Pushing Source 1 data for game ID [%s] to cache.', gameID)
            r_games.json().set(gameID, "$.s1", {})
            r_games.json().set(gameID, '$.s1.match', res)
        else:
            logging.debug('Source 1 data for game ID [%s] already in database.', gameID)
            res = res_s1_match[0]
    else:
        raiseNoGameFound(gameID)

    return {"data": res}


@ares.get("/s1/chapter")
def get_chapter_s1(id: str, gameID: int, token: str = Depends(oauth2_scheme)) -> dict:

    auth(token)
    
    logging.debug('Searching chapters for data from Source 1 for game ID [%s].', gameID)

    res_name = r_games.json().get(gameID, '$.name')
    if res_name:
        res_s1_chapter = r_games.json().get(gameID, '$.s1.chapter')
        if not res_s1_chapter:
            s1_client = s1()
            res = s1_client.get_chapter(id)
            logging.debug('Pushing Source 1 chapters for game ID [%s] to cache.', gameID)
            r_games.json().set(gameID, '$.s1.videoID', id)
            r_games.json().set(gameID, '$.s1.chapter', res)
        else:
            logging.debug('Source 1 chapters for game ID [%s] already in database.', gameID)
            res = res_s1_chapter[0]
    else:
        raiseNoGameFound(gameID)

    return {"data": res}


@ares.get("/s1/download")
async def get_download_s1(vidID: str, gameID: int, token: str = Depends(oauth2_scheme)) -> None:

    auth(token)
    
    logging.debug('Downloading audio data from Source 1 for game ID [%s].', gameID)

    res_s1_chapter = r_games.json().get(gameID, '$.s1.chapter')
    if res_s1_chapter:

        r_games.json().set(gameID, '$.album', [])

        s1_cli = s1()
        vid_dur: list = s1_cli.downloader(vidID, gameID)
    else:
        raiseNoChapterFound(gameID)

    return {"data": {'vid_dur': vid_dur}}

@ares.get("/s1/format_file")
async def get_file_format_s1(vidID: str, gameID: int, vid_dur: int, token: str = Depends(oauth2_scheme)) -> None:

    auth(token)
    
    logging.debug('Formating audio data from Source 1 for game ID [%s].', gameID)

    res_s1_chapter = r_games.json().get(gameID, '$.s1.chapter')

    s1_cli = s1()
    tracklist: list = s1_cli.file_formater(vidID, gameID, res_s1_chapter[0],vid_dur, r_games)

    return {"data": tracklist}

@ares.get("/r1/new")
def add_new_user_redis(userData: object) -> None:

    print(userData)

    userData = json.loads(userData)
    userData['is_admin'] = False
    iris_user_cli = iris_user()
    exist = iris_user_cli.get_user_exist(userData['id'])

    if exist:
        r_users.json().set(userData['id'], '$', userData)
    else:
        raiseNoUserFound(userData['id']) 

    return {}

@ares.get("/r1/get")
def get_user_redis(data: object) -> None:

    data = json.loads(data)
    print(data)
    elements = data['el']

    iris_user_cli = iris_user()
    exist = iris_user_cli.get_user_exist(data['id'])

    if exist:
        r_res = r_users.json().get(data['id'], f'${elements}')
        res = {elements[i]: r_res[i] for i in range(len(r_res))}

    else:
        raiseNoUserFound(data['id']) 

    print(res)
    return {'data': res}

# type: ignore

from fastapi import FastAPI
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import json
import time
from app.clients.igdb_cli import IGDB
from app.clients.iris_cli import iris, iris_user
from app.clients.s1_cli import s1
from app.utils.errors import raiseNoUserFound
from app.utils.loggers import base_logger

from dotenv import load_dotenv
load_dotenv()

limiter = Limiter(key_func=get_remote_address)
ares = FastAPI()
ares.state.limiter = limiter
ares.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

from app.routers import game_construction
ares.include_router(game_construction.router)

from app.routers import v1_public
ares.include_router(v1_public.router)

# Init Redis connections
from app.utils.connection import REDIS_USERS

# Init API clients
IGDB_cli = IGDB()
iris_cli = iris()
s1_cli = s1()

f = open('./app/json/schema.json')
db_schema: dict = json.load(f)

origins = ["*"]
ares.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@ares.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(f"{process_time:0.4f} sec")
    return response


@ares.get("/r1/new")
# @limiter.limit("5/minute")
async def add_new_user_redis(userData: object) -> None:
    print(userData)

    userData = json.loads(userData)
    userData["is_admin"] = False
    iris_user_cli = iris_user()
    exist = iris_user_cli.get_user_exist(userData["id"])

    if exist:
        REDIS_USERS.json().set(userData["id"], "$", userData)
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
        r_res = REDIS_USERS.json().get(data["id"], f"${elements}")
        res = {elements[i]: r_res[i] for i in range(len(r_res))}

    else:
        raiseNoUserFound(data["id"])

    return {"data": res}
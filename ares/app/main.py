import time
from contextlib import asynccontextmanager
import requests

from fastapi import Request, FastAPI
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.internal.errors.igdb_exceptions import (
    IGDBInvalidReponseCode,
    IGDBInvalidReponse,
)
from app.internal.errors.global_exceptions import (
    InvalidBody,
    ObjectNotFound,
    GenericError,
)
from app.internal.errors.iris_exceptions import (
    ObjectAlreadyExistsError,
    SQLError,
    DatabaseCommitError,
)
from app.internal.errors.youtube_exceptions import YoutubeException

from app.internal.IRIS.iris_db_connection import IrisAsyncConnection
from app.internal.IRIS.data_access_layer.iris_dal_main import IrisDataAccessLayer
from app.internal.IRIS.iris_queries_wrapper import Iris

from app.routers import games_routes
from app.routers import youtube_routes
from app.routers import task_routes
from app.routers import public_routes

import app.connectors as connectors

from app.utils.loggers import base_logger as logger

from dotenv import load_dotenv

load_dotenv()

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def get_iris_conn(app: FastAPI):  # pylint: disable=unused-argument
    """Initialize FastAPI objects before starting the app"""

    # Init IRIS connection
    conn = IrisAsyncConnection()
    await conn.connect_to_iris()
    await connectors.init_global_aconn(conn)

    # Init IRIS Data Access Layer
    await connectors.init_global_iris_dal(IrisDataAccessLayer())

    # Init IRIS API wrapper
    await connectors.init_global_iris_query_wrapper(Iris())

    yield  # All the code after this line is executed after the app is closed

    # Close IRIS connection
    await conn.close()


ares = FastAPI(lifespan=get_iris_conn)

ares.state.limiter = limiter
ares.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

ares.include_router(games_routes.router)
ares.include_router(youtube_routes.router)
ares.include_router(task_routes.router)
ares.include_router(public_routes.router)


# ------------------ IGDB EXCEPTION HANDLERS ---------------------- #


@ares.exception_handler(IGDBInvalidReponseCode)
async def IGDBInvalidReponseCode_handler(request: Request, exc: IGDBInvalidReponseCode):
    logger.error("Invalid response code from IGDB API: %s", exc.code)
    return JSONResponse(
        status_code=500, content={"detail": "Invalid response code from IGDB API"}
    )


@ares.exception_handler(IGDBInvalidReponse)
async def IGDBInvalidReponse_handler(request: Request, exc: IGDBInvalidReponse):
    logger.error("Invalid response from IGDB API")
    return JSONResponse(
        status_code=500, content={"detail": "Invalid response from IGDB API"}
    )


# ------------------ GLOBAL EXCEPTION HANDLERS ---------------------- #


@ares.exception_handler(InvalidBody)
async def InvalidBody_handler(request: Request, exc: InvalidBody):
    logger.error("Invalid body: %s", exc)
    return JSONResponse(status_code=400, content={"detail": exc.message})


@ares.exception_handler(ObjectNotFound)
async def ObjectNotFound_handler(request: Request, exc: ObjectNotFound):
    logger.error("Object not found: %s", exc)
    return JSONResponse(status_code=404, content={"detail": exc.message})


@ares.exception_handler(GenericError)
async def GenericError_handler(request: Request, exc: GenericError):
    logger.error("Generic error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Generic error"})


# ------------------ IRIS EXCEPTION HANDLERS ---------------------- #


@ares.exception_handler(ObjectAlreadyExistsError)
async def ObjectAlreadyExistsError_handler(
    request: Request, exc: ObjectAlreadyExistsError
):
    logger.warning(exc.message)
    return JSONResponse(status_code=409, content={"detail": exc.message})


@ares.exception_handler(SQLError)
async def SQLError_handler(request: Request, exc: SQLError):
    logger.error(exc.message)
    return JSONResponse(status_code=500, content={"detail": exc.message})


@ares.exception_handler(DatabaseCommitError)
async def DatabaseCommitError_handler(request: Request, exc: DatabaseCommitError):
    logger.error(exc.message)
    return JSONResponse(
        status_code=500, content={"detail": "Error while committing data to database"}
    )


# ------------------ YOUTUBE EXCEPTION HANDLERS ---------------------- #


@ares.exception_handler(YoutubeException)
async def YoutubeException_handler(request: Request, exc: YoutubeException):
    return JSONResponse(
        status_code=exc.error_http_code,
        content={"message": exc.message, "error_code": exc.error_code},
    )


# ------------------ OTHER EXCEPTION HANDLERS ---------------------- #


@ares.exception_handler(requests.exceptions.RequestException)
async def requests_exception_handler(
    request: Request, exc: requests.exceptions.RequestException
):
    logger.error("Error while requesting: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Error while requesting"})


@ares.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Generic exception: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Unknown error"})


origins = ["*"]
ares.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time"],
)


@ares.middleware("http")
async def add_process_time_header(request, call_next):
    """Add X-Process-Time header to every response"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(f"{process_time:0.4f} sec")
    return response


@ares.get("/health")
async def health_check():
    """Health check endpoint for docker-compose"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(ares, host="0.0.0.0", port=8000)

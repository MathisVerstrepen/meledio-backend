from os.path import exists
import glob
import json
import logging
import os
import pathlib
import uuid
import threading
from contextlib import asynccontextmanager
import redis
import psycopg

from fastapi import FastAPI, Path, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.internal.iris_db_connection import IrisAsyncConnection

from dotenv import load_dotenv

load_dotenv()

# IRIS_PASS = os.getenv("POSTGRES_PASSWORD")
# IRIS_HOST = os.getenv("POSTGRES_HOST")

# IRIS_CONN = psycopg2.connect(
#     database="",
#     user="postgres",
#     password=IRIS_PASS,
#     host=IRIS_HOST,
#     port="5432",
# )

logging.basicConfig(
    filename="app/logs/triton.log",
    encoding="utf-8",
    level=logging.DEBUG,
    format="%(asctime)s -- %(levelname)s -- %(message)s",
)

IRIS_CONN = None

@asynccontextmanager
async def get_iris_conn(app: FastAPI):  # pylint: disable=unused-argument
    """Initialize FastAPI objects before starting the app"""

    # Init IRIS connection
    conn = IrisAsyncConnection()
    try:
        await conn.connect_to_iris()
    except psycopg.Error as e:
        logging.error("Error connecting to IRIS: %s", e)
        raise e
    
    global IRIS_CONN
    IRIS_CONN = conn.get_conn()
    
    logging.info("Connected to IRIS")

    yield  # All the code after this line is executed after the app is closed

    # Close IRIS connection
    await conn.close()

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


manager = ConnectionManager()


r_games = redis.Redis(host="atlas", port=6379, db=0, password=os.getenv("REDIS_PASSWORD"))



# patch(fastapi=True)
triton = FastAPI()
origins = ["*"]
triton.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# triton.add_middleware(TraceMiddleware)


validation_cat = {
    "artwork": "a",
    "screenshot": "s",
    "cover": "c",
}
validation_qual = {"big": "b", "med": "m", "huge": "h", "small": "s"}


def increment_listen_count(fileID):
    with IRIS_CONN.cursor() as cursor:
        cursor.execute(
            "UPDATE iris.track SET view_count = view_count + 1 WHERE file = %s",
            (fileID,),
        )
        IRIS_CONN.commit()


from fastapi.staticfiles import StaticFiles

triton.mount("/static", StaticFiles(directory="/bacchus/audio/"), name="static")

@triton.get("/health")
async def health_check():
    return {"status": "healthy"}


@triton.get("/audio/{gameID}/{albumID}/{trackID}/{filename}")
async def read_video(gameID: int, albumID: str, trackID: int, filename: str):
    logging.debug(f"gameID: {gameID}, trackID: {trackID}, filename: {filename}")
    file_path = f"/bacchus/audio/{gameID}/{albumID}/{trackID}/{filename}"
    return FileResponse(file_path)


@triton.get("/media/{cat}/{qual}/{hash}")
async def get_best_matching_games(
    cat: str = Path(default=..., title="media category"),
    qual: str = Path(default=..., title="media quality"),
    hash: str = Path(default=..., title="media hash/id"),
) -> FileResponse:
    headers = {"Cache-Control": "public, max-age=15552000"}

    format_cat = validation_cat.get(cat)
    if format_cat:
        format_qual = validation_qual.get(qual)
        if format_qual:
            file_path = f"/bacchus/media/{format_cat}_{format_qual}_{hash}.jpg"
            if exists(file_path):
                return FileResponse(file_path, headers=headers)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Media resource not found",
    )


@triton.delete("/api/games/images")
async def delete_media(game_id: str) -> dict:
    nfile = 0
    if game_id:
        for f in glob.glob("/bacchus/media/{}/*.jpg".format(game_id)):
            os.remove(f)
            nfile += 1

    return {"file_removed": nfile}


@triton.get("/audio/info/{audioID}")
async def get_audio_stream_init_info(
    audioID: str = Path(default=..., title="media category")
):
    return {"data": audioID}


@triton.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            messData = json.loads(message)
            logging.debug(message)

            message_type = messData["type"]
            fileID = messData["file"]

            if message_type == "init":
                with IRIS_CONN.cursor() as cursor:
                    cursor.execute(
                        "SELECT length FROM iris.track WHERE file = %s", (fileID,)
                    )
                    audioLength = cursor.fetchone()[0]
                    logging.debug(audioLength)

                trackSessionData = {
                    "type": "init",
                    "nchunk": audioLength // 10000 + 1,
                    "chunkLength": 10,
                    "audioLength": audioLength,
                }

                await manager.send_personal_message(
                    json.dumps(trackSessionData), websocket
                )
            elif message_type == "chunk":
                gameID = messData["game"]
                chunkIdx = messData["chunk"]

                if chunkIdx == 20000:
                    threading.Thread(
                        target=increment_listen_count, args=(fileID,)
                    ).start()

                audioID = uuid.UUID(fileID).hex
                audio_bytes = pathlib.Path(
                    f"/bacchus/audio/{gameID}/{audioID}/{chunkIdx}"
                ).read_bytes()
                chunk_id_bytes = messData["chunk"].to_bytes(4, byteorder="big")
                message = chunk_id_bytes + audio_bytes
                await manager.send_personal_message(message, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast("Client # left the chat")

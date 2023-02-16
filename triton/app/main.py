from fastapi import Body, FastAPI, Path, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from os.path import exists
import glob
import json
import logging
import os
import pathlib
import redis
from ddtrace import patch



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

from dotenv import load_dotenv
load_dotenv()
r_games = redis.Redis(host="atlas", port=6379, db=0, password=os.getenv("REDIS_SECRET"))

logging.basicConfig(
    filename="app/logs/triton.log",
    encoding="utf-8",
    level=logging.DEBUG,
    format="%(asctime)s -- %(levelname)s -- %(message)s",
)

patch(fastapi=True)
triton = FastAPI()


# triton.add_middleware(TraceMiddleware)


validation_cat = {
    'artwork': 'a',
    'screenshot': 's',
    'cover': 'c',
}
validation_qual = {
    'big': 'b',
    'med': 'm',
    'huge': 'h',
    'small': 's'
}


@triton.get("/media/{cat}/{qual}/{hash}")
async def get_best_matching_games(
    cat: str = Path(default=..., title="media category"),
    qual: str = Path(default=..., title="media quality"),
    hash: str = Path(default=..., title="media hash/id")
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


@triton.delete("/del_media")
async def delete_media(body: dict = Body(...)) -> dict:
    medias = body.get('medias')
    nfile = 0
    if medias:
        for hash in medias:
            for f in glob.glob(f"/bacchus/media/*{hash}*"):
                os.remove(f)
                nfile += 1

    return {'file_removed': nfile}


@triton.get("/audio/info/{audioID}")
async def get_audio_stream_init_info(audioID: str = Path(default=..., title="media category")):
    return {"data": audioID}

@triton.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            messData = json.loads(message)
            logging.debug(message)
            gameID = messData['gid']
            audioIndex = messData['audIdx']
            audioID = messData['id']
            
            if (messData['chunk'] == 0):
                trackChunksMetadata = r_games.json().get(f"g:{gameID}", f"$.album[0].track[{audioIndex}].chunkMeta")[0]
                audioLength = r_games.json().get(f"g:{gameID}", f"$.album[0].track[{audioIndex}].length")[0]

                trackSessionData = {
                    "base" : message,
                    "chunk" : -1,
                    "chunkMeta" : trackChunksMetadata,
                    "audioLength" : audioLength
                }
                
                await manager.send_personal_message(json.dumps(trackSessionData), websocket)
                
                audio_bytes = pathlib.Path(f"/bacchus/audio/{gameID}/{audioID}/0").read_bytes()
                await manager.send_personal_message(audio_bytes, websocket)
                
            else :
                audio_bytes = pathlib.Path(f"/bacchus/audio/{gameID}/{audioID}/{messData['chunk']}").read_bytes()
                # b = str(messData['chunk']).encode('utf-8')
                # logging.debug(audio_bytes)
                # logging.debug(b)
                # logging.debug(b+audio_bytes)
                # sendData = {
                #     "chunk" : messData['chunk'],
                #     'bytes' : str(audio_bytes, 'latin-1')
                # }
                await manager.send_personal_message(audio_bytes, websocket)
            
            # audio_bytes = pathlib.Path(f"/bacchus/audio/1942/{audioID}/0").read_bytes()
            
                # await manager.send_personal_message(audio_bytes, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client # left the chat")
from fastapi import Body, FastAPI, Path, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydub import AudioSegment
from os.path import exists
from io import BytesIO
import glob
import os

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



triton = FastAPI()
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

    format_cat = validation_cat.get(cat)
    if format_cat:
        format_qual = validation_qual.get(qual)
        if format_qual:
            file_path = f"/bacchus/media/{format_cat}_{format_qual}_{hash}.jpg"
            if exists(file_path):
                return FileResponse(file_path)

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
async def get_audio_stream_init_info(audioID: str = Path(default=..., title="media category")) :
    return {"data": audioID}

@triton.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            audio = AudioSegment.from_file(f"/bacchus/audio/1942/{data}.m4a")
            ten_seconds = 10 * 1000
            first_10_seconds = audio[:ten_seconds]

            wavIO=BytesIO()
            audio.export(wavIO, format="mp3")
            await manager.send_personal_message(wavIO, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client # left the chat")
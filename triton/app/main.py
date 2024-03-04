from os.path import exists
import glob
import logging
import os
from contextlib import asynccontextmanager
from PIL import Image

from fastapi import FastAPI, Path, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.internal.iris_db_connection import IrisAsyncConnection
from app.internal.utilities.auth import require_valid_token

from dotenv import load_dotenv

load_dotenv()

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
    await conn.connect_to_iris()

    # TODO : deport db connection to a separate module like in ares
    global IRIS_CONN
    IRIS_CONN = conn.get_conn()

    logging.info("Connected to IRIS")

    yield  # All the code after this line is executed after the app is closed

    # Close IRIS connection
    await conn.close()


triton = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
origins = ["*"]
triton.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


validation_cat = {
    "artwork": "a",
    "screenshot": "s",
    "cover": "c",
}
validation_qual = {"big": "b", "med": "m", "huge": "h", "small": "s"}

# Mount static files from bacchus
triton.mount("/static", StaticFiles(directory="/bacchus/audio/"), name="static")

# Empty media cache folder
for f in glob.glob("/bacchus/media/cache/*"):
    os.remove(f)

@triton.get("/health")
async def health_check():
    """ Health check endpoint for docker compose """
    return {"status": "healthy"}


@triton.get("/audio/{game_id}/{album_id}/{track_id}/{filename}")
async def read_video(
    game_id: int, album_id: str, track_id: int, filename: str
) -> FileResponse:
    """Get an audio MPD file by its ID

    Args:
        gameID (int): Game ID
        albumID (str): Album ID
        trackID (int): Track ID
        filename (str): Filename of the audio file

    Returns:
        FileResponse: The audio file
    """

    file_path = f"/bacchus/audio/{game_id}/{album_id}/{track_id}/{filename}"
    return FileResponse(file_path)


@triton.get("/media/{game_id}/{cat}/{qual}/{filehash}")
async def read_media(
    game_id: int,
    cat: str = Path(default=..., title="media category"),
    qual: str = Path(default=..., title="media quality"),
    filehash: str = Path(default=..., title="media hash/id"),
    width: int = 0,
    height: int = 0,
    format: str = "jpg",
) -> FileResponse:
    """ Get a media file by its hash and category

    Args:
        cat (str, optional): 
        qual (str, optional):
        filehash (str, optional):

    Raises:
        HTTPException:

    Returns:
        FileResponse:
    """

    # Cache file for 6 months
    headers = {"Cache-Control": "public, max-age=15552000"}

    format_cat = validation_cat.get(cat)
    if format_cat:
        format_qual = validation_qual.get(qual)
        if format_qual:
            file_path = f"/bacchus/media/{game_id}/{format_cat}_{format_qual}_{filehash}.jpg"
            if exists(file_path):
                # Check if resized cached file exists
                cached_file_path = f"/bacchus/media/cache/{format_cat}_{format_qual}_{filehash}_{width}_{height}.{format}"
                if width and height:
                    if exists(cached_file_path):
                        return FileResponse(cached_file_path, headers=headers)
                
                # Resize image if needed and cache it
                # resize needs to keep the aspect ratio of the original image
                # if only one dimension is provided, the other one is calculated to keep the aspect ratio
                # if both dimensions are provided, the image is resized to fit in the provided dimensions
                
                if width and height:
                    # Keep aspect ratio by resizing to fit in the provided dimensions
                    img = Image.open(file_path)
                    aspect_ratio = img.size[0] / img.size[1]
                    if width / aspect_ratio < height:
                        img = img.resize((width, int(width / aspect_ratio)), Image.Resampling.LANCZOS)
                    else:
                        img = img.resize((int(height * aspect_ratio), height), Image.Resampling.LANCZOS)
                    img.save(cached_file_path, optimize=True)
                    
                elif width:
                    # Only width is provided
                    img = Image.open(file_path)
                    wpercent = (width / float(img.size[0]))
                    hsize = int((float(img.size[1]) * float(wpercent)))
                    img = img.resize((width, hsize), Image.Resampling.LANCZOS)
                    img.save(cached_file_path, optimize=True)
                    
                elif height:
                    # Only height is provided
                    img = Image.open(file_path)
                    hpercent = (height / float(img.size[1]))
                    wsize = int((float(img.size[0]) * float(hpercent)))
                    img = img.resize((wsize, height), Image.Resampling.LANCZOS)
                    img.save(cached_file_path, optimize=True)
                
                else:
                    # No dimensions provided
                    cached_file_path = file_path
                    
                return FileResponse(cached_file_path, headers=headers)
                
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Media resource not found",
    )


@triton.delete("/api/games/images")
@require_valid_token
async def delete_media(request: Request, game_id: str) -> dict:
    """ Delete all media files associated with a game
        Only used in the admin media management in ares

    Args:
        game_id (str): Game ID

    Returns:
        dict: Number of files removed
    """

    nfile = 0
    if game_id:
        for f in glob.glob(f"/bacchus/media/{game_id}/*.jpg"):
            os.remove(f)
            nfile += 1

    return {"file_removed": nfile}

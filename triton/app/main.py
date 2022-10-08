from fastapi import Body, FastAPI, Path, HTTPException, status
from fastapi.responses import FileResponse
from os.path import exists
import glob
import os


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
async def get_best_matching_games(body: dict = Body(...)) -> dict:
    medias = body.get('medias')
    nfile = 0
    if medias:
        for hash in medias:
            for f in glob.glob(f"/bacchus/media/*{hash}*"):
                os.remove(f)
                nfile += 1

    return {'file_removed': nfile}

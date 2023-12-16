import asyncio
from functools import partial
import re
import blurhash
import aiofiles

from app.internal.IGDB.igdb_request import igdb_request

from app.utils.loggers import base_logger as logger

DOWNLOAD_QUALITY = {
    "artworks": [
        ["screenshot_huge", "a_h"],
        ["screenshot_big", "a_b"],
        ["screenshot_med", "a_m"],
    ],
    "cover": [["cover_big", "c_b"], ["cover_small", "c_s"]],
    "screenshots": [
        ["screenshot_huge", "s_h"],
        ["screenshot_big", "s_b"],
        ["screenshot_med", "s_m"],
    ],
}


def detect_year_in_name(name: str) -> (int, str):
    """Detect year in game name.
        Used to detect year in game name to get the right game from IGDB.

    Args:
        name (str): Game name

    Returns:
        (int, str): Year, cleaned name
    """

    pattern = r"\((\d{4})\)"

    match = re.search(pattern, name)

    if match:
        year = int(match.group(1))
        cleaned_string = re.sub(pattern, "", name).strip()
        return year, cleaned_string
    else:
        return None, name


async def run_in_thread(sync_function, *args, **kwargs) -> str:
    """Run a synchronous function in a thread.
        Used to run blurhash.encode in a thread.
        blurhash.encode take approx 0.5s to run, so it's better to run it in a thread.

    Args:
        sync_function (function): Synchronous function to run

    Returns:
        str: Blurhash
    """
    loop = asyncio.get_running_loop()
    sync_function_noargs = partial(sync_function, *args, **kwargs)
    return await loop.run_in_executor(None, sync_function_noargs)


async def igdb_image_downloader(field: str, image_id: str, game_id: str) -> str:
    """Download image from IGDB and generate blurhash.

    Args:
        field (str): Type of media (artworks, cover, screenshots)
        image_id (str): Image ID
        game_id (str): Game ID

    Returns:
        str: Blurhash
    """

    dl_quality = DOWNLOAD_QUALITY.get(field)

    if dl_quality is None or image_id is None or image_id == "":
        return None

    blur_hashs = []
    for qual in dl_quality:
        try:
            res = await igdb_request.get_image(qual[0], image_id)
            image_path = f"/bacchus/media/{game_id}/{qual[1]}_{image_id}.jpg"

            async with aiofiles.open(image_path, "w+b") as f:
                await f.write(res)

            blur_hash = await run_in_thread(
                blurhash.encode, image_path, x_components=4, y_components=3
            )
            if blur_hash:
                blur_hashs.append(blur_hash)
                
            break
        except Exception as e:
            logger.error(
                "An error occurred while downloading image %s. Error: %s", image_id, e
            )

    if blur_hashs:
        return blur_hashs[-1]
    return None

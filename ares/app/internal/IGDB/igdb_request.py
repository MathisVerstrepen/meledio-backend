import random
import os
import httpx

from app.utils.loggers import base_logger

from app.utils.connection import REDIS_GLOBAL
from app.internal.utilities.json import unload_json

from app.internal.errors.igdb_exceptions import (
    IGDBInvalidReponseCode,
    IGDBInvalidReponse,
)

from app.internal.Youtube.youtube_const import PROXIES



class IGDB_Request:
    def __init__(self):
        self.token = self.get_igdb_token()
        if not self.token:
            print("Erreur lors de la récupération du token.")
            return None

        self.req_header = {
            "Accept": "application/json",
            "Client-ID": os.getenv("IGDB_ID"),
            "Authorization": f"Bearer {self.token}",
        }

    def get_igdb_token(self):
        # token = REDIS_GLOBAL.json().get("IGDB_TOKEN", "$.access_token")
        token = REDIS_GLOBAL.get("IGDB_TOKEN")

        if not token:
            token = self.refresh_igdb_token()

        token = token[0]
        # Test if token is still valid
        headers = {
            "Client-ID": os.getenv("IGDB_ID"),
            "Authorization": f"Bearer {token}",
        }
        response = httpx.get(
            "https://api.igdb.com/v4/games", headers=headers, timeout=10
        )

        if response.status_code != 200:
            token = self.refresh_igdb_token()

        return token

    def refresh_igdb_token(self):
        base_logger.info("Refreshing IGDB token.")
        try:
            response = httpx.post(
                "https://id.twitch.tv/oauth2/token",
                data={
                    "client_id": os.getenv("IGDB_ID"),
                    "client_secret": os.getenv("IGDB_SECRET"),
                    "grant_type": "client_credentials",
                },
                timeout=10,
            )

            response.raise_for_status()
            data = response.json()
            # REDIS_GLOBAL.json().set("IGDB_TOKEN", "$", data["access_token"])
            REDIS_GLOBAL.set("IGDB_TOKEN", data["access_token"])

            return data["access_token"]
        except httpx.HTTPError as e:
            base_logger.error("Error while refreshing IGDB token: %s", e)
            return None

    async def get(self, endpoint: str, data: str):
        async with httpx.AsyncClient() as client:
            IGDB_res = await client.post(
                f"https://api.igdb.com/v4/{endpoint}",
                headers=self.req_header,
                data=data,
                timeout=10,
            )

            if IGDB_res.status_code != 200:
                raise IGDBInvalidReponseCode(IGDB_res.status_code)

            parsed_igdb_res: list = unload_json(IGDB_res.text)

            if parsed_igdb_res is None:
                raise IGDBInvalidReponse()

            return parsed_igdb_res

    async def get_image(self, size: int, img_hash: str) -> bytes:
        """Get image from IGDB API

        Args:
            size (int): Format of image (cover_small, cover_big, screenshot_med,
                        screenshot_big, screenshot_huge, thumb, ...)
            img_hash (str): Hash of image (id of image)

        Returns:
            bytes: Image data
        """
        max_retries = 3

        for attempt in range(max_retries):
            try:
                proxy = random.choice(PROXIES)
                async with httpx.AsyncClient(proxies = proxy) as client:
                    igdb_res = await client.get(
                        f"https://images.igdb.com/igdb/image/upload/t_{size}/{img_hash}.jpg",
                        headers=self.req_header,
                        timeout=10,
                    )

                    if igdb_res.status_code != 200:
                        raise IGDBInvalidReponseCode(igdb_res.status_code)

                    return igdb_res.content

            except (httpx.HTTPError, IGDBInvalidReponseCode):
                if attempt < max_retries - 1:
                    continue
                else:
                    raise



igdb_request = IGDB_Request()

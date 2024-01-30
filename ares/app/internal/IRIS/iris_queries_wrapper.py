import json
from typing import Literal
import requests

# from app.internal.IRIS.data_access_layer.iris_dal_main import IRIS_DAL
from app.internal.utilities.files import delete_folder, delete_file

import app.connectors as connectors

from app.internal.errors.global_exceptions import ObjectNotFound
from app.internal.errors.iris_exceptions import SQLError

from app.utils.loggers import base_logger as logger


class Iris:
    """General IRIS API queries wrapper"""

    def __init__(self) -> None:
        self.iris_dal = connectors.iris_dal

        with open("app/config/IGDB_IRIS_association.json", "r", encoding="utf-8") as f:
            self.igdb_iris_association: dict = json.load(f)

    async def push_new_game(self, game_data: dict, game_existence: int) -> None:
        """Push new game to database

        Args:
            game_data (dict): Game data
        """

        game_id = game_data[0]["id"]
        game_name = game_data[0]["name"]
        logger.info("Adding game [%s] to database.", game_id)

        async with connectors.iris_aconn.transaction():
            new_game_dal = self.iris_dal.IrisDalNewGame(self.iris_dal, game_id)

            if game_existence == 0:
                await new_game_dal.add_new_game_root_data(game_id, game_name)

            for field in game_data[0]:
                field_data = game_data[0][field]
                field_schema_data: dict = self.igdb_iris_association.get(field)
                field_type: str = field_schema_data.get("type")
                field_sql_identifier = field_schema_data.get("field")

                match field_type:
                    case "base":
                        await new_game_dal.add_base_data(
                            field_sql_identifier, field_data
                        )
                    case "date":
                        await new_game_dal.add_date_data(
                            field_sql_identifier, field_data
                        )
                    case "parent":
                        await new_game_dal.add_parent_data(
                            field_sql_identifier, field_data
                        )
                    case "extra":
                        await new_game_dal.add_extra_data(
                            field_sql_identifier,
                            field_data,
                            field_schema_data.get("sub_field"),
                        )
                    case "base-ext":
                        await new_game_dal.add_base_extra_data(
                            field_sql_identifier,
                            field_schema_data.get("base_field"),
                            field_data,
                        )
                    case "company":
                        await new_game_dal.add_company_data(
                            field_sql_identifier,
                            field_schema_data.get("sub_field"),
                            field_data,
                        )
                    case "media":
                        await new_game_dal.add_media_data(
                            field_sql_identifier, field, field_data
                        )
                    case "normal":
                        await new_game_dal.add_normalized_data(
                            field_sql_identifier, field_data
                        )
                    case "association_table":
                        await new_game_dal.add_association_table_data(
                            field_sql_identifier,
                            field_data,
                            field_schema_data.get("association_table"),
                        )

            await new_game_dal.finalize_game()

        await new_game_dal.commit_changes()

        logger.info("Game [%s] added to database.", game_id)

    async def delete_game(self, game_id: int) -> None:
        """Delete game from database and media server

        Args:
            game_id (int): Game ID
        """
        game_existence = await self.iris_dal.check_game_existence(game_id)
        logger.info("game_existence : %s", game_existence)

        if game_existence == 0 or game_existence == 1:
            logger.info("Game [%s] not in database.", game_id)
            raise ObjectNotFound("Game to delete with IGDB ID " + str(game_id))

        try:
            requests.delete(
                "http://media.meledio.com/api/games/images",
                params={"game_id": game_id},
                timeout=10,
            )

            await self.iris_dal.delete_game(game_id)
        except SQLError as error:
            logger.error("Error while getting game images: %s", error)
            return None

    async def get_base_game_data(self, game_id: int) -> dict:
        """Get base game data

        Args:
            game_id (int): Game ID

        Returns:
            dict: Base game data
        """
        base_data = await self.iris_dal.get_full_game_data(game_id)

        base_data["categories"] = await self.iris_dal.get_categories_by_game_id(game_id)

        return base_data

    async def add_game_tracks(
        self, game_id: int, album_id: str, tracks: list, video_id: str
    ) -> None:
        """Add game tracks

        Args:
            game_id (int): Game ID
            album_id (str): Album ID
            tracks (list): Tracks
            video_id (str): Video ID
        """

        curent_main_album_id = await self.iris_dal.check_album_existence(game_id)
        if curent_main_album_id:
            logger.warning(
                "Album [%s] already exists in database. Deleting album folder.",
                curent_main_album_id,
            )
            delete_folder(f"/bacchus/audio/{game_id}/{curent_main_album_id}")

        await self.iris_dal.add_game_tracks(
            game_id, album_id, tracks, "youtube", video_id
        )

        delete_file(f"/bacchus/audio/tmp/{video_id}.opus")

    async def get_games_sorted(
        self,
        sort_type: Literal["rating", "random", "recent"],
        sort_order: Literal["asc", "desc"],
        offset: int = 0,
        limit: int = 20,
    ) -> list:
        """Get games sorted by a specific type (rating, random, recent)

        Args:
            sort_type (str): Field to sort by

        Returns:
            list: Games data
        """
        
        sort_type_map = {
            "rating": "c.rating",
            "random": "random()",
            "recent": "c.creation_date",
        }

        return await self.iris_dal.get_games_sorted(
            sort_type_map[sort_type], sort_order, offset, limit
        )

    async def get_game_top_tracks(self, game_id: int, offset: int, limit: int):
        """Get game top tracks

        Args:
            game_id (int): Game ID

        Returns:
            list: Game top tracks
        """
        return await self.iris_dal.get_game_top_tracks(game_id, offset, limit)

    async def get_games_albums(self, game_id: int):
        """Get game albums

        Args:
            game_id (int): Game ID

        Returns:
            list: Game albums
        """
        return await self.iris_dal.get_games_albums(game_id)

    async def get_game_related_games(self, game_id: int, offset: int, limit: int):
        """Get game related games

        Args:
            game_id (int): Game ID
            offset (int): offset in results (default 0)
            limit (int): limit of results (default 10, max 50)

        Returns:
            list: Game related games
        """
        return await self.iris_dal.get_game_related_games(game_id, offset, limit)

    async def get_collection_by_id(self, collection_id: int):
        """Get collection by ID

        Args:
            collection_id (int): Collection ID

        Returns:
            dict: Collection data
        """
        collection_data = await self.iris_dal.get_collection_info_by_id(collection_id)
        collection_reduce_game_data = (
            await self.iris_dal.get_collection_reduce_game_info(collection_id)
        )

        collection_data["games"] = collection_reduce_game_data

        return collection_data

    async def get_collection_top_tracks(
        self, collection_id: int, offset: int, limit: int
    ):
        """Get collection top tracks

        Args:
            collection_id (int): Collection ID
            offset (int): offset in results (default 0)
            limit (int): limit of results (default 10, max 50)

        Returns:
            list: Collection top tracks
        """
        return await self.iris_dal.get_collection_top_tracks(
            collection_id, offset, limit
        )

    async def get_collections_sorted(
        self,
        sort_type: Literal["rating", "random", "recent"],
        sort_order: Literal["asc", "desc"],
        offset: int = 0,
        limit: int = 20,
    ):
        """Get collections sorted by a specific type (rating, random, recent)

        Args:
            sort_type (str): Field to sort by

        Returns:
            list: Collections data
        """
        sort_type_map = {
            "rating": "avg_rating",
            "random": "random()",
            "recent": "latest_game_release_date",
        }

        collections = await self.iris_dal.get_collections_sorted(
            sort_type_map[sort_type], sort_order, offset, limit
        )
        
        for collection in collections:
            collection["games"] = await self.iris_dal.get_collection_reduce_game_info(
                collection["id"]
            )
            
        return collections
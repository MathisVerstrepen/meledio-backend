import json
import requests
from typing import Literal

# from app.internal.IRIS.data_access_layer.iris_dal_main import IRIS_DAL
from app.internal.utilities.files import delete_folder, delete_file

import app.connectors as connectors

from app.internal.errors.iris_exceptions import DatabaseCommitError
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

        return await self.iris_dal.get_full_game_data(game_id)

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
        offset: int,
        limit: int
    ) -> list:
        """Get games sorted by a specific type (rating, random, recent)

        Args:
            sort_type (str): Field to sort by

        Returns:
            list: Games data
        """

        return await self.iris_dal.get_games_sorted(sort_type, sort_order, offset, limit)

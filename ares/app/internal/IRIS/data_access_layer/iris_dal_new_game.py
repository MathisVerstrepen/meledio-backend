import os
import asyncio
from datetime import datetime
from psycopg import sql
from psycopg.errors import Error as psycopg_Error

import app.connectors as connectors
from app.internal.IGDB.igdb_api_wrapper import igdb_client
from app.internal.IGDB.igdb_utils import igdb_image_downloader

from app.internal.errors.iris_exceptions import SQLError

from app.utils.loggers import base_logger as logger


async def insert_media_with_semaphore(semaphore, media, insert_media):
    async with semaphore:
        return await insert_media(media)


class IrisDalNewGame:
    def __init__(self, IRIS_DAL, gameID: int = None) -> None:
        self.IRIS_DAL = IRIS_DAL
        
        self.iris_aconn = connectors.iris_aconn
        
        self.gameID = gameID
        self.igdb_client = igdb_client

        try:
            os.mkdir(f"/bacchus/media/{self.gameID}")
        except FileExistsError:
            pass

    async def commit_changes(self) -> None:
        """Commit changes to database"""

        try:
            await self.iris_aconn.commit()
        except psycopg_Error as exc:
            raise SQLError(
                f"An error occurred while committing changes to game ID {self.gameID}"
            ) from exc
        
    async def finalize_game(self) -> None:
        """Finalize game in database"""

        try:
            query = sql.SQL("UPDATE iris.game SET complete = true WHERE id=%s;")
            data = (self.gameID,)
            
            async with self.iris_aconn.cursor() as cur:
                await cur.execute(query, data)
        except SQLError as exc:
            logger.error(
                "An error occurred while finalizing game ID %s. Error: %s",
                self.gameID,
                exc,
            )
            raise

    async def add_new_game_root_data(self, game_id: int, game_name=None) -> None:
        """Add new game ID to database

        Args:
            game_id (int): Game ID
            game_name (str, optional): Game name. Defaults to None.
        """

        try:
            query = "INSERT INTO iris.game (id, complete, name) VALUES (%s,False,%s);"
            data = (
                game_id,
                game_name,
            )
            
            async with self.iris_aconn.cursor() as cur:
                await cur.execute(query, data)
                
            # await self.iris_aconn.commit()
        except psycopg_Error as exc:
            raise SQLError("Error while inserting new game ID") from exc

    async def add_base_data(self, field: str, field_data: dict) -> None:
        """Add base data to game

        Args:
            field (str): Field name
            field_data (str): Field data
        """

        try:
            query = sql.SQL("UPDATE iris.game SET {field} = %s WHERE id=%s;").format(
                field=sql.Identifier(field)
            )
            data = (
                field_data,
                self.gameID,
            )
            
            async with self.iris_aconn.cursor() as cur:
                await cur.execute(query, data)
        except psycopg_Error as exc:
            raise SQLError(
                f"An error occurred while adding base data to game ID {self.gameID}"
            ) from exc

    async def add_date_data(self, field: str, field_data: dict) -> None:
        """Add date data to game

        Args:
            field (str): Field name
            field_data (str): Field data
        """

        try:
            query = sql.SQL("UPDATE iris.game SET {field} = %s WHERE id=%s;").format(
                field=sql.Identifier(field)
            )
            data = (
                datetime.fromtimestamp(field_data),
                self.gameID,
            )

            async with self.iris_aconn.cursor() as cur:
                await cur.execute(query, data)
        except psycopg_Error as exc:
            raise SQLError(
                f"An error occurred while adding date data to game ID {self.gameID}"
            ) from exc

    async def add_parent_data(self, field: str, field_data: dict) -> None:
        """Add parent data to game

        Args:
            field (str): Field name
            field_data (str): Field data
        """

        try:
            parent_id = field_data.get("id")
            if not parent_id:
                return

            parent_existence = await self.IRIS_DAL.check_game_existence(field_data.get("id"))
            if parent_existence == 0:
                await self.add_new_game_root_data(parent_id, field_data.get("name"))

            query = sql.SQL("UPDATE iris.game SET {field} = %s WHERE id=%s;").format(
                field=sql.Identifier(field)
            )
            data = (
                parent_id,
                self.gameID,
            )
            
            async with self.iris_aconn.cursor() as cur:
                await cur.execute(query, data)

        except psycopg_Error as exc:
            logger.error(
                "An error occurred while adding parent data to game ID %s. Error: %s",
                self.gameID,
                exc,
            )
            raise SQLError(
                f"An error occurred while adding parent data to game ID {self.gameID}"
            ) from exc

    async def add_extra_data(self, field: str, field_data: dict, sub_field: str) -> None:
        """Add extra data to game

        Args:
            field (str): Field name
            field_data (str): Field data
        """

        try:
            async with self.iris_aconn.cursor() as cur:
                for extra_data in field_data:
                    extra_data_id = extra_data.get("id")

                    if not extra_data_id:
                        continue

                    extra_data_existence = await self.IRIS_DAL.check_game_existence(extra_data_id)

                    if extra_data_existence == 0:
                        await self.add_new_game_root_data(extra_data_id, extra_data.get("name"))

                    query = sql.SQL(
                        "INSERT INTO iris.{table} (game_id, extra_id, type) VALUES (%s,%s,%s);"
                    ).format(table=sql.Identifier(field))
                    data = (
                        self.gameID,
                        extra_data_id,
                        sub_field,
                    )
                    
                    await cur.execute(query, data)
        except psycopg_Error as exc:
            raise SQLError(
                f"An error occurred while adding extra data to game ID {self.gameID}"
            ) from exc

    async def add_base_extra_data(
        self, field: str, base_field: str, field_data: dict
    ) -> None:
        """Add base extra data to game

        Args:
            field (str): Field name
            base_field (str): Base field name
            field_data (dict): Field data
        """

        try:
            async with self.iris_aconn.cursor() as cur:
                query = sql.SQL(
                    "INSERT INTO iris.{table} ({fields}) VALUES ({values}) ON CONFLICT DO NOTHING;"
                ).format(
                    table=sql.Identifier(field),
                    fields=sql.SQL(",").join(
                        sql.Identifier(nfield) for nfield in field_data.keys()
                    ),
                    values=sql.SQL(", ").join(sql.Placeholder() * len(field_data)),
                )
                data = [*field_data.values()]

                await cur.execute(query, data)

                query = sql.SQL("UPDATE iris.game SET {field} = %s WHERE id=%s;").format(
                    field=sql.Identifier(base_field)
                )
                data = (
                    field_data["id"],
                    self.gameID,
                )
                
                await cur.execute(query, data)
        except psycopg_Error as exc:
            raise SQLError(
                f"An error occurred while adding base extra data to game ID {self.gameID}"
            ) from exc

    async def add_company_data(
        self, field: str, sub_field: str, field_data: dict
    ) -> None:
        """Add company data to game

        Args:
            field (str): Field name
            sub_field (str): Sub field name
            field_data (dict): Field data
        """

        try:
            companies_data: list = await self.igdb_client.get_companies(field_data)
            async with self.iris_aconn.cursor() as cur:
                for company_data in companies_data:
                    query = sql.SQL(
                        """INSERT INTO iris.{table} 
                                (id, name, slug, description, logo_id) VALUES (%s,%s,%s,%s,%s) 
                            ON CONFLICT DO NOTHING;"""
                    ).format(
                        table=sql.Identifier(sub_field),
                    )
                    data = (
                        company_data.get("id"),
                        company_data.get("name"),
                        company_data.get("slug"),
                        company_data.get("description"),
                        company_data.get("logo", {}).get("image_id"),
                    )
                    
                    await cur.execute(query, data)

                for involved_company in field_data:
                    query = sql.SQL(
                        """INSERT INTO iris.{table} 
                                (game_id, company_id, developer, porting, publisher, supporting) 
                            VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING;"""
                    ).format(
                        table=sql.Identifier(field),
                    )
                    data = (
                        self.gameID,
                        involved_company.get("company"),
                        involved_company.get("developer"),
                        involved_company.get("porting"),
                        involved_company.get("publisher"),
                        involved_company.get("supporting"),
                    )
                    
                    await cur.execute(query, data)

        except psycopg_Error as exc:
            raise SQLError(
                f"An error occurred while adding company data to game ID {self.gameID}"
            ) from exc

    async def add_media_data(
        self, field: str, field_type: str, field_data: dict
    ) -> None:
        """Add media data to game

        Args:
            field (str): Field name
            field_type (str): Field type
            field_data (str): Field data
        """

        try:
            async with self.iris_aconn.cursor() as cur:
                async def insert_media(media: dict):
                    image_id = media.get("image_id")
                    blur_hash = await igdb_image_downloader(
                        field_type, image_id, self.gameID
                    )

                    if blur_hash is None:
                        return

                    query = sql.SQL(
                        """INSERT INTO iris.{table} 
                        (image_id, game_id, type, height, width, blur_hash) 
                        VALUES (%s,%s,%s,%s,%s,%s);"""
                    ).format(
                        table=sql.Identifier(field),
                    )
                    data = (
                        image_id,
                        self.gameID,
                        field_type,
                        media.get("height"),
                        media.get("width"),
                        blur_hash,
                    )
                    await cur.execute(query, data)

                semaphore = asyncio.Semaphore(8)

                tasks = []

                if isinstance(field_data, list):
                    for media in field_data:
                        task = insert_media_with_semaphore(semaphore, media, insert_media)
                        tasks.append(task)

                else:
                    task = insert_media_with_semaphore(semaphore, field_data, insert_media)
                    tasks.append(task)

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, Exception):
                        logger.error(
                            "An error occurred while adding media data to game ID %s. Error: %s",
                            self.gameID,
                            result,
                        )

        except psycopg_Error as exc:
            raise SQLError(
                f"An error occurred while adding media data to game ID {self.gameID}"
            ) from exc

    async def add_normalized_data(self, field: str, field_data: dict) -> None:
        """Add normalized data to game

        Args:
            field (str): Field name
            field_data (str): Field data
        """

        try:
            async with self.iris_aconn.cursor() as cur:
                for elmt_data in field_data:
                    query = sql.SQL(
                        "INSERT INTO iris.{table} (game_id,{fields}) VALUES ({values});"
                    ).format(
                        table=sql.Identifier(field),
                        fields=sql.SQL(",").join(
                            sql.Identifier(nfield) for nfield in ([*elmt_data.keys()])[1:]
                        ),
                        values=sql.SQL(", ").join(sql.Placeholder() * len(elmt_data)),
                    )
                    data = [self.gameID, *([*elmt_data.values()])[1:]]
                    
                    await cur.execute(query, data)
        except psycopg_Error as exc:
            raise SQLError(
                f"An error occurred while adding normalized data to game ID {self.gameID}"
            ) from exc

    async def add_association_table_data(self, field: str, field_data: dict, association_table: str) -> None:
        """ Field that have an association table with game and other data (e.g. genres, keywords)

        Args:
            field (str): Field name (e.g. genres, keywords)
            field_data (dict): Field data
            association_table (str): Association table name (e.g. game_genres, game_keywords)
        """
        
        try :
            async with self.iris_aconn.cursor() as cur:
                for elmt_data in field_data:
                    query = sql.SQL(
                        """INSERT INTO iris.{table} (name, slug)
                            VALUES (%s, %s)
                            ON CONFLICT (name) DO NOTHING
                            RETURNING id;
                            """
                    ).format(
                        table=sql.Identifier(field),
                    )
                    data = (
                        elmt_data.get("name"),
                        elmt_data.get("slug"),
                    )
                    
                    await cur.execute(query, data)
                    res = await cur.fetchone()
                    
                    if res is None:
                        query = sql.SQL(
                            """SELECT id FROM iris.{table}
                                WHERE name = %s;
                                """
                        ).format(
                            table=sql.Identifier(field),
                        )
                        data = (
                            elmt_data.get("name"),
                        )
                        
                        await cur.execute(query, data)
                        field_id = (await cur.fetchone()).get("id", None)
                    else:
                        field_id = res.get("id")
                        
                    field_id_column = field + "_id"
                    query = sql.SQL(
                        """INSERT INTO iris.{table} (game_id, {field})
                            VALUES (%s, %s)
                            ON CONFLICT DO NOTHING;
                            """
                    ).format(
                        table=sql.Identifier(association_table),
                        field=sql.Identifier(field_id_column),
                    )
                    
                    data = (
                        self.gameID,
                        field_id,
                    )
                    
                    await cur.execute(query, data)
                    
        except psycopg_Error as exc:
            raise SQLError(
                f"An error occurred while adding association table data to game ID {self.gameID}"
            ) from exc
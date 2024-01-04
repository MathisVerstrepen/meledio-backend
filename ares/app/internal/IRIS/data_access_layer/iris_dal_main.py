import traceback
from slugify import slugify
from psycopg import Error as psycopg_Error, sql

from app.internal.IRIS.data_access_layer.iris_dal_new_game import IrisDalNewGame
from app.internal.IRIS.iris_const import GAME_TABLES

from app.internal.errors.iris_exceptions import SQLError
from app.utils.loggers import base_logger as logger
import app.connectors as connectors


class IrisDataAccessLayer:
    IrisDalNewGame = IrisDalNewGame

    def __init__(self) -> None:
        self.aconn = connectors.iris_aconn
        self.new_game = IrisDalNewGame(self)

    async def check_game_existence(self, game_id: int) -> int:
        """Check if game exists in database

        Args:
            game_id (int): Game ID

        Returns:
            int:
                - 0: game doesn't exist at all
                - 1: root data of game exists but not all data
                - 2: game exists
        """

        try:
            async with self.aconn.cursor() as curs:
                query = "SELECT g.complete FROM iris.game g WHERE id=%s"
                data = (game_id,)
                await curs.execute(query, data)
                res = await curs.fetchone()

                if not res:
                    return 0
                if res.get("complete") is True:
                    return 2
                return 1
        except psycopg_Error as exc:
            await self.aconn.rollback()
            raise SQLError("Error while checking game existence") from exc

    async def delete_game(self, game_id: int, hard_delete: bool = False) -> None:
        try:
            async with self.aconn.cursor() as curs:
                for game_table in GAME_TABLES:
                    query = sql.SQL(
                        "DELETE FROM iris.{table} WHERE game_id = %s;"
                    ).format(table=sql.Identifier(game_table))
                    data = (game_id,)

                    await curs.execute(query, data)

                if hard_delete:
                    query = sql.SQL("DELETE FROM iris.game WHERE id=%s;")
                    data = (game_id,)

                    await curs.execute(query, data)

                else:
                    query = sql.SQL(
                        """
                        --begin-sql
                        UPDATE iris.game 
                            SET category = null, collection_id = null, 
                                complete = false, first_release_date = null, parent_game = null, 
                                rating = null, slug = null, summary = null 
                            WHERE id=%s;"""
                    )
                    data = (game_id,)

                    await curs.execute(query, data)

                await self.aconn.commit()
                logger.info("Game ID %s has been successfully deleted.", game_id)
        except psycopg_Error as exc:
            await self.aconn.rollback()
            raise SQLError(f"Error while deleting game ID {game_id}") from exc

    async def get_categories_by_game_id(self, game_id: int) -> list:
        """Get categories of a game by game ID

        Args:
            game_id (int): Game ID

        Raises:
            SQLError: Error while getting categories

        Returns:
            list: List of categories
        """
        try:
            async with self.aconn.cursor() as curs:
                query = sql.SQL(
                    """--begin-sql
                    SELECT
                        t.id,
                        t.name,
                        t.slug
                    FROM
                        iris.theme t
                    LEFT JOIN
                        iris.game_theme gt 
                            ON
                        gt.theme_id = t.id
                    WHERE
                        gt.game_id = %s;"""
                )
                data = (game_id,)

                await curs.execute(query, data)
                return await curs.fetchall()
        except psycopg_Error as exc:
            raise SQLError("Error while getting categories") from exc

    async def get_full_game_data(self, game_id: int) -> dict:
        """ Get full game data from database

        Args:
            game_id (int): Game ID
            sort_type (str, optional): Sort type. Defaults to "default". 
                Possible values: "default", "random", "recent", "rating".

        Raises:
            SQLError: Error while getting full game data

        Returns:
            dict: Full game data (
                id, name, complete, cover_id, cover_hash, parent_game, collection_id, collection_name,
                first_release_date, rating, popularity, summary, type, main_album_id
            )
        """        
        try:
            async with self.aconn.cursor() as curs:
                query = sql.SQL(
                    """--begin-sql    
                    SELECT
                        g.id,
                        g.name,
                        g.complete,
                        m.image_id AS cover_id,
                        m.blur_hash AS cover_hash,
                        g.parent_game,
                        g.collection_id,
                        c2.name AS collection_name,
                        g.first_release_date,
                        round(g.rating::numeric, 2) AS rating,
                        g.popularity,
                        g.summary,
                        c.name AS TYPE,
                        a.id AS main_album_id
                    FROM
                        iris.game g
                    LEFT JOIN
                        iris.media m 
                            ON
                        m.game_id = g.id
                        AND m.type = 'cover'
                    LEFT JOIN
                        iris.album a 
                            ON
                        a.game_id = g.id
                        AND a.is_main
                        AND a.is_visible
                    LEFT JOIN
                        iris.category c 
                            ON
                        c.id = g.category
                    LEFT JOIN 
                        iris.collection c2 
                            ON
                        c2.id = g.collection_id 
                    WHERE
                        g.id = %s;
                """
                )
                data = (game_id,)

                await curs.execute(query, data)
                res = await curs.fetchone()
                
                res["categories"] = await self.get_categories_by_game_id(game_id)
                
                return res
        except psycopg_Error as exc:
            raise SQLError("Error while getting base game data") from exc

    async def get_reduced_game_data(self, game_id: int) -> dict:
        try:
            async with self.aconn.cursor() as curs:
                query = sql.SQL(
                    """--begin-sql
                    SELECT
                        g.id,
                        g.name,
                        m.image_id as cover_id,
                        m.blur_hash as cover_hash,
                        a.id as album_id
                    FROM
                        iris.game g
                    LEFT JOIN
                        iris.media m 
                            on m.game_id = g.id
                            and m.type = 'cover'
                    LEFT JOIN
                        iris.album a 
                            on a.game_id = g.id
                            and a.is_main 
                            and a.is_visible 
                    WHERE
                        g.id = %s;"""
                )
                data = (game_id,)

                await curs.execute(query, data)
                return await curs.fetchone()
        except psycopg_Error as exc:
            raise SQLError("Error while getting base game data") from exc

    async def get_next_album_id(self):
        try:
            async with self.aconn.cursor() as curs:
                query = sql.SQL("SELECT MAX(id) FROM iris.album;")
                await curs.execute(query)
                res = await curs.fetchone()
                max_id = res.get("max")

                if max_id is None:
                    return 1
                else:
                    return max_id + 1
        except psycopg_Error as exc:
            raise SQLError("Error while getting next album id") from exc

    async def check_album_existence(self, game_id):
        try:
            async with self.aconn.cursor() as curs:
                name = "Original Soundtrack"

                query = sql.SQL(
                    "SELECT id FROM iris.album WHERE game_id=%s AND name=%s;"
                )
                data = (game_id, name)

                await curs.execute(query, data)
                res = await curs.fetchone()

                return res.get("id", None) if res else None
        except psycopg_Error as exc:
            raise SQLError("Error while checking album existence") from exc

    async def add_game_tracks(self, game_id, album_id, tracks, source, video_id):
        try:
            async with connectors.iris_aconn.transaction():
                async with self.aconn.cursor() as curs:
                    query = sql.SQL(
                        """INSERT INTO iris.album_source(name, media_type, url)
                            VALUES (%s,%s,%s) RETURNING id;"""
                    )
                    # "video" in place of media_type is a placeholder for now
                    data = (
                        source,
                        "video",
                        "https://www.youtube.com/watch?v=" + video_id,
                    )
                    await curs.execute(query, data)
                    res = await curs.fetchone()
                    source_id = res.get("id")

                    name = "Original Soundtrack"
                    name_slug = slugify(name)

                    query = sql.SQL(
                        """INSERT INTO iris.album (id, game_id, name, slug, is_main, is_visible, source_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s);"""
                    )
                    data = (album_id, game_id, name, name_slug, "t", "t", source_id)
                    await curs.execute(query, data)

                    for track in tracks:
                        if track["title"] is None:
                            track["title"] = "Untitled"

                        query = sql.SQL(
                            """INSERT INTO iris.track 
                                    (game_id, title, slug, file_id, length)
                            VALUES (%s,%s,%s,%s,%s) RETURNING id;"""
                        )
                        data = (
                            game_id,
                            track["title"],
                            slugify(track["title"]),
                            track["id"],
                            track["duration"],
                        )
                        await curs.execute(query, data)
                        res = await curs.fetchone()
                        track_id = res.get("id")

                        query = sql.SQL(
                            "INSERT INTO iris.album_track (album_id, track_id) VALUES (%s,%s);"
                        )
                        data = (album_id, track_id)
                        await curs.execute(query, data)

            await self.aconn.commit()
        except psycopg_Error as exc:
            await self.aconn.rollback()
            logger.error(traceback.format_exc())
            raise SQLError("Error while adding game tracks") from exc

    async def get_games_sorted(self, sort_type, sort_order, offset, limit):
        # TODO
        return None
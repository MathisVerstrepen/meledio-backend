import traceback
from typing import Literal
from slugify import slugify
from psycopg import Error as psycopg_Error, sql

from app.internal.IRIS.data_access_layer.iris_dal_new_game import IrisDalNewGame
from app.internal.IRIS.iris_const import GAME_TABLES

from app.internal.errors.iris_exceptions import SQLError
from app.utils.loggers import base_logger as logger
import app.connectors as connectors


class IrisDataAccessLayer:
    """Class for IRIS Data Access Layer to the database"""

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

    async def get_full_game_data(self, game_id: int) -> dict:
        """Get full game data from database

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
                return await curs.fetchone()
        except psycopg_Error as exc:
            raise SQLError("Error while getting base game data") from exc

    async def get_games_sorted(
        self,
        sort_type: Literal["g.rating", "random()", "g.first_release_date"],
        sort_order: Literal["asc", "desc"],
        offset: int,
        limit: int,
    ) -> list:
        """Get reduced games sorted by a specific type (rating, random, recent)
            by a specific order (asc, desc)

        Args:
            sort_type (str): Field to sort by
            sort_order (str): Sort order
            offset (int): Offset
            limit (int): Limit

        Raises:
            SQLError: Error while getting games data

        Returns:
            list: Reduced games data
        """
        try:
            async with self.aconn.cursor() as curs:
                query = sql.SQL(
                    """--begin-sql    
                    SELECT
                        g.id,
                        g.name,
                        m.image_id AS cover_id,
                        m.blur_hash AS cover_hash,
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
                    WHERE 
                        g.complete 
                    ORDER BY {sort_type} {sort_order}
                    OFFSET %s
                    LIMIT %s;
                    """
                )
                query = query.format(
                    sort_type=sql.SQL(sort_type),
                    sort_order=sql.SQL(sort_order),
                )
                data = (offset, limit)

                await curs.execute(query, data)
                return await curs.fetchall()
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

    async def get_game_top_tracks(self, game_id: int, offset: int, limit: int) -> list:
        """Get top tracks of a game by game ID

        Args:
            game_id (int): Game ID

        Raises:
            SQLError: Error while getting top tracks

        Returns:
            list: List of top tracks
        """
        try:
            async with self.aconn.cursor() as curs:
                query = sql.SQL(
                    """--begin-sql
                    SELECT 
                        t.id AS track_id,
                        at2.album_id,
                        t.title,
                        t.slug,
                        t.file_id AS mpd,
                        t.like_count,
                        t.play_count,
                        t.last_played,
                        t.length
                    FROM 
                        iris.track t 
                    LEFT JOIN
                        iris.album_track at2 
                        ON
                        at2.track_id = t.id
                    INNER JOIN 
                        iris.album a 
                        ON
                        a.id = at2.album_id 
                        AND 
                        a.is_main 
                    WHERE
                        t.game_id = %s
                    ORDER BY 
	                    t.play_count desc
                    OFFSET %s
                    LIMIT %s;"""
                )
                data = (game_id, offset, limit)

                await curs.execute(query, data)
                return await curs.fetchall()
        except psycopg_Error as exc:
            raise SQLError("Error while getting top tracks") from exc

    async def get_games_albums(self, game_id: int) -> list:
        """Get the list of albums of a game by its ID

        Args:
            game_id (int): Game ID

        Raises:
            SQLError: Error while getting albums

        Returns:
            list: List of albums
        """
        try:
            async with self.aconn.cursor() as curs:
                query = sql.SQL(
                    """--begin-sql
                    SELECT
                        a.id AS album_id,
                        a."name" ,
                        a.slug ,
                        a.is_certified ,
                        a.is_main ,
                        a.created_at ,
                        a.like_count
                    FROM
                        iris.album a 
                    WHERE 
                        a.game_id  = %s;"""
                )
                data = (game_id,)

                await curs.execute(query, data)
                return await curs.fetchall()
        except psycopg_Error as exc:
            raise SQLError("Error while getting albums") from exc

    async def get_game_related_games(
        self, game_id: int, offset: int, limit: int
    ) -> list:
        """Get related games of a game by game ID

        Args:
            game_id (int): Game ID

        Raises:
            SQLError: Error while getting related games

        Returns:
            list: List of related games
        """
        try:
            async with self.aconn.cursor() as curs:
                query = sql.SQL(
                    """--begin-sql
                    SELECT
                        ec.extra_id,
                        g.name,
                        m.image_id AS cover_id,
                        m.blur_hash AS cover_hash,
                        a.id AS main_album_id
                    FROM
                        iris.extra_content AS ec
                    LEFT JOIN iris.game g ON
                        g.id = ec.extra_id 
                    LEFT JOIN iris.media m ON
                        m.game_id = ec.extra_id 
                        AND m.type = 'cover'
                    LEFT JOIN
                        iris.album a 
                            ON
                        ec.extra_id  = a.game_id
                        AND a.is_main
                        AND a.is_visible
                    WHERE ec.game_id = %s AND ec."type" = 'similar_game' 
                    OFFSET %s
                    LIMIT %s;"""
                )
                data = (game_id, offset, limit)

                await curs.execute(query, data)
                return await curs.fetchall()
        except psycopg_Error as exc:
            raise SQLError("Error while getting related games") from exc

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

    async def get_collection_info_by_id(self, collection_id: int) -> dict:
        """Data Access Layer method to get collection info by ID

        Args:
            collection_id (int): The ID of the collection

        Returns:
            dict: Collection data
        """

        try:
            async with self.aconn.cursor() as curs:
                query = sql.SQL(
                    """--begin-sql
                    SELECT
                        c."name" AS collection_name,
                        count(DISTINCT(g.id)) AS n_games,
                        count(at2.track_id) AS n_tracks
                    FROM
                        iris.collection c
                    LEFT JOIN iris.game g 
                        ON g.collection_id = c.id
                    LEFT JOIN iris.media m ON
                        m.game_id = g.id
                        AND m.type = 'cover'
                    LEFT JOIN
                        iris.album a 
                            ON
                        g.id = a.game_id
                        AND a.is_main
                        AND a.is_visible
                    LEFT JOIN 
                        iris.album_track at2 
                        ON at2.album_id = a.id 
                    WHERE c.id = %s
                    GROUP BY c.name;"""
                )
                data = (collection_id,)

                await curs.execute(query, data)
                return (await curs.fetchall())[0]
        except psycopg_Error as exc:
            raise SQLError("Error while getting related games") from exc

    async def get_collection_reduce_game_info(self, collection_id: int) -> list[dict]:
        """Data Access Layer method to get collection minimal game info by ID

        Args:
            collection_id (int): The ID of the collection

        Returns:
            dict: Collection data
        """

        try:
            async with self.aconn.cursor() as curs:
                query = sql.SQL(
                    """--begin-sql
                    SELECT
                        g.id,
                        g.name,
                        m.image_id AS cover_id,
                        m.blur_hash AS cover_hash,
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
                    WHERE 
                        g.collection_id = %s;"""
                )
                data = (collection_id,)

                await curs.execute(query, data)
                return await curs.fetchall()
        except psycopg_Error as exc:
            raise SQLError("Error while getting related games") from exc

    async def get_collection_top_tracks(
        self, collection_id: int, offset: int, limit: int
    ) -> list:
        """Data Access Layer method to get collection top tracks by ID

        Args:
            collection_id (int): The ID of the collection

        Returns:
            dict: Collection data
        """

        try:
            async with self.aconn.cursor() as curs:
                query = sql.SQL(
                    """--begin-sql
                    SELECT 
                        t.id AS track_id,
                        at2.album_id,
                        t.title,
                        t.slug,
                        t.file_id AS mpd,
                        t.like_count,
                        t.play_count,
                        t.last_played,
                        t.length
                    FROM
                        iris.game g 
                    LEFT JOIN  
                        iris.track t 
                        ON t.game_id = g.id 
                    LEFT JOIN
                        iris.album_track at2 
                        ON
                        at2.track_id = t.id
                    INNER JOIN 
                        iris.album a 
                        ON
                        a.id = at2.album_id 
                        AND 
                        a.is_main 
                    WHERE
                        g.collection_id = %s
                    ORDER BY 
                        t.play_count desc
                    OFFSET %s
                    LIMIT %s;"""
                )
                data = (collection_id, offset, limit)

                await curs.execute(query, data)
                return await curs.fetchall()
        except psycopg_Error as exc:
            raise SQLError("Error while getting top tracks") from exc

    async def get_collections_sorted(
        self,
        sort_type: Literal["c.name", "c.n_games", "c.n_tracks"],
        sort_order: Literal["asc", "desc"],
        offset: int,
        limit: int,
    ) -> list:
        """Data Access Layer method to get collection sorted by a specific type (name, n_games, n_tracks)
            by a specific order (asc, desc)

        Args:
            sort_type (str): Field to sort by
            sort_order (str): Sort order
            offset (int): Offset
            limit (int): Limit

        Raises:
            SQLError: Error while getting games data

        Returns:
            list: Reduced games data
        """
        try:
            async with self.aconn.cursor() as curs:
                query = sql.SQL(
                    """--begin-sql    
                    SELECT
                        c.id,
                        c.name,
                        count(DISTINCT(g.id)) AS n_games,
                        avg(DISTINCT(g.rating)) AS avg_rating,
                        max(DISTINCT(g.first_release_date)) AS latest_game_release_date,
                        count(at2.track_id) AS n_tracks
                    FROM
                        iris.collection c
                    LEFT JOIN iris.game g 
                        ON g.collection_id = c.id
                    LEFT JOIN iris.media m ON
                        m.game_id = g.id
                        AND m.type = 'cover'
                    LEFT JOIN
                        iris.album a 
                            ON
                        g.id = a.game_id
                        AND a.is_main
                        AND a.is_visible
                    LEFT JOIN 
                        iris.album_track at2 
                        ON at2.album_id = a.id 
                    GROUP BY c.id
                    ORDER BY random() desc
                    OFFSET %s
                    LIMIT %s;
                    """
                )
                query = query.format(
                    sort_type=sql.SQL(sort_type),
                    sort_order=sql.SQL(sort_order),
                )
                data = (offset, limit)

                await curs.execute(query, data)
                return await curs.fetchall()
        except psycopg_Error as exc:
            raise SQLError("Error while getting base game data") from exc

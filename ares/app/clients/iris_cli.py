# Description: Iris DB client wrapper
# type: ignore

from app.clients.igdb_cli import IGDB
from psycopg2 import sql
import threading
import logging
import logging.handlers
import json
import requests
from slugify import slugify
from datetime import datetime
from timeit import default_timer as timer
import blurhash
from collections.abc import Generator

from dotenv import load_dotenv
load_dotenv()

# ------ Load basic knowledge needed for database push of retrived data ------ #
f = open('./app/config/IGDB_IRIS_association.json')
SQL_schema: dict = json.load(f)

# ------------- Load category_id / category label correspondance ------------- #
f = open('./app/config/category.json')
SQL_category: dict = json.load(f)

# -------------------- Create database cursor with logging ------------------- #
from app.utils.loggers import base_logger
from app.utils.loggers import get_database_logger
sql_logger, LoggingCursor = get_database_logger()

from psycopg2.extras import RealDictCursor

class LoggingRealDictCursor(RealDictCursor, LoggingCursor):
    pass

DOWNLOAD_QUALITY = {
    "artworks": [
        ["screenshot_med", "a_m"],
        ["screenshot_big", "a_b"],
        ["screenshot_huge", "a_h"],
    ],
    "cover": [["cover_small", "c_s"], ["cover_big", "c_b"]],
    "screenshots": [
        ["screenshot_med", "s_m"],
        ["screenshot_big", "s_b"],
        ["screenshot_huge", "s_h"],
    ],
}

GAMEID_TABLES = [
    "album",
    "alternative_name",
    "media",
    "extra_content",
    "genre",
    "involved_companies",
    "keyword",
    "theme",
    "track"
]

PRE_CALC_DATA = {
    "base_columns": ['name', 'slug', 'complete', 'parent_game', 'category', 'collection_id', 'first_release_date', 'rating', 'popularity', 'summary', 'n_tracks'],
    "track_columns": ['title', 'track_slug', 'file', 'view_count', 'like_count', 'length'],
    "company_columns": ['company_id', 'developer', 'porting', 'publisher', 'supporting', 'name', 'slug', 'description', 'logo_id'],
    "album_columns": ['game_id', 'game_name', 'game_slug', 'game_cover', 'game_blurhash', 'album_id', 'album_name', 'album_slug', 'album_n_tracks'],
    'similar_games_columns': ['game_id', 'name', 'slug', 'cover', 'blurhash'],
}

def image_downloader(IGDB_client, field, media):
    hash = media["image_id"]
    blur_hashs = []
    for qual in DOWNLOAD_QUALITY[field]:
        res = IGDB_client.images(qual[0], hash)
        with open(f"/bacchus/media/{qual[1]}_{hash}.jpg", "wb") as f:
            f.write(res)
            
        with open(f"/bacchus/media/{qual[1]}_{hash}.jpg", 'rb') as image_file:
            blur_hash = blurhash.encode(image_file, x_components=4, y_components=3)
            if blur_hash : blur_hashs.append(blur_hash)
    
    return blur_hashs[-1]

from app.utils.connection import IRIS_CONN, REDIS_GAMES

class iris:
    def __init__(self):
        self.rcli = REDIS_GAMES
        self.conn = IRIS_CONN
        self.IGDB_cli = IGDB()

    def isGameInDatabase(self, curs, table, id):
        query = sql.SQL("SELECT complete FROM iris.{table} where id=%s;").format(
                table=sql.Identifier(table))
        curs.execute(query, (id,))
        return curs.fetchone()
    
    def getGameName(self, gameID: int) -> str:
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT name FROM iris.game WHERE id = %s;")
            curs.execute(query, (gameID,))
            return curs.fetchone()[0]
        
    # UNUSED
    def getAlbum(self, gameID: int, albumName: str) -> list:
        """Get the playlist of a game by its name if it exists

        Args:
            gameID (int): Game ID
            albumName (str): Name of the album

        Returns:
            list: List of track IDs
        """
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("""SELECT track_id FROM iris.album WHERE game_id = %s AND name = %s;""")
            curs.execute(query, (gameID, albumName))
            if curs.rowcount == 0:
                return []
            return curs.fetchall()
        
    # UNUSED
    def addAlbum(self, gameID: int, albumName: str, trackIDs: list):
        """ Add a new album to the database

        Args:
            gameID (int): Game ID
            albumName (str): Album name
            trackIDs (list): List of track IDs
        """
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("""INSERT INTO iris.album (game_id, name, track_id) VALUES (%s, %s, %s);""")
            curs.execute(query, (gameID, albumName, trackIDs))
        
        self.conn.commit()

    # UNUSED
    def searchGameByName(self, searchText : str) :
        req = f"({searchText})|({searchText.strip()}*)|({searchText.strip()})"
        returnVal = []
        try :
            res = self.rcli.ft("gameIdx").search(req)
            for row in res.docs:
                jsonrow = json.loads(row.json)
                logging.info(jsonrow)
                returnVal.append({
                    "name" : jsonrow['name'],
                    "cover" : jsonrow['media']['cover'] if jsonrow.get('media') else None,
                    "id" : row.id.split(':')[1],
                })
        except:
            pass

        return returnVal

    def push_chapters(self, gameID: int, chapters: list) -> None:
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            
            name = self.getGameName(gameID) + " - Full OST"
            name_slug = slugify(name)
            
            query = sql.SQL("INSERT INTO iris.album (game_id, name, slug, is_main) VALUES (%s,%s,%s,%s) RETURNING id;")
            data = (gameID, name, name_slug, 't')
            curs.execute(query, data)
            album_id = curs.fetchone()[0]
            
            for chapter in chapters:
                query = sql.SQL("INSERT INTO iris.track (game_id, title, slug, file, view_count, like_count, length)"
                                "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id;")
                data = (gameID, chapter['title'], slugify(chapter['title']), chapter['file'], 0, 0, chapter['duration'])
                curs.execute(query, data)
                track_id = curs.fetchone()[0]
                
                query = sql.SQL("INSERT INTO iris.album_track (album_id, track_id) VALUES (%s,%s);")
                data = (album_id, track_id)
                curs.execute(query, data)
                
        self.conn.commit()

    # ---------------------------------------------------------------------------- #
    #                                 PUSH NEW GAME                                #
    # ---------------------------------------------------------------------------- #

    # MIGRATION DONE
    def push_new_game(self, game_data: dict) -> None:
        """Push new game to database

        Args:
            game_data (_type_): _description_
        """
        
        base_logger.info("Pushing new game to database.")
        gameID = game_data[0]["id"]

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:

            INDB = self.isGameInDatabase(curs, "game", gameID)
            
            if not INDB:
                #-- Contruct base db data --# 
                query = "INSERT INTO iris.game (id) VALUES (%s);"
                data = (gameID, )
                curs.execute(query, data)

            if not INDB or not INDB[0]:
                #-- Upload all metadata to DB --#
                
                for field in game_data[0]:
                    logging.info(field)
                    field_data = game_data[0][field]
                    field_schema_data = SQL_schema.get(field)
                    field_type = field_schema_data.get('type') 
                    
                    #-- Game table root column --#
                    if field_type == 'base':
                        
                        query = sql.SQL("UPDATE iris.game SET {field} = %s WHERE id=%s;").format(
                                field=sql.Identifier(field_schema_data.get('field')))
                        data = (field_data, gameID,)
                        logging.info(query)
                        logging.info(data)
                        curs.execute(query, data)
                                                
                    #-- Game table root column but type date --# 
                    elif field_type == 'date':
                        
                        query = sql.SQL("UPDATE iris.game SET {field} = %s WHERE id=%s;").format(
                                field=sql.Identifier(field_schema_data.get('field')))
                        data = (datetime.fromtimestamp(field_data), gameID,)
                        curs.execute(query, data)
                                                
                    #-- Game table root column but parent game --# 
                    elif field_type == 'parent':
                        logging.info(field_data)
                        if not self.isGameInDatabase(curs, "game", field_data["id"]):
                            query = sql.SQL("INSERT INTO iris.game (id, complete, name) VALUES (%s,False,%s);")
                            data = (field_data["id"], field_data["name"],)
                            curs.execute(query, data)
                                                    
                        query = sql.SQL("UPDATE iris.game SET {field} = %s WHERE id=%s;").format(
                                field=sql.Identifier(field_schema_data.get('field')))
                        data = (field_data["id"], gameID,)
                        curs.execute(query, data)
                                                
                    #-- All sort of extra content of the game --# 
                    elif field_type == 'extra':
                        for extra_data in field_data:
                            if not self.isGameInDatabase(curs, "game", extra_data["id"]):
                                query = sql.SQL("INSERT INTO iris.game (id, complete, name) VALUES (%s,False,%s);")
                                data = (extra_data["id"], extra_data["name"],)
                                curs.execute(query, data)
                                
                            query = sql.SQL("INSERT INTO iris.{table} (game_id, extra_id, type) VALUES (%s,%s,%s);").format(
                                    table=sql.Identifier(field_schema_data.get('field')))
                            data = (gameID, extra_data["id"], field,)
                            curs.execute(query, data)

                    #-- Game table root column and external table --#    
                    elif field_type == 'base-ext':
                        
                        #-- Insert data to external linked table --# 
                        query = sql.SQL("INSERT INTO iris.{table} ({fields}) VALUES ({values}) ON CONFLICT DO NOTHING;").format(
                                table=sql.Identifier(field_schema_data.get('field')),
                                fields=sql.SQL(',').join(sql.Identifier(nfield) for nfield in field_data.keys()),
                                values=sql.SQL(', ').join(sql.Placeholder()*len(field_data)),
                            )
                        data = [*field_data.values()]
                        curs.execute(query, data)
                                                
                        #-- Update root game table --# 
                        query = sql.SQL("UPDATE iris.game SET {field} = %s WHERE id=%s;").format(
                                field=sql.Identifier(field_schema_data.get('base_field')))
                        data = (field_data["id"], gameID,)
                        curs.execute(query, data)
                        
                    #-- Company and involved companies tables --#    
                    elif field_type == 'company':
                        
                        company_data: list = self.IGDB_cli.companies(field_data)
                        for company in company_data:
                            query = sql.SQL("INSERT INTO iris.{table} (id, name, slug, description, logo_id) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING;").format(
                                    table=sql.Identifier(field_schema_data.get('sub_field')),
                                )
                            data = (
                                company.get("id"),
                                company.get("name"),
                                company.get("slug"),
                                company.get("description"),
                                company.get("logo", {}).get("image_id"),
                            )
                            curs.execute(query, data)
                            
                        for involved_company in field_data:
                            
                            query = sql.SQL("INSERT INTO iris.{table} (game_id, company_id, developer, porting, publisher, supporting) VALUES (%s,%s,%s,%s,%s,%s);").format(
                                    table=sql.Identifier(field_schema_data.get('field')),
                                )
                            data = (
                                gameID,
                                involved_company.get("company"),
                                involved_company.get("developer"),
                                involved_company.get("porting"),
                                involved_company.get("publisher"),
                                involved_company.get("supporting"),
                            )
                            curs.execute(query, data)
                            
                    #-- Media tables (screenshots, artworks, cover) --#
                    elif field_type == 'media':
                        
                        def insert_media(media):
                            blur_hash = image_downloader(self.IGDB_cli, field, media)
                            
                            query = sql.SQL("INSERT INTO iris.{table} (image_id, game_id, type, height, width, blur_hash) VALUES (%s,%s,%s,%s,%s,%s);").format(
                                    table=sql.Identifier(field_schema_data.get('field')),
                                )
                            data = (
                                media.get("image_id"),
                                gameID,
                                field,
                                media.get("height"),
                                media.get("width"),
                                blur_hash,
                            )
                            curs.execute(query, data)
                        
                        if isinstance(field_data, list):
                            for media in field_data: 
                                insert_media(media)
                        else:
                            insert_media(field_data)
                            
                    #-- All other tables --#
                    elif field_type == 'normal':
                        for elmt_data in field_data:
                            query = sql.SQL("INSERT INTO iris.{table} (game_id,{fields}) VALUES ({values});").format(
                                    table=sql.Identifier(field_schema_data.get('field')),
                                    fields=sql.SQL(',').join(sql.Identifier(nfield) for nfield in ([*elmt_data.keys()])[1:]),
                                    values=sql.SQL(', ').join(sql.Placeholder()*len(elmt_data)),
                                )
                            data = [gameID, *([*elmt_data.values()])[1:]]
                            curs.execute(query, data)

                    query = sql.SQL("UPDATE iris.game SET complete = true WHERE id=%s;")
                    data = (gameID,)
                    curs.execute(query, data)
                                    
        self.conn.commit()


    def del_game(self, gameID: int) -> bool:

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:

            query = sql.SQL("SELECT image_id FROM iris.media WHERE game_id=%s;")
            curs.execute(query, (gameID,))
            res = curs.fetchall()
            medias_hash = [hash[0] for hash in res]

            requests.delete(
                "http://media.meledio.com/del_media", data=json.dumps({"medias": medias_hash})
            )
            
            # inCache = self.isGameCached(gameID)
            inDB = self.isGameInDatabase(curs, "game", gameID)
            
            # if inCache:
            #     gameName = self.rcli.json().get(f"g:{gameID}", "$.name")[0]
            #     self.rcli.json().set(f"g:{gameID}", "$", {
            #         'complete': False,
            #         'name': gameName
            #     })
                
            if inDB: 
                for table in GAMEID_TABLES:
                    query = sql.SQL("DELETE FROM iris.{table} WHERE game_id = %s;").format(
                            table=sql.Identifier(table))
                    curs.execute(query, (gameID,))

                query = sql.SQL("UPDATE iris.game SET category = null, collection_id = null, complete = false, first_release_date = null, parent_game = null, rating = null, slug = null, summary = null WHERE id=%s;")
                curs.execute(query, (gameID,))

        self.conn.commit()
    
    
    # ---------------------------------------------------------------------------- #
    #                                 GET GAME DATA                                #
    # ---------------------------------------------------------------------------- #
    
    # --------------------------------- Full Wrapper -------------------------------- #
    
    async def get_game(self, gameID: int, labels: list[str] = ['base'], debug: bool = False) -> dict:
        """ Wrapper for all the get_game_* functions, allow to get specific data from a game

        Args:
            gameID (int): Game ID
            labels (list[str], optional): List of labels to filter by. Defaults to ['base'].
            debug (bool, optional): Specify if performance debug mode is active. Defaults to False.

        Returns:
            dict: Dictionary with the wanted data
        """
        
        game_data = {}
        debug_data = {}

        for label in labels:
            start = timer()
            match label:
                case 'base':
                    res = self.get_game_base(gameID)
                case 'artworks' | 'cover' | 'screenshots':
                    res = self.get_game_media(gameID, label)
                case 'alternative_name':
                    res = self.get_game_alternative_name(gameID)
                case 'album':
                    res = self.get_game_album(gameID)
                case 'involved_companies':
                    res = self.get_game_involved_companies(gameID)
                case 'dlcs' | 'expansions' | 'expanded_games' | 'similar_games' | 'standalone_expansions':
                    res = self.get_game_extra_content(gameID, label)
                case 'genre':
                    res = self.get_game_genre(gameID)
                case 'theme':
                    res = self.get_game_theme(gameID)
                case 'keyword':
                    res = self.get_game_keyword(gameID)
                case _:
                    continue
            game_data[label] = res
            end = timer()
            if debug: debug_data[label] = (end - start) * 1000

        return {"debug_data": debug_data, "gameID": gameID, "data": game_data}
    
    # --------------------------------- Base data -------------------------------- #
    
    def get_game_base(self, gameID: int) -> dict:
        """ Get game base data

        Args:
            gameID (int): Game ID

        Returns:
            dict: Game base data
        """
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            
            query = sql.SQL("select * from iris.get_game_info(%s)")
            curs.execute(query, (gameID,))
            res = curs.fetchone()

            if res: 
                return {column:res[i] for i, column in enumerate(PRE_CALC_DATA['base_columns'])}
            else: 
                return {}
        
    # ---------------------------- All media type data --------------------------- #
    
    def get_game_media(self, gameID, media_type) -> dict:
        """ Get all data from a media type of a game in the database

        Args:
            gameID (int): Game ID
            media_type (str): Media type (screenshots, artwork, cover)

        Returns:
            dict: Media data
        """
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            
            query = sql.SQL("SELECT image_id, blur_hash FROM iris.media WHERE game_id=%s AND type=%s;")
            curs.execute(query, (gameID, media_type,))
            res = curs.fetchall()

            return [{'id': row[0], 'blurhash': row[1]} for row in res]

    # ------------------------------ Main album data ----------------------------- #
        
    def get_game_album(self, gameID: int) -> dict:
        """ Get all data from the main album of a game in the database

        Args:
            gameID (int): Game ID

        Returns:
            dict: Album data
        """
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT * FROM iris.get_album_tracks(%s)")
            curs.execute(query, (gameID,))
            res = curs.fetchall()
            
            if res:
                return {
                    'id' : res[0][0],
                    'name' : res[0][1],
                    'slug' : res[0][2],
                    'track' : [{column: row[i+2] for i, column in enumerate(PRE_CALC_DATA['track_columns'])} for row in res]
                }
            else: 
                return {}
        
    # ---------------------------- Similar games data ---------------------------- # 
    
    def get_similar_games(self, gameID: int) -> list[dict]:
        """ Get all data from the similar games of a game in the database

        Args:
            gameID (int):  Game ID

        Returns:
            list[dict]: Similar games data
        """
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT * FROM iris.get_similar_games(%s)")
            curs.execute(query, (gameID,))
            res = curs.fetchall()

            return [{
                        "gameID" : row[0],
                        "data" : {
                            "base" : {
                                "name" : row[1],
                                "slug" : row[2],
                            },
                            "cover" : [
                                {
                                    "id" : row[3],
                                    "blurhash" : row[4]
                                }
                            ]                            
                        }
                    } for row in res]
        
    
    # ---------------------------- All related Albums ---------------------------- #
    
    async def get_game_albums(self, gameID: int) -> list:
        """ Get all data from the related albums of a game in the database

        Args:
            gameID (int): Game ID

        Returns:
            list: Related albums data
        """
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT * FROM iris.get_game_albums(%s)")
            curs.execute(query, (gameID,))
            res = curs.fetchall()

            return [{column: row[i] for i, column in enumerate(PRE_CALC_DATA['album_columns'])} for row in res]

    # -------------------------- Involved companies data ------------------------- #
        
    def get_game_involved_companies(self, gameID: int) -> dict:
        """ Get all data from the involved companies of a game in the database

        Args:
            gameID (int): Game ID

        Returns:
            dict: Involved companies data
        """

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT * FROM iris.get_game_company(%s)")
            curs.execute(query, (gameID,))
            res = curs.fetchall()

            return [{column: row[i] for i, column in enumerate(PRE_CALC_DATA['company_columns'])} for row in res]
        
    # ---------------------------- All 'extra' content --------------------------- #
        
    def get_game_extra_content(self, gameID: int, extra_type: str) -> dict:
        """ Get all data from a extra content type of a game in the database

        Args:
            gameID (int): Game ID
            extra_type (str): Extra content type (dlcs, expansions, expanded_games, similar_games, standalone_expansions)

        Returns:
            dict: Extra content data
        """

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL(
                "SELECT extra_id FROM iris.extra_content WHERE game_id=%s AND type=%s;")
            curs.execute(query, (gameID, extra_type,))
            res = curs.fetchall()

            return [row[0] for row in res]
        
    # -------------------------------- Genre data -------------------------------- #
        
    def get_game_genre(self, gameID: int) -> dict:
        """ Get all data from the genres of a game in the database

        Args:
            gameID (int): Game ID

        Returns:
            dict: Genre data
        """

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL(
                "SELECT name,slug FROM iris.genre WHERE iris.genre.game_id = %s;")
            curs.execute(query, (gameID,))
            res = curs.fetchall()
            column = ['name', 'slug']

            return [{column[i]:row[i] for i in range(2)} for row in res]
        
    # -------------------------------- Theme data -------------------------------- #
        
    def get_game_theme(self, gameID: int) -> dict:
        """ Get all data from the themes of a game in the database

        Args:
            gameID (int): Game ID

        Returns:
            dict: Theme data
        """

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL(
                "SELECT name,slug FROM iris.theme WHERE iris.theme.game_id = %s;")
            curs.execute(query, (gameID,))
            res = curs.fetchall()
            column = ['name', 'slug']

            return [{column[i]:row[i] for i in range(2)} for row in res]

    # ------------------------------- Keywords data ------------------------------ #

    def get_game_keyword(self, gameID: int) -> dict:
        """ Get all data from the keywords of a game in the database

        Args:
            gameID (int): Game ID

        Returns:
            dict: Keyword data
        """

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL(
                "SELECT id,name,slug FROM iris.keyword WHERE iris.keyword.game_id = %s;")
            curs.execute(query, (gameID,))
            res = curs.fetchall()
            column = ['id', 'name', 'slug']

            return [{column[i]:row[i] for i in range(3)} for row in res]

    # -------------------------- Alternative names data -------------------------- #

    def get_game_alternative_name(self, gameID: int) -> dict:
        """ Get all data from the alternative names of a game in the database

        Args:
            gameID (int): Game ID

        Returns:
            dict: Alternative name data
        """

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL(
                "SELECT * FROM iris.alternative_name WHERE game_id=%s;")
            curs.execute(query, (gameID,))
            res = curs.fetchall()
            column = ['id', 'game_id', 'name', 'comment']

            return [{column[i]:row[i] for i in range(4)} for row in res]

    
    # ---------------------------------------------------------------------------- #
    #                               GET GAME FUNCTIONS                             #
    # ---------------------------------------------------------------------------- #
    
    # ------------------------------- Random Games ------------------------------- #
    
    async def get_random_games(self, number: int, labels: list[str], debug: bool) -> Generator:
        """ Get a specified number of random games from the database that are complete

        Args:
            number (int): Number of games to get
            labels (list[str]): List of labels to filter by
            debug (bool): Debug mode

        Returns:
            generator: Generator of random games
        """
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT id FROM iris.game WHERE complete ORDER BY random() LIMIT %s;")
            curs.execute(query, (number,))
            random_games_id = curs.fetchall()
            for random_game_id in random_games_id:
                game = await self.get_game(random_game_id[0], labels, debug)
                if game:
                    yield game
                    
    # ----------------------------- Top Rated Games ----------------------------- #

    async def get_top_rated_games(self, number: int, offset: int, labels: list[str], debug: bool) -> Generator:
        """ Get a specified number of top rated games from the database that are complete

        Args:
            number (int): Number of games to get
            offset (int): Offset of games to get
            labels (list[str]): List of labels to filter by
            debug (bool): Debug mode

        Returns:
            generator: Generator of top rated games data
        """
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT id FROM iris.game WHERE complete AND rating IS NOT NULL ORDER BY rating desc LIMIT %s OFFSET %s;")
            curs.execute(query, (number, offset,))
            top_rated_games_id = curs.fetchall()
            for top_rated_game_id in top_rated_games_id:
                game = await self.get_game(top_rated_game_id[0], labels, debug)
                if game:
                    yield game
    
    # ------------------------ Top Listened Tracks by game ----------------------- #
    
    async def get_top_listened_tracks(self, gameID: int, number: int, debug: bool) -> Generator:
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            start = timer()
            query = sql.SQL("SELECT * FROM iris.get_game_popular_tracks(%s, %s);")
            curs.execute(query, (gameID, number,))
            tracks = curs.fetchall()
            end = timer()
            
            if debug: base_logger.info(f"get_game_popular_tracks: {(end - start) * 1000}")
            
            for track in tracks:
                yield {
                    "title": track[0],
                    "slug": track[1],
                    "file": track[2],
                    "view_count": track[3],
                    "like_count": track[4],
                    "length": track[5],
                }
    
    # ---------------------------------------------------------------------------- #
    #                            GET COLLECTION FUNCTIONS                          #
    # ---------------------------------------------------------------------------- #
    
    # ----------------------------- Get Collection ------------------------------ #
       
    async def get_collection(self, collectionID: int, labels: list[str], debug: bool) -> dict:
        """ Get a collection of games from the database

        Args:
            collectionID (int): Collection ID
            labels (list[str]): List of labels to filter by
            debug (bool): Debug mode

        Returns:
            list: Dictionary of collection data and games data
        """

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT * FROM iris.get_collection_info(%s)")
            curs.execute(query, (collectionID,))
            collection_games_id = curs.fetchall()
                        
            if not collection_games_id: return None

            # Create collection data
            collection = {
                "collection": {
                    "name": collection_games_id[0][1],
                    "slug": collection_games_id[0][2]
                },
                "games": []
            }

            # Get and add games data to collection
            for collection_game_id in collection_games_id:
                game = await self.get_game(collection_game_id[0], labels, debug)
                if game:
                    collection["games"].append(game)

            return collection

    # --------------------------- Top Rated Collection -------------------------- #

    async def get_top_rated_collection(self, number: int, offset: int) -> list:
        """ Get a specified number of top rated collections from the database

        Args:
            number (int): Number of collections to get
            offset (int): Offset of collections to get

        Returns:
            list: List of top rated collections data
        """

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            start = timer()
            query = sql.SQL("SELECT * FROM iris.get_top_collections(%s, %s);")
            curs.execute(query, (number, offset,))
            top_rated_collections = curs.fetchall()
            base_logger.info(top_rated_collections)

            # Parse top rated collections
            parse_top_rated_collections = []
            collection_id = []
            last_collection_idx = []
            for top_rate_collection in top_rated_collections:
                if top_rate_collection[0] not in collection_id:
                    parse_top_rated_collections.append({
                        "collection": {
                            "id": top_rate_collection[0],
                            "name": top_rate_collection[1],
                            "slug": top_rate_collection[2]
                        },
                        "games": []
                    })
                    collection_id.append(top_rate_collection[0])
                    last_collection_idx.append(len(parse_top_rated_collections) - 1)
                parse_top_rated_collections[last_collection_idx[collection_id.index(top_rate_collection[0])]]["games"].append(
                    {
                        "id": top_rate_collection[3],
                        "name": top_rate_collection[4],
                        "cover": top_rate_collection[5],
                        "blurhash": top_rate_collection[6],
                    })
                
            end = timer()
            return parse_top_rated_collections, (end - start) * 1000
        
    # ----------------------------- Top Rated Tracks Collection ------------------------------- #
    
    async def get_collection_top_tracks(self, collectionID: int, number: int, debug: bool) -> Generator:
        """ Get a specified number of most listened tracks from all games in a collection

        Args:
            collectionID (int): Collection ID
            number (int): Number of tracks to get

        Returns:
            list: List of most listened tracks data
        """
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            start = timer()
            query = sql.SQL("SELECT * FROM iris.get_collection_popular_tracks(%s, %s);")
            curs.execute(query, (collectionID, number,))
            tracks = curs.fetchall()
            end = timer() 
            
            if debug: base_logger.info(f"get_collection_top_tracks: {(end - start) * 1000}")
            
            for track in tracks:
                yield {
                    "game_data": {
                        "id": track[0],
                        'name': track[1],
                        'slug': track[2],
                        'cover': track[3],
                    },
                    "title": track[4],
                    "slug": track[5],
                    "file": track[6],
                    "view_count": track[7],
                    "like_count": track[8],
                    "length": track[9],
                }
        
        
    # --------------------------- Search By Name -------------------------- #
    
    # SQL Function :
    # CREATE OR REPLACE FUNCTION search_games(
	# _game_name TEXT,
    # _category INT[], _company_id INT[], _genre_name TEXT[], 
    # _rating_lower_bound REAL, _rating_upper_bound REAL, 
    # _release_date_lower_bound DATE, _release_date_upper_bound DATE,
    # _limit INT, _offset INT
    # )
    
    async def get_search_results(self, searchObject: dict) -> list:
        """ Get search results
        
        Args:
            searchObject (dict): Search object

        Returns:
            _type_: _description_
        """
        base_logger.info(searchObject)
        
        order_table = {
            "name_asc": 1,
            "name_desc": 2,
            "rating_asc": 3,
            "rating_desc": 4,
            "release_date_asc": 5,
            "release_date_desc": 6,
        }
        
        with self.conn.cursor(cursor_factory=LoggingRealDictCursor) as curs:
            query = sql.SQL("SELECT * FROM iris.search_games(%s::text, %s::int[], %s::int[], %s::text[], %s::real, %s::real, %s::date, %s::date, %s::int, %s::int, %s::int);")
            curs.execute(query, (
                searchObject.get("game_name", ""),
                searchObject.get("categories", []),
                searchObject.get("developers", []),
                searchObject.get("genres", []),
                searchObject.get("rating", {}).get("from", 0),
                searchObject.get("rating", {}).get("to", 100),
                searchObject.get("releaseDate", {}).get("from", "1900-01-01"),
                searchObject.get("releaseDate", {}).get("to", "2100-01-01"),
                searchObject.get("limit", 50),
                searchObject.get("offset", 0),
                order_table.get(searchObject.get("order", "name_asc"), 1),
            ))
            search_results = curs.fetchall()
            
            # Parse search results
            # parse_search_results = []
            # for search_result in search_results:
            #     parse_search_results.append({
            #         "id": search_result[0],
            #         "name": search_result[1],
            #         "slug": search_result[2],
            #         "cover": search_result[3],
            #         "blurhash": search_result[4],
            #         "rating": search_result[5],
            #         "release_date": search_result[6],
            #         "genres": search_result[7],
            #         "categories": search_result[8],
            #         "companies": search_result[9]
            #     })
            
            return search_results
        
                
    # --------------------------- Last Released -------------------------- #
    
    async def get_last_released_games(self, number: int, labels: list[str], debug: bool) -> Generator:
        """ Get a specified number of last released games from the database

        Args:
            number (int): Number of games to get
            labels (list[str]): List of labels to filter by
            debug (bool): Debug mode

        Returns:
            generator: Generator of last released games data
        """

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT id FROM iris.game g WHERE g.first_release_date IS NOT NULL ORDER BY g.first_release_date DESC LIMIT %s;")
            curs.execute(query, (number,))
            last_released_games_id = curs.fetchall()
            for last_released_game_id in last_released_games_id:
                game = await self.get_game(last_released_game_id[0], labels, debug)
                if game:
                    yield game
                    
    # --------------------------- Developer Companies -------------------------- #
    
    async def get_dev_companies(self) -> list[dict]:
        """ Get all developer companies

        Returns:
            list[dict]: List of developer companies
        """

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT * FROM iris.get_all_devs();")
            curs.execute(query)
            dev_companies = curs.fetchall()
            return dev_companies
        
    # --------------------------- All Genres + count -------------------------- #
    
    async def get_genres(self) -> list[dict]:
        """ Get all genres

        Returns:
            list[dict]: List of genres
        """

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT * FROM iris.get_genres();")
            curs.execute(query)
            genres = curs.fetchall()
            return genres
        
    # --------------------------- All Categories + count -------------------------- #
    
    async def get_categories(self) -> list[dict]:
        """ Get all categories

        Returns:
            list[dict]: List of categories
        """

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT * FROM iris.get_categories();")
            curs.execute(query)
            categories = curs.fetchall()
            return categories
        

class iris_user:
    def __init__(self):
        self.conn = IRIS_CONN

    def get_user_exist(self, userID: str) -> bool:

        with self.conn.cursor() as curs:

            curs.execute(f"select count(*) from public.profiles where id = '{userID}'")
            res = curs.fetchall()

            return res[0][0]

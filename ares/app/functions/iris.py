from app.functions.IGDB import IGDB
import psycopg2
import psycopg2.extensions
from psycopg2 import sql
import os
import threading
import logging
import json
import requests
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

f = open('./app/functions/json/sql_game_schema.json')
SQL_schema: dict = json.load(f)

class LoggingCursor(psycopg2.extensions.cursor):
    def execute(self, sql, args=None):
        logger = logging.getLogger('sql_debug')
        logger.info(self.mogrify(sql, args))

        try:
            psycopg2.extensions.cursor.execute(self, sql, args)
        except Exception as exc:
            logger.error("%s: %s" % (exc.__class__.__name__, exc))
            raise


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

ALL_TABLES = [
    "albums",
    "alternative_names",
    "artworks",
    "category",
    "collection",
    "companies",
    "cover",
    "dlcs",
    "expanded_games",
    "expansions",
    "games",
    "genres",
    "involved_companies",
    "keywords",
    "screenshots",
    "similar_games",
    "standalone_expansions",
    "themes",
]

GAMEID_TABLES = [
    "albums",
    "alternative_names",
    "artworks",
    "cover",
    "dlcs",
    "expanded_games",
    "expansions",
    "genres",
    "involved_companies",
    "keywords",
    "screenshots",
    "similar_games",
    "standalone_expansions",
    "themes",
]

MEDIA_TABLES = ["cover", "screenshots", "artworks"]

CLEAR_GAME = "category = null, collection = null, complete = false, first_release_date = null, parent_game = null, rating = null, slug = null, summary = null"

def glob_exist(curs, table, id):
    curs.execute("SELECT count(*) FROM iris.{0} where id={1};".format(table, id))
    fetch_res = curs.fetchone()
    return fetch_res


def valid_str(string):
    if type(string) == str:
        return string.replace("'", "''")
    else:
        return string


def insert_to_db(curs, field, field_data, game_id=None, check_company=False):

    keys = ()
    values = ""

    for key in field_data:
        keys += (key,)
        values += f"'{valid_str(field_data[key])}',"

    if (game_id and not check_company) or (
        check_company and field == "involved_companies"
    ):
        keys += ("game_id",)
        values += f"{game_id},"

    exist = glob_exist(curs, field, field_data["id"])
    if not exist[0]:
        # print(str(values))

        curs.execute(
            "INSERT INTO iris.{0} {1} VALUES ({2});".format(
                field, str(keys).replace("'", ""), values[:-1]
            )
        )


def image_downloader(IGDB_client, field, field_data):
    if field == "cover":
        hash = field_data["image_id"]
        for qual in DOWNLOAD_QUALITY[field]:
            res = IGDB_client.images(qual[0], hash)
            with open(f"/bacchus/media/{qual[1]}_{hash}.jpg", "wb") as f:
                f.write(res)
    else:
        for el in field_data:
            hash = el["image_id"]
            for qual in DOWNLOAD_QUALITY[field]:
                res = IGDB_client.images(qual[0], hash)
                with open(f"/bacchus/media/{qual[1]}_{hash}.jpg", "wb") as f:
                    f.write(res)


class iris:
    def __init__(self, r, r_games):

        self.rcli = r_games
        # level 1 data -> raw data, no need for other requests
        self.lvl_1_data = [
            "category",
            "first_release_date",
            "name",
            "rating",
            "slug",
            "summary",
        ]
        # level 2 data -> refer to other games, no need for other requests
        self.lvl_2_data = [
            "dlcs",
            "expansions",
            "expanded_games",
            "similar_games",
            "standalone_expansions",
        ]
        # level 3 data -> need other requests
        self.lvl_3_data = [
            "alternative_names",
            "artworks",
            "collection",
            "cover",
            "franchise",
            "genres",
            "involved_companies",
            "keywords",
            "themes",
            "screenshots",
        ]
        # cache level -> data replicate in redis db 1
        self.cache_level = ["name", "slug", "summary", "cover", "screenshots"]
        # download level -> need to download content
        self.download_level = ["artworks", "cover", "screenshots"]

        try:
            self.conn = psycopg2.connect(
                database="",
                user="postgres",
                password=os.environ["POSTGRES_PASSWORD"],
                host="iris",
                port="5432",
            )
            self.IGDB_client = IGDB(r)
        except:
            self.conn = None
            
    def existInCache(self, gameID: str):
        return self.rcli.json().get(f"games:{gameID}", "$.complete")

    def existInDB(self, curs, table, id):
        curs.execute("SELECT complete FROM iris.{0} where id={1};".format(table, id))
        fetch_res = curs.fetchone()
        return fetch_res


    def push_new_game(self, game_data):
        gameID = game_data[0]["id"]

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:

            inCache = self.existInCache(gameID)
            inDB = self.existInDB(curs, "game", gameID)
            
            logging.debug(inCache)
            logging.debug(inDB)
            
            if inCache == None:
                #-- Construct base cache data --#
                self.rcli.json().set(f"games:{gameID}", "$", {'complete': False})

            if not inDB:
                #-- Contruct base db data --# 
                query = "INSERT INTO iris.game (id) VALUES (%s);"
                data = (gameID, )
                curs.execute(query, data)

            if not inDB or not inDB[0] or inCache == None or not all(inCache):
                #-- Upload all metadata to DB and cache --#
                
                for field in game_data[0]:
                    logging.debug(field)
                    field_data = game_data[0][field]
                    field_schema_data = SQL_schema.get(field)
                    
                    #-- Game table root column --#
                    if field_schema_data.get('type') == 'base':
                        
                        query = sql.SQL("UPDATE iris.game SET {field} = %s WHERE id=%s;").format(
                                field=sql.Identifier(field_schema_data.get('field')))
                        data = (field_data, gameID)
                        curs.execute(query, data)
                        
                    #-- Game table root column but type date --# 
                    if field_schema_data.get('type') == 'date':
                        
                        query = sql.SQL("UPDATE iris.game SET {field} = %s WHERE id=%s;").format(
                                field=sql.Identifier(field_schema_data.get('field')))
                        data = (datetime.fromtimestamp(field_data), gameID)
                        curs.execute(query, data)

        self.conn.commit()

    def del_game(self, gameID: int) -> bool:

        with self.conn.cursor() as curs:

            medias_hash = []
            for table in MEDIA_TABLES:
                curs.execute(
                    f"SELECT image_id FROM iris.{table} WHERE game_id = {gameID}"
                )
                res = curs.fetchall()
                for hash in res:
                    medias_hash.append(hash[0])

            requests.delete(
                "http://triton:5110/del_media", data=json.dumps({"medias": medias_hash})
            )
            
            inCache = self.existInCache(gameID)
            inDB = self.existInDB(curs, "games", gameID)
            
            if inCache:
                gameName = self.rcli.json().get(f"games:{gameID}", "$.name")[0]
                self.rcli.json().set(f"games:{gameID}", "$", {
                    'complete': False,
                    'name': gameName
                })
                
            if inDB:
                for table in GAMEID_TABLES:
                    curs.execute(f"DELETE FROM iris.{table} WHERE game_id = {gameID}")

                curs.execute(f"UPDATE iris.games SET {CLEAR_GAME} WHERE id = {gameID}")

        self.conn.commit()


class iris_user:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(
                database="",
                user="postgres",
                password=os.environ["POSTGRES_PASSWORD"],
                host="iris",
                port="5432",
            )
        except:
            self.conn = None

    def get_user_exist(self, userID: str) -> bool:

        with self.conn.cursor() as curs:

            curs.execute(f"select count(*) from public.profiles where id = '{userID}'")
            res = curs.fetchall()

            return res[0][0]

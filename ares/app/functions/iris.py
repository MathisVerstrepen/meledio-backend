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
f = open('./app/functions/json/category.json')
SQL_category: dict = json.load(f)

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

def image_downloader(IGDB_client, field, media):
    hash = media["image_id"]
    for qual in DOWNLOAD_QUALITY[field]:
        res = IGDB_client.images(qual[0], hash)
        with open(f"/bacchus/media/{qual[1]}_{hash}.jpg", "wb") as f:
            f.write(res)


class iris:
    def __init__(self, r, r_games):

        self.rcli = r_games

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
        return self.rcli.json().get(f"g:{gameID}", "$.complete")

    def existInDB(self, curs, table, id):
        query = sql.SQL("SELECT complete FROM iris.{table} where id=%s;").format(
                table=sql.Identifier(table))
        curs.execute(query, (id,))
        return curs.fetchone()


    def push_new_game(self, game_data):
        gameID = game_data[0]["id"]

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:

            INCACHE = self.existInCache(gameID)
            INDB = self.existInDB(curs, "game", gameID)
            
            if INCACHE == None:
                #-- Construct base cache data --#
                self.rcli.json().set(f"g:{gameID}", "$", {'complete': False})

            if not INDB:
                #-- Contruct base db data --# 
                query = "INSERT INTO iris.game (id) VALUES (%s);"
                data = (gameID, )
                curs.execute(query, data)

            if not INDB or not INDB[0] or INCACHE == None or not all(INCACHE):
                #-- Upload all metadata to DB and cache --#
                
                for field in game_data[0]:
                    logging.debug(field)
                    field_data = game_data[0][field]
                    field_schema_data = SQL_schema.get(field)
                    field_type = field_schema_data.get('type') 
                    
                    #-- Game table root column --#
                    if field_type == 'base':
                        
                        query = sql.SQL("UPDATE iris.game SET {field} = %s WHERE id=%s;").format(
                                field=sql.Identifier(field_schema_data.get('field')))
                        data = (field_data, gameID,)
                        logging.debug(query)
                        logging.debug(data)
                        curs.execute(query, data)
                        
                        cache_data = field_data if field != 'category' else SQL_category.get(str(field_data))
                        self.rcli.json().set(f"g:{gameID}", f"$.{field_schema_data.get('field')}", cache_data)
                        
                    #-- Game table root column but type date --# 
                    elif field_type == 'date':
                        
                        query = sql.SQL("UPDATE iris.game SET {field} = %s WHERE id=%s;").format(
                                field=sql.Identifier(field_schema_data.get('field')))
                        data = (datetime.fromtimestamp(field_data), gameID,)
                        curs.execute(query, data)
                        
                        self.rcli.json().set(f"g:{gameID}", f"$.{field_schema_data.get('field')}", field_data)
                        
                    #-- Game table root column but parent game --# 
                    elif field_type == 'parent':
                        logging.debug(field_data)
                        if not self.existInDB(curs, "game", field_data["id"]):
                            query = sql.SQL("INSERT INTO iris.game (id, complete, name) VALUES (%s,False,%s);")
                            data = (field_data["id"], field_data["name"],)
                            curs.execute(query, data)
                            
                            self.rcli.json().set(f"g:{field_data['id']}", "$",{"complete": False, "name": field_data["name"]},)
                        
                        query = sql.SQL("UPDATE iris.game SET {field} = %s WHERE id=%s;").format(
                                field=sql.Identifier(field_schema_data.get('field')))
                        data = (field_data["id"], gameID,)
                        curs.execute(query, data)
                        
                        self.rcli.json().set(f"g:{gameID}", f"$.{field_schema_data.get('field')}", field_data["id"])
                        
                    #-- All sort of extra content of the game --# 
                    elif field_type == 'extra':
                        for extra_data in field_data:
                            if not self.existInDB(curs, "game", extra_data["id"]):
                                query = sql.SQL("INSERT INTO iris.game (id, complete, name) VALUES (%s,False,%s);")
                                data = (extra_data["id"], extra_data["name"],)
                                curs.execute(query, data)
                                
                                self.rcli.json().set(f"g:{extra_data['id']}", "$",{"complete": False, "name": extra_data["name"]},)

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
                        
                        self.rcli.json().set(f"g:{gameID}", f"$.{field_schema_data.get('base_field')}", field_data.get('id'))
                        
                        #-- Update root game table --# 
                        query = sql.SQL("UPDATE iris.game SET {field} = %s WHERE id=%s;").format(
                                field=sql.Identifier(field_schema_data.get('base_field')))
                        data = (field_data["id"], gameID,)
                        curs.execute(query, data)
                        
                    #-- Company and involved companies tables --#    
                    elif field_type == 'company':
                        
                        company_data: list = self.IGDB_client.companies(field_data)
                        logging.debug(field)
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
                            query = sql.SQL("INSERT INTO iris.{table} (image_id, game_id, type, height, width) VALUES (%s,%s,%s,%s,%s);").format(
                                    table=sql.Identifier(field_schema_data.get('field')),
                                )
                            data = (
                                media.get("image_id"),
                                gameID,
                                field,
                                media.get("height"),
                                media.get("width"),
                            )
                            curs.execute(query, data)
                            
                            thread = threading.Thread(target=image_downloader, args=(self.IGDB_client, field, media))
                            thread.start()
                        
                        if isinstance(field_data, list):
                            for media in field_data: 
                                insert_media(media)
                            self.rcli.json().set(f"g:{gameID}", f"$.{field}", [media.get("image_id") for media in field_data])
                        else:
                            insert_media(field_data)
                            self.rcli.json().set(f"g:{gameID}", f"$.{field}", field_data.get("image_id"))
                            
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
                    
                    self.rcli.json().set(f"g:{gameID}", "$.complete", True)
                
        self.conn.commit()

    def del_game(self, gameID: int) -> bool:

        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:

            query = sql.SQL("SELECT image_id FROM iris.media WHERE game_id=%s;")
            curs.execute(query, (gameID,))
            res = curs.fetchall()
            medias_hash = [hash[0] for hash in res]

            requests.delete(
                "http://triton:5110/del_media", data=json.dumps({"medias": medias_hash})
            )
            
            inCache = self.existInCache(gameID)
            inDB = self.existInDB(curs, "game", gameID)
            
            if inCache:
                gameName = self.rcli.json().get(f"g:{gameID}", "$.name")[0]
                self.rcli.json().set(f"g:{gameID}", "$", {
                    'complete': False,
                    'name': gameName
                })
                
            if inDB: 
                for table in GAMEID_TABLES:
                    query = sql.SQL("DELETE FROM iris.{table} WHERE game_id = %s;").format(
                            table=sql.Identifier(table))
                    curs.execute(query, (gameID,))

                query = sql.SQL("UPDATE iris.game SET category = null, collection_id = null, complete = false, first_release_date = null, parent_game = null, rating = null, slug = null, summary = null WHERE id=%s;")
                curs.execute(query, (gameID,))

        self.conn.commit()
    
    def get_base_game_data(self, gameID: int, forceDB: bool) -> dict:
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            
            inCacheComplete = self.existInCache(gameID)
            if (inCacheComplete and inCacheComplete[0] and not forceDB):
                rRes = self.rcli.json().get(f"g:{gameID}", "$.name", "$.slug", "$.complete", "$.parent_game", "$.category", "$.collection_id", "$.first_release_date", "$.rating", "$.popularity", "$.summary")
                logging.debug(rRes)
                res = {key.split('.')[1]:next(iter(value), None) for key, value in rRes.items()}
                return res
            else:
                query = sql.SQL("SELECT name,slug,complete,parent_game,category,collection_id,first_release_date,rating,popularity,summary FROM iris.game WHERE id=%s;")
                data = (gameID,)
                curs.execute(query, data)
                res = curs.fetchone()
                column = ['name', 'slug', 'complete', 'parent_game', 'category', 'collection_id', 'first_release_date', 'rating', 'popularity', 'summary']
                # res  = None
                if (res) : return {column[i]:res[i] for i in range(10)}
                else : return {}
        
    def get_media_game_data(self, gameID, media_type) -> dict:
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT * FROM iris.media WHERE game_id=%s AND type=%s;")
            data = (gameID, media_type,)
            curs.execute(query, data)
            res = curs.fetchall()
            column = ['image_id', 'game_id', 'type', 'height', 'width']

            return [{column[i]:row[i] for i in range(5)} for row in res]
        
    def get_alternative_name_game_data(self, gameID) -> dict:
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT * FROM iris.alternative_name WHERE game_id=%s;")
            data = (gameID,)
            curs.execute(query, data)
            res = curs.fetchall()
            column = ['id', 'game_id', 'name', 'comment']

            return [{column[i]:row[i] for i in range(4)} for row in res]
        
    def get_album_game_data(self, gameID) -> dict:
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT album.id, name, album.slug, track_id, title, track.slug, file, view_count, like_count, length FROM iris.album JOIN iris.track ON iris.album.track_id = iris.track.id WHERE iris.album.game_id = %s AND iris.album.name = 'Full Album'")
            data = (gameID,)
            curs.execute(query, data)
            res = curs.fetchall()
            
            result = {}
            if (len(res)) :
                column = ['','','','id', 'title', 'slug', 'file', 'view_count', 'like_count', 'length']
                result = {
                    'id' : res[0][0],
                    'name' : res[0][1],
                    'slug' : res[0][2],
                    'track' : [{column[i]:row[i] for i in range(3,10)} for row in res]
                }
            
            return result
        
    def get_involved_companies_game_data(self, gameID) -> dict:
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT company_id, developer, porting, publisher, supporting, name, slug, description, logo_id FROM iris.involved_companies JOIN iris.company ON iris.involved_companies.company_id = iris.company.id WHERE iris.involved_companies.game_id = %s;")
            data = (gameID,)
            curs.execute(query, data)
            res = curs.fetchall()
            column = ['company_id', 'developer', 'porting', 'publisher', 'supporting', 'name', 'slug', 'description', 'logo_id']
            
            return [{column[i]:row[i] for i in range(9)} for row in res]
        
    def get_extra_content_game_data(self, gameID, extra_type) -> dict:
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT extra_id FROM iris.extra_content WHERE game_id=%s AND type=%s;")
            data = (gameID, extra_type,)
            curs.execute(query, data)
            res = curs.fetchall()

            return [row[0] for row in res]
        
    def get_genre_game_data(self, gameID) -> dict:
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT name,slug FROM iris.genre WHERE iris.genre.game_id = %s;")
            data = (gameID,)
            curs.execute(query, data)
            res = curs.fetchall()
            column = ['name', 'slug']
            
            return [{column[i]:row[i] for i in range(2)} for row in res]
        
    def get_theme_game_data(self, gameID) -> dict:
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT name,slug FROM iris.theme WHERE iris.theme.game_id = %s;")
            data = (gameID,)
            curs.execute(query, data)
            res = curs.fetchall()
            column = ['name', 'slug']
            
            return [{column[i]:row[i] for i in range(2)} for row in res]
        
    def get_keyword_game_data(self, gameID) -> dict:
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            query = sql.SQL("SELECT id,name,slug FROM iris.keyword WHERE iris.keyword.game_id = %s;")
            data = (gameID,)
            curs.execute(query, data)
            res = curs.fetchall()
            column = ['id', 'name', 'slug']
            
            return [{column[i]:row[i] for i in range(3)} for row in res]


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

from app.functions.IGDB import IGDB
import psycopg2
import os
import threading
import json
import requests
from rich import print

from dotenv import load_dotenv
load_dotenv()


DOWNLOAD_QUALITY = {
    'artworks': [['screenshot_med', 'a_m'], ['screenshot_big', 'a_b'], ['screenshot_huge', 'a_h']],
    'cover': [['cover_small', 'c_s'], ['cover_big', 'c_b']],
    'screenshots': [['screenshot_med', 's_m'], ['screenshot_big', 's_b'], ['screenshot_huge', 's_h']]
}

ALL_TABLES = ['albums', 'alternative_names', 'artworks', 'category', 'collection', 'companies', 'cover', 'dlcs', 'expanded_games',
              'expansions', 'games', 'genres', 'involved_companies', 'keywords', 'screenshots', 'similar_games', 'standalone_expansions', 'themes']

GAMEID_TABLES = ['albums', 'alternative_names', 'artworks', 'cover', 'dlcs', 'expanded_games',
                 'expansions', 'genres', 'involved_companies', 'keywords', 'screenshots', 'similar_games', 'standalone_expansions', 'themes']

MEDIA_TABLES = ['cover', 'screenshots', 'artworks']

CLEAR_GAME = 'category = null, collection = null, complete = false, first_release_date = null, parent_game = null, rating = null, slug = null, summary = null'


def game_exist(curs, table, id):
    curs.execute(
        'SELECT complete FROM iris.{0} where id={1};'.format(
            table, id)
    )
    fetch_res = curs.fetchone()
    return fetch_res


def glob_exist(curs, table, id):
    curs.execute(
        'SELECT count(*) FROM iris.{0} where id={1};'.format(
            table, id)
    )
    fetch_res = curs.fetchone()
    return fetch_res


def valid_str(string):
    if type(string) == str:
        return string.replace("'", "''")
    else:
        return string


def insert_to_db(curs, field, field_data, game_id=None, check_company=False):

    keys = ()
    values = ''

    for key in field_data:
        keys += (key,)
        values += f"'{valid_str(field_data[key])}',"

    if (game_id and not check_company) or (check_company and field == 'involved_companies'):
        keys += ('game_id',)
        values += f'{game_id},'

    exist = glob_exist(curs, field, field_data['id'])
    if not exist[0]:
        # print(str(values))

        curs.execute("INSERT INTO iris.{0} {1} VALUES ({2});".format(
            field,
            str(keys).replace("'", ""),
            values[:-1]
        ))


def image_downloader(IGDB_client, field, field_data):
    if field == 'cover':
        hash = field_data['image_id']
        for qual in DOWNLOAD_QUALITY[field]:
            res = IGDB_client.images(qual[0], hash)
            with open(f"/bacchus/media/{qual[1]}_{hash}.jpg", 'wb') as f:
                f.write(res)
    else:
        for el in field_data:
            hash = el['image_id']
            for qual in DOWNLOAD_QUALITY[field]:
                res = IGDB_client.images(qual[0], hash)
                with open(f"/bacchus/media/{qual[1]}_{hash}.jpg", 'wb') as f:
                    f.write(res)


class iris:
    def __init__(self, r, r_games):
        self.rcli = r_games
        # level 1 data -> raw data, no need for other requests
        self.lvl_1_data = ['category',
                           'first_release_date', 'name', 'rating', 'slug', 'summary']
        # level 2 data -> refer to other games, no need for other requests
        self.lvl_2_data = ['dlcs', 'expansions', 'expanded_games',
                           'similar_games', 'standalone_expansions']
        # level 3 data -> need other requests
        self.lvl_3_data = ['alternative_names', 'artworks', 'collection',
                           'cover', 'franchise', 'genres', 'involved_companies', 'keywords', 'themes', 'screenshots']
        # cache level -> data replicate in redis db 1
        self.cache_level = ['name', 'slug', 'summary', 'cover', 'screenshots']
        # download level -> need to download content
        self.download_level = ['artworks', 'cover', 'screenshots']

        try:
            self.conn = psycopg2.connect(database="", 
                                        user="postgres",
                                        password=os.environ['POSTGRES_PASSWORD'], 
                                        host="iris",
                                        port="5432")
            self.IGDB_client = IGDB(r)
        except:
            self.conn = None

    def push_new_game(self, game_data):
        gameID = game_data[0]['id']

        with self.conn.cursor() as curs:

            gameInDB = game_exist(curs, 'games', gameID)
            if not gameInDB:
                # insert game base data to db and cache if non existent
                curs.execute(f"INSERT INTO iris.games (id) VALUES ({gameID})")
                self.rcli.json().set(gameID, "$", {'complete': False})

            if not gameInDB or not gameInDB[0]:
                # insert game complete data to db and cache if non complete
                query_lvl1 = 'complete = true,'

                for field in game_data[0]:
                    field_data = game_data[0][field]

                    if field in self.lvl_1_data:

                        value = f"'{valid_str(field_data)}'" if field != 'first_release_date' \
                                else f'date(to_timestamp({field_data}))'

                        query_lvl1 += f"{field} = {value},"

                    if field in self.lvl_2_data:

                        field_query, games_query = [], ''
                        for data in field_data:
                            field_query.append((gameID, data['id']))

                            exist = game_exist(curs, 'games', data['id'])
                            if not exist:
                                name = data['name'].replace("'", "''")
                                games_query += f"('{data['id']}', False, '{name}'),"

                                self.rcli.json().set(data['id'], "$", {
                                    'complete': False,
                                    'name': data['name']
                                })

                        if games_query:
                            curs.execute(
                                f"INSERT INTO iris.games (id, complete, name) VALUES {games_query[:-1]}")

                        field_val = ', '.join(map(str, field_query))
                        curs.execute(
                            f"INSERT INTO iris.{field} (game_id, {field}_id) VALUES {field_val};")

                    if field in self.lvl_3_data:

                        if type(field_data) is list and field != 'involved_companies':

                            for el in field_data:
                                insert_to_db(curs, field, el, gameID)

                        elif field == 'involved_companies':
                            company_data = self.IGDB_client.companies(
                                field_data)

                            for company in company_data:
                                for field in company:
                                    insert_to_db(
                                        curs, field, company[field], gameID, True)

                        elif field == 'collection':
                            insert_to_db(curs, field, field_data)

                            query_lvl1 += f'collection = {field_data["id"]},'

                        else:
                            insert_to_db(curs, field, field_data, gameID)

                        if field in self.download_level:
                            thread = threading.Thread(target=image_downloader, args=(
                                self.IGDB_client, field, field_data))
                            thread.start()

                    if field in self.cache_level:
                        if field == 'cover':
                            self.rcli.json().set(
                                gameID, "$.cover", field_data['image_id'])
                        elif field == 'screenshots':
                            self.rcli.json().set(
                                gameID, "$.screenshots", [screenshot['image_id'] for screenshot in field_data])
                        else:
                            self.rcli.json().set(
                                gameID, f"$.{field}", field_data)

                parent = game_data[0].get('parent_game')
                if parent:
                    parent_id = parent['id']
                    if not game_exist(curs, 'games', parent_id):
                        curs.execute(
                            "INSERT INTO iris.games (id, complete, name) VALUES ({0}, false, '{1}')".format(parent_id, parent['name']))
                    query_lvl1 += f'parent_game = {parent_id},'

                self.rcli.json().set(gameID, "$.complete", True)

                curs.execute("UPDATE iris.games SET {0} WHERE id={1}".format(
                    query_lvl1[0:-1], gameID))

        print('commit')
        self.conn.commit()

    def del_game(self, gameID: int) -> bool:

        with self.conn.cursor() as curs:

            medias_hash = []
            for table in MEDIA_TABLES:
                curs.execute(
                    f"SELECT image_id FROM iris.{table} WHERE game_id = {gameID}")
                res = curs.fetchall()
                for hash in res:
                    medias_hash.append(hash[0])

            requests.delete('http://triton:5110/del_media',
                            data=json.dumps({'medias': medias_hash}))

            gameName = self.rcli.json().get(gameID, "$.name")[0]
            self.rcli.json().set(gameID, "$", {
                'complete': False,
                'name': gameName
            })

            for table in GAMEID_TABLES:
                curs.execute(f"DELETE FROM iris.{table} WHERE game_id = {gameID}")

            curs.execute(
                f"UPDATE iris.games SET {CLEAR_GAME} WHERE id = {gameID}")

        self.conn.commit()

class iris_user:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(database="", 
                                        user="postgres",
                                        password=os.environ['POSTGRES_PASSWORD'], 
                                        host="iris",
                                        port="5432")
        except:
            self.conn = None

    def get_user_exist(self, userID: str) -> bool:
        
        with self.conn.cursor() as curs:

            curs.execute(
                f"select count(*) from public.users where id = '{userID}'")
            res = curs.fetchall()
            
            return res[0][0]
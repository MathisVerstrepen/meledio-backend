from fuzzywuzzy import fuzz
from rich import print
import requests
import json
import os


def GET_IGDB_TOKEN(r):
    try:
        RES_TOKEN = r.json().get('IGDB_TOKEN', "$.access_token")

        if RES_TOKEN:
            return RES_TOKEN[0]
        else:
            IGDB_res_token = REFRESH_TOKEN()
            r.json().set('IGDB_TOKEN', "$", IGDB_res_token)
            return IGDB_res_token['access_token']

    except:
        return None


def REFRESH_TOKEN():
    try:
        IGDB_res = requests.post('https://id.twitch.tv/oauth2/token', data={
            'client_id': os.getenv('IGDB_ID'),
            'client_secret': os.getenv('IGDB_SECRET'),
            'grant_type': 'client_credentials'
        })

        return json.loads(IGDB_res.text)
    except:
        return None


class IGDB():
    def __init__(self, r):
        self.TOKEN = GET_IGDB_TOKEN(r)
        self.req_header = {
            'Accept': 'application/json',
            'Client-ID': os.getenv('IGDB_ID'),
            'Authorization': 'Bearer {0}'.format(self.TOKEN)
        }

    def matching_games(self, input):
        clean_input = input.lower()
        IGDB_res = requests.post('https://api.igdb.com/v4/games',
                                 headers=self.req_header,
                                 data='fields name; search "{0}";'.format(clean_input))
        parsed_IGDB_res = json.loads(IGDB_res.text)

        matching_game = [{
            'id': game['id'],
            'name': game['name'],
            'score': fuzz.ratio(game['name'].lower(), clean_input)
        } for game in parsed_IGDB_res]

        matching_game_sort = sorted(
            matching_game, key=lambda d: d['score'], reverse=True)

        return {"data": matching_game_sort[:3]}

    def new_game(self, gameID):
        IGDB_res = requests.post('https://api.igdb.com/v4/games',
                                 headers=self.req_header,
                                 data="""fields name, 
                                        alternative_names.name, alternative_names.comment, 
                                        artworks.alpha_channel, artworks.animated, artworks.height, artworks.width, artworks.image_id, 
                                        category, 
                                        cover.alpha_channel, cover.animated, cover.height, cover.width, cover.image_id, 
                                        collection.name, collection.slug, 
                                        dlcs.name, 
                                        expanded_games.name, 
                                        expansions.name, 
                                        first_release_date,  
                                        genres.name, genres.slug,
                                        involved_companies.company, involved_companies.developer, involved_companies.porting, involved_companies.publisher, involved_companies.supporting, 
                                        keywords.name, keywords.slug, 
                                        parent_game.name,
                                        rating, 
                                        screenshots.alpha_channel, screenshots.animated, screenshots.height, screenshots.width, screenshots.image_id,
                                        similar_games.name, 
                                        slug, 
                                        standalone_expansions.name, 
                                        summary, 
                                        themes.name, themes.slug; 
                                        where id={0};""".format(gameID))
        parsed_IGDB_res = json.loads(IGDB_res.text)

        return {"data": parsed_IGDB_res}

    def companies(self, field_data):
        # final_data = []

        # for company in field_data:
        #     company_id = company['company']
        #     IGDB_res = requests.post('https://api.igdb.com/v4/companies',
        #                              headers=self.req_header,
        #                              data="""fields description, 
        #                                     logo.image_id, 
        #                                     name, slug;
        #                                     where id={0};""".format(company_id))
        #     parsed_IGDB_res = json.loads(IGDB_res.text)
        #     # parsed_IGDB_res[0]['logo'] = parsed_IGDB_res[0]['logo']['image_id']

        #     if parsed_IGDB_res[0] and parsed_IGDB_res[0].get("logo"):
        #         parsed_IGDB_res[0]['logo'] = parsed_IGDB_res[0]['logo']['image_id']
        #     else:
        #         parsed_IGDB_res[0]['logo'] = None
        #     final_data.append(
        #         {'companies': parsed_IGDB_res[0], 'involved_companies': company})

        # return final_data

        res = requests.post('https://api.igdb.com/v4/companies',
                                headers=self.req_header,
                                data=("fields description, logo.image_id, name, slug; where id=({companies});").format(
                                    companies=','.join([str(company['company']) for company in field_data])
                                ))
    
        return json.loads(res.text)

    def images(self, size, hash):
        IGDB_res = requests.get('https://images.igdb.com/igdb/image/upload/t_{0}/{1}.jpg'.format(
            size, hash), headers=self.req_header)
        return IGDB_res.content

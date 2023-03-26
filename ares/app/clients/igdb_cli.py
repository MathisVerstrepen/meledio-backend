# Description: IGDB API client wrapper
# type: ignore

from fuzzywuzzy import fuzz
from rich import print
import requests
import redis
import json
import os


def get_igdb_token(r):
    token = r.json().get('IGDB_TOKEN', "$.access_token")

    if not token:
        token = refresh_igdb_token(r)
    
    token = token[0]
    # Test if token is still valid
    headers = {
        'Client-ID': os.getenv('IGDB_ID'),
        'Authorization': f'Bearer {token}'
    }
    response = requests.get('https://api.igdb.com/v4/games', headers=headers)

    if response.status_code != 200:
        # Token is invalid, refresh it
        token = refresh_igdb_token(r)

    return token

def refresh_igdb_token(r):
    try:
        response = requests.post('https://id.twitch.tv/oauth2/token', data={
            'client_id': os.getenv('IGDB_ID'),
            'client_secret': os.getenv('IGDB_SECRET'),
            'grant_type': 'client_credentials'
        })

        response.raise_for_status()
        data = response.json()

        r.json().set('IGDB_TOKEN', "$", data['access_token'])
        return data['access_token']
    except requests.exceptions.RequestException as e:
        print(f'Failed to refresh IGDB token: {e}')
        return None


class IGDB():
    """IGDB related functions"""
    
    def __init__(self):
        r_glob = redis.Redis(host="atlas", port=6379, db=1, password=os.getenv("REDIS_SECRET"))
        self.TOKEN = get_igdb_token(r_glob)
        self.req_header = {
            'Accept': 'application/json',
            'Client-ID': os.getenv('IGDB_ID'),
            'Authorization': 'Bearer {0}'.format(self.TOKEN)
        }

    def matching_games(self, input: str) -> list:
        """Get matching games from IGDB API

        Args:
            input (str): Game name

        Returns:
            list: List of matching games with score
        """
        
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

        return matching_game_sort[:3]

    def new_game(self, gameID: int) -> dict: 
        """ Get game data from IGDB API

        Args:
            gameID (int): Game ID

        Returns:
            dict: Game data
        """
        
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

        return parsed_IGDB_res

    def companies(self, field_data: list) -> list:
        """ Get company data from IGDB API

        Args:
            field_data (list): List of company IDs

        Returns:
            list: List of company data
        """
        res = requests.post('https://api.igdb.com/v4/companies',
                                headers=self.req_header,
                                data=("fields description, logo.image_id, name, slug; where id=({companies}); limit {limit};").format(
                                    companies=','.join([str(company['company']) for company in field_data]),
                                    limit = len(field_data) + 1
                                ))
    
        return json.loads(res.text)

    def images(self, size: int, hash: str) -> bytes:
        """ Get image from IGDB API

        Args:
            size (int): Format of image (cover_small, cover_big, screenshot_med, screenshot_big, screenshot_huge, thumb, ...)
            hash (str): Hash of image (id of image)

        Returns:
            bytes: Image data
        """
        
        IGDB_res = requests.get('https://images.igdb.com/igdb/image/upload/t_{0}/{1}.jpg'.format(
            size, hash), headers=self.req_header)
        
        return IGDB_res.content

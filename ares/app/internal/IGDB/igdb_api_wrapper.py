# Description: IGDB API client wrapper
from datetime import datetime
from fuzzywuzzy import fuzz

from app.internal.IGDB.igdb_request import igdb_request

from app.internal.IGDB.igdb_utils import detect_year_in_name

from app.utils.loggers import base_logger as logger


class IGDB:
    """IGDB related functions"""

    def __init__(self):
        self.igdb_request = igdb_request

    async def get_matching_games(self, input_string: str, number: int) -> list:
        """Get matching games from IGDB API

        Args:
            input_string (str): Game name

        Returns:
            list: List of matching games with (id, name, score)
        """

        clean_input = input_string.lower()
        year, clean_input = detect_year_in_name(clean_input)

        logger.info("Searching for game [%s] of year [%s].", clean_input, year)

        if year is None:
            data = f'fields name; search "{clean_input}";'
        else:
            unix_start = datetime(year, 1, 1).timestamp()
            unix_end = datetime(year, 12, 31).timestamp()
            data = f'fields name; search "{clean_input}"; where first_release_date >= {unix_start} & first_release_date <= {unix_end};'

        parsed_igdb_res = await self.igdb_request.get("games", data)

        matching_game = []
        for game in parsed_igdb_res:
            game: dict
            match = {
                "id": game.get("id"),
                "name": game.get("name"),
                "score": fuzz.ratio(game.get("name", "").lower(), clean_input),
            }
            matching_game.append(match)

        matching_game_sort = sorted(matching_game, key=lambda d: (-d["score"], d["id"]))

        if year is not None:
            for game in matching_game_sort:
                game_release_date = await self.get_game_first_release_date(game["id"])
                if game_release_date is None or len(game_release_date) == 0:
                    continue

                game_release_date = game_release_date[0].get("first_release_date")
                if game_release_date is None:
                    continue

                igdb_year = datetime.fromtimestamp(game_release_date).year
                if igdb_year == year:
                    game["score"] = 101
                    matching_game_sort = sorted(
                        matching_game_sort, key=lambda d: (-d["score"], d["id"])
                    )
                    break

        return matching_game_sort[: min(number, len(matching_game_sort))]

    async def get_game_data(self, gameID: int) -> dict:
        """Get game data from IGDB API

        Args:
            gameID (int): Game ID

        Returns:
            dict: Game data
        """

        data = f"""fields name,
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
                        where id={gameID};"""

        parsed_igdb_res = await self.igdb_request.get("games", data)

        return parsed_igdb_res

    async def get_companies(self, field_data: list) -> list:
        """Get company data from IGDB API

        Args:
            field_data (list): List of company IDs

        Returns:
            list: List of company data
        """

        companies = ",".join([str(company["company"]) for company in field_data])
        limit = len(field_data) + 1

        data = f"""fields description, logo.image_id, name, slug;
                    where id=({companies}); limit {limit};"""

        parsed_igdb_res = await self.igdb_request.get("companies", data)

        return parsed_igdb_res

    async def get_game_first_release_date(self, game_id: int) -> list:
        """Get game release dates from IGDB API

        Args:
            game_id (int): Game ID

        Returns:
            list: List of release dates
        """

        data = f"""fields first_release_date; where id={game_id};"""

        parsed_igdb_res = await self.igdb_request.get("games", data)

        return parsed_igdb_res


igdb_client = IGDB()

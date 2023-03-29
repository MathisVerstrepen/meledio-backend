from fastapi import Request, APIRouter, Path, Query
from slowapi.util import get_remote_address
from timeit import default_timer as timer
from slowapi import Limiter

from app.clients.iris_cli import iris
from app.utils.loggers import base_logger
from app.utils.errors import raiseNoGameFound

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
iris_cli = iris()

async def get_game_data(gID: int, labels: list[str] = Query(default=['base']), debug: bool = False) -> dict:
    fData = {}
    debugData = {}

    for label in labels:
        if label == 'base':
            start = timer()
            res = iris_cli.get_game_base(gID)
            end = timer()
            fData['base'] = res
            if debug: debugData['base'] = (end - start) * 1000

        elif label in ['artworks', 'cover', 'screenshots']:
            start = timer()
            res = iris_cli.get_media_game_data(gID, label)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end - start) * 1000

        elif label == 'alternative_name':
            start = timer()
            res = iris_cli.get_alternative_name_game_data(gID)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end - start) * 1000

        elif label == 'album':
            start = timer()
            res = iris_cli.get_album_game_data(gID)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end - start) * 1000

        elif label == 'involved_companies':
            start = timer()
            res = iris_cli.get_involved_companies_game_data(gID)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end - start) * 1000

        elif label in ['dlcs', 'expansions', 'expanded_games', 'similar_games', 'standalone_expansions']:
            start = timer()
            res = iris_cli.get_extra_content_game_data(gID, label)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end - start) * 1000

        elif label == 'genre':
            start = timer()
            res = iris_cli.get_genre_game_data(gID)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end - start) * 1000

        elif label == 'theme':
            start = timer()
            res = iris_cli.get_theme_game_data(gID)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end - start) * 1000

        elif label == 'keyword':
            start = timer()
            res = iris_cli.get_keyword_game_data(gID)
            end = timer()
            fData[label] = res
            if debug: debugData[label] = (end - start) * 1000

    return {"debug_data": debugData, "gameID": gID, "data": fData}

@router.get('/v1/game/{game_id}') 
# @limiter.limit("60/minute")
async def get_game_by_id(   game_id: int, 
                            labels: list[str] = Query(default=['base']), 
                            debug: bool = False ) -> dict:
    
    game_data = await get_game_data(game_id, labels, debug)
    if not game_data:
        raiseNoGameFound(game_id)
    return game_data


@router.get("/v1/game/random/{limit}")
# @limiter.limit("60/minute")
async def get_random_games( request: Request, 
                            labels: list[str] = Query(default=['base']),
                            limit: int = Path(0, title="Number of random games", gt=0, le=1000), 
                            debug: bool = False ) -> dict:

    data = []
    randID: list = iris_cli.getRandomCompleteGameIDs(limit)
    for gameID in randID:
        data.append(await get_game_data(gameID[0], labels, debug))

    return {"data": data}


@router.get("/v1/game/top/rating/{limit}")
# @limiter.limit("60/minute")
async def get_top_rated_games(  request: Request, 
                                labels: list[str] = Query(default=['base']),
                                limit: int = Path(0, title="Number of top rating games", gt=0, le=1000),
                                debug: bool = False  ) -> dict:

    data = []
    topRateIDs: list = iris_cli.getTopRatedGameIDs(limit)
    for gameID in topRateIDs:
        data.append(await get_game_data(gameID[0], labels, debug))

    return {"data": data}


@router.get("/v1/collection/top/{limit}")
# @limiter.limit("60/minute")
async def get_top_rated_collection( request: Request, 
                                    labels: list[str] = Query(default=['base']),
                                    limit: int = Path(0, title="Number of top rating collection", gt=0, le=1000),
                                    debug: bool = False ) -> dict:

    data = {}
    topRateIDs: list = iris_cli.getTopRatedCollectionIDs(limit)

    for gameID, collectionID, collectionName in topRateIDs:
        data.setdefault(collectionID, {})['collectionName'] = collectionName
        data[collectionID].setdefault('gameData', []).append(
            await get_game_data(gameID, labels, debug))

    return {"data": data}


@router.get("/v1/collection/{collectionID}")
# @limiter.limit("60/minute")
async def get_collection_by_id(request: Request, labels: list[str] = Query(default=['base']),
                            collectionID: int = Path(0, title="Collection ID"), debug: bool = False,
                            forceDB: bool = False) -> dict:
    base_logger.info(labels)
    collectionData: list = iris_cli.getCollectionData(collectionID)
    collectionGameID: list = iris_cli.getGameIDofCollection(collectionID)

    data = {
        "collection": {
            "name": collectionData[0],
            "slug": collectionData[1]
        },
        "games": {}
    }
    base_logger.info(data)
    for game in collectionGameID:
        data["games"][game[0]] = await get_game_data(game[0], labels, debug, forceDB)

    return {"data": data}


@router.get("/v1/game/search/{searchText}")
# @limiter.limit("60/minute")
async def get_collection_by_id(request: Request, searchText: str = Path(0, title="Search game text"),
                            debug: bool = False) -> dict:
    searchResults = iris_cli.searchGameByName(searchText)

    return {"data": searchResults}
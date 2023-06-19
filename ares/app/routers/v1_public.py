from fastapi import Request, APIRouter, Path, Query
from slowapi.util import get_remote_address
from slowapi import Limiter

from app.clients.iris_cli import iris
from app.utils.loggers import base_logger
from app.utils.errors import raiseNoGameFound, raiseNoCollectionFound

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
iris_cli = iris()


@router.get('/v1/game/{game_id}')
# @limiter.limit("60/minute")
async def get_game_by_id(game_id: int,
                         labels: list[str] = Query(default=['base']),
                         debug: bool = False) -> dict:

    game_data = await iris_cli.get_game(game_id, labels, debug)
    if not game_data:
        raiseNoGameFound(game_id)
    return game_data


@router.get("/v1/games/random")
# @limiter.limit("60/minute")
async def v1_random_games(request: Request,
                          n: int = Query(
                              0, title="Number of random games", gt=0, le=100),
                          labels: list[str] = Query(default=['base']),
                          debug: bool = False) -> dict:

    random_games = [random_game async for random_game in iris_cli.get_random_games(n, labels, debug)]

    return {"data": random_games}


@router.get("/v1/games/top-rated")
# @limiter.limit("60/minute")
async def v1_top_rated_games(request: Request,
                             n: int = Query(
                                 0, title="Number of top rated games", gt=0, le=100),
                             offset: int = Query(0, title="Offset"),
                             labels: list[str] = Query(default=['base']),
                             debug: bool = False) -> dict:

    top_rated_games = [top_rated_game async for top_rated_game in iris_cli.get_top_rated_games(n, offset, labels, debug)]

    return {"data": top_rated_games}


@router.get("/v1/games/search")
# @limiter.limit("60/minute")
async def get_collection_by_id(request: Request,
                               name: str = Query(0, title="Search game text"),
                               n: int = Query(
                                   0, title="Number of top rated games", gt=0, le=100),
                               debug: bool = False) -> dict:

    searchResults = [searchResult async for searchResult in iris_cli.search_by_name(name, n)]

    return {"data": searchResults}

@router.get("/v1/games/last/released")
async def get_last_released_games(request: Request,
                                  n: int = Query(
                                      0, title="Number of top rated games", gt=0, le=100),
                                  labels: list[str] = Query(default=['base']),
                                  debug: bool = False) -> dict:

    last_released_games = [last_released_game async for last_released_game in iris_cli.get_last_released_games(n, labels, debug)]

    return {"data": last_released_games}

@router.get("/v1/collection/{collectionID}/tracks/top-rated")
# @limiter.limit("60/minute")
async def v1_collection_tracks_top_rated(request: Request,
                                         collectionID: int = Path(
                                            0, title="Collection ID"),
                                         n: int = Query(
                                            0, title="Number of top rated collection tracks", gt=0, le=100),
                                         debug: bool = False) -> list[dict]:
    
    collection_top_tracks = [collection_top_track async for collection_top_track in iris_cli.get_collection_top_tracks(collectionID, n, debug)]
    
    return {"data": collection_top_tracks}
    


@router.get("/v1/collection/{collectionID}")
# @limiter.limit("60/minute")
async def v1_collection_by_id(request: Request,
                              labels: list[str] = Query(default=['base']),
                              collectionID: int = Path(
                                  0, title="Collection ID"),
                              debug: bool = False) -> dict:

    collection = await iris_cli.get_collection(collectionID, labels, debug)
    
    if collection is None:
        raiseNoCollectionFound(collectionID)

    return {"data": collection}


@router.get("/v1/collections/top-rated")
# @limiter.limit("60/minute")
async def get_top_rated_collection(request: Request,
                                   n: int = Query(
                                       0, title="Number of top rating collection", gt=0, le=1000),
                                   offset: int = Query(0, title="Offset"),
                                   debug: bool = False) -> dict:

    topRatedCollection, debug_data = await iris_cli.get_top_rated_collection(n, offset)

    if debug:
        return {"debug": debug_data, "data": topRatedCollection}
    return {"data": topRatedCollection}

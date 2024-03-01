from typing import Annotated, List, Optional
from fastapi import Request, APIRouter, Query, Body
from fastapi.security import OAuth2PasswordBearer
from slowapi.util import get_remote_address
from slowapi import Limiter
from pydantic import BaseModel, Field, conint, constr

import app.connectors as connectors

from app.internal.errors.global_exceptions import (
    InvalidBody,
    ObjectNotFound,
    GenericError,
)
from app.internal.errors.iris_exceptions import ObjectAlreadyExistsError

from app.utils.loggers import base_logger as logger

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# ------------------ GAMES ---------------------- #


@router.get("/games/sort", tags=["games"])
@limiter.limit("30/minute")
async def get_games_sorted(
    request: Request,
    sort_type: Annotated[str, Query(..., regex="^(rating|random|recent)$")],
    sort_order: Annotated[str, Query(..., regex="^(asc|desc)$")] = "desc",
    offset: Annotated[int, Query(..., ge=0)] = 0,
    limit: Annotated[int, Query(..., ge=1, le=50)] = 10,
):  # pylint: disable=unused-argument
    """Get games sorted by a specific type (rating, random, recent)

    Args:
        request (Request): FastAPI Request object
        sort_type (Annotated[str, Query, optional): Sort type (rating, random, recent)
        sort_order (Annotated[str, Query, optional): Sort order (asc, desc)
        offset (int): offset in results (default 0)
        limit (int): limit of results (default 10, max 50)

    Returns:
        JSONResponse: JSON response with games data
    """
    games_data = await connectors.iris_query_wrapper.get_games_sorted(
        sort_type, sort_order, offset, limit
    )

    return games_data


@router.get("/games/{game_id}/top-tracks", tags=["games"])
@limiter.limit("30/minute")
async def get_game_top_tracks(
    request: Request,
    game_id: int,
    offset: Annotated[int, Query(..., ge=0)] = 0,
    limit: Annotated[int, Query(..., ge=1, le=50)] = 10,
):  # pylint: disable=unused-argument
    """Get game top tracks by game ID

    Args:
        request (Request): FastAPI Request object
        game_id (int): Game ID
        offset (int): offset in results (default 0)
        limit (int): limit of results (default 10, max 50)
    Raises:
        ObjectNotFound: _description_

    Returns:
        List[dict]: List of top tracks
    """

    game_top_tracks = await connectors.iris_query_wrapper.get_game_top_tracks(
        game_id, offset, limit
    )

    return game_top_tracks

@router.get("/games/{game_id}/albums", tags=["games"])
@limiter.limit("30/minute")
async def get_games_albums(
    request: Request,
    game_id: int,
):  # pylint: disable=unused-argument
    """Get game albums by game ID

    Args:
        request (Request): FastAPI Request object
        game_id (int): Game ID
        
    Returns:
        List[dict]: List of game albums
    """

    game_albums = await connectors.iris_query_wrapper.get_games_albums(
        game_id
    )

    return game_albums

@router.get("/games/{game_id}/related-games", tags=["games"])
@limiter.limit("30/minute")
async def get_game_related_games(
    request: Request,
    game_id: int,
    offset: Annotated[int, Query(..., ge=0)] = 0,
    limit: Annotated[int, Query(..., ge=1, le=50)] = 10,
):
    """Get game related games by game ID

    Args:
        request (Request): FastAPI Request object
        game_id (int): Game ID
        offset (int): offset in results (default 0)
        limit (int): limit of results (default 10, max 50)

    Returns:
        List[dict]: List of related games
    """
    game_related_games = await connectors.iris_query_wrapper.get_game_related_games(
        game_id, offset, limit
    )

    return game_related_games

@router.get("/games/{game_id}", tags=["games"])
@limiter.limit("30/minute")
async def get_game_by_id(
    request: Request, game_id: int
):  # pylint: disable=unused-argument
    """Get game by ID

    Args:
        request (Request): FastAPI Request object
        game_id (int): IGDB ID of the game

    Returns:
        JSONResponse: JSON response with game data
    """
    game_data = await connectors.iris_query_wrapper.get_base_game_data(game_id)

    if not game_data:
        raise ObjectNotFound("Game not found.")

    return game_data

# ------------------ COLLECTIONS ---------------------- #

@router.get("/collection/{collection_id}/top-tracks", tags=["collection"])
@limiter.limit("30/minute")
async def get_collection_top_tracks(
    request: Request,
    collection_id: int,
    offset: Annotated[int, Query(..., ge=0)] = 0,
    limit: Annotated[int, Query(..., ge=1, le=50)] = 10,
): # pylint: disable=unused-argument
    """Get collection top tracks by collection ID

    Args:
        request (Request): FastAPI Request object
        collection_id (int): Collection ID
        offset (int): offset in results (default 0)
        limit (int): limit of results (default 10, max 50)

    Returns:
        List[dict]: List of top tracks
    """
    collection_top_tracks = await connectors.iris_query_wrapper.get_collection_top_tracks(
        collection_id, offset, limit
    )

    return collection_top_tracks

@router.get("/collections/sort", tags=["collection"])
@limiter.limit("30/minute")
async def get_collections_sorted(
    request: Request,
    sort_type: Annotated[str, Query(..., regex="^(rating|random|recent)$")],
    sort_order: Annotated[str, Query(..., regex="^(asc|desc)$")] = "desc",
    offset: Annotated[int, Query(..., ge=0)] = 0,
    limit: Annotated[int, Query(..., ge=1, le=50)] = 10,
):  # pylint: disable=unused-argument
    """Get collections sorted by a specific type (rating, random, recent)

    Args:
        request (Request): FastAPI Request object
        sort_type (Annotated[str, Query, optional): Sort type (rating, random, recent)
        sort_order (Annotated[str, Query, optional): Sort order (asc, desc)
        offset (int): offset in results (default 0)
        limit (int): limit of results (default 10, max 50)

    Returns:
        JSONResponse: JSON response with collections data
    """
    collections_data = await connectors.iris_query_wrapper.get_collections_sorted(
        sort_type, sort_order, offset, limit
    )

    return collections_data

@router.get("/collection/{collection_id}", tags=["collection"])
@limiter.limit("30/minute")
async def get_collection_by_id(
    request: Request, collection_id: int
): # pylint: disable=unused-argument
    """ Get a collection by its ID

    Args:
        request (Request): FastAPI Request object
        collection_id (int): ID of the collection
    """
    collection_data = await connectors.iris_query_wrapper.get_collection_by_id(collection_id)

    if not collection_data:
        raise ObjectNotFound("Collection not found.")

    return collection_data

# ------------------ ALBUMS ---------------------- #

@router.get("/album/{album_id}", tags=["album"])
@limiter.limit("30/minute")
async def get_album_by_id(
    request: Request, album_id: int
): # pylint: disable=unused-argument
    """ Get an album by its ID

    Args:
        request (Request): FastAPI Request object
        album_id (int): ID of the album
    """
    album_data = await connectors.iris_query_wrapper.get_album_by_id(album_id)

    if not album_data:
        raise ObjectNotFound("Album not found.")

    return album_data

# ------------------ SEARCH ---------------------- #

class RatingRange(BaseModel):
    """ Type definition for rating range """
    from_: float = Field(0, alias="from")
    to: float = Field(100)

class DateRange(BaseModel):
    """ Type definition for date range """
    from_: str = Field("1900-01-01", alias="from", pattern="^\\d{4}-\\d{2}-\\d{2}$")
    to: str = Field("2100-01-01", pattern="^\\d{4}-\\d{2}-\\d{2}$")

class SearchObject(BaseModel):
    """ Type definition for search object with all search parameters fields """
    game_name: Optional[str]
    categories: List[int] = Field(default_factory=list)
    developers: List[int] = Field(default_factory=list)
    genres: List[str] = Field(default_factory=list)
    rating: RatingRange = Field(default_factory=RatingRange)
    releaseDate: DateRange = Field(default_factory=DateRange)
    limit: conint(ge=1, le=100) = 50
    offset: conint(ge=0) = 0
    order: Optional[constr(pattern="^(name_asc|name_desc|date_asc|date_desc)$")] = "name_asc"

@router.post("/search", tags=["search"])
@limiter.limit("30/minute")
async def search(
    request: Request,
    search_object: SearchObject = Body(...),
):
    """Search for games, collections, albums, and tracks

    Args:
        request (Request): FastAPI Request object
        search_object (Annotated[dict, Query, optional): Search object containing all search parameters
        
    Returns:
        List[dict]: List of search results
    """
    search_results = await connectors.iris_query_wrapper.search(
        search_object
    )

    return search_results

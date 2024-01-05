from fastapi import Request, APIRouter, Query
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from slowapi.util import get_remote_address
from slowapi import Limiter
from typing import Annotated

from app.internal.IGDB.igdb_api_wrapper import igdb_client
from app.internal.Global.wizard import Wizard, multiple_wizard

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
        _type_: _description_
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
        _type_: _description_
    """

    game_albums = await connectors.iris_query_wrapper.get_games_albums(
        game_id
    )

    return game_albums

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

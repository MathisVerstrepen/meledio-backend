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


@router.get("/games/sort/", tags=["games"])
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
        sort_type (str): Field to sort by

    Returns:
        JSONResponse: JSON response with games data
    """
    games_data = await connectors.iris_query_wrapper.get_games_sorted(
        sort_type, sort_order, offset, limit
    )

    if not games_data:
        raise ObjectNotFound("Games not found.")

    return games_data


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

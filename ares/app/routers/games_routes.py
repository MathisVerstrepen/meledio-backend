import asyncio
import traceback
from fastapi import Request, APIRouter
from fastapi.security import OAuth2PasswordBearer
from fastapi.encoders import jsonable_encoder
from slowapi.util import get_remote_address
from slowapi import Limiter

from app.internal.IGDB.igdb_api_wrapper import igdb_client
from app.internal.Global.wizard import Wizard, multiple_wizard

import app.connectors as connectors

from app.internal.errors.global_exceptions import (
    InvalidBody,
    ObjectNotFound,
    GenericError,
)
from app.internal.errors.iris_exceptions import ObjectAlreadyExistsError

from app.internal.utilities.auth import require_valid_token
from app.utils.loggers import base_logger as logger
from app.internal.utilities.task import task_manager, Task

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def process_games(igdb_ids: list, task: Task):
    """Function to process games in bulk and push them to database

    Args:
        igdb_ids (list): List of IGDB IDs to process
        task_id (str): Task ID to track progress
    """

    total_games = len(igdb_ids)
    logger.info("Starting bulk game creation. Total games: %s", total_games)

    for index, igdb_id in enumerate(igdb_ids):
        try:
            game_existence = await connectors.iris_dal.check_game_existence(igdb_id)
            if game_existence == 2:
                logger.info("Game [%s] already exists in database. Skipping.", igdb_id)
                continue
            game_data = await igdb_client.get_game_data, igdb_id
            await connectors.iris_query_wrapper.push_new_game(game_data, game_existence)
        except Exception as e:
            logger.error("Error while processing game [%s].", igdb_id)
            logger.error(traceback.format_exc())

            task.add_error(e, igdb_id)

        task.update_task_progress((index + 1) / total_games * 100)
    task.complete_task()


# ------------------ ROUTEURS ---------------------- #


@router.get("/games/external-search/igdb")
@require_valid_token
async def get_best_matching_games(request: Request, name: str) -> dict:
    res = await igdb_client.get_matching_games(name, 5)

    return {"data": res}


@router.post("/games/bulk-create/list")
@require_valid_token
async def add_new_game_bulk_list(request: Request) -> dict:
    body: dict = await request.json()
    igdb_ids = body.get("igdb_ids")

    if igdb_ids is None:
        raise InvalidBody()

    task = task_manager.create_task(
        "bulk-game-creation",
        "percent",
        "Bulk game creation from list of %s games" % len(igdb_ids),
    )

    try:
        asyncio.create_task(process_games(igdb_ids, task))
    except Exception as e:
        raise GenericError(e)

    return jsonable_encoder(task.toDict())


@router.post("/games/bulk-create/range")
@require_valid_token
async def add_new_game_bulk_range(request: Request) -> dict:
    body: dict = await request.json()

    igdb_ids_from = body.get("igdb_ids_from")
    igdb_ids_to = body.get("igdb_ids_to")

    if igdb_ids_from is None or igdb_ids_to is None:
        raise InvalidBody()

    igdb_ids_from = int(igdb_ids_from)
    igdb_ids_to = int(igdb_ids_to)

    igdb_ids = list(range(igdb_ids_from, igdb_ids_to + 1))

    task = task_manager.create_task(
        "bulk-game-creation",
        "percent",
        "Bulk game creation from range %s to %s" % (igdb_ids_from, igdb_ids_to),
    )

    try:
        asyncio.create_task(process_games(igdb_ids, task))
    except Exception as e:
        raise GenericError(e)

    return jsonable_encoder(task.toDict())


@router.post("/games/{igdb_id}")
@require_valid_token
async def add_new_game(request: Request, igdb_id: str) -> dict:
    game_existence = await connectors.iris_dal.check_game_existence(igdb_id)

    if game_existence == 2:
        raise ObjectAlreadyExistsError("Game already exists in database.")

    game_data_res = await igdb_client.get_game_data(igdb_id)

    if game_data_res is None:
        raise ObjectNotFound("Game with IGDB ID " + igdb_id)

    await connectors.iris_query_wrapper.push_new_game(game_data_res, game_existence)

    return {"data": game_data_res}


@router.delete("/games/bulk-delete/list")
@require_valid_token
async def delete_game_bulk_list(request: Request) -> dict:
    body: dict = await request.json()
    igdb_ids = body.get("igdb_ids")

    if igdb_ids is None:
        raise InvalidBody()

    status = []

    for igdb_id in igdb_ids:
        try:
            await connectors.iris_query_wrapper.delete_game(igdb_id)
            status.append({"igdb_id": igdb_id, "statusCode": 200, "status": "success"})
        except ObjectNotFound:
            status.append(
                {"igdb_id": igdb_id, "statusCode": 404, "status": "not-found"}
            )
        except Exception:
            status.append({"igdb_id": igdb_id, "statusCode": 500, "status": "error"})

    return {"data": status}


@router.delete("/games/bulk-delete/range")
@require_valid_token
async def delete_game_bulk_range(request: Request) -> dict:
    body: dict = await request.json()
    igdb_ids_from = body.get("igdb_ids_from")
    igdb_ids_to = body.get("igdb_ids_to")

    igdb_ids_from = int(igdb_ids_from)
    igdb_ids_to = int(igdb_ids_to)

    if igdb_ids_from is None or igdb_ids_to is None:
        raise InvalidBody()

    status = []
    igdb_ids = list(range(igdb_ids_from, igdb_ids_to + 1))

    for igdb_id in igdb_ids:
        try:
            await connectors.iris_query_wrapper.delete_game(igdb_id)
            status.append({"igdb_id": igdb_id, "statusCode": 200, "status": "success"})
        except ObjectNotFound:
            status.append(
                {"igdb_id": igdb_id, "statusCode": 404, "status": "not-found"}
            )
        except Exception:
            status.append({"igdb_id": igdb_id, "statusCode": 500, "status": "error"})

    return {"data": status}


@router.delete("/games/{igdb_id}")
@require_valid_token
async def delete_game(request: Request, igdb_id: str) -> dict:
    await connectors.iris_query_wrapper.delete_game(igdb_id)

    return {"data": "Game deleted"}


@router.post("/games/wizard/bulk-create/list")
@require_valid_token
async def add_new_game_bulk_list_wizard(request: Request) -> dict:
    game_name_list: list = await request.json()
    number_of_games = len(game_name_list["gameList"])

    task = task_manager.create_task(
        "bulk-game-creation",
        "percent",
        f"Bulk game creation from list of {number_of_games} games",
    )

    try:
        asyncio.create_task(multiple_wizard(game_name_list, task))
    except Exception as e:
        raise GenericError(e)

    return jsonable_encoder(task.toDict())

@router.post("/games/wizard/{game_id}/force-media")
@require_valid_token
async def add_new_game_wizard_force_media(request: Request, game_id: str) -> dict:
    logger.info("Starting forced wizard for game [%s]", game_id)
    
    media_data = await request.json()

    game_wizard = Wizard(game_id = game_id, media = media_data)
    await game_wizard.start()

    return {"data": "ok"}


@router.post("/games/wizard/{game_name}")
@require_valid_token
async def add_new_game_wizard(request: Request, game_name: str) -> dict:
    logger.info("Starting wizard for game [%s]", game_name)

    game_wizard = Wizard(game_name)

    await game_wizard.start()

    return {"data": "ok"}
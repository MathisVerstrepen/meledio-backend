
from __future__ import annotations
from typing import TYPE_CHECKING

from psycopg import AsyncConnection
from psycopg.rows import DictRow

if TYPE_CHECKING:
    from app.internal.IRIS.data_access_layer.iris_dal_main import IrisDataAccessLayer
    from app.internal.IRIS.iris_db_connection import IrisAsyncConnection
    from app.internal.IRIS.iris_queries_wrapper import Iris

iris_aconn : AsyncConnection[DictRow] | None = None
iris_dal : IrisDataAccessLayer | None = None
iris_query_wrapper : Iris | None = None

async def init_global_aconn(conn: IrisAsyncConnection):
    """ Initialize global IRIS database connection

    Args:
        conn (IrisAsyncConnection): IRIS psycopg database connection object
    """
    global iris_aconn # pylint: disable=global-statement
    iris_aconn = conn.get_conn()
    
async def init_global_iris_dal(dal : IrisDataAccessLayer):
    """ Initialize global IRIS Data Access Layer

    Args:
        dal (IrisDataAccessLayer): IRIS Data Access Layer object
    """
    global iris_dal  # pylint: disable=global-statement
    iris_dal = dal

async def init_global_iris_query_wrapper(wrapper : Iris):
    """ Initialize global IRIS API queries wrapper

    Args:
        wrapper (Iris): IRIS API queries wrapper object
    """
    global iris_query_wrapper  # pylint: disable=global-statement
    iris_query_wrapper = wrapper
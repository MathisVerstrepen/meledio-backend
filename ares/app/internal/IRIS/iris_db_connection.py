import os

from dotenv import load_dotenv

import psycopg
from psycopg.rows import dict_row

from app.utils.loggers import base_logger as logger, get_database_logger

# Impossible to use this logger because it's not async
# sql_logger, LoggingConnection = get_database_logger() 
load_dotenv()

IRIS_HOST = os.getenv("POSTGRES_HOST")

class IrisAsyncConnection():
    def __init__(self):
        self.conn = None

    async def connect_to_iris(self):
        try:
            self.conn = await psycopg.AsyncConnection.connect(
                user="postgres",
                password=os.getenv("POSTGRES_PASSWORD"),
                host=IRIS_HOST,
                port="5432",
                row_factory=dict_row,
                autocommit=False,
            )
            logger.info("Connection to IRIS database established.")
        except psycopg.Error as e:
            logger.error("Error while connecting to IRIS: %s", e)
            
    async def close(self):
        await self.conn.close()
        logger.info("Connection to IRIS database closed.")
        
    def get_conn(self):
        return self.conn

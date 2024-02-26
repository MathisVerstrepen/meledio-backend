import os

import logging
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

load_dotenv()

IRIS_HOST = os.getenv("POSTGRES_HOST")


class IrisAsyncConnection:
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
            logging.info("Connection to IRIS database established.")
        except psycopg.Error as e:
            logging.error("Error while connecting to IRIS: %s", e)

    async def close(self):
        await self.conn.close()
        logging.info("Connection to IRIS database closed.")

    def get_conn(self):
        return self.conn

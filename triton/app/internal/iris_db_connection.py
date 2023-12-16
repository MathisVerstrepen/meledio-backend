import os

from dotenv import load_dotenv

import psycopg
from psycopg.rows import dict_row

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
        except psycopg.Error as e:
            raise e

    async def close(self):
        await self.conn.close()
        
    def get_conn(self):
        return self.conn

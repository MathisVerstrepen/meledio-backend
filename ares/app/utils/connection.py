import psycopg2
import psycopg2.extensions
from psycopg2 import sql
import redis
import os

from dotenv import load_dotenv
load_dotenv()

REDIS_GLOBAL = redis.Redis(host="atlas", port=6379,
                           db=1, password=os.getenv("REDIS_SECRET"))
REDIS_GAMES = redis.Redis(host="atlas", port=6379,
                          db=0, password=os.getenv("REDIS_SECRET"))
REDIS_USERS = redis.Redis(host="atlas", port=6379,
                          db=2, password=os.getenv("REDIS_SECRET"))

IRIS_CONN = psycopg2.connect(
    database="",
    user="postgres",
    password=os.getenv("POSTGRES_PASSWORD"),
    host="iris",
    port="5432",
)

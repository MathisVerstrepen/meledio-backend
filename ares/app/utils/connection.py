import os
import redis

from dotenv import load_dotenv

load_dotenv()

REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

REDIS_GLOBAL = redis.Redis(
    host=REDIS_HOST, port="6379", password=REDIS_PASSWORD, db=0
)
from os import getenv
from app.utils.errors import raiseAuthFailed

from dotenv import load_dotenv
load_dotenv()


def admin_auth(token: str):
    if token != getenv("ARES_TOKEN"):
        raiseAuthFailed()

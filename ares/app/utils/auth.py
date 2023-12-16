from os import getenv
from app.utils.errors import raiseAuthFailed

from dotenv import load_dotenv
load_dotenv()


def admin_auth(token: str):
    return token.split(" ")[1] == getenv("ARES_TOKEN")
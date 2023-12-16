from os import getenv
from functools import wraps
from fastapi import HTTPException

from dotenv import load_dotenv
load_dotenv()

def admin_auth(token: str):
    return token.split(" ")[1] == getenv("ARES_TOKEN")

def require_valid_token(route_function):
    @wraps(route_function)
    async def wrapper(*args, **kwargs):
        request = kwargs.get('request')
        token = request.headers.get("Authorization")
        if not admin_auth(token):
            raise HTTPException(status_code=403, detail="Invalid token")
        return await route_function(*args, **kwargs)
    return wrapper
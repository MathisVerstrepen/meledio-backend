from fastapi import HTTPException, status

from app.utils.loggers import get_base_logger
base_logger = get_base_logger()

def raiseNoGameFound(gameID: int) -> None:
    base_logger.error("No matching game found in database for ID [%s].", gameID)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No matching game found in database for ID {gameID}",
    )


def raiseNoChapterFound(videoID: str) -> None:
    base_logger.error("No chapter found for video [%s].", videoID)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No chapter found for video {videoID}",
    )


def raiseNoUserFound(userID: int) -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No user found in database for userID {userID}",
    )
    
def raiseAuthFailed() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
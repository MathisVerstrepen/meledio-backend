from fastapi import HTTPException, status

import app.utils.loggers
base_logger = app.utils.loggers.base_logger

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
    
def raiseNoCollectionFound(collectionID: int) -> None:
    base_logger.error("No collection found for ID [%s].", collectionID)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No collection found for ID {collectionID}",
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
    
def raiseInvalidBody() -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid body",
    )
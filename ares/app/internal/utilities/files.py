import shutil
import os

from app.utils.loggers import base_logger as logger

def delete_folder(folder_path: str) -> None:
    """Delete a folder and its content

    Args:
        folder_path (str): Folder path
    """
    try:
        shutil.rmtree(folder_path)
    except Exception:
        logger.error("Error while deleting folder %s", folder_path)
    
def delete_file(file_path: str) -> None:
    """Delete a file

    Args:
        file_path (str): File path
    """
    try:
        os.remove(file_path)
    except Exception:
        logger.error("Error while deleting file %s", file_path)
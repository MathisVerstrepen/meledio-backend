import psycopg
import traceback

from app.utils.loggers import base_logger as logger

class ObjectAlreadyExistsError(Exception):
    """Exception raised when an object already exists.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message="Object already exists"):
        self.message = message
        super().__init__(self.message)


class SQLError(psycopg.Error):
    """Exception raised when an object already exists.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message="Error while executing SQL query"):
        logger.error(traceback.format_exc())
        self.message = message
        super().__init__(self.message)


class DatabaseCommitError(psycopg.Error):
    """Exception raised when an object already exists.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message="Error while committing data to database"):
        logger.error(traceback.format_exc())
        self.message = message
        super().__init__(self.message)

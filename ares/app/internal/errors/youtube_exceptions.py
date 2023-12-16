import traceback

from app.utils.loggers import base_logger as logger

ARES_YOUTUBE_ERROR = "04"

ARES_YOUTUBE_INFO_EXTRACTOR_ERROR = "01"
ARES_YOUTUBE_CHAPTERS_EXTRACTOR_ERROR = "02"
ARES_YOUTUBE_DOWNLOAD_ERROR = "03"
ARES_YOUTUBE_ALIGN_CHAPTERS_ERROR = "04"
ARES_YOUTUBE_SEGMENTATION_ERROR = "05"

class YoutubeException(Exception):
    """Base class for all Youtube exceptions."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class YoutubeInfoExtractorError(YoutubeException):
    """Base class for extractor errors."""

    def __init__(
        self, message: str, error_id: str = "0001", error_http_code: int = 500
    ):
        self.error_id = error_id
        self.error_http_code = error_http_code
        self.error_code = "ARESx{}x{}x{}".format(
            ARES_YOUTUBE_ERROR, ARES_YOUTUBE_INFO_EXTRACTOR_ERROR, error_id
        )
        
        self.message = message

        logger.error(self.message)
        logger.error(traceback.format_exc())

        super().__init__(self.message)


class YoutubeChaptersExtractorError(YoutubeException):
    """Base class for chapters extractor errors."""

    def __init__(
        self, message: str, error_id: str = "0001", error_http_code: int = 500
    ):
        self.error_id = error_id
        self.error_http_code = error_http_code
        self.error_code = "ARESx{}x{}x{}".format(
            ARES_YOUTUBE_ERROR, ARES_YOUTUBE_INFO_EXTRACTOR_ERROR, error_id
        )
        
        self.message = message

        logger.error(self.message)
        logger.error(traceback.format_exc())

        super().__init__(self.message)


class YoutubeDownloadError(YoutubeException):
    """Base class for download errors."""

    def __init__(
        self, message: str, error_id: str = "0001", error_http_code: int = 500
    ):
        self.error_id = error_id
        self.error_http_code = error_http_code
        self.error_code = "ARESx{}x{}x{}".format(
            ARES_YOUTUBE_ERROR, ARES_YOUTUBE_INFO_EXTRACTOR_ERROR, error_id
        )
        
        self.message = message

        logger.error(self.message)
        logger.error(traceback.format_exc())

        super().__init__(self.message)


class YoutubeAlignChaptersError(YoutubeException):
    """Base class for align chapters errors."""

    def __init__(
        self, message: str, error_id: str = "0001", error_http_code: int = 500
    ):
        self.error_id = error_id
        self.error_http_code = error_http_code
        self.error_code = "ARESx{}x{}x{}".format(
            ARES_YOUTUBE_ERROR, ARES_YOUTUBE_ALIGN_CHAPTERS_ERROR, error_id
        )

        self.message = message

        logger.error("[{}] {}".format(self.error_code, self.message))
        logger.error(traceback.format_exc())

        super().__init__(self.message)


class YoutubeSegmentationError(YoutubeException):
    """Base class for segmentation errors."""

    def __init__(
        self, message: str, error_id: str = "0001", error_http_code: int = 500
    ):
        self.error_id = error_id
        self.error_http_code = error_http_code
        self.error_code = "ARESx{}x{}x{}".format(
            ARES_YOUTUBE_ERROR, ARES_YOUTUBE_INFO_EXTRACTOR_ERROR, error_id
        )
        
        self.message = message

        logger.error(self.message)
        logger.error(traceback.format_exc())

        super().__init__(self.message)

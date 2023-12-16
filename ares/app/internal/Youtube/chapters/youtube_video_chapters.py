import json
import httpx

from app.internal.errors.youtube_exceptions import YoutubeChaptersExtractorError
from app.internal.Youtube.youtube_utils import (
    clean_chapter_line,
    extract_video_comments_data,
)
from app.internal.Youtube.chapters.extractors import (
    extract_chapter_description_data,
    extract_chapter_comment_data,
)

from app.utils.loggers import base_logger as logger


def save_chapters_to_file(chapters: list, video_id: str, game_id: str) -> None:
    """Save chapters to file

    Args:
        chapters (list): List of chapters
        filename (str): Filename
    """

    filepath = f"/bacchus/chapters/{video_id}.json"

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json_data = {
                "gameID": game_id,
                "chapters": chapters,
            }
            json.dump(json_data, f)
    except Exception as exc:
        raise YoutubeChaptersExtractorError(
            "Error while saving chapters to file", "0005", 500
        ) from exc


class VideoChaptersExtractor:
    def __init__(self, video_id: str, game_id: str) -> None:
        self.video_id = video_id
        self.game_id = game_id

        self.continuation_token = None
        self.yt_initial_data = None

        with open(
            "/ares/app/config/youtube_comments_body.json", "r", encoding="utf-8"
        ) as f:
            self.youtube_comments_body = json.load(f)

    async def extract_initial_data(self) -> None:
        async with httpx.AsyncClient() as client:
            try:
                res = await client.get(
                    f"https://www.youtube.com/watch?v={self.video_id}", timeout=10
                )
                self.yt_initial_data = res.text.split("var ytInitialData = ")[1].split(
                    ";</script>"
                )[0]
                self.yt_initial_data = json.loads(self.yt_initial_data)
            except Exception as exc:
                raise YoutubeChaptersExtractorError(
                    "Error while extracting initial data from video", "0002", 500
                ) from exc

            try:
                self.continuation_token = (
                    self.yt_initial_data["contents"]
                    ["twoColumnWatchNextResults"]
                    ["results"]
                    ["results"]
                    ["contents"][-1]
                    ["itemSectionRenderer"]
                    ["contents"][0]
                    ["continuationItemRenderer"]
                    ["continuationEndpoint"]
                    ["continuationCommand"]
                    ["token"]
                )
            except (KeyError, IndexError):
                # Continuation token can be missing if the video has no comments
                logger.warning(
                    "Error while extracting continuation token, comments are probably disabled"
                )

    async def extract_chapters(self) -> list:
        """Get chapters from video

        Returns:
            list: List of chapters
        """

        chapters = None

        logger.info("Extracting chapters from video info")
        chapters = self.extract_chapters_from_video_info()

        if not chapters:
            logger.info("Extracting chapters from description")
            chapters = self.extract_chapters_from_description()

        if (not chapters) and (self.continuation_token):
            logger.info("Extracting chapters from comments")
            chapters = await self.extract_chapters_from_comments()

        if not chapters:
            logger.warning("No chapters found")
            raise YoutubeChaptersExtractorError(
                "Error while extracting chapters from video info", "0004", 500
            )

        logger.info("Found %s chapters", len(chapters))
        save_chapters_to_file(chapters, self.video_id, self.game_id)

        return chapters

    def extract_chapters_from_video_info(self) -> list:
        """Extract chapters from video info

        Returns:
            list: List of chapters
        """

        chapters = []

        try:
            chapters_meta = (
                self.yt_initial_data.get("playerOverlays", {})
                .get("playerOverlayRenderer", {})
                .get("decoratedPlayerBarRenderer", {})
                .get("decoratedPlayerBarRenderer", {})
                .get("playerBar", {})
                .get("multiMarkersPlayerBarRenderer", {})
                .get("markersMap", [])[0]
                .get("value", {})
                .get("chapters")
            )
            for chapter_meta in chapters_meta:
                unformatted_title = (
                    chapter_meta.get("chapterRenderer", {})
                    .get("title", {})
                    .get("simpleText", "")
                )
                title = clean_chapter_line(unformatted_title)
                chapters.append(
                    {
                        "title": title,
                        "timestamp": chapter_meta.get("chapterRenderer", {}).get(
                            "timeRangeStartMillis", 0
                        )
                        / 1000,
                    }
                )

        except Exception as e:
            logger.warning("Error while extracting chapters from video info: %s", e)
            return None

        return chapters

    def extract_chapters_from_description(self) -> list:
        """Extract chapters from description

        Returns:
            list: List of chapters
        """

        chapters = []

        try:
            description_meta = (
                self.yt_initial_data.get("contents", {})
                .get("twoColumnWatchNextResults", {})
                .get("results", {})
                .get("results", {})
                .get("contents", {})[1]
                .get("videoSecondaryInfoRenderer")
            )

            if not description_meta:
                return None

            chapters = extract_chapter_description_data(description_meta)

            if not chapters or len(chapters) < 3:
                return None

        except Exception as e:
            logger.warning("Error while extracting chapters from description: %s", e)
            return None

        return chapters

    async def extract_chapters_from_comments(self) -> list:
        """Extract chapters from comments

        Returns:
            list: List of chapters
        """

        chapters = []

        try:
            comments = await extract_video_comments_data(
                self.video_id, self.continuation_token, self.youtube_comments_body
            )

            for comment in comments:
                is_comment = comment.get("commentThreadRenderer")
                if not is_comment:
                    continue

                comment = (
                    comment.get("commentThreadRenderer")
                    .get("comment", {})
                    .get("commentRenderer", {})
                    .get("contentText", {})
                    .get("runs", [])
                )

                chapters = extract_chapter_comment_data(comment)

                if len(chapters) > 3:
                    break

        except Exception as e:
            logger.warning("Error while extracting chapters from comments: %s", e)
            return None

        return chapters

import json
import re
import httpx
import requests


from app.utils.loggers import base_logger as logger

from app.internal.Youtube.youtube_const import (
    YT_COMMENT_URL,
)


async def extract_video_comments_data(
    video_id: str, continuation_token: str, youtube_comments_body: dict
) -> list:
    """Extract video comments data

    Args:
        video_id (str): Video ID
        continuation_token (str): Continuation token

    Returns:
        list: List of video comments data
    """

    video_url = f"https://www.youtube.com/watch?v={video_id}"
    youtube_comments_body["continuation"] = continuation_token
    youtube_comments_body["context"]["client"]["originalUrl"] = video_url
    youtube_comments_body["context"]["client"]["mainAppWebInfo"]["graftUrl"] = video_url

    # res = requests.post(YT_COMMENT_URL, data=json.dumps(youtube_comments_body))

    async with httpx.AsyncClient() as client:
        res = await client.post(
            YT_COMMENT_URL, data=json.dumps(youtube_comments_body), timeout=10.0
        )

        res_json = json.loads(res.text)

        comments = (
            res_json.get("onResponseReceivedEndpoints", [])[-1]
            .get("reloadContinuationItemsCommand", {})
            .get("continuationItems", [])
        )

        while True:
            continuation_token = (
                comments[-1]
                .get("continuationItemRenderer", {})
                .get("continuationEndpoint", {})
                .get("continuationCommand", {})
                .get("token")
            )

            if continuation_token is None:
                break

            youtube_comments_body["context"]["clickTracking"]["clickTrackingParams"] = (
                comments[-1]
                .get("continuationItemRenderer", {})
                .get("continuationEndpoint", {})
                .get("clickTrackingParams")
            )

            youtube_comments_body["continuation"] = continuation_token

            #res = requests.post(YT_COMMENT_URL, data=json.dumps(youtube_comments_body))
            res = await client.post(
                YT_COMMENT_URL, data=json.dumps(youtube_comments_body), timeout=10.0
            )

            res_json = json.loads(res.text)

            new_comments = (
                res_json.get("onResponseReceivedEndpoints", [])[-1]
                .get("appendContinuationItemsAction", {})
                .get("continuationItems", [])
            )

            if len(new_comments) == 0:
                break

            comments.extend(new_comments)

        logger.info("Found %s comments", len(comments))

        return comments


def clean_chapter_line(line: str) -> str:
    """Clean chapter line

    Args:
        line (str): Line to clean

    Returns:
        str: Cleaned line
    """

    # Remove elements inside parentheses
    line = re.sub(r"\([^)]*\)", "", line)

    # Remove leading and trailing whitespace, and select the first non-empty line
    line = (
        line.strip().split("\n")[0]
        if line.strip().split("\n")[0]
        else line.strip().split("\n")[1]
    )

    # Remove timecode from title
    for timecode in re.findall(
        r"\b(?:\d{1,2}:)?\d{1,2}:\d{1,2}\b|\b\d{1,2}:\d{1,2}\b", line
    ):
        line = line.replace(timecode, "")

    # If the line contains any alphabetical characters, proceed with formatting
    if re.search("[a-zA-Z]", line):
        # Find the first alphabetical character in the line
        start_index = next((i for i, c in enumerate(line) if c.isalpha()), 0)

        # Find the last alphabetical or numeric character in the line
        end_index = next(
            (i for i, c in reversed(list(enumerate(line))) if c.isalnum()),
            len(line) - 1,
        )

        # Return the formatted line
        return line[start_index : end_index + 1].strip()

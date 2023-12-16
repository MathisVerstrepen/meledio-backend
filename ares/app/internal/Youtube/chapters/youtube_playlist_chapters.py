import json
import traceback
import requests
import httpx

from app.internal.errors.youtube_exceptions import (
    YoutubeChaptersExtractorError,
    YoutubeInfoExtractorError,
)

from app.internal.Youtube.youtube_const import (
    YT_PLAYLIST_URL,
    get_youtube_header
)

from app.utils.loggers import base_logger as logger


def save_chapters_to_file(chapters: list, playlist_id: str, game_id: str) -> None:
    """Save chapters to file

    Args:
        chapters (list): List of chapters
        filename (str): Filename
    """

    filepath = f"/bacchus/chapters/{playlist_id}.json"

    try:
        with open(filepath, "w") as f:
            json_data = {
                "gameID": game_id,
                "chapters": chapters,
            }
            json.dump(json_data, f)
    except Exception:
        raise YoutubeChaptersExtractorError(
            "Error while saving chapters to file", "0005", 500
        )


class PlaylistChaptersExtractor:
    def __init__(self, playlist_id, game_id) -> None:
        self.header_bypass_youtube_cookie = get_youtube_header()

        with open("/ares/app/config/youtube_body.json", "r") as f:
            self.youtube_body = json.load(f)

        self.playlist_id = playlist_id
        self.game_id = game_id

    def extract_video_information(self, videoRenderer: dict):
        videoId = videoRenderer.get("videoId")
        title = videoRenderer["title"]["runs"][0]["text"]

        thumbnailOverlayTimeStatusRenderer = videoRenderer["thumbnailOverlays"][0].get(
            "thumbnailOverlayTimeStatusRenderer"
        )

        duration = thumbnailOverlayTimeStatusRenderer["text"]["simpleText"]

        return videoId, title, duration

    def extract_client_playlist_data(self, req_text) -> dict:
        """Extract client playlist data

        Args:
            req_text (str): Request text

        Returns:
            dict: Client playlist data
        """
        client_playlist_data = (req_text.split('{"client":')[1].split("},")[0]) + "}}"

        return json.loads(client_playlist_data)

    def extract_playlist_video_data(self, renderer_content: list) -> (str, list):
        """Extract playlist video data

        Args:
            renderer_content (list): Renderer content

        Returns:
            str: Continuation token
            list: Playlist video data
        """
        playlist_videos_data = []
        continuation_token = None

        for playlist_video in renderer_content:
            playlistVideoRenderer = playlist_video.get("playlistVideoRenderer")

            if not playlistVideoRenderer:
                if playlist_video and playlist_video.get("continuationItemRenderer"):
                    continuation_token = (
                        playlist_video.get("continuationItemRenderer")
                        .get("continuationEndpoint")
                        .get("continuationCommand")
                        .get("token")
                    )
                continue

            videoId, title, duration = self.extract_video_information(
                playlistVideoRenderer
            )

            playlist_videos_data.append(
                {"id": videoId, "title": title, "duration": duration}
            )

        return continuation_token, playlist_videos_data

    def parse_video_duration(self, duration: str) -> int:
        """Parse video duration

        Args:
            duration (str): Video duration

        Returns:
            int: Video duration in seconds
        """
        duration = duration.split(":")
        duration.reverse()

        duration_seconds = 0

        for index, time in enumerate(duration):
            duration_seconds += int(time) * (60**index)

        return duration_seconds

    async def extract_chapters(self):
        url = YT_PLAYLIST_URL + self.playlist_id
        
        async with httpx.AsyncClient() as client:
            res = await client.get(url, headers=self.header_bypass_youtube_cookie, timeout=10)
            client_data = self.extract_client_playlist_data(res.text)

        try:
            ytInitialData = res.text.split("var ytInitialData = ")[1].split(";</script>")[
                0
            ]
            ytInitialData = json.loads(ytInitialData)
        except Exception as exc:
            raise YoutubeInfoExtractorError(
                "Error while extracting playlist video info from youtube" + traceback.format_exc()
            ) from exc

        renderer_content = (
            ytInitialData.get("contents", {})
            .get("twoColumnBrowseResultsRenderer", {})
            .get("tabs", [])[0]
            .get("tabRenderer", {})
            .get("content", {})
            .get("sectionListRenderer", {})
            .get("contents", [])[0]
            .get("itemSectionRenderer", {})
            .get("contents")[0]
            .get("playlistVideoListRenderer", {})
            .get("contents")
        )

        if not renderer_content:
            raise ValueError("Error while extracting video info from youtube")

        continuation_token, playlist_videos_data = self.extract_playlist_video_data(
            renderer_content
        )

        while len(playlist_videos_data) % 100 == 0:
            url = "https://www.youtube.com/youtubei/v1/browse"

            payload = {
                "context": {"client": client_data},
                "continuation": continuation_token,
            }
            
            async with httpx.AsyncClient() as client:
                res = await client.post(url, json=payload, headers=self.header_bypass_youtube_cookie, timeout=10)

            renderer_content = (
                res.json()
                .get("onResponseReceivedActions", [])[0]
                .get("appendContinuationItemsAction", {})
                .get("continuationItems", [])
            )

            (
                continuation_token,
                new_playlist_videos_data,
            ) = self.extract_playlist_video_data(renderer_content)

            playlist_videos_data += new_playlist_videos_data
            
        # Remove duplicated videos ids
        playlist_videos_data = [
            dict(t) for t in {tuple(d.items()) for d in playlist_videos_data}
        ]

        for index, video_data in enumerate(playlist_videos_data):
            prev_timestamp = prev_duration = 0

            if index > 0:
                prev_timestamp = playlist_videos_data[index - 1]["timestamp"]
                prev_duration = self.parse_video_duration(
                    playlist_videos_data[index - 1]["duration"]
                )
                del playlist_videos_data[index - 1]["duration"]
            video_data["timestamp"] = prev_timestamp + prev_duration

        del playlist_videos_data[-1]["duration"]

        save_chapters_to_file(playlist_videos_data, self.playlist_id, self.game_id)

        return playlist_videos_data

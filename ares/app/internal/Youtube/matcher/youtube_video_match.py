import json
import asyncio
import httpx
import datetime

from concurrent.futures import ThreadPoolExecutor

from app.utils.loggers import base_logger as logger
from app.internal.Youtube.youtube_const import (
    YT_SEARCH_URL,
    YT_PLAYLIST_URL,
    SEARCH_URLS_END,
    get_youtube_header,
)

from app.internal.errors.youtube_exceptions import YoutubeInfoExtractorError


class YoutubeVideoMatcher:
    def __init__(self) -> None:
        self.search_urls_end = SEARCH_URLS_END
        self.headers = get_youtube_header()

        with open("/ares/app/config/youtube_body.json", "r", encoding="utf-8") as f:
            self.youtube_body = json.load(f)

    async def extract_search_requests_data(self, query_endpoint: str) -> list:
        """Extract video info from youtube

        Args:
            query_endpoint (str): Query endpoint
            youtube_body (dict): Youtube body

        Returns:
            list: List of video info
        """

        youtube_body = self.youtube_body.copy()
        youtube_body["query"] = query_endpoint

        async with httpx.AsyncClient() as client:
            r = await client.post(
                YT_SEARCH_URL,
                data=json.dumps(youtube_body),
                headers=self.headers,
                timeout=10,
            )

            r_parse: dict = json.loads(r.text)

            renderer = (
                r_parse.get("contents", {})
                .get("twoColumnSearchResultsRenderer", {})
                .get("primaryContents", {})
                .get("sectionListRenderer", {})
                .get("contents", [])[0]
                .get("itemSectionRenderer", {})
                .get("contents")
            )

            if not renderer:
                raise ValueError("Error while extracting video info from youtube")

            return renderer

    async def extract_playlist_requests_data(self, playlist_id: str) -> (list, str):
        """Extract video info from youtube playlist

        Args:
            playlist_id (str): Playlist ID

        Returns:
            list: List of video info
            str: Playlist name
        """

        url = YT_PLAYLIST_URL + playlist_id
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=self.headers, timeout=10)

            try:
                ytPlaylistName = r.text.split("<title>")[1].split("</title>")[0]

                ytInitialData = r.text.split("var ytInitialData = ")[1].split(
                    ";</script>"
                )[0]
                ytInitialData = json.loads(ytInitialData)
            except Exception as exc:
                raise YoutubeInfoExtractorError(
                    "Error while extracting playlist video info from youtube"
                ) from exc

            renderer = (
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

            if not renderer:
                raise ValueError("Error while extracting video info from youtube")

            return renderer, ytPlaylistName

    def extract_video_information(self, videoRenderer: dict):
        videoId = videoRenderer.get("videoId")
        title = videoRenderer["title"]["runs"][0]["text"]

        thumbnailOverlayTimeStatusRenderer = videoRenderer["thumbnailOverlays"][0].get(
            "thumbnailOverlayTimeStatusRenderer"
        )

        duration = thumbnailOverlayTimeStatusRenderer["text"]["simpleText"]

        return videoId, title, duration

    async def video_match(self, game_name: str, release_date: datetime.date) -> dict:
        """Get best matching video for game name

        Args:
            game_name (str): Game name

        Returns:
            dict: Best matching video
        """

        if release_date:
            release_year = str(release_date.year)
            game_name = game_name + release_year

        query_endpoints = [str(game_name + query) for query in self.search_urls_end]

        # Créer et exécuter des tâches asynchrones
        tasks = [
            self.extract_search_requests_data(query_endpoint)
            for query_endpoint in query_endpoints
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        outputs = [result[0 : min(10, len(result))] for result in results]

        if outputs == [] or outputs == [None]:
            raise YoutubeInfoExtractorError("No results found")

        # Extract the video data from the video info and score it by the order of appearance
        video_data_table = {}
        playlist_data_table = {}

        for output in outputs:
            n_videos = len(output)

            for index, video_output in enumerate(output):
                videoRenderer = video_output.get("videoRenderer")
                playlistRenderer = video_output.get("playlistRenderer")

                if not videoRenderer and not playlistRenderer:
                    continue

                # Case of a standard video
                if videoRenderer:
                    try:
                        videoId, title, duration = self.extract_video_information(
                            videoRenderer
                        )

                        if video_data_table.get(videoId):
                            video_data_table[videoId][0] += n_videos - index
                        else:
                            video_data_table[videoId] = {
                                "score": n_videos - index,
                                "title": title,
                                "duration": duration,
                            }
                    except Exception:
                        continue

                # Case of a playlist
                if playlistRenderer:
                    playlist_id = playlistRenderer.get("playlistId")

                    if playlist_data_table.get(playlist_id) is not None:
                        continue

                    (
                        playlist_videos,
                        playlist_title,
                    ) = await self.extract_playlist_requests_data(
                        playlist_id,
                    )

                    playlist_videos_data = []

                    for playlist_video in playlist_videos:
                        playlistVideoRenderer = playlist_video.get(
                            "playlistVideoRenderer"
                        )

                        if not playlistVideoRenderer:
                            continue

                        videoId, title, duration = self.extract_video_information(
                            playlistVideoRenderer
                        )

                        playlist_videos_data.append(
                            {"id": videoId, "title": title, "duration": duration}
                        )

                    playlist_data_table[playlist_id] = {
                        "videos": playlist_videos_data,
                        "score": n_videos - index,
                        "title": playlist_title,
                    }

        if video_data_table == {}:
            raise YoutubeInfoExtractorError(
                "Error while extracting video info from youtube"
            )

        # Sort the final output by score and return the top 5
        final_video_data_table_sorted = sorted(
            video_data_table.items(), 
            key=lambda tup: tup[1]["score"], 
            reverse=True
        )[0 : min(5, len(video_data_table))]

        final_playlist_data_table = (
            sorted(
                playlist_data_table.items(),
                key=lambda tup: tup[1]["score"],
                reverse=True,
            )
        )[0 : min(5, len(playlist_data_table))]

        return_value = {"videos": [], "playlists": []}
        for video in final_video_data_table_sorted:
            return_value["videos"].append(
                {
                    "id": video[0],
                    "title": video[1]["title"],
                    "duration": video[1]["duration"],
                    "score": video[1]["score"],
                }
            )

        for playlist in final_playlist_data_table:
            return_value["playlists"].append(
                {
                    "id": playlist[0],
                    "title": playlist[1]["title"],
                    "score": playlist[1]["score"],
                    "videos": playlist[1]["videos"],
                }
            )

        return return_value

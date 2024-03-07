import json
import traceback
import datetime

from app.internal.Youtube.matcher.youtube_video_match import YoutubeVideoMatcher
from app.internal.Youtube.chapters.youtube_video_chapters import VideoChaptersExtractor
from app.internal.Youtube.downloader.youtube_audio_downloader import (
    YoutubeAudioDownloader,
)
from app.internal.Youtube.segmenter.youtube_audio_segment import YoutubeAudioSegmenter
from app.internal.Youtube.chapters.align_chapters import ChapterAligner
from app.internal.Youtube.chapters.youtube_playlist_chapters import (
    PlaylistChaptersExtractor,
)

from app.internal.errors.youtube_exceptions import YoutubeDownloadError

from app.utils.loggers import base_logger as logger


class Youtube:
    def __init__(self) -> None:
        with open("/ares/app/config/youtube_body.json", "r", encoding="utf-8") as f:
            self.youtube_body = json.load(f)

    async def video_match(self, game_name: str, release_date: datetime.date) -> dict:
        """Get best matching video for game name

        Args:
            game_name (str): Game name

        Returns:
            dict: Best matching video
        """

        matcher = YoutubeVideoMatcher()
        matching_videos = await matcher.video_match(game_name, release_date)

        return matching_videos

    async def get_video_chapters(self, videoID: str, gameID: str) -> list:
        """Get the chapters of a video

        Args:
            videoID (str): Video ID

        Returns:
            list: List of chapters
        """

        try:
            videoID = videoID.strip()
            video_chapters_extractor = VideoChaptersExtractor(videoID, gameID)
            await video_chapters_extractor.extract_initial_data()
            chapters = await video_chapters_extractor.extract_chapters()

        except Exception:
            return None

        return chapters

    async def get_playlist_chapters(self, playlistID: str, gameID: str) -> list:
        """Get the chapters of a playlist

        Args:
            playlistID (str): Playlist ID

        Returns:
            list: List of chapters
        """

        try:
            playlistID = playlistID.strip()
            playlist_chapters_extractor = PlaylistChaptersExtractor(playlistID, gameID)
            chapters = await playlist_chapters_extractor.extract_chapters()

        except Exception:
            return None

        return chapters

    async def download_video(self, videoID: str, complete_task: callable) -> None:
        """Download the audio of a video

        Args:
            videoID (str): Video ID
            complete_task (callable): Update the task status and progress
        """

        audio_downloader = YoutubeAudioDownloader()
        await audio_downloader.initialize(videoID, "video")
        for i in range(5):
            try:
                await audio_downloader.download_audio_sync()
                break
            except YoutubeDownloadError:
                logger.warning( "Retrying download for video %s",  videoID)
                continue

        if i == 4:
            logger.error("Failed to download video %s", videoID)
            raise YoutubeDownloadError("Failed to download video")

        complete_task()

    async def download_playlist(self, playlistID: str, complete_task: callable) -> None:
        """Download the audio of a playlist

        Args:
            playlistID (str): Playlist ID
            complete_task (callable): Update the task status and progress
        """

        audio_downloader = YoutubeAudioDownloader()
        await audio_downloader.initialize(playlistID, "playlist")
        await audio_downloader.download_playlist()
        await audio_downloader.fix_timestamps()
        await audio_downloader.merge_audio()

        complete_task()

        logger.info("Finished downloading playlist [%s].", playlistID)

    async def align_chapters(self, videoID: str, computeGraph: bool) -> None:
        """Align the chapters of a video

        Args:
            videoID (str): Video ID
        """

        chapter_aligner = ChapterAligner(videoID, computeGraph)
        new_chapters = await chapter_aligner.align_chapters()
        chapter_aligner.save_chapters()

        return new_chapters

    async def format_audio(self, videoID: str) -> dict:
        """Format audio of a video

        Args:
            videoID (str): Video ID

        Returns:
            dict: Audio info
        """

        audio_segmenter = YoutubeAudioSegmenter(videoID)
        await audio_segmenter.set_next_album_id()
        audio_segmenter.load_chapters()
        tracks = await audio_segmenter.segment_audio()

        return audio_segmenter.game_id, audio_segmenter.album_id, tracks


youtube_client = Youtube()

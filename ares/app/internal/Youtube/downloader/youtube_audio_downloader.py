import os
import asyncio
import pathlib
import json
import traceback
import aiofiles
import random

from app.internal.errors.youtube_exceptions import YoutubeDownloadError
from app.internal.Youtube.youtube_const import PROXIES

from app.utils.loggers import base_logger as logger


class YoutubeAudioDownloader:
    """Youtube audio downloader.
    Given a video ID, download the audio of the video and save it in /bacchus/audio/tmp as an .opus file.

    Raises:
        YoutubeDownloadError: Raised if an error occurs while downloading the audio

    Args:
        videoID (str): Video ID
    """

    def __init__(self) -> None:
        self.videoID = None
        self.filepath = None
        self.playlistID = None
        self.dir_path = None
        self.video_ids = None
        self.chapters = None
        self.need_reencode = None

    async def initialize(self, mediaID: str, mediaType: str) -> None:
        if mediaType == "video":
            self.videoID = mediaID
            self.filepath = f"/bacchus/audio/tmp/{self.videoID}.opus"

            pathlib.Path("/bacchus/audio/tmp").mkdir(parents=True, exist_ok=True)

            if os.path.exists(self.filepath):
                os.remove(self.filepath)

        elif mediaType == "playlist":
            try:
                self.playlistID = mediaID
                self.need_reencode = False

                async with aiofiles.open(
                    f"/bacchus/chapters/{self.playlistID}.json", "r", encoding="utf-8"
                ) as f:
                    self.chapters = json.loads(await f.read())

                self.video_ids = [
                    chapter["id"] for chapter in self.chapters["chapters"]
                ]
                self.dir_path = f"/bacchus/audio/tmp/{self.playlistID}"

                if os.path.exists(self.dir_path):
                    os.system(f"rm -rf {self.dir_path}")

                pathlib.Path(self.dir_path).mkdir(parents=True, exist_ok=True)

                logger.info(
                    "Initialized playlist downloader for playlist %s", self.playlistID
                )
            except Exception as e:
                logger.error(
                    "Error while initializing YoutubeAudioDownloader for media ID %s: %s",
                    mediaID,
                    e,
                )
                logger.error(traceback.format_exc())

    async def download_audio_sync_backup(
        self, backup_filepath: str, out_filepath: str, video_id: str = None
    ) -> None:
        """Download the audio of a video in m4a, transcode it to opus and save it in /bacchus/audio/tmp as an .opus file.

        Args:
            video_id (str, optional): _description_. Defaults to None.
        """
        
        proxy = PROXIES[random.randint(0, len(PROXIES) - 1)]

        cmd = [
            "yt-dlp",
            "--proxy",
            proxy,
            "--force-ipv4",
            "--no-check-certificate",
            "-f",
            "bestaudio[ext=m4a]",
            "--output",
            backup_filepath,
            "https://youtu.be/" + video_id,
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        _, stderr = await process.communicate()

        if stderr:
            logger.error(
                "Error while downloading audio for video %s: %s", video_id, stderr
            )
            raise YoutubeDownloadError("Error while downloading audio", "0001", 500)

        cmd = [
            "ffmpeg",
            "-i",
            backup_filepath,
            "-c:a",
            "libopus",
            "-loglevel",
            "error",
            "-y",
            out_filepath,
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        _, stderr = await process.communicate()

        if stderr:
            logger.error(
                "Error while transcoding audio for video %s: %s", video_id, stderr
            )
            raise YoutubeDownloadError("Error while transcoding audio", "0001", 500)

    async def download_audio_sync(self, video_id: str = None) -> None:
        """Download the audio of a video and save it in /bacchus/audio/tmp as an .opus file.

        Args:
            video_id (str, optional): Video ID. Defaults to None.
        """
        if video_id is None:
            video_id = self.videoID
            filepath = self.filepath
        else:
            filepath = f"{self.dir_path}/{video_id}.opus"
            
        proxy = PROXIES[random.randint(0, len(PROXIES) - 1)]

        cmd = [
            "yt-dlp",
            "--proxy",
            proxy,
            "--force-ipv4",
            "--no-check-certificate",
            "-f",
            "bestaudio[ext=webm]",
            "-x",
            "--audio-format", 
            "opus",
            "--audio-quality",
            "0",
            "--output",
            filepath,
            "https://www.youtube.com/watch?v=" + video_id,
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        _, stderr = await process.communicate()
        
        if stderr and not "WARNING: [youtube] Failed to download m3u8 information" in stderr.decode("utf-8"):
            if "Requested format is not available" in stderr.decode("utf-8"):
                logger.warning(
                    "Requested format is not available for video %s, downloading m4a and transcoding to opus",
                    video_id,
                )
                self.need_reencode = True
                backup_filepath = f"{self.dir_path}/{video_id}.m4a"
                await self.download_audio_sync_backup(
                    backup_filepath, filepath, video_id
                )
            else:
                logger.error(
                    "Error while downloading audio for video %s: %s", video_id, stderr
                )
                raise YoutubeDownloadError("Error while downloading audio", "0001", 500)

    async def fix_timestamps(self) -> None:
        """Get the exact duration of each audio file and fix the timestamps found during the youtube extraction."""

        new_chapters = []
        last_timestamp = 0

        for idx, video_id in enumerate(self.video_ids):
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                f"{self.dir_path}/{video_id}.opus",
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if stderr:
                logger.error(
                    "Error while fixing timestamps for video %s: %s", video_id, stderr
                )
                raise YoutubeDownloadError("Error while fixing timestamps", "0002", 500)

            duration = float(stdout.decode("utf-8").strip())
            new_chapters.append(
                {
                    "id": video_id,
                    "title": self.chapters["chapters"][idx]["title"],
                    "timestamp": last_timestamp,
                }
            )
            last_timestamp += duration
        try:
            async with aiofiles.open(
                "/bacchus/chapters/" + self.playlistID + ".json", "w", encoding="utf-8"
            ) as f:
                await f.write(
                    json.dumps(
                        {"gameID": self.chapters["gameID"], "chapters": new_chapters}
                    )
                )
        except Exception as exc:
            logger.error(
                "Error while fixing timestamps for playlist %s: %s",
                self.playlistID,
                exc,
            )
            raise YoutubeDownloadError(
                "Error while fixing timestamps", "0002", 500
            ) from exc

    async def merge_audio(self) -> None:
        """Merge the audio of a playlist and save it in /bacchus/audio/tmp as an .opus file."""

        async with aiofiles.open(
            self.dir_path + "/concat.txt", "w", encoding="utf-8"
        ) as f:
            for video_id in self.video_ids:
                await f.write(f"file '{self.dir_path}/{video_id}.opus'\n")

        if self.need_reencode is True:
            logger.warning(
                "Reencoding audio for playlist %s, this may take a while...",
                self.playlistID,
            )

        cmd = [
            "ffmpeg",
            "-f",
            "concat",
            "-loglevel",
            "error",
            "-safe",
            "0",
            "-y",
            "-i",
            self.dir_path + "/concat.txt",
            "-c",
            "copy" if not self.need_reencode else "libopus",
            f"/bacchus/audio/tmp/{self.playlistID}.opus",
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        _, stderr = await process.communicate()

        if stderr:
            logger.error(
                "Error while merging audio for playlist %s: %s", self.playlistID, stderr
            )
            raise YoutubeDownloadError("Error while merging audio", "0002", 500)

        proc = await asyncio.create_subprocess_exec(
            "rm",
            "-rf",
            self.dir_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await proc.communicate()

        if stderr:
            logger.error(
                "Error while merging audio for playlist %s: %s", self.playlistID, stderr
            )
            raise YoutubeDownloadError("Error while deleting audio files", "0003", 500)

    async def download_playlist(self) -> None:
        """Download all the audio of a playlist and save it in /bacchus/audio/tmp as an .opus file."""

        loop = asyncio.get_event_loop()

        queue = asyncio.Queue()

        for video_id in self.video_ids:
            queue.put_nowait(video_id)

        async def worker():
            while not queue.empty():
                video_id = await queue.get()
                try:
                    await self.download_audio_sync(video_id)
                except YoutubeDownloadError as exc:
                    print(f"Error while downloading video {video_id}: {exc}")
                except Exception as exc:
                    print(f"Unexpected error while downloading video {video_id}: {exc}")
                    raise
                queue.task_done()

        tasks = [loop.create_task(worker()) for _ in range(10)]

        await queue.join()
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Finished downloading audio for playlist %s", self.playlistID)

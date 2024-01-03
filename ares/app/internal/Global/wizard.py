import traceback
import datetime
from uuid import uuid4
import aiofiles
import json

from app.internal.IGDB.igdb_api_wrapper import igdb_client
from app.internal.Youtube.youtube_api_wrapper import youtube_client

import app.connectors as connectors

from app.internal.errors.global_exceptions import (
    InvalidBody,
    ObjectNotFound,
)
from app.internal.errors.youtube_exceptions import YoutubeInfoExtractorError, YoutubeChaptersExtractorError
from app.internal.errors.iris_exceptions import ObjectAlreadyExistsError
from app.internal.utilities.task import Task

from app.utils.loggers import base_logger as logger


class Report:
    def __init__(self, total: int) -> None:
        self.report_id = str(uuid4())
        self.file = None
        self.n_success = 0
        self.n_error = 0
        self.n_total = total
        self.creation_date = datetime.datetime.now()
        self.games = []

    async def init_file(self):
        self.file = await aiofiles.open(
            f"/bacchus/reports/wizard/{self.report_id}.json", mode="w"
        )

    async def save(self):
        await self.init_file()

        final_data = {
            "report_id": self.report_id,
            "n_success": self.n_success,
            "n_error": self.n_error,
            "n_total": self.n_total,
            "creation_date": self.creation_date.strftime("%Y-%m-%d %H:%M:%S"),
            "games": self.games,
        }

        await self.file.write(json.dumps(final_data))
        await self.file.close()

    async def add_report(self, game_report: dict, success: bool):
        self.games.append(game_report)
        if success:
            self.n_success += 1
        else:
            self.n_error += 1
        await self.save()


class Wizard:
    def __init__(self, game_name: str = None, task: Task = None, media: str = None, game_id: str = None) -> None:
        self.game_name = game_name
        self.game_id = game_id
        self.matching_medias = None
        self.media = media
        self.media_id = media.get("id") if media else None
        self.media_type = media.get("type") if media else None
        self.media_title = media.get("title") if media else None
        self.album_id = None
        self.tracks = None

        self.status = "Not started"
        self.error = None
        self.warn = None

        self.task = task

    async def start(self):
        """Starts the wizard."""
        self.status = "Started"

        logger.info("[Wizard] Starting wizard for [%s]", self.game_name or self.game_id)

        if self.game_id is None:
            # Get matching games
            logger.info("[Wizard] Matching games for [%s]", self.game_name or self.game_id)
            try:
                await self.get_matching_games()
            except Exception as e:
                self.status = "Failed"
                self.error = "[Matching games] " + str(e)
                logger.error(traceback.format_exc())
                raise

            logger.info("[Wizard] Adding game data for [%s]", self.game_name or self.game_id)
            # Add game data
            try:
                await self.add_game_data()
            except ObjectAlreadyExistsError as e:
                if e.message == "Album already exists in database.":
                    self.status = "Failed"
                    self.error = "[Album data] Album already exists in database."
                    raise
                else:
                    self.warn = "[Game data] Game already exists in database."
            except ObjectNotFound:
                self.status = "Failed"
                self.error = "[Game data] Game not found in IGDB."
                logger.error(traceback.format_exc())
                raise

            logger.info("[Wizard] Matching videos for [%s]", self.game_name or self.game_id)
            # Get matching videos
            try:
                await self.get_matching_videos()
            except Exception as e:
                self.status = "Failed"
                self.error = "[Matching videos] " + str(e)
                logger.error(traceback.format_exc())
                raise
        elif self.media_id is None:
            raise InvalidBody("media_id must be provided if game_id is provided")

        if not self.media:
            logger.info("[Wizard] Getting chapters for [%s]", self.game_name or self.game_id)
            # Get chapters
            try:
                await self.get_chapters()
            except Exception as e:
                self.status = "Failed"
                self.error = "[Chapters] " + str(e)
                logger.error(traceback.format_exc())
                raise
        else:
            if self.media_type == "video":
                chapters = await youtube_client.get_video_chapters(
                    self.media_id, self.game_id
                )
            elif self.media_type == "playlist":
                chapters = await youtube_client.get_playlist_chapters(
                    self.media_id, self.game_id
                )
                
            if chapters is None:
                raise YoutubeChaptersExtractorError("No chapters found")

        logger.info("[Wizard] Downloading videos for [%s]", self.game_name or self.game_id)
        # Download videos
        try:
            await self.download_media()
        except Exception as e:
            self.status = "Failed"
            self.error = "[Download videos] " + str(e)
            logger.error(traceback.format_exc())
            raise

        logger.info("[Wizard] Aligning videos for [%s]", self.game_name or self.game_id)
        # Align videos
        try:
            self.align_videos()
        except Exception as e:
            self.status = "Failed"
            self.error = "[Align videos] " + str(e)
            logger.error(traceback.format_exc())
            raise

        logger.info("[Wizard] Segmenting videos for [%s]", self.game_name or self.game_id)
        # Segment videos
        try:
            await self.segment_videos()
        except Exception as e:
            self.status = "Failed"
            self.error = "[Segment videos] " + str(e)
            logger.error(traceback.format_exc())
            raise

        logger.info("[Wizard] Adding album to database for [%s]", self.game_name or self.game_id)
        # Add album to database
        try:
            await self.add_album_to_database()
        except Exception as e:
            self.status = "Failed"
            self.error = "[Add album to database] " + str(e)
            logger.error(traceback.format_exc())
            raise

        self.status = "Success"

    async def get_matching_games(self):
        matching_games = await igdb_client.get_matching_games(self.game_name, 5)

        if not matching_games:
            raise ObjectNotFound("No matching games found")

        self.game_id = matching_games[0].get("id")

    async def add_game_data(self):
        game_existence = await connectors.iris_dal.check_game_existence(self.game_id)

        if game_existence == 2:
            album_existence = await connectors.iris_dal.check_album_existence(
                self.game_id
            )
            if album_existence:
                raise ObjectAlreadyExistsError("Album already exists in database.")
            raise ObjectAlreadyExistsError("Game already exists in database.")

        game_data_res = await igdb_client.get_game_data(self.game_id)

        if game_data_res is None:
            raise ObjectNotFound("Game with IGDB ID " + self.game_id)

        await connectors.iris_query_wrapper.push_new_game(game_data_res, game_existence)

    async def get_matching_videos(self):
        game_data = await connectors.iris_query_wrapper.get_base_game_data(self.game_id)
        self.game_name = game_data.get("name")
        release_date: datetime.date = game_data.get("first_release_date")

        self.matching_medias = await youtube_client.video_match(
            self.game_name, release_date
        )
        self.extract_top_media()

    def extract_top_media(self):
        videos = self.matching_medias.get("videos", [])
        playlists = self.matching_medias.get("playlists", [])

        if len(videos) == 0 and len(playlists) == 0:
            raise YoutubeInfoExtractorError("No matching videos found")

        if len(videos) > 0 and len(playlists) > 0:
            if videos[0].get("score") > playlists[0].get("score"):
                video = videos.pop(0)
                self.media = video
                self.media_id = video.get("id")
                self.media_type = "video"
                self.media_title = video.get("title")
            else:
                playlist = playlists.pop(0)
                self.media = playlist
                self.media_id = playlist.get("id")
                self.media_type = "playlist"
                self.media_title = playlist.get("title")

        elif len(videos) > 0:
            video = videos.pop(0)
            self.media = video
            self.media_id = video.get("id")
            self.media_type = "video"
            self.media_title = video.get("title")

        elif len(playlists) > 0:
            playlist = playlists.pop(0)
            self.media = playlist
            self.media_id = playlist.get("id")
            self.media_type = "playlist"
            self.media_title = playlist.get("title")

    async def get_chapters(self):
        chapters = None
        start_score = self.media.get("score")
        while not chapters:
            logger.info("[Chapters] Trying with media ID [%s]", self.media_id)
            if self.media_type == "video":
                chapters = await youtube_client.get_video_chapters(
                    self.media_id, self.game_id
                )
            elif self.media_type == "playlist":
                chapters = await youtube_client.get_playlist_chapters(
                    self.media_id, self.game_id
                )
            else:
                raise InvalidBody("mediaType must be either video or playlist")

            if chapters is None:
                self.extract_top_media()
                logger.info(
                    "[Chapters] No chapters found, trying with media ID [%s]",
                    self.media_id,
                )
                if (start_score * 0.9 > self.media.get("score")) and (
                    start_score - 1 > self.media.get("score")
                ):
                    break

        if chapters is None:
            raise YoutubeChaptersExtractorError("No chapters found")

        logger.info("[Chapters] Found %s chapters", len(chapters))

    def end_download(self):
        pass

    async def download_media(self):
        if self.media_type == "playlist":
            await youtube_client.download_playlist(self.media_id, self.end_download)
        elif self.media_type == "video":
            await youtube_client.download_video(self.media_id, self.end_download)

    async def align_videos(self):
        await youtube_client.align_chapters(self.media_id, False)

    async def segment_videos(self):
        game_id, album_id, tracks = await youtube_client.format_audio(self.media_id)

        self.game_id = game_id
        self.album_id = album_id
        self.tracks = tracks

    async def add_album_to_database(self):
        await connectors.iris_query_wrapper.add_game_tracks(
            self.game_id, self.album_id, self.tracks, self.media_id
        )


async def multiple_wizard(game_name_list: list, task: Task):
    number_step = len(game_name_list["gameList"])
    current_step = 0

    report = Report(number_step)

    def update_task_progress():
        """Updates the progress of a task.

        Args:
            step (int): Progress step
        """

        nonlocal current_step
        current_step += 1
        task.update_task_progress(current_step * 100 / number_step)

    for game_name in game_name_list["gameList"]:
        wizard = Wizard(game_name, task = task)
        error = None
        try:
            await wizard.start()
        except Exception as e:
            task.add_error(e, game_name)
            error = str(e)

        game_report = {
            "game_name": game_name,
            "game_id": wizard.game_id,
            "media_id": wizard.media_id,
            "media_type": wizard.media_type,
            "media_title": wizard.media_title,
            "status": wizard.status,
            "error": error,
        }
        await report.add_report(game_report, error is None)

        update_task_progress()

    task.complete_task()

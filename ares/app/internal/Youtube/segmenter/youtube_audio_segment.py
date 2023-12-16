import json
import subprocess
import shutil
import os
import xml.etree.ElementTree as ET
import asyncio

from concurrent.futures import ThreadPoolExecutor

from app.utils.loggers import base_logger as logger

# from app.internal.IRIS.data_access_layer.iris_dal_main import IRIS_DAL
import app.connectors as connectors

from app.internal.errors.youtube_exceptions import YoutubeSegmentationError
from app.internal.errors.global_exceptions import ObjectNotFound


class TrackSegmenterWorker:
    def __init__(
        self,
        game_id: str,
        album_id: str,
        track_idx: int,
        start_time: int,
        end_time: int,
        full_audio_filepath: str,
    ) -> None:
        
        self.full_audio_filepath = full_audio_filepath
        self.game_id = game_id
        self.album_id = album_id
        self.track_idx = track_idx
        self.start_time = start_time
        
        if end_time is None:
            self.end_time = self.get_audio_end_time()
        else:
            self.end_time = end_time
            
        self.track_duration = self.end_time - start_time
        
        self.game_track_folder = (
            f"/bacchus/audio/{self.game_id}/{self.album_id}/{self.track_idx}"
        )
        os.makedirs(self.game_track_folder, exist_ok=True)
        
    def get_audio_end_time(self) -> int:
        """Get audio end time

        Returns:
            int: Audio end time
        """

        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            self.full_audio_filepath,
        ]

        try:
            res = subprocess.run(command, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            raise YoutubeSegmentationError(
                "FFMPEG error while extracting audio duration", "0001"
            )
                    
        return int(float(res.stdout))

    def segment_and_create_mpd(self) -> str:
        """Segment audio file into 3 second segments and create MPD file for DASH streaming

        Returns:
            str: MPD file path of the track
        """

        output_mpd_path = "{}/audio.mpd".format(self.game_track_folder)
        segment_file_path = "{}/segment_%04d.webm".format(self.game_track_folder)

        command = [
            "ffmpeg",
            "-ss",
            str(self.start_time),
            "-to",
            str(self.end_time),
            "-i",
            self.full_audio_filepath,
            "-acodec",
            "libopus",
            "-f",
            "segment",
            "-segment_time",
            "3",
            segment_file_path,
        ]

        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError:
            raise YoutubeSegmentationError(
                "FFMPEG error while segmenting audio file", "0003"
            )

        self.generate_mpd(output_mpd_path)

        return self.track_idx, self.track_duration

    def generate_mpd(self, output_mpd_path: str) -> None:
        """Generate MPD file for DASH streaming

        Args:
            output_mpd_path (str): MPD file path of the track to generate
        """

        mediaPresentationDuration = f"PT{self.track_duration}S"
        sample_rate, bit_rate = self.extract_audio_metadata()

        root = ET.Element(
            "MPD",
            xmlns="urn:mpeg:dash:schema:mpd:2011",
            **{"xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"},
            **{"xsi:schemaLocation": "urn:mpeg:dash:schema:mpd:2011 DASH-MPD.xsd"},
            profiles="urn:mpeg:dash:profile:isoff-live:2011,http://dashif.org/guidelines/dash-if-simple",
            maxSegmentDuration="PT3S",
            minBufferTime="PT3S",
            type="static",
            mediaPresentationDuration=mediaPresentationDuration,
        )

        prog_info = ET.SubElement(root, "ProgramInformation")

        title = ET.SubElement(prog_info, "Title")
        title.text = "[MELEDIO] Track {} of game {}".format(
            self.track_idx, self.game_id
        )

        period = ET.SubElement(root, "Period", start="PT0S", id="standard_audio")

        audio_adaptation_set = ET.SubElement(
            period,
            "AdaptationSet",
            contentType="audio",
            mimeType="audio/webm",
            lang="en",
            segmentAlignment="true",
            startWithSAP="1",
        )

        role = ET.SubElement(
            audio_adaptation_set,
            "Role",
            schemeIdUri="urn:mpeg:dash:role:2011",
            value="main",
        )

        segment_template = ET.SubElement(
            audio_adaptation_set,
            "SegmentTemplate",
            startNumber="1",
            initialization="https://media.meledio.com/audio/{}/{}/{}/segment_0000.webm".format(
                self.game_id, self.album_id, self.track_idx
            ),
            media="https://media.meledio.com/audio/{}/{}/{}/segment_$Number%04d$.webm".format(
                self.game_id, self.album_id, self.track_idx
            ),
            duration="3",
        )

        representation = ET.SubElement(
            audio_adaptation_set,
            "Representation",
            id="audio",
            codecs="opus",
            bandwidth=bit_rate,
            audioSamplingRate=sample_rate,
        )

        audio_channel_config = ET.SubElement(
            representation,
            "AudioChannelConfiguration",
            schemeIdUri="urn:mpeg:dash:23003:3:audio_channel_configuration:2011",
            value="2",
        )

        tree = ET.ElementTree(root)
        try:
            tree.write(
                output_mpd_path, encoding="utf-8", xml_declaration=True, method="xml"
            )
        except Exception:
            raise YoutubeSegmentationError("Error while creating MPD file", "0006")

    def extract_audio_metadata(self) -> (str, str):
        """Extract Sample Rate and Bitrate from audio file using ffprobe

        Returns:
            str: Sample Rate
            str: Bitrate
        """

        segment_file_path = "{}/segment_0000.webm".format(self.game_track_folder)

        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=bit_rate,sample_rate",
            "-of",
            "json",
            segment_file_path,
        ]

        try:
            res = subprocess.run(command, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            raise YoutubeSegmentationError(
                "FFMPEG error while extracting audio metadata", "0004"
            )

        res_json = json.loads(res.stdout)
        if res_json["streams"] == []:
            raise YoutubeSegmentationError(
                "No audio stream found in the segment file", "0005"
            )

        sample_rate = res_json["streams"][0].get("sample_rate", "48000")
        bit_rate = res_json["streams"][0].get("bit_rate", "128000")

        return sample_rate, bit_rate


class YoutubeAudioSegmenter:
    def __init__(self, video_id: str) -> None:
        self.video_id = video_id
        self.full_audio_filepath = f"/bacchus/audio/tmp/{video_id}.opus"
        self.chapters_filepath = f"/bacchus/chapters/{video_id}.json"
        self.num_cores = int(os.cpu_count() / 2)
        
        self.album_id = None
        self.game_id = None
        self.timecodes = None
        self.track_names = None
        self.album_folder = None
        
        logger.info("Start segmenter for video %s with %s cores", video_id, self.num_cores)
        
    async def set_next_album_id(self) -> None:
        """Set next album ID

        Returns:
            str: Album ID
        """

        self.album_id = await connectors.iris_dal.get_next_album_id()

    def load_chapters(self) -> None:
        """Load chapters from json file

        Args:
            video_id (str): Video ID to load chapters from

        Raises:
            ObjectNotFound: No chapters/gameID found
        """

        try:
            with open(self.chapters_filepath, "r", encoding="utf-8") as f:
                json_data: dict = json.load(f)

                self.game_id = json_data.get("gameID")
                chapters = json_data.get("chapters")

                if not self.game_id or not chapters:
                    raise ObjectNotFound("No chapters/gameID found")

                self.timecodes = [chapter.get("timestamp") for chapter in chapters]
                self.track_names = [chapter.get("title") for chapter in chapters]
                self.album_folder = f"/bacchus/audio/{self.game_id}/{self.album_id}"
        except Exception as exc:
            raise ObjectNotFound("Chapters") from exc

    async def segment_audio(self) -> (str, list[str]):
        """Segment audio file into tracks and split each track into 3 second segments
        For each track, also create the MPD file for DASH streaming

        Returns:
            list[str]: List of MPD file paths of the tracks
        """

        tracks = []

        try:
            if os.path.isdir(self.album_folder):
                shutil.rmtree(self.album_folder)
            os.makedirs(self.album_folder, exist_ok=True)
        except Exception as exc:
            raise YoutubeSegmentationError("Error while creating album folder", "0002") from exc
        
        timecode_to_end = self.timecodes[1:] + [None]
        loop = asyncio.get_running_loop()

        with ThreadPoolExecutor(max_workers=self.num_cores) as executor:
            tasks = []
            
            for track_idx, (start_time, end_time) in enumerate(
                zip(self.timecodes, timecode_to_end)
            ):
                track_segmenter_worker = TrackSegmenterWorker(
                    self.game_id,
                    self.album_id,
                    track_idx,
                    start_time,
                    end_time,
                    self.full_audio_filepath,
                )

                task = loop.run_in_executor(
                    executor,
                    track_segmenter_worker.segment_and_create_mpd
                )
                tasks.append(task)

            for completed_task in await asyncio.gather(*tasks):
                track_id, track_duration = completed_task
                tracks.append({
                    "id": track_id,
                    "title": self.track_names[track_id],
                    "duration": track_duration,
                })

        return tracks

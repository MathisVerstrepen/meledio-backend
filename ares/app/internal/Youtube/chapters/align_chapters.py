import json
import shutil
import os
import concurrent.futures
from pathlib import Path
import asyncio
import numpy as np
import soundfile as sf

import matplotlib.pyplot as plt
import matplotlib

matplotlib.use("Agg")  # Improve memory usage

from app.internal.errors.youtube_exceptions import YoutubeAlignChaptersError


class ChapterAligner:
    """Align the chapters to the audio file by computing the mean of the
        absolute values of the audio data for each 20ms frame.
        The timecode is then set to the frame with the lowest mean.
        A graph is generated for each timecode and saved in
        /bacchus/audio/tmp/img if save_graph is True.
        New chapters are saved in the original chapters file.

    Raises:
        ObjectNotFound: Raised if the chapters file is not found
    """

    num_cores = int(os.cpu_count() / 2)
    step = 1000

    def __init__(self, video_id: str, save_graph: bool = False) -> None:
        self.video_id = video_id
        self.save_graph = save_graph

        self.full_audio_filepath = f"/bacchus/audio/tmp/{video_id}.opus"
        self.chapters_filepath = f"/bacchus/chapters/{video_id}.json"

        try:
            with open(self.chapters_filepath, "r", encoding="utf-8") as f:
                json_data: dict = json.load(f)

                self.game_id = json_data.get("gameID")
                self.chapters = json_data.get("chapters")

                if not self.game_id or not self.chapters:
                    raise YoutubeAlignChaptersError(
                        "Chapters file is not valid", "0002", 500
                    )

        except Exception as exc:
            raise YoutubeAlignChaptersError(
                "Chapters file not found", "0002", 404
            ) from exc

        shutil.rmtree(
            f"/bacchus/media/{self.game_id}/chapter_graphs/{self.video_id}/",
            ignore_errors=True,
        )
        Path(f"/bacchus/media/{self.game_id}/chapter_graphs/{self.video_id}/").mkdir(
            parents=True, exist_ok=True
        )

    def get_image_filepath(self, timecode: int) -> str:
        """Get the filepath of the graph for a given timecode"""
        return f"/bacchus/media/{self.game_id}/chapter_graphs/{self.video_id}/{timecode}.png"

    def process_graph(
        self, timecode: int, min_idx: int, data_abs: np.ndarray, means: np.ndarray
    ) -> None:
        """Generate a graph of the audio data and the means of the audio data for each 20ms frame.
            A vertical line is drawn at the timecode and the timecode corrected by the algorithm.

        Args:
            timecode (int): Timecode in seconds
            min_idx (int): Index of the frame with the lowest mean
            data_abs (np.ndarray): Data of the 10 seconds before and after the timecode (absolute values)
            means (np.ndarray): Means of the audio data for each 20ms frame
        """

        original_idx = 0 if timecode < 10 else 500
        fig, axs = plt.subplots(2, figsize=(10, 10))
        fig.suptitle(f"Timecode: {timecode}s")

        axs[0].plot(data_abs)
        axs[0].set_title("Audio data")

        axs[1].stairs(values=means, edges=np.arange(len(means) + 1), label="Means")
        axs[1].set_title("Means")
        axs[1].axvline(x=min_idx, color="g", label="Corrected timecode")
        axs[1].axvline(x=original_idx, color="r", label="Original timecode")
        axs[1].legend()

        fig.savefig(self.get_image_filepath(timecode))
        plt.close(fig)

    def process_timecode(self, timecode: int) -> int:
        """For a given timecode, extract the audio data around 10 seconds before and after the timecode.
            Then, compute the mean of the absolute values of the audio data for each 20ms frame.
            The timecode is then set to the frame with the lowest mean.

        Args:
            timecode (int): Timecode to process in seconds

        Returns:
            int: Corrected timecode in seconds
        """
        data, _ = sf.read(
            self.full_audio_filepath,
            start=max(0, timecode - 10) * 48000,
            stop=(timecode + 10) * 48000,
            always_2d=True,
        )

        data_abs = np.abs(data[:, 0]) + np.abs(data[:, 1])

        n = len(data_abs)

        reshaped_data = data_abs[: n // self.step * self.step].reshape(-1, self.step)
        means = np.mean(reshaped_data, axis=1)

        min_idx = np.argmin(means)
        min_timecode = max(0, timecode - 10) + min_idx * 0.02

        if self.save_graph:
            self.process_graph(timecode, min_idx, data_abs, means)

        return min_timecode.item()

    async def align_chapters(self) -> list:
        """Main function to align the chapters to the audio file.
        For each chapter, a thread is created to process the timecode.
        """

        loop = asyncio.get_running_loop()
        n_worker = self.num_cores if not self.save_graph else 1

        with concurrent.futures.ThreadPoolExecutor(max_workers=n_worker) as executor:
            tasks = []
            for i, chapter in enumerate(self.chapters):
                task = loop.run_in_executor(
                    executor, self.process_timecode, int(chapter.get("timestamp"))
                )
                tasks.append((i, task))

            results = await asyncio.gather(*[task for _, task in tasks])

            for task, result in zip(tasks, results):
                i = task[0]
                try:
                    corrected_timestamp = result
                    self.chapters[i]["corrected_timestamp"] = corrected_timestamp
                    if self.save_graph:
                        self.chapters[i]["graph_filepath"] = self.get_image_filepath(
                            self.chapters[i].get("timestamp")
                        )
                except Exception as exc:
                    timestamp = self.chapters[i].get("timestamp")
                    raise YoutubeAlignChaptersError(
                        f"Error while processing timecode {timestamp}",
                        "0004",
                    ) from exc

        return self.chapters

    def save_chapters(self) -> None:
        """Save the chapters in the original chapters file"""

        try:
            with open(self.chapters_filepath, "w", encoding="utf-8") as f:
                json.dump({"gameID": self.game_id, "chapters": self.chapters}, f)
        except OSError as exc:
            raise YoutubeAlignChaptersError(
                "Error while saving chapters", "0003"
            ) from exc
        except Exception as exc:
            raise YoutubeAlignChaptersError(
                "Unknown error while saving chapters", "0001"
            ) from exc

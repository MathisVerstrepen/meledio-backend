# Description: S1 client wrapper
# type: ignore

import os
import re
import json
import uuid
import shutil
import logging
import pathlib
import requests
import psycopg2
import numpy as np
import yt_dlp
from io import BytesIO
from pydub import AudioSegment
from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor
from scipy.io import wavfile
from psycopg2 import sql
import psycopg2.extensions

from app.clients.iris_cli import iris
Iris_client = iris()

from app.utils.loggers import get_database_logger
sql_logger, LoggingCursor = get_database_logger()

import app.utils.loggers
base_logger = app.utils.loggers.base_logger

def extract_video_info(data: tuple) -> list:
    """ Extract video info from youtube

    Args:
        data (tuple): (query, body_data, game, URL)

    Returns:
        list: List of video info
    """
    
    query, body_data, game, URL = data
    body_data['query'] = game + query
    r = requests.post(URL, data=json.dumps(body_data))
    r_parse = json.loads(r.text)

    renderer = (r_parse['contents']['twoColumnSearchResultsRenderer']['primaryContents']
    ['sectionListRenderer']['contents'][0]['itemSectionRenderer']['contents'])

    return renderer

class chapter_scrap():
    def __init__(self, id: str) -> None:
        r = requests.get(f'https://www.youtube.com/watch?v={id}')
        r_cut_1 = r.text.split('var ytInitialData = ')[1]
        r_cut_2 = r_cut_1.split(';</script><script')[0]

        self.vid_meta = json.loads(r_cut_2)
        self.id = id
        
        self.continuation_token = (self.vid_meta['contents']['twoColumnWatchNextResults']['results']['results']
        ['contents'][-1]['itemSectionRenderer']['contents'][0]['continuationItemRenderer']
        ['continuationEndpoint']['continuationCommand']['token'])
        
        with open('/ares/app/json/youtube_comments_body.json', 'r') as f:
            self.youtube_comments_body = json.load(f)
            
    def format_line(self, line: str) -> str:
        """Format a YouTube chapter line to remove timecodes and other characters.

        Args:
            line (str): Line to format

        Returns:
            str: Formatted line
        """

        # Remove leading and trailing whitespace, and select the first non-empty line
        line = line.strip().split('\n')[0] if line.strip().split('\n')[0] else line.strip().split('\n')[1]
        
        # Remove timecode from title
        for timecode in re.findall(r'\b(?:\d{1,2}:)?\d{1,2}:\d{1,2}\b|\b\d{1,2}:\d{1,2}\b', line):
            line = line.replace(timecode, "")
            
        # If the line contains any alphabetical characters, proceed with formatting
        if re.search('[a-zA-Z]', line):
            # Find the first alphabetical character in the line
            start_index = next((i for i, c in enumerate(line) if c.isalpha()), 0)

            # Find the last alphabetical or numeric character in the line
            end_index = next((i for i, c in reversed(list(enumerate(line))) if c.isalnum()), len(line) - 1)

            # Return the formatted line
            return line[start_index:end_index + 1]

        return ""

    def extract_chapter_comment_data(self, comments: list) -> list:
        """Extract chapter data from YouTube comments.

        Args:
            comments (list): List of YouTube comments

        Returns:
            list: List of chapter data including titles and timestamps
        """

        chapter_data = []
        ntext = len(comments)
        index = 0
        last_watch_endpoint = -1

        while index < ntext:
            # Initialize variables for the current iteration
            watch_endpoint = -1

            # Iterate through the subsequent comments to find the next newline character
            next_index = index + 1
            while next_index < ntext and '\n' not in comments[next_index]['text']:
                navigation_endpoint = comments[next_index].get('navigationEndpoint')
                if navigation_endpoint and watch_endpoint == -1:
                    watch_endpoint = navigation_endpoint.get('watchEndpoint', {}).get('startTimeSeconds')

                next_index += 1

            # If a navigation endpoint is found and the watch endpoint is greater than the last one,
            # extract the chapter data and add it to the list
            if watch_endpoint is not None and last_watch_endpoint < watch_endpoint:
                full_row_elt = []

                # Extract text data from the current comment and subsequent comments
                full_row_elt.append(comments[index]['text'].split('\n')[-1])
                for tmp_index in range(index + 1, next_index):
                    full_row_elt.append(comments[tmp_index]['text'])

                # If there are more comments, add the first line of the next comment
                if next_index < ntext:
                    full_row_elt.append(comments[next_index]['text'].split('\n')[0])

                # Add the extracted chapter data to the list
                chapter_data.append({
                    'title': self.format_line("".join(full_row_elt)),
                    'timestamp': watch_endpoint
                })
                last_watch_endpoint = watch_endpoint

            index = next_index

        return chapter_data
    
    def extract_chapter_description_data(self, json_data: dict) -> list:
        """ Extract titles and timestamps from json data of a youtube video

        Args:
            json_data (dict): json data of a youtube video

        Returns:
            list: List of titles and timestamps
        """
        
        # Youtube json format can change at any time so this may break
        command_runs = json_data["attributedDescription"]["commandRuns"] # List of youtube timestamps
        content = json_data["attributedDescription"]["content"] # Full description string
        titles_and_timestamps = []
        last_timestamp = -1

        for command_run in command_runs:
            title_start = command_run["startIndex"]
            title_length = command_run["length"]
            title_end = title_start + title_length
            
            # Find start and end of title
            prev_char = content[title_start - 1:title_start]
            while prev_char != "\n" and title_start > 0:
                title_start -= 1
                prev_char = content[title_start - 1:title_start]
                
            next_char = content[title_end:title_end + 1]
            while next_char != "\n" and title_end < len(content):
                title_end += 1
                next_char = content[title_end:title_end + 1]

            title = self.format_line(content[title_start : title_end])
            
            # Get timestamp and add to list if it is greater than the last timestamp
            watchEndpoint = command_run["onTap"]["innertubeCommand"].get("watchEndpoint")
            if watchEndpoint:
                timestamp = command_run["onTap"]["innertubeCommand"]["watchEndpoint"]["startTimeSeconds"]
                if timestamp > last_timestamp:
                    last_timestamp = timestamp
                    titles_and_timestamps.append({"timestamp": timestamp, "title": title})

        return titles_and_timestamps

    def by_youtube_data(self) -> list:
        """ Extract chapter data from youtube embedded data

        Returns:
            list: List of chapter data
        """
        
        chapter_data = []
        try:
            chapters = (self.vid_meta['playerOverlays']['playerOverlayRenderer']['decoratedPlayerBarRenderer']
            ['decoratedPlayerBarRenderer']['playerBar']['multiMarkersPlayerBarRenderer']['markersMap'][0]['value']['chapters'])
            for chapter in chapters:
                title = self.format_line(chapter['chapterRenderer']['title']['simpleText'])
                chapter_data.append({
                    'title': title,
                    'timestamp': chapter['chapterRenderer']['timeRangeStartMillis'] / 1000
                })
        except Exception:
            base_logger.warning('Error extracting chapter data from youtube data')

        return chapter_data

    def by_video_desc(self) -> list:
        """ Extract chapter data from video description

        Returns:
            list: List of chapter data
        """

        try:            
            desc = self.vid_meta['contents']['twoColumnWatchNextResults']['results']['results']['contents'][1]['videoSecondaryInfoRenderer']
            chapter_data = self.extract_chapter_description_data(desc)
            
            # Check if chapter data has enough data (more than 3 chapters)
            if len(chapter_data) <= 3:
                chapter_data = []
                
        except Exception:
            chapter_data = []
            base_logger.warning('Error extracting chapter data from video description')
            
        return chapter_data

    def by_video_comments(self) -> list:
        """ Extract chapter data from video comments

        Returns:
            list: List of chapter data
        """
        
        vid_url = f"https://www.youtube.com/watch?v={self.id}"
        self.youtube_comments_body['context']['client']['originalUrl'] = vid_url
        self.youtube_comments_body['context']['client']['mainAppWebInfo']['graftUrl'] = vid_url
        self.youtube_comments_body['continuation'] = self.continuation_token

        r = requests.post(
            'https://www.youtube.com/youtubei/v1/next', data=json.dumps(self.youtube_comments_body))
        r_parse = json.loads(r.text)

        chapter_data = []
        comments = r_parse['onResponseReceivedEndpoints'][1]['reloadContinuationItemsCommand']['continuationItems']
        # For each comment, extract the chapter data and if it is valid, add it to the list
        for comment in comments:
            isComment = comment.get('commentThreadRenderer')
            if not isComment:
                continue

            com_parts = isComment['comment']['commentRenderer']['contentText']['runs']
            chapter_data = self.extract_chapter_comment_data(com_parts)

            if len(chapter_data) > 3:
                break

        return chapter_data

class s1():
    def __init__(self) -> None:
        self.search_url = [
            ' game full ost',
            ' game full album',
            ' game full soundtrack',
            ' game complete soundtrack',
            ' original game soundtrack',
        ]

        try:
            self.conn = psycopg2.connect(database="",
                                        user="postgres",
                                        password=os.environ['POSTGRES_PASSWORD'],
                                        host="iris",
                                        port="5432")
        except:
            self.conn = None
            
        with open('/ares/app/json/youtube_body.json', 'r') as f:
            self.youtube_body = json.load(f)

    def best_video_match(self, gameName: str) -> list:
        """ Get the best matching video for a game

        Args:
            gameName (str): Game name

        Returns:
            list: List of best matching video
        """

        URL = 'https://www.youtube.com/youtubei/v1/search'
        data_list = [
            (query, self.youtube_body, gameName, URL) for query in self.search_url
        ]

        # Extract the video info from the search results using multiprocessing pool
        p = Pool(len(data_list)).map(extract_video_info, data_list)
        outputs = [result for result in p]
        logging.info(outputs)

        # Merge all the outputs
        final = {}
        for output in outputs:
            position = len(output)
            for video in output:
                videoRenderer = video.get('videoRenderer')
                if videoRenderer:
                    videoId = videoRenderer.get('videoId')
                    title = videoRenderer['title']['runs'][0]['text']
                    thumbnailOverlayTimeStatusRenderer = videoRenderer['thumbnailOverlays'][0].get(
                        'thumbnailOverlayTimeStatusRenderer')
                    if thumbnailOverlayTimeStatusRenderer:
                        duration = thumbnailOverlayTimeStatusRenderer['text']['simpleText']
                        if final.get(videoId):
                            final[videoId][0] += position
                        else:
                            final[videoId] = [position, title, duration]
                        position -= 1

        # Sort the final output by score and return the top 5
        final_sorted = (sorted(final.items(), key=lambda tup: tup[1][0], reverse=True))[0:5]
        return_value = {}
        for video in final_sorted:
            return_value[video[0]] = {
                "title": video[1][1],
                "duration": video[1][2],
                "score": video[1][0],
            }
            
        return return_value

    def get_chapter(self, id: str) -> list:
        """ Get chapter data for a video

        Args:
            id (str): Video ID

        Returns:
            list: List of chapter data
        """

        chapter_turtle = chapter_scrap(id)
        chapter_data = []

        # Try to get chapter data from youtube embedded data
        base_logger.info(f"Trying to get chapter data for {id} from youtube embedded data")
        chapter_data = chapter_turtle.by_youtube_data()

        # If no chapter data is found, try to get chapter data from video description
        if not chapter_data:
            base_logger.info(f"Trying to get chapter data for {id} from description")
            chapter_data = chapter_turtle.by_video_desc()

        # If no chapter data is found, try to get chapter data from video comments
        if not chapter_data:
            base_logger.info(f"Trying to get chapter data for {id} from comments")
            chapter_data = chapter_turtle.by_video_comments()

        return chapter_data

    def downloader(self, vidID: str, gameID: int) -> int:
        """ Download the audio from a video

        Args:
            vidID (str): Video ID
            gameID (int): Game ID

        Returns:
            int: video duration in seconds
        """

        # Remove the temp file if it exists 
        file = f'/bacchus/audio/{gameID}/temp.wav'
        try: os.remove(file)
        except: pass

        URL = f'http://www.youtube.com/watch?v={vidID}'
        ydl_opts = {
            'outtmpl': f'/bacchus/audio/{gameID}/temp',
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',  # Changer le format à WAV non compressé
                'preferredquality': '320',  # Qualité audio en kilobits par seconde (320 kbps)
            }],
        }
        
        # Download the audio file and get the duration
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(URL, download=False)
            vid_dur = info['duration']
            ydl.download([URL])

        return vid_dur

    def index_moyenne_proche_de_zero(self, arr: np.ndarray) -> int:
        """ Compute the index of the array where the mean is closest to zero

        Args:
            arr (np.ndarray): Numpy array of waveform data

        Returns:
            int: Index of the array where the mean is closest to zero
        """

        abs_arr = np.abs(arr)
        moyennes = []
        
        for i in range(0, len(arr), 100):
            debut = max(0, i-100)
            fin = min(len(arr), i+100)
            moyenne = np.mean(abs_arr[debut:fin])
            moyennes.append(moyenne)
        moyennes = np.array(moyennes)
        
        return np.argmin(moyennes)*100

    def fix_audio_timestamp(self, gameID: int, vidID: str) -> None:
        """ Fix audio timestamp extracted from youtube

        Args:
            gameID (int): Game ID
            vidID (str): Video ID
        """
        
        file_path = f"/bacchus/chapters/{vidID}.json"
        with open(file_path, "r") as f:
            chapters = json.loads(f.read())
            
        AudioName = f"/bacchus/audio/{gameID}/temp.wav"
        fs_wav, data_wav = wavfile.read(AudioName)
        
        for ch in chapters[1:]:
            ch_wav = data_wav[int((ch['timestamp'] - 20) * fs_wav):int((ch['timestamp'] + 20) * fs_wav), 0]
            closest_index = self.index_moyenne_proche_de_zero(ch_wav)
            ch['corrected_timestamp'] = ch['timestamp'] - 20 + closest_index / fs_wav
            
        with open(file_path, "w") as f:
            f.write(json.dumps(chapters, indent=4))
    
    def cut_and_save_audio_segment(self, gameID: int, file_uuid: str, audio: list, start: int, end: int):
        """ Cut and save the audio segment

        Args:
            gameID (int): Game ID
            file_uuid (str): File UUID
            audio (list): Full audio file
            start (int): Start timecode
            end (int): End timecode
        """
        
        # Cut the audio file into 10 second chunks
        currentTimecode = start
        while currentTimecode < end - 10 * 1000:
            currentTimecodeDelay = currentTimecode if currentTimecode == 0 else currentTimecode - 100
            cutAudio = audio[currentTimecodeDelay:currentTimecode + (10 * 1000 + 100)]

            wavIO = BytesIO()
            cutAudio.export(wavIO, format="mp3")
            pathlib.Path(f"/bacchus/audio/{gameID}/{file_uuid}/{int(currentTimecode - start)}").write_bytes(wavIO.getbuffer())

            currentTimecode += 10 * 1000

        # Cut the last audio file (less than 10 seconds)
        cutAudio = audio[currentTimecode - 100:end]
        wavIO = BytesIO()
        cutAudio.export(wavIO, format="mp3")
    
    def full_audio_format(self, gameID: int, chapters: list) -> None:
        """ Format the full audio file into 10 second chunks

        Args:
            gameID (int): Game ID
            chapters (list): List of chapters
            duration (int): Video duration in seconds
        """ 
        
        # Remove old audio files directory
        def delete_dirs(path):
            for file in os.listdir(path):
                full_path = os.path.join(path, file)
                if os.path.isdir(full_path):
                    shutil.rmtree(full_path)
        delete_dirs(f"/bacchus/audio/{gameID}")

        # Load the full audio file
        audio = AudioSegment.from_file(f"/bacchus/audio/{gameID}/temp.wav")
        duration = len(audio)

        # Cut the audio file into 10 second chunks
        tasks = []
        # tracks_id = []
        with ThreadPoolExecutor() as executor, self.conn.cursor(cursor_factory=LoggingCursor) as curs:
            for i, chapter in enumerate(chapters):
                start = chapter.get('corrected_timestamp', chapter['timestamp'])*1000
                end = duration if i >= len(chapters) - 1 else chapters[i + 1].get('corrected_timestamp', chapters[i]['timestamp'])*1000
                file_uuid = uuid.uuid4().hex
                os.mkdir(f"/bacchus/audio/{gameID}/{file_uuid}")
                
                task = executor.submit(self.cut_and_save_audio_segment, gameID, file_uuid, audio, start, end)
                tasks.append(task)
                
                chapter['file'] = file_uuid
                chapter['duration'] = end - start
                
                # query = sql.SQL("INSERT INTO iris.track (game_id, title, slug, file, view_count, like_count, length)"
                #                 "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id;")
                # data = (gameID, chapter['title'], slugify(chapter['title']), file_uuid, 0, 0, end - start)
                # curs.execute(query, data)
                # tracks_id.append(curs.fetchone()[0])

        # Wait for all tasks to complete
        for task in tasks:
            task.result()
            
        # Add the track to the database album table
        Iris_client.push_chapters(gameID, chapters)
        # with self.conn.cursor(cursor_factory=LoggingCursor) as curs:
        #     query = sql.SQL("SELECT name FROM iris.game WHERE id = %s;")
        #     curs.execute(query, (gameID,))
        #     name = curs.fetchone()[0] + " - Full OST"
        #     name_slug = slugify(name)
            
        #     query = sql.SQL("INSERT INTO iris.album (game_id, name, slug, is_main) VALUES (%s,%s,%s,%s) RETURNING id;")
        #     data = (gameID, name, name_slug, 't')
        #     curs.execute(query, data)
        #     album_id = curs.fetchone()[0]
            
        #     for track_id in tracks_id:
        #         query = sql.SQL("INSERT INTO iris.album_track (album_id, track_id) VALUES (%s,%s);")
        #         data = (album_id, track_id)
        #         curs.execute(query, data)
                
        # self.conn.commit()
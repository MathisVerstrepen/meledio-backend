# from selenium import webdriver
import requests
import json
from rich import print
import yt_dlp
import os
import subprocess
from datetime import timedelta
from pydub import AudioSegment
import uuid
from multiprocessing import Pool
from threading import Thread
import psycopg2
import psycopg2.extensions
from psycopg2 import sql
from slugify import slugify
import logging
import re
import glob
import shutil
from io import BytesIO
import pathlib
import numpy as np
from scipy.io import wavfile


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
        r = requests.get(
            f'https://www.youtube.com/watch?v={id}')

        r_cut_1 = r.text.split('var ytInitialData = ')[1]
        r_cut_2 = r_cut_1.split(';</script><script')[0]

        self.vid_meta = json.loads(r_cut_2)
        self.id = id
        self.continuation_token = (self.vid_meta['contents']['twoColumnWatchNextResults']['results']['results']
        ['contents'][-1]['itemSectionRenderer']['contents'][0]['continuationItemRenderer']
        ['continuationEndpoint']['continuationCommand']['token'])

        # f = open(
        #     f'/ares/app/functions/json-{id}.json', 'w')
        # f.write(json.dumps(self.vid_meta))
        # f.close()

    def extract_chapter_data(self, text):
        chapter_data = []
        ntext = len(text)
        index = 0
        lastWatchEndpoint = -1

        while (index < ntext):

            hasNavigationEndpoint = False
            watchEndpoint = -1

            nextIndex = index + 1
            while nextIndex < ntext and not '\n' in text[nextIndex].get('text'):
                # logging.debug(text[nextIndex].get('text'))
                if text[nextIndex].get('navigationEndpoint'):
                    if watchEndpoint == -1: watchEndpoint = text[nextIndex].get('navigationEndpoint').get(
                        'watchEndpoint', {}).get('startTimeSeconds')
                    if watchEndpoint != None: hasNavigationEndpoint = True

                nextIndex += 1

            if hasNavigationEndpoint and lastWatchEndpoint < watchEndpoint:
                fullRowElt = []

                fullRowElt.append(text[index].get('text').split('\n')[-1])

                for tmpIndex in range(index + 1, nextIndex):
                    # logging.debug(text[tmpIndex].get('text'))
                    fullRowElt.append(text[tmpIndex].get('text'))

                if nextIndex < ntext: fullRowElt.append(text[nextIndex].get('text').split('\n')[0])

                # logging.debug(fullRowElt)

                # if nextIndex < ntext : start_next_string = text[nextIndex].get('text').split('\n')[-1]

                chapter_data.append({
                    'title': self.format_line(fullRowElt),
                    'timestamp': watchEndpoint
                })
                lastWatchEndpoint = watchEndpoint

                watchEndpoint = -1
            index = nextIndex

        return chapter_data

    def by_youtube_data(self):

        try:
            chapters = (self.vid_meta['playerOverlays']['playerOverlayRenderer']['decoratedPlayerBarRenderer']
            ['decoratedPlayerBarRenderer']['playerBar']['multiMarkersPlayerBarRenderer']['markersMap'][0]['value'][
                'chapters'])
        except Exception:
            chapter_data = None
        else:
            chapter_data = []
            for chapter in chapters:
                title = self.format_line([chapter['chapterRenderer']['title']['simpleText']])
                chapter_data.append({
                    'title': title,
                    'timestamp': chapter['chapterRenderer']['timeRangeStartMillis'] / 1000
                })

        return chapter_data

    def by_video_desc(self):
        try:
            desc = (self.vid_meta['contents']['twoColumnWatchNextResults']['results']['results']
            ['contents'][1]['videoSecondaryInfoRenderer']['description']['runs'])
        except Exception:
            chapter_data = None
        else:
            chapter_data = self.extract_chapter_data(desc)

        return chapter_data

    def by_video_comments(self):
        with open('/ares/app/functions/json/youtube_comments_body.json', 'r') as f:

            body_data = json.load(f)

            vid_url = f"https://www.youtube.com/watch?v={self.id}"
            body_data['context']['client']['originalUrl'] = vid_url
            body_data['context']['client']['mainAppWebInfo']['graftUrl'] = vid_url
            body_data['continuation'] = self.continuation_token

            r = requests.post(
                'https://www.youtube.com/youtubei/v1/next', data=json.dumps(body_data))

            r_parse = json.loads(r.text)

            comments = (r_parse['onResponseReceivedEndpoints']
            [1]['reloadContinuationItemsCommand']['continuationItems'])

            comment_index = 0
            while comment_index >= 0 and comment_index <= len(comments) - 1:
                isComment = comments[comment_index].get('commentThreadRenderer')

                if isComment:
                    com_parts = isComment['comment']['commentRenderer']['contentText']['runs']
                    chapter_data = self.extract_chapter_data(com_parts)

                    if len(chapter_data) > 3:
                        comment_index = -1
                    else:
                        comment_index += 1

        return chapter_data

    def format_line(self, lline: str) -> str:
        for lpart in lline:
            if lpart:
                lpart = lpart.split('\n')[0].strip() if (lpart.split('\n')[0]) else lpart.split('\n')[1].strip()
                part_len = len(lpart)

                if re.search('[a-zA-Z]', lpart):

                    start_index = 0
                    while start_index < part_len and not lpart[start_index].isalpha():
                        start_index += 1

                    end_index = part_len - 1
                    while end_index > start_index and not lpart[end_index].isalpha() and not lpart[
                        end_index].isnumeric():
                        end_index -= 1

                    return lpart[start_index:end_index + 1]


class LoggingCursor(psycopg2.extensions.cursor):
    def execute(self, sql, args=None):
        logger = logging.getLogger('sql_debug')
        logger.info(self.mogrify(sql, args))

        try:
            psycopg2.extensions.cursor.execute(self, sql, args)
        except Exception as exc:
            logger.error("%s: %s" % (exc.__class__.__name__, exc))
            raise


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
            
        with open('/ares/app/functions/json/youtube_body.json', 'r') as f:
            self.youtube_body = json.load(f)

    def best_match(self, gameName: str) -> list:
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

        chapter_turtle = chapter_scrap(id)

        chapter_data = chapter_turtle.by_youtube_data()

        if not chapter_data:
            chapter_data = chapter_turtle.by_video_desc()

        if not chapter_data:
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
                'preferredcodec': 'wav',
            }],
        }
        
        # Download the audio file and get the duration
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(URL, download=False)
            vid_dur = info['duration']
            ydl.download([URL])

        return vid_dur

    def format_audio(gameID: int, audioID: str, audioIndex: int, r_games):
        audio = AudioSegment.from_file(f"/bacchus/audio/{gameID}/{audioID}.m4a")
        audioLength = len(audio)
        audioMetadata = []

        dir = f"/bacchus/audio/{gameID}/{audioID}"
        if (not os.path.isdir(dir)): os.makedirs(dir)
        files = glob.glob(f"/bacchus/audio/{gameID}/{audioID}/*")
        for f in files:
            os.remove(f)

        currentTimecode = 0
        while currentTimecode < audioLength - 10 * 1000:
            currentTimecodeDelay = currentTimecode if currentTimecode == 0 else currentTimecode - 100
            cutAudio = audio[currentTimecodeDelay:currentTimecode + (10 * 1000 + 100)]

            wavIO = BytesIO()
            cutAudio.export(wavIO, format="mp3")
            pathlib.Path(f"/bacchus/audio/{gameID}/{audioID}/{currentTimecode}").write_bytes(wavIO.getbuffer())

            audioMetadata.append(currentTimecode)
            currentTimecode += 10 * 1000

        cutAudio = audio[currentTimecode - 100:audioLength]
        wavIO = BytesIO()
        cutAudio.export(wavIO, format="mp3")
        pathlib.Path(f"/bacchus/audio/{gameID}/{audioID}/{currentTimecode}").write_bytes(wavIO.getbuffer())
        audioMetadata.append(currentTimecode)

        r_games.json().set(f"g:{gameID}", f"$.album[0].track[{audioIndex}].chunkMeta", audioMetadata)

        logging.debug(f'Format track {audioID}')

    def file_formater(self, gameID: int, chapters: list, vid_dur: int, r_games) -> list:


        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:

            subprocess_list = []
            tracklist = []

            for i in range(len(chapters)):
                file_uuid = uuid.uuid4().hex
                title_slug = slugify(chapters[i]['title'])
                start = chapters[i]['timestamp']
                end = vid_dur if i >= len(chapters) - 1 else chapters[i + 1]['timestamp']

                query = sql.SQL("INSERT INTO iris.track (game_id, title, slug, file, view_count, like_count, length) "
                                "VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id;")
                data = (gameID, chapters[i]['title'], title_slug, file_uuid, 0, 0, end - start)
                curs.execute(query, data)
                track_id = curs.fetchall()[0][0]

                query = sql.SQL("INSERT INTO iris.album (game_id, track_id, name, slug) VALUES (%s,%s,%s,%s);")
                data = (gameID, track_id, "Full Album", "full-album")
                curs.execute(query, data)

                p = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-i', f'/bacchus/audio/{gameID}/temp.wav', '-ss',
                                    str(timedelta(seconds=start)), '-to', str(timedelta(seconds=end)), '-c:a', 'aac', '-b:a', '256k',
                                    '-y', f'/bacchus/audio/{gameID}/{file_uuid}.m4a'], shell=False,
                                    stdin=None, stdout=None, stderr=None, close_fds=True)
                subprocess_list.append(p)

                tracklist.append({
                    'id': track_id,
                    'title': chapters[i]['title'],
                    'slug': title_slug,
                    'file': file_uuid,
                    'view_count': 0,
                    'like_count': 0,
                    'length': end - start
                })

        [p.wait() for p in subprocess_list]

        r_games.json().arrinsert(f"g:{gameID}", "$.album", 0, {
            "name": "Full Album",
            "slug": "test",
            "track": tracklist
        })

        for index, track in enumerate(tracklist):
            Thread(target=s1.format_audio, args=(gameID, track['file'], index, r_games,)).start()

        # os.remove(f"/bacchus/audio/{gameID}/temp.m4a")

        self.conn.commit()

        return tracklist

    def index_moyenne_proche_de_zero(self, arr):
        abs_arr = np.abs(arr)
        moyennes = []
        for i in range(0, len(arr), 100):
            debut = max(0, i-100)
            fin = min(len(arr), i+100)
            moyenne = np.mean(abs_arr[debut:fin])
            moyennes.append(moyenne)
        moyennes = np.array(moyennes)
        return np.argmin(moyennes)*100

    def fix_audio_timestamp(self, gameID: int, vidID: str):
        file_path = f"/bacchus/chapters/{vidID}.json"
        with open(file_path, "r") as f:
            chapters = json.loads(f.read())
            
        AudioName = f"/bacchus/audio/{gameID}/temp.wav"
        fs_wav, data_wav = wavfile.read(AudioName)
        
        for ch in chapters[1:]:
            print(ch['title'])
            ch_wav = data_wav[int((ch['timestamp'] - 20) * fs_wav):int((ch['timestamp'] + 20) * fs_wav), 0]
            
            closest_index = self.index_moyenne_proche_de_zero(ch_wav)

            logging.debug(f"Closest index: {closest_index}")
            ch['corrected_timestamp'] = ch['timestamp'] - 20 + closest_index / fs_wav
            
        with open(file_path, "w") as f:
            f.write(json.dumps(chapters, indent=4))
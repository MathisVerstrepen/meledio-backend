# from selenium import webdriver
import requests
import json
from rich import print
import yt_dlp
import os
import subprocess
from datetime import timedelta
import uuid
from multiprocessing import Pool
import psycopg2
import psycopg2.extensions
from psycopg2 import sql
from slugify import slugify
import logging
import re


def extract_video_info(data) -> str:
    query, body_data, game, URL = data
    body_data['query'] = game + query
    r = requests.post(URL, data=json.dumps(body_data))
    r_parse = json.loads(r.text)

    # f = open(f'/ares/app/functions/json/test.json', 'w')
    # f.write(json.dumps(r_parse))
    # f.close()

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
        
        while (index < ntext):
            
            hasNavigationEndpoint = False
            watchEndpoint = -1
            
            nextIndex = index + 1
            while nextIndex < ntext and not '\n' in text[nextIndex].get('text'): 
                # logging.debug(text[nextIndex].get('text'))
                if text[nextIndex].get('navigationEndpoint'): 
                    if watchEndpoint == -1 : watchEndpoint = text[nextIndex].get('navigationEndpoint').get('watchEndpoint', {}).get('startTimeSeconds')
                    if watchEndpoint != None : hasNavigationEndpoint = True
                    
                nextIndex += 1
            
            if hasNavigationEndpoint:
                fullRowElt = []
                
                fullRowElt.append(text[index].get('text').split('\n')[-1])
                
                for tmpIndex in range(index + 1, nextIndex):
                    logging.debug(text[tmpIndex].get('text'))
                    fullRowElt.append(text[tmpIndex].get('text'))
                    
                if nextIndex < ntext : fullRowElt.append(text[nextIndex].get('text').split('\n')[0])
                
                logging.debug(fullRowElt)
                
                # if nextIndex < ntext : start_next_string = text[nextIndex].get('text').split('\n')[-1]
                
                chapter_data.append({
                    'title': self.format_line(fullRowElt),
                    'timestamp': watchEndpoint
                })
                
                watchEndpoint = -1
            index = nextIndex
            
        return chapter_data
        
    def by_youtube_data(self):

        try:
            chapters = (self.vid_meta['playerOverlays']['playerOverlayRenderer']['decoratedPlayerBarRenderer']
                        ['decoratedPlayerBarRenderer']['playerBar']['multiMarkersPlayerBarRenderer']['markersMap'][0]['value']['chapters'])
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
            logging.debug(desc)
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
            while comment_index >= 0 and comment_index <= len(comments)-1:
                isComment = comments[comment_index].get('commentThreadRenderer')
                
                if isComment:
                    com_parts = isComment['comment']['commentRenderer']['contentText']['runs']
                    chapter_data = self.extract_chapter_data(com_parts)
                        
                    if len(chapter_data) > 3: comment_index = -1
                    else : comment_index += 1

        return chapter_data

    def format_line(self, lline: str) -> str:
        logging.debug(lline)
        for lpart in lline:
            if lpart:
                lpart = lpart.split('\n')[0].strip() if (lpart.split('\n')[0]) else lpart.split('\n')[1].strip()
                part_len = len(lpart)
                    
                if re.search('[a-zA-Z]', lpart):
            
                    start_index = 0
                    while start_index < part_len and not lpart[start_index].isalpha():
                        start_index += 1

                    end_index = part_len - 1
                    while end_index > start_index and not lpart[end_index].isalpha() and not lpart[end_index].isnumeric():
                        end_index -= 1

                    return lpart[start_index:end_index+1]
                

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

        # option = webdriver.ChromeOptions()

        # option.add_argument("--disable-gpu")
        # option.add_argument("--disable-extensions")
        # option.add_argument("--disable-infobars")
        # option.add_argument("--start-maximized")
        # option.add_argument("--disable-notifications")
        # option.add_argument('--headless')
        # option.add_argument('--no-sandbox')
        # option.add_argument('--disable-dev-shm-usage')

        # self.driver = webdriver.Chrome(options=option)
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

    def best_match(self, game: str) -> list:

        f = open('/ares/app/functions/json/youtube_body.json', 'r')
        body_data = json.load(f)
        f.close()

        URL = 'https://www.youtube.com/youtubei/v1/search'
        data_list = [
            (query, body_data, game, URL) for query in self.search_url
        ]

        p = Pool(len(data_list)).map(extract_video_info, data_list)
        outputs = [result for result in p]

        final = {}
        for output in outputs:
            position = len(output)
            for video in output:
                videoRenderer = video.get('videoRenderer')
                if videoRenderer:
                    videoId = videoRenderer.get('videoId')
                    title = videoRenderer['title']['runs'][0]['text']
                    thumbnailOverlayTimeStatusRenderer = videoRenderer['thumbnailOverlays'][0].get('thumbnailOverlayTimeStatusRenderer')
                    if thumbnailOverlayTimeStatusRenderer:
                        duration = thumbnailOverlayTimeStatusRenderer['text']['simpleText']
                        if final.get(videoId):
                            final[videoId][0] += position
                        else:
                            final[videoId] = [position, title, duration]
                        position -= 1

        return (sorted(final.items(), key=lambda tup: tup[1][0], reverse=True))[0:10]

    def get_chapter(self, id: str) -> list:

        chapter_turtle = chapter_scrap(id)

        chapter_data = chapter_turtle.by_youtube_data()
        logging.debug(chapter_data)

        if not chapter_data:
            chapter_data = chapter_turtle.by_video_desc()
            logging.debug(chapter_data)

        if not chapter_data:
            chapter_data = chapter_turtle.by_video_comments()
            logging.debug(chapter_data)

        return chapter_data

    def downloader(self, vidID: str, gameID: int) -> list:
        
        dir = f'/bacchus/audio/{gameID}'
        try:
            os.mkdir(dir)
        except:
            for f in os.listdir(dir):
                os.remove(os.path.join(dir, f))
            
        
        URL = f'http://www.youtube.com/watch?v={vidID}'

        ydl_opts = {
            'outtmpl': f'/bacchus/audio/{gameID}/temp.m4a',
            'format': 'm4a/bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(URL, download=False)
            vid_dur = info['duration']
            ydl.download([URL])

        return vid_dur

    def file_formater(self, gameID: int, chapters: list, vid_dur:int, r_games) -> list:
        
        with self.conn.cursor(cursor_factory=LoggingCursor) as curs:

            game_name_slug = r_games.json().get(f"g:{gameID}", '$.slug')
            subprocess_list = []
            tracklist = []
            
            for i in range(len(chapters)):
                
                file_uuid = uuid.uuid4().hex
                start = chapters[i]['timestamp']
                end = vid_dur if i >= len(chapters)-1 else chapters[i+1]['timestamp']

                query = sql.SQL("INSERT INTO iris.track (game_id, title, slug, file, view_count, like_count, length) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id;")
                data = (gameID, chapters[i]['title'], slugify(chapters[i]['title']), file_uuid, 0, 0, end-start)
                curs.execute(query, data)
                track_id = curs.fetchall()[0][0]
                
                query = sql.SQL("INSERT INTO iris.album (game_id, track_id, name, slug) VALUES (%s,%s,%s,%s);")
                data = (gameID, track_id, "Full Album", slugify(game_name_slug[0] + " full album"))
                curs.execute(query, data)

                p = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-i', f'/bacchus/audio/{gameID}/temp.m4a', '-ss',
                                str(timedelta(seconds=start)), '-to', str(timedelta(seconds=end)), '-c', 'copy', '-y', f'/bacchus/audio/{gameID}/{file_uuid}.m4a'], shell=False,
                                stdin=None, stdout=None, stderr=None, close_fds=True)
                subprocess_list.append(p)

                tracklist.append({
                    'title': chapters[i]['title'],
                    'file': file_uuid
                })

        [p.wait() for p in subprocess_list]

        os.remove(f"/bacchus/audio/{gameID}/temp.m4a")
        
        r_games.json().set(f"g:{gameID}", "$.album", tracklist)
        self.conn.commit()

        return tracklist
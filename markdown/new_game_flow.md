---
markmap:
  colorFreezeLevel: 2
  maxWidth: 300
---

# New Game Flow

## Matching Games

- `IGDB_cli.matching_games`
    - IGDB API request
    - Sorting and cleaning

## New Game

- `IGDB_cli.new_game`
    - IGDB API request game data
- `iris_cli.push_new_game`
    - check if game already exists
    - push game to Iris


## Matching Videos

- `iris_cli.getGameName`
    - get game name from Iris
- `s1_cli.best_video_match`
    - scrap S1 for videos
        - `extract_video_info`
    - Merge all scraped videos output
    - Sort and clean

## Chapters

- `s1_cli.get_chapter`
    - try `by_youtube_data`
        - embeded youtube data
    - try `by_video_desc`
        - video description data
    - try `by_video_comments`
        - video comments data
- save chapter in JSON file

## Download Video

- `s1_cli.downloader`
    - remove old temp files
    - download video audio with `youtube-dl` and `ffmpeg` in wav format
    - extract duration
- `s1_cli.fix_audio_timestamp`
    - open JSON file
    - load audio file
    - fix timestamp
    - save JSON file

## Format File

- open JSON file
- `s1_cli.full_audio_format`
    - remove track directory
    - load audio file
    - cut audio file in 10sec chunks
        - `self.cut_and_save_audio_segment`
        - IrisDB insert track data
    - IrisDB insert album data
    - IrisDB insert album_track data
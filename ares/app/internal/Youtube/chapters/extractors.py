from app.internal.Youtube.youtube_utils import clean_chapter_line

from app.utils.loggers import base_logger as logger

def extract_command_runs(json_data: dict) -> list:
    return json_data["attributedDescription"]["commandRuns"]


def extract_content(json_data: dict) -> str:
    return json_data["attributedDescription"]["content"]


def find_title_boundaries(content: str, start: int, end: int) -> tuple:
    prev_char = content[start - 1 : start]
    while prev_char != "\n" and start > 0:
        start -= 1
        prev_char = content[start - 1 : start]

    next_char = content[end : end + 1]
    while next_char != "\n" and end < len(content):
        end += 1
        next_char = content[end : end + 1]

    return start, end


def extract_timestamp(command_run: dict) -> int:
    watchEndpoint = command_run["onTap"]["innertubeCommand"].get("watchEndpoint")
    return watchEndpoint["startTimeSeconds"] if watchEndpoint else None


def find_next_newline_index(comments: list, start_index: int) -> tuple:
    next_index = start_index + 1
    watch_endpoint = -1
    while next_index < len(comments) and "\n" not in comments[next_index]["text"]:
        navigation_endpoint = comments[next_index].get("navigationEndpoint")
        if navigation_endpoint and watch_endpoint == -1:
            watch_endpoint = navigation_endpoint.get("watchEndpoint", {}).get(
                "startTimeSeconds"
            )
        next_index += 1
    return next_index, watch_endpoint


def extract_full_row_text(
    comments: list, start_index: int, end_index: int
) -> str:
    full_row_elt = []
    full_row_elt.append(comments[start_index]["text"].split("\n")[-1])
    for tmp_index in range(start_index + 1, end_index):
        full_row_elt.append(comments[tmp_index]["text"])
    if end_index < len(comments):
        full_row_elt.append(comments[end_index]["text"].split("\n")[0])
    return "".join(full_row_elt)


def extract_chapter_description_data(json_data: dict) -> list:
    """Extract titles and timestamps from json data of a youtube video

    Args:
        json_data (dict): json data of a youtube video

    Returns:
        list: List of titles and timestamps
    """

    command_runs = extract_command_runs(json_data)
    content = extract_content(json_data)
    titles_and_timestamps = []
    
    last_timestamp = -1
    last_title = ""
        
    for command_run in command_runs:
        title_start = command_run["startIndex"]
        title_length = command_run["length"]
        title_end = title_start + title_length

        title_start, title_end = find_title_boundaries(content, title_start, title_end)
        title = clean_chapter_line(content[title_start:title_end])
        
        timestamp = extract_timestamp(command_run)
        
        if timestamp is not None and timestamp > last_timestamp and title != last_title:
            last_timestamp = timestamp
            last_title = title
            titles_and_timestamps.append({"timestamp": timestamp, "title": title})

    return titles_and_timestamps


def extract_chapter_comment_data(comments: list) -> list:
    """Extract chapter data from YouTube comments.

    Args:
        comments (list): List of YouTube comments

    Returns:
        list: List of chapter data including titles and timestamps
    """

    chapter_data = []
    last_watch_endpoint = -1
    index = 0

    while index < len(comments):
        next_index, watch_endpoint = find_next_newline_index(comments, index)

        if watch_endpoint is not None and last_watch_endpoint < watch_endpoint:
            full_row_text = extract_full_row_text(comments, index, next_index)
            formatted_text = clean_chapter_line(full_row_text)

            chapter_data.append({"title": formatted_text, "timestamp": watch_endpoint})

            last_watch_endpoint = watch_endpoint

        index = next_index

    return chapter_data

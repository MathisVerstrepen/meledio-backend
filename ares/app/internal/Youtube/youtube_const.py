import random

user_agent_list = [ 
	'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36', 
	'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36', 
	'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15', 
]

SEARCH_URLS_END = [
    " game full ost",
    " game full album",
    " game full soundtrack",
    " game complete soundtrack",
    " original game soundtrack",
]

PROXIES = [
    "socks5://192.168.2.51:1080",
    "socks5://192.168.2.51:1081",
    "socks5://192.168.2.51:1082"
]

YT_SEARCH_URL = "https://www.youtube.com/youtubei/v1/search"
YT_COMMENT_URL = "https://www.youtube.com/youtubei/v1/next"
YT_PLAYLIST_URL = "https://www.youtube.com/playlist?list="

HEADER_BYPASS_YOUTUBE_COOKIE = {
    "Authorization": "authorization",
    "cookie": "SOCS=CAISNQgDEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjMwODI5LjA3X3AxGgJlbiACGgYIgLC_pwY",
}

def get_youtube_header():
    headers = {
        "User-Agent": user_agent_list[random.randint(0, len(user_agent_list) - 1)],
        "Authorization": "authorization",
        "cookie": "SOCS=CAISNQgDEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjMwODI5LjA3X3AxGgJlbiACGgYIgLC_pwY",
    }
    return headers
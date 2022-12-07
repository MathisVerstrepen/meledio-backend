import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import requests
from timeit import default_timer as timer

N = 1000

# URL = "http://65.21.91.39:5100/v1/games/id"
url = "http://65.21.91.39:5100/v1/game"
API_ADMIN_KEY = "uAJRzpD5JQK8o8pHN7YsajXW6DoHmdoS"
GAME_ID = 1942
querystring = {"gID": "1942", "debug": "true"}
headers = {"Content-Type": "application/json"}
payload = [ "base" ]
debug = {}


def mesureTime(n: int):
    if n % 100 == 0:
        print(f"Request {n}")
    t1_start = timer()
    res = requests.request(
        "GET", url, json=payload, headers=headers, params=querystring
    )
    t1_stop = timer()
    jsonRes = res.json()
    # print(jsonRes["debug_data"]["base"])
    for key, value in jsonRes["debug_data"].items():
        debug.setdefault(key, 0)
        debug[key] += value
    # return t1_stop - t1_start
    return jsonRes["debug_data"]["base"]


xplot = np.array([k for k in range(0, N)])
yplot = np.array([mesureTime(k) for k in xplot])

df_describe = pd.DataFrame(yplot)
# df_describe *= 1000
print(df_describe.describe())
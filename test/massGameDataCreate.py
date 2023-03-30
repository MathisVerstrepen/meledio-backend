import requests

N = 1000

# URL = "http://65.21.91.39:5100/v1/games/id"
url = "http://65.21.91.39:5100/new_game"
API_ADMIN_KEY = "uAJRzpD5JQK8o8pHN7YsajXW6DoHmdoS"
headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_ADMIN_KEY}"}
debug = {}

for i in range(1000, 2000):
    querystring = {"gameID": i}
    res = requests.request(
        "POST", url, headers=headers, params=querystring
    )
    print(f"Game {i} created [Status: {res.status_code}]")
    
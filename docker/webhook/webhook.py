from flask import Flask, request
import json
import subprocess
import os

app = Flask(__name__)

# Authenticate with Docker registry
os.system(f'echo "{os.environ["DOCKER_REGISTRY_TOKEN"]}" | docker login --username {os.environ["DOCKER_REGISTRY_USERNAME"]} --password-stdin registry.diikstra.fr')

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    payload = json.loads(request.data)

    if payload['action'] == 'completed' and payload['workflow_run']['conclusion'] == 'success':
        subprocess.run(['docker', 'pull', 'registry.diikstra.fr/dune_dionysos:latest'])
        subprocess.run(['docker', 'compose', '-f', '/app/front-compose.yml', 'down'])
        subprocess.run(['docker', 'compose', '-f', '/app/front-compose.yml', 'up', '-d'])

    return 'OK', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)


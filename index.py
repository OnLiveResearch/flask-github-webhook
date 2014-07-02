#!/usr/bin/env python
import io
import os
import re
import sys
import json
import subprocess
import requests
import ipaddress
from flask import Flask, request, abort

app = Flask(__name__)


HI_MSG = json.dumps({'msg': 'Hi!'})
WRONG_EVENT_TYPE_MSG = json.dumps({'msg': "wrong event type"})

@app.route("/", methods=['POST'])
def index():

    if not is_ip_from_github(request.remote_addr):
        abort(403)

    if is_ping_event(request):
        return HI_MSG
    if not is_push_event(request):
        return WRONG_EVENT_TYPE_MSG

    repos = json.loads(io.open('repos.json', 'r').read())

    payload = json.loads(request.data)
    repo_meta = {
        'name': payload['repository']['name'],
        'owner': payload['repository']['owner']['name'],
    }
    match = re.match(r"refs/heads/(?P<branch>.*)", payload['ref'])
    repo = None
    if match:
        repo_meta['branch'] = match.groupdict()['branch']
        repo = repos.get('{owner}/{name}/branch:{branch}'.format(**repo_meta), None)
    if repo is None:
        repo = repos.get('{owner}/{name}'.format(**repo_meta), None)
    if repo and repo.get('path', None):
        if repo.get('action', None):
            for action in repo['action']:
                subprocess.Popen(action,
                                 cwd=repo['path'])
        else:
            subprocess.Popen(["git", "pull", "origin", "master"],
                             cwd=repo['path'])
    return 'OK'


def is_ip_from_github(remote_addr):
    for block in get_ip_blocks_from_github():
        if is_ip_in_block(remote_addr, block):
            return True
    return False


def is_ip_in_block(ip, block):
    ip = ipaddress.ip_address(u'%s' % ip)
    return ipaddress.ip_address(ip) in ipaddress.ip_network(block)


def get_ip_blocks_from_github():
    return requests.get('https://api.github.com/meta').json()['hooks']


def is_ping_event(request):
    return request.headers.get('X-GitHub-Event') == "ping"

def is_push_event(request):
    return request.headers.get('X-GitHub-Event') == "push"


if __name__ == "__main__":
    try:
        port_number = int(sys.argv[1])
    except ValueError:
        port_number = 80
    host = os.environ.get('HOST', '0.0.0.0')
    is_dev = os.environ.get('ENV', None) == 'dev'
    if os.environ.get('USE_PROXYFIX', None) == 'true':
        from werkzeug.contrib.fixers import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app)
        if host == '0.0.0.0':
            host = '127.0.0.1'
    app.run(host=host, port=port_number, debug=is_dev)

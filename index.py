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

repos_cache = None


HI_MSG = json.dumps({'msg': 'Hi!'})
WRONG_EVENT_TYPE_MSG = json.dumps({'msg': "wrong event type"})
OK_MSG = 'OK'

@app.route("/", methods=['POST'])
def index():
    if not is_ip_from_github(request.remote_addr):
        abort(403)

    if is_ping_event(request):
        return HI_MSG
    if not is_push_event(request):
        return WRONG_EVENT_TYPE_MSG

    payload = json.loads(request.data)

    repo = find_repo(payload)

    if not repo:
        abort(404)

    run_actions_for_repo(repo)

    return OK_MSG


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


def get_repos():
    global repos_cache
    if not repos_cache:
        repos_cache = json.loads(io.open('repos.json', 'r').read())

    return repos_cache


def find_repo(payload):
    repos = get_repos()

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
    return repo


def run_command(command, path):
    return subprocess.Popen(command, cwd=path)


def git_pull(path):
    return run_command(command=["git", "pull", "origin", "master"],
                       path=path)


def repo_has_path(repo):
    return 'path' in repo


def repo_has_action(repo):
    return repo.get('action', None)


def run_actions_for_repo(repo):
    if repo and repo_has_path(repo):
        if repo_has_action(repo):
            for action in repo['action']:
                run_command(action, repo['path'])
        else:
            git_pull(repo['path'])


def get_host():
    host = os.environ.get('HOST', '0.0.0.0')
    if os.environ.get('USE_PROXYFIX', None) == 'true':
        from werkzeug.contrib.fixers import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app)
        if host == '0.0.0.0':
            host = '127.0.0.1'
    return host


def get_port_number():
    try:
        return int(sys.argv[1])
    except ValueError:
        return 80


def is_dev():
    return os.environ.get('ENV', None) == 'dev'


if __name__ == "__main__":
    app.run(host=get_host(), port=get_port_number(), debug=is_dev())


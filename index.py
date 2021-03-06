#!/usr/bin/env python
import io
import os
import re
import sys
import json
import subprocess
import requests
import ipaddress
import signal
from flask import Flask, request, abort

app = Flask(__name__)

repos_cache = None


HI_MSG = json.dumps({'msg': 'Hi!'})
WRONG_EVENT_TYPE_MSG = json.dumps({'msg': "wrong event type"})
OK_MSG = 'OK'

PING_EVENT = 'ping'
PUSH_EVENT = 'push'

@app.route("/", methods=['POST'])
def index():
    if not is_ip_from_github(request.headers.get('X-Real-Ip', None)
                             or request.remote_addr):
        abort(403)

    event = get_event(request)
    if event == PING_EVENT:
        return HI_MSG
    if event != PUSH_EVENT:
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


def get_event(request):
    return request.headers.get('X-GitHub-Event')


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


def run_command(command, path, env=None):
    return subprocess.Popen(command, cwd=path, env=env)


def git_pull(path, env=None):
    return run_command(command=["git", "pull", "origin", "master"],
                       path=path, env=env)


def run_actions_for_repo(repo):
    if repo and 'path' in repo:
        env = os.environ.copy()
        env.update(repo.get('env', {}))

        actions = repo.get('action', [])
        if actions:
            for action in actions:
                run_command(action, repo['path'], env=env)
        else:
            git_pull(repo['path'], env=env)


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


def reload_config():
    global repos_cache
    repos_cache = None
    get_repos()


def handle_sigusr1(signum, stack):
    if signum is signal.SIGUSR1:
        reload_config()


if __name__ == "__main__":
    signal.signal(signal.SIGUSR1, handle_sigusr1)

    app.run(host=get_host(), port=get_port_number(), debug=is_dev())


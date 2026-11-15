#!/usr/bin/env python3
"""Refresh the stats sentence and badges in README.md from the GitHub API.

Usage: GITHUB_TOKEN=... python3 scripts/update_stats.py [login]
Only the standard library is used so it runs on a bare Actions runner.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request

LOGIN = sys.argv[1] if len(sys.argv) > 1 else "admin0330"
TOKEN = os.environ["GITHUB_TOKEN"]
README = os.path.join(os.path.dirname(__file__), "..", "README.md")


def call(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-stats")
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def search_count(q, kind="issues"):
    return call(f"https://api.github.com/search/{kind}?q={q}&per_page=1")["total_count"]


query = """query($login:String!){ user(login:$login){
  createdAt
  repositories(ownerAffiliations:OWNER, isFork:false, privacy:PUBLIC, first:100){
    totalCount nodes{ stargazerCount } }
  repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST,ISSUE],
    includeUserRepositories:false, privacy:PUBLIC){ totalCount } } }"""
u = call("https://api.github.com/graphql", {"query": query, "variables": {"login": LOGIN}})["data"]["user"]
public_repos = call(f"https://api.github.com/users/{LOGIN}")["public_repos"]

created = dt.datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00"))
now = dt.datetime.now(dt.timezone.utc)
years = now.year - created.year - ((now.month, now.day) < (created.month, created.day))
stars = sum(n["stargazerCount"] for n in u["repositories"]["nodes"])
projects = u["repositories"]["totalCount"]
contributed = u["repositoriesContributedTo"]["totalCount"]
commits = search_count(f"author:{LOGIN}", "commits")
issues = search_count(f"author:{LOGIN}+type:issue")
prs = search_count(f"author:{LOGIN}+type:pr")


def n(v, word):
    return f"**{v}** {word}{'' if v == 1 else 's'}"


sentence = (
    f"I joined GitHub **{years}** years ago and have since pushed {n(commits, 'commit')}, "
    f"opened {n(issues, 'issue')}, submitted {n(prs, 'pull request')}, "
    f"and earned {n(stars, 'star')} across {n(projects, 'personal project')}, "
    f"with contributions to {n(contributed, 'public repository').replace('repositorys', 'repositories')}."
)

text = open(README, encoding="utf-8").read()
new = re.sub(r"(<!-- stats:start -->\n).*?(\n<!-- stats:end -->)",
             lambda m: m.group(1) + sentence + m.group(2), text, flags=re.S)
new = re.sub(r"badge/repos-\d+-", f"badge/repos-{public_repos}-", new)
new = re.sub(r"badge/stars-\d+-", f"badge/stars-{stars}-", new)
if new != text:
    open(README, "w", encoding="utf-8").write(new)
    print("README updated:", sentence)
else:
    print("No change:", sentence)

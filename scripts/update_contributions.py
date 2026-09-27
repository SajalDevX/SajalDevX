#!/usr/bin/env python3
"""Regenerate the open-source contribution ledger in README.md.

Pulls every public pull request @SajalDevX has opened in repositories he does
not own and rewrites the section between the CONTRIB markers. Runs in GitHub
Actions daily; can also be run locally with a GITHUB_TOKEN in the environment.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

USER = "SajalDevX"
README = Path(__file__).resolve().parent.parent / "README.md"
START = "<!-- CONTRIB:START -->"
END = "<!-- CONTRIB:END -->"

# Short human labels for upstream projects; anything missing falls back to the repo name.
PROJECT_LABELS = {
    "The-OpenROAD-Project/OpenROAD": "OpenROAD · open-source RTL-to-GDS EDA",
    "OneBusAway/maglev": "OneBusAway Maglev · transit REST API (Go)",
    "ohcnetwork/care": "CARE · hospital & patient management (Django)",
    "ankidroid/Anki-Android": "AnkiDroid · spaced-repetition Android app",
    "TeamAmaze/AmazeFileManager": "Amaze File Manager · Android",
    "mlflow/mlflow": "MLflow · ML lifecycle platform",
    "kubeflow/kale": "Kubeflow Kale · notebooks → pipelines",
    "mesa/mesa": "Mesa · agent-based modelling (Python)",
    "arxlang/arx": "Arx · compiler front-end (LLVM)",
    "theochem/grid": "theochem/grid · numerical integration",
    "dora-rs/dora-hub": "dora-rs · robotics dataflow nodes",
    "fossasia/eventyay": "FOSSASIA eventyay · event ticketing",
    "CCExtractor/ccextractor": "CCExtractor · subtitle extraction (C)",
    "CCExtractor/sample-platform": "CCExtractor sample platform (Flask)",
    "CircuitVerse/cv-frontend-vue": "CircuitVerse · digital logic simulator (Vue)",
    "omegaup/omegaup": "omegaUp · competitive programming platform",
    "hermetoproject/hermeto": "Hermeto · hermetic build dependency fetcher",
    "openfoodfacts/open-prices": "Open Food Facts · Open Prices (Django)",
    "Submitty/Submitty": "Submitty · course management & autograding",
    "OpenMS/pyopenms_viz": "OpenMS · pyopenms_viz (mass-spec plotting)",
    "neuroinformatics-unit/movement": "movement · animal pose-tracking analysis",
    "JdeRobot/PerceptionMetrics": "JdeRobot PerceptionMetrics · CV evaluation",
    "openwisp/netjsonconfig": "OpenWISP netjsonconfig · network config rendering",
    "foss42/apidash": "API Dash · Flutter API client",
}


def gh(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": f"{USER}-profile-updater"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_prs() -> list[dict]:
    q = urllib.parse.quote(f"author:{USER} is:pr -user:{USER} is:public")
    items: list[dict] = []
    page = 1
    while True:
        data = gh(f"https://api.github.com/search/issues?q={q}&per_page=100&page={page}&sort=created&order=desc")
        batch = data.get("items", [])
        items.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    prs = []
    for it in items:
        repo = "/".join(it["repository_url"].split("/")[-2:])
        merged = bool((it.get("pull_request") or {}).get("merged_at"))
        state = "merged" if merged else ("open" if it["state"] == "open" else "closed")
        prs.append({"repo": repo, "number": it["number"], "title": it["title"].rstrip("…").strip(),
                    "url": it["html_url"], "state": state, "created": it["created_at"][:10]})
    return prs


def repo_link(repo: str) -> str:
    return f"[`{repo}`](https://github.com/{repo})"


def render(prs: list[dict]) -> str:
    merged = [p for p in prs if p["state"] == "merged"]
    open_ = [p for p in prs if p["state"] == "open"]
    projects = sorted({p["repo"] for p in prs})
    out: list[str] = []

    # Headline numbers
    out.append('<p>')
    out.append(f'  <img src="https://img.shields.io/badge/pull_requests-{len(prs)}-1f6feb?style=flat-square&labelColor=161b22&logo=git&logoColor=white" />')
    out.append(f'  <img src="https://img.shields.io/badge/merged-{len(merged)}-8957e5?style=flat-square&labelColor=161b22&logo=github&logoColor=white" />')
    out.append(f'  <img src="https://img.shields.io/badge/in_review-{len(open_)}-2da44e?style=flat-square&labelColor=161b22&logo=githubactions&logoColor=white" />')
    out.append(f'  <img src="https://img.shields.io/badge/projects-{len(projects)}-f78166?style=flat-square&labelColor=161b22&logo=opensourceinitiative&logoColor=white" />')
    out.append("</p>\n")

    # Merged table
    out.append("### Merged upstream\n")
    out.append("| Project | Pull request |")
    out.append("|:--|:--|")
    for p in sorted(merged, key=lambda x: x["created"], reverse=True):
        label = PROJECT_LABELS.get(p["repo"], p["repo"])
        out.append(f"| **{repo_link(p['repo'])}**<br/><sub>{label}</sub> | [#{p['number']}]({p['url']}) {p['title']} |")
    out.append("")

    # Open, grouped by project
    out.append("### In review\n")
    out.append("<details>")
    out.append(f"<summary><b>{len(open_)} open pull requests across {len({p['repo'] for p in open_})} projects</b> — click to expand</summary>\n")
    by_repo: dict[str, list[dict]] = defaultdict(list)
    for p in open_:
        by_repo[p["repo"]].append(p)
    for repo in sorted(by_repo, key=lambda r: (-len(by_repo[r]), r.lower())):
        label = PROJECT_LABELS.get(repo, repo)
        out.append(f"**{repo_link(repo)}** · <sub>{label}</sub>")
        for p in sorted(by_repo[repo], key=lambda x: x["number"]):
            out.append(f"- [#{p['number']}]({p['url']}) {p['title']}")
        out.append("")
    out.append("</details>\n")

    # Project cloud
    out.append("### Contributed to\n")
    out.append('<p>')
    for repo in projects:
        owner, name = repo.split("/")
        badge_name = urllib.parse.quote(name.replace("-", "--").replace("_", "__"))
        out.append(f'  <a href="https://github.com/{repo}"><img alt="{repo}" src="https://img.shields.io/badge/{badge_name}-0d1117?style=flat-square&logo=github&logoColor=white&labelColor=0d1117&color=30363d" /></a>')
    out.append("</p>")
    return "\n".join(out)


def main() -> int:
    prs = fetch_prs()
    if not prs:
        print("No PRs returned; leaving README untouched.", file=sys.stderr)
        return 0
    text = README.read_text(encoding="utf-8")
    if START not in text or END not in text:
        print("Markers not found in README.md", file=sys.stderr)
        return 1
    new_block = f"{START}\n{render(prs)}\n{END}"
    updated = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: new_block, text, flags=re.S)
    if updated != text:
        README.write_text(updated, encoding="utf-8")
        print(f"README updated: {len(prs)} PRs, {sum(p['state']=='merged' for p in prs)} merged.")
    else:
        print("README already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

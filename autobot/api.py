# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2015-2019 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Autobot API."""

import json
from datetime import datetime

import requests
import yaml

from autobot.config_loader import Config
from autobot.github import GitHubAPI


class BotAPI:
    """Bot's API."""

    def __init__(self, config: Config):
        """Bot initialization."""
        self.config = config
        self.gh_api = GitHubAPI(
            self.config["AUTOBOT_OWNER"],
            self.config["AUTOBOT_GH_TOKEN"],
            self.config.repositories,
        )

    @classmethod
    def md_report(cls, report):
        """Returns the report in markdown format."""
        lines = []
        for repo_report in report.values():
            lines.append(
                f"### [{repo_report['url'].split('/')[-1]}]({repo_report['url']})"
            )
            for action, targets in repo_report["actions"].items():
                lines.append(f"- **{action}**")
                for target in targets:
                    lines.append(
                        f"  - {target['url']}: {target['title']} "
                        f"({target['creation_date'].date()})"
                    )
            lines.append("\n\n")
        return "\n".join(lines)

    @classmethod
    def format_report(cls, report, format="json"):
        """Returns the report in the specified format."""
        if format == "json":
            return json.dumps(report, indent=4, default=str)
        elif format == "yaml":
            return yaml.dump(report)
        elif format == "markdown":
            return cls.md_report(report)
        return report

    def generate_report(self, maintainer=None):
        """Returns the report."""
        report = self.gh_api.report()
        if not maintainer:
            return report
        maintainer_report = {}
        for repo in report:
            repo_report = report[repo]
            if maintainer not in repo_report["maintainers"]:
                continue
            maintainer_report.update({repo: repo_report})
        return maintainer_report

    def send_report(self, maintainer: str, via: str):
        """Send the report to a maintainer."""
        report = self.generate_report(maintainer=maintainer)
        if via == "gitter":
            room = requests.post(
                "https://api.gitter.im/v1/rooms",
                headers={
                    "Authorization": f"Bearer {self.config['AUTOBOT_GITTER_TOKEN']}"
                },
                json={"uri": maintainer},
            )
            room_id = room.json()["id"]
            md_report = self.format_report(report, "markdown")
            if len(md_report) < 4000:
                text = md_report
            else:
                data = {"files": {maintainer + ".md": {"content": md_report}}}
                response = requests.post(
                    "https://api.github.com/gists",
                    headers={
                        "Authorization": f"Bearer {self.config['AUTOBOT_GH_TOKEN']}"
                    },
                    json=data,
                )
                text = response.json()["html_url"]
            res = requests.post(
                f"https://api.gitter.im/v1/rooms/{room_id}/chatMessages",
                json={"text": text},
                headers={
                    "Authorization": f"Bearer {self.config['AUTOBOT_GITTER_TOKEN']}"
                },
            )

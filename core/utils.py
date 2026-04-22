# ============================================================
# astrbot_plugin_location_guard
# Copyright (C) 2026 沈菀 (Akusative)
#
# This program is free software: you can redistribute it and/or
# modify it under the terms of the GNU Affero General Public
# License as published by the Free Software Foundation, either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program. If not, see
# <https://www.gnu.org/licenses/>.
# ============================================================

import os
import re
import json
from datetime import datetime
import logging

logger = logging.getLogger("location_guard")


def fill_prompt(
    template, distance='',
    weather='', temperature='',
    current_time=''
):
    if not current_time:
        current_time = datetime.now().strftime(
            "%Y-%m-%d %H:%M"
        )
    result = template.replace(
        "{{distance}}", str(distance)
    )
    result = result.replace(
        "{{weather}}", str(weather)
    )
    result = result.replace(
        "{{temperature}}", str(temperature)
    )
    result = result.replace(
        "{{current_time}}", str(current_time)
    )
    return result


def load_config_from_file():
    try:
        base = os.path.dirname(
            os.path.abspath(__file__)
        )
        candidates = [
            os.path.join(
                base, "..", "..", "..",
                "config",
                "astrbot_plugin_location_guard"
                "_config.json"
            ),
            os.path.join(
                base, "..", "..",
                "config",
                "astrbot_plugin_location_guard"
                "_config.json"
            ),
        ]
        for p in candidates:
            real = os.path.normpath(p)
            if os.path.exists(real):
                with open(
                    real, "r", encoding="utf-8"
                ) as f:
                    return json.load(f)
    except Exception as e:
        logger.error(
            "failed to load config file: %s", e
        )
    return {}


def find_db_path():
    base = os.path.dirname(
        os.path.abspath(__file__)
    )
    candidates = [
        os.path.join(
            base, "..", "..", "..",
            "data_v4.db"
        ),
        os.path.join(
            base, "..", "..",
            "data_v4.db"
        ),
        os.path.join(
            base, "..", "..", "..", "..",
            "data", "data_v4.db"
        ),
    ]
    for p in candidates:
        real = os.path.normpath(p)
        if os.path.exists(real):
            return real
    return None


def clean_utf8(text):
    if not text:
        return text
    return text.encode(
        'utf-8', errors='ignore'
    ).decode('utf-8')


def clean_markdown(text):
    if not text:
        return text
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'\*{1,3}', '', text)
    text = re.sub(r'>\s*', '', text)
    text = re.sub(r'`{1,3}', '', text)
    text = re.sub(r'---+', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(
        r'<details.*?</details>',
        '', text, flags=re.DOTALL
    )
    return text.strip()


def segment_text(text):
    if not text:
        return [text]
    segments = [
        s.strip() for s in
        text.split('\n')
        if s.strip()
    ]
    if not segments:
        return [text]
    return segments


def safe_get(config, file_config, key, default):
    val = config.get(key, None)
    if val is None or val == default:
        val = file_config.get(key, default)
    return val
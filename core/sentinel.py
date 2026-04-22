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

import logging

logger = logging.getLogger("location_guard")


def get_sentinel_provider(
    context, sentinel_provider_id
):
    if (sentinel_provider_id
            and len(sentinel_provider_id) > 0):
        prov = (
            context.get_provider_by_id(
                sentinel_provider_id
            )
        )
        if prov:
            return prov
    return context.get_using_provider()


async def check_if_reported(
    context, sentinel_provider_id,
    history_list
):
    if not history_list:
        return False
    try:
        lines = []
        for msg in history_list:
            role = msg.get('role', '')
            content = msg.get('content', '')
            if role == 'user':
                lines.append(
                    "user: " + str(content)
                )
            elif role == 'assistant':
                lines.append(
                    "assistant: "
                    + str(content)
                )
        history_text = "\n".join(lines)
        if not history_text.strip():
            return False
        sentinel = get_sentinel_provider(
            context, sentinel_provider_id
        )
        if sentinel is None:
            return False
        prompt = (
            "Analyze the following recent "
            "chat history and determine if "
            "the user mentioned they were "
            "going out, leaving home, or "
            "going somewhere. Only answer "
            "YES or NO, nothing else."
            "\n\nChat history:\n"
            + history_text[-8000:]
        )
        response = await (
            sentinel.text_chat(prompt)
        )
        if hasattr(
            response, 'completion_text'
        ):
            answer = (
                response.completion_text
                .strip().upper()
            )
        else:
            answer = (
                str(response)
                .strip().upper()
            )
        return "YES" in answer
    except Exception as e:
        logger.error(
            "sentinel check failed: %s", e
        )
        return False
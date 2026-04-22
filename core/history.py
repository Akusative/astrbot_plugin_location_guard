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

import json
import sqlite3
import logging

logger = logging.getLogger("location_guard")


def detect_umo(db_path, notify_qq, fallback_umo):
    if not db_path:
        return fallback_umo
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT user_id "
            "FROM conversations "
            "WHERE user_id LIKE ? "
            "ORDER BY updated_at "
            "DESC LIMIT 1",
            ("%FriendMessage:"
             + notify_qq + "%",)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            logger.info(
                "detected umo: %s", row[0]
            )
            return row[0]
    except Exception as e:
        logger.error(
            "detect umo failed: %s", e
        )
    return fallback_umo


async def get_recent_context(
    context, umo, context_rounds
):
    if context_rounds <= 0:
        return []
    try:
        conv_mgr = (
            context.conversation_manager
        )
        curr_cid = await (
            conv_mgr
            .get_curr_conversation_id(umo)
        )
        if curr_cid is None:
            return []
        conversation = await (
            conv_mgr.get_conversation(
                umo, curr_cid
            )
        )
        if conversation is None:
            return []
        if not conversation.history:
            return []
        if isinstance(
            conversation.history, str
        ):
            history = json.loads(
                conversation.history
            )
        else:
            history = conversation.history
        rounds = context_rounds * 2
        recent = history[-rounds:]
        return recent
    except Exception as e:
        logger.error(
            "failed to get context: %s", e
        )
        return []


def write_to_chat_history(
    db_path, notify_qq,
    location_msg, bot_reply
):
    if not db_path:
        logger.error(
            "db path not found, "
            "cannot write to chat history"
        )
        return
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT conversation_id, content "
            "FROM conversations "
            "WHERE user_id LIKE ? "
            "ORDER BY updated_at "
            "DESC LIMIT 1",
            ("%" + notify_qq + "%",)
        )
        row = cursor.fetchone()
        if row:
            cid = row[0]
            content = row[1]
            if content:
                history = json.loads(content)
            else:
                history = []
            history.append({
                "role": "user",
                "content": (
                    "[location update] "
                    + location_msg
                )
            })
            history.append({
                "role": "assistant",
                "content": bot_reply
            })
            new_content = json.dumps(
                history, ensure_ascii=False
            )
            conn.execute(
                "UPDATE conversations "
                "SET content=? "
                "WHERE conversation_id=?",
                (new_content, cid)
            )
            conn.commit()
            logger.info(
                "wrote location info to "
                "chat history, cid=%s", cid
            )
        else:
            logger.warning(
                "no conversation found "
                "for qq %s", notify_qq
            )
        conn.close()
    except Exception as e:
        logger.error(
            "failed to write to "
            "chat history: %s", e
        )
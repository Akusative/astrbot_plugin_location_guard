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

import time
import random
import requests
import logging
from .utils import (
    fill_prompt, clean_utf8,
    clean_markdown, segment_text
)

logger = logging.getLogger("location_guard")

DEFAULT_ALERT_PROMPT = (
    "用户刚刚离开了家，而且没有提前告诉你。"
    "离家大约{{distance}}米。"
    "现在的时间是{{current_time}}，"
    "外面天气是{{weather}}，"
    "温度{{temperature}}度。"
    "以有点不满但更多是担心的语气，"
    "询问用户去哪了，提醒注意安全，"
    "如果天气不好要自然地提到"
    "天气相关的叮嘱。"
    "不要使用任何markdown格式如#*>等符号，"
    "用纯文本回复，像发微信消息一样自然，"
    "回复控制在2到4句话"
)

DEFAULT_SAFE_PROMPT = (
    "用户刚刚出门了，之前在聊天中提过"
    "要出门，所以这是预期内的。"
    "离家大约{{distance}}米。"
    "现在的时间是{{current_time}}，"
    "外面天气是{{weather}}，"
    "温度{{temperature}}度。"
    "以温柔关心的语气提醒用户注意安全，"
    "如果天气不好要自然地提到"
    "天气相关的叮嘱，到了报个平安。"
    "不要使用任何markdown格式如#*>等符号，"
    "用纯文本回复，像发微信消息一样自然，"
    "回复控制在2到4句话"
)

DEFAULT_HOME_PROMPT = (
    "用户刚刚到家了。"
    "现在的时间是{{current_time}}，"
    "外面天气是{{weather}}，"
    "温度{{temperature}}度。"
    "以开心温暖的语气欢迎用户回家，"
    "可以问问在外面顺不顺利，"
    "或者说你准备了什么在等她。"
    "不要使用任何markdown格式如#*>等符号，"
    "用纯文本回复，像发微信消息一样自然，"
    "回复控制在2到4句话"
)


def get_prompt(
    prompt_type, distance='',
    weather='', temperature='',
    alert_prompt='',
    safe_travel_prompt='',
    home_prompt=''
):
    if prompt_type == 'alert':
        template = (
            alert_prompt
            if alert_prompt
            and len(alert_prompt.strip()) > 0
            else DEFAULT_ALERT_PROMPT
        )
    elif prompt_type == 'safe':
        template = (
            safe_travel_prompt
            if safe_travel_prompt
            and len(
                safe_travel_prompt.strip()
            ) > 0
            else DEFAULT_SAFE_PROMPT
        )
    elif prompt_type == 'home':
        template = (
            home_prompt
            if home_prompt
            and len(home_prompt.strip()) > 0
            else DEFAULT_HOME_PROMPT
        )
    else:
        template = DEFAULT_ALERT_PROMPT
    return fill_prompt(
        template, distance,
        weather, temperature
    )


async def get_persona_prompt(context):
    try:
        persona_mgr = context.persona_manager
        all_personas = await (
            persona_mgr.get_all_personas()
        )
        if all_personas:
            return (
                all_personas[0].system_prompt
            )
    except Exception as e:
        logger.warning(
            "get persona failed: %s", e
        )
    return ""


async def generate_msg(
    context, prompt_type,
    distance='', weather='',
    temperature='',
    fallback='查岗消息',
    alert_prompt='',
    safe_travel_prompt='',
    home_prompt='',
    guard_provider_id='',
    umo='',
    context_rounds=6
):
    try:
        from .history import get_recent_context
        base_prompt = get_prompt(
            prompt_type, distance,
            weather, temperature,
            alert_prompt,
            safe_travel_prompt,
            home_prompt
        )
        persona = (
            await get_persona_prompt(context)
        )
        context_list = (
            await get_recent_context(
                context, umo, context_rounds
            )
        )
        if (guard_provider_id
                and len(guard_provider_id) > 0):
            guard_prov = (
                context.get_provider_by_id(
                    guard_provider_id
                )
            )
            if guard_prov is None:
                logger.error(
                    "guard provider not found"
                )
                return fallback
            response = await (
                guard_prov.text_chat(
                    prompt=base_prompt,
                    contexts=context_list,
                    system_prompt=(
                        persona
                        if persona
                        else ""
                    )
                )
            )
        else:
            provider_id = await (
                context
                .get_current_chat_provider_id(
                    umo
                )
            )
            response = await (
                context.llm_generate(
                    chat_provider_id=(
                        provider_id
                    ),
                    prompt=base_prompt,
                    contexts=context_list,
                    system_prompt=(
                        persona
                        if persona
                        else ""
                    )
                )
            )
        if (response
                and response.completion_text):
            msg = (
                response.completion_text
                .strip()
            )
            if msg and len(msg) > 0:
                return clean_markdown(msg)
        return fallback
    except Exception as e:
        import traceback
        logger.error(
            "AI msg generation failed: "
            "%s\n%s",
            e,
            traceback.format_exc()
        )
        return fallback


def send_msg(
    msg, notify_qq, onebot_url,
    enable_segment=False
):
    msg = clean_utf8(msg)
    if enable_segment:
        segments = segment_text(msg)
        for i, seg in enumerate(segments):
            payload = {
                "user_id": notify_qq,
                "message": [{
                    "type": "text",
                    "data": {"text": seg}
                }]
            }
            requests.post(
                onebot_url
                + "/send_private_msg",
                json=payload, timeout=10
            )
            if i < len(segments) - 1:
                time.sleep(
                    random.uniform(1.0, 2.5)
                )
    else:
        payload = {
            "user_id": notify_qq,
            "message": [{
                "type": "text",
                "data": {"text": msg}
            }]
        }
        requests.post(
            onebot_url
            + "/send_private_msg",
            json=payload, timeout=10
        )
    return msg
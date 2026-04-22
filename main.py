# ============================================================
# astrbot_plugin_location_guard
# 位置查岗插件 - 通过WiFi状态变化自动查岗
#
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

import math
import threading
import asyncio
import logging
from astrbot.api import AstrBotConfig
from astrbot.api.event import (
    filter, AstrMessageEvent
)
from astrbot.api.star import (
    Context, Star, register
)
from .core.utils import (
    load_config_from_file,
    find_db_path, safe_get
)
from .core.http_server import start_http_server
from .core.history import (
    detect_umo, get_recent_context,
    write_to_chat_history
)
from .core.sentinel import check_if_reported
from .core.message import (
    generate_msg, send_msg,
    get_persona_prompt
)

logger = logging.getLogger("location_guard")


@register(
    "location_guard", "wanwan",
    "location guard plugin", "3.0.0",
    "GPS location guard with Android/iOS "
    "support and AI-powered notifications"
)
class LocationGuard(Star):
    def __init__(
        self, context: Context,
        config: AstrBotConfig
    ):
        super().__init__(context)
        self.config = config
        file_config = load_config_from_file()
        self.home_lat = safe_get(
            config, file_config, "home_lat", 0.0
        )
        self.home_lng = safe_get(
            config, file_config, "home_lng", 0.0
        )
        self.alert_distance = safe_get(
            config, file_config,
            "alert_distance", 500
        )
        self.http_port = safe_get(
            config, file_config, "http_port", 8090
        )
        self.notify_qq = safe_get(
            config, file_config, "notify_qq", ""
        )
        self.bot_qq = safe_get(
            config, file_config, "bot_qq", ""
        )
        self.bot_platform = safe_get(
            config, file_config,
            "bot_platform", "default"
        )
        self.onebot_url = safe_get(
            config, file_config, "onebot_url",
            "http://127.0.0.1:3000"
        )
        self.sentinel_provider_id = safe_get(
            config, file_config,
            "sentinel_provider", ""
        )
        self.guard_provider_id = safe_get(
            config, file_config,
            "guard_provider", ""
        )
        self.alert_prompt = safe_get(
            config, file_config,
            "alert_prompt", ""
        )
        self.safe_travel_prompt = safe_get(
            config, file_config,
            "safe_travel_prompt", ""
        )
        self.home_prompt = safe_get(
            config, file_config,
            "home_prompt", ""
        )
        raw_segment = safe_get(
            config, file_config,
            "enable_segment", False
        )
        if isinstance(raw_segment, str):
            self.enable_segment = (
                raw_segment.lower() == 'true'
            )
        else:
            self.enable_segment = bool(
                raw_segment
            )
        self.context_rounds = safe_get(
            config, file_config,
            "context_rounds", 6
        )
        self.device_filter = safe_get(
            config, file_config,
            "device_filter", "all"
        )
        self.db_path = find_db_path()
        self.last_alert = None
        self.is_away = False  # 离家状态标记
        self.first_report = True  # 首次上报标记
        fallback_umo = (
            str(self.bot_platform)
            + ":FriendMessage:"
            + str(self.notify_qq)
        )
        self.umo = detect_umo(
            self.db_path,
            self.notify_qq,
            fallback_umo
        )
        logger.info(
            "location guard config: "
            "lat=%s lng=%s dist=%s qq=%s "
            "segment=%s rounds=%s db=%s "
            "umo=%s",
            self.home_lat, self.home_lng,
            self.alert_distance, self.notify_qq,
            self.enable_segment,
            self.context_rounds, self.db_path,
            self.umo
        )
        self.main_loop = asyncio.get_event_loop()
        t = threading.Thread(
            target=start_http_server,
            args=(self.http_port, self),
            daemon=True
        )
        t.start()
        logger.info(
            "location guard HTTP server "
            "started on port %s",
            self.http_port
        )

    def calc_distance(
        self, lat1, lng1, lat2, lng2
    ):
        R = 6371000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lng2 - lng1)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1)
            * math.cos(phi2)
            * math.sin(dlambda / 2) ** 2
        )
        c = 2 * math.atan2(
            math.sqrt(a), math.sqrt(1 - a)
        )
        return R * c

    async def send_alert(
        self, distance, lat, lng,
        weather='', temperature=''
    ):
        try:
            context_list = (
                await get_recent_context(
                    self.context, self.umo,
                    self.context_rounds
                )
            )
            reported = await check_if_reported(
                self.context,
                self.sentinel_provider_id,
                context_list
            )
            if reported:
                alert_msg = await generate_msg(
                    self.context,
                    'safe', distance,
                    weather, temperature,
                    "出门了? 注意安全, 早点回来",
                    self.alert_prompt,
                    self.safe_travel_prompt,
                    self.home_prompt,
                    self.guard_provider_id,
                    self.umo,
                    self.context_rounds
                )
            else:
                alert_msg = await generate_msg(
                    self.context,
                    'alert', distance,
                    weather, temperature,
                    "离家了, 去哪了也不说一声?",
                    self.alert_prompt,
                    self.safe_travel_prompt,
                    self.home_prompt,
                    self.guard_provider_id,
                    self.umo,
                    self.context_rounds
                )
            alert_msg = send_msg(
                alert_msg, self.notify_qq,
                self.onebot_url,
                self.enable_segment
            )
            logger.info(
                "alert sent: %s",
                alert_msg[:50]
            )
            write_to_chat_history(
                self.db_path, self.notify_qq,
                "离家了", alert_msg
            )
        except Exception as e:
            logger.error(
                "failed to send alert: %s", e
            )

    async def send_safe_msg(self, distance):
        try:
            msg = (
                "在家附近, 距离"
                + str(int(distance))
                + "米, 很乖"
            )
            msg = send_msg(
                msg, self.notify_qq,
                self.onebot_url,
                self.enable_segment
            )
            loc_msg = (
                "在家附近, 距离"
                + str(int(distance)) + "米"
            )
            write_to_chat_history(
                self.db_path, self.notify_qq,
                loc_msg, msg
            )
        except Exception as e:
            logger.error(
                "failed to send safe msg: %s", e
            )

    async def send_home_msg(
        self, weather='', temperature=''
    ):
        try:
            msg = await generate_msg(
                self.context,
                'home', '',
                weather, temperature,
                "回来了? 路上顺利吗",
                self.alert_prompt,
                self.safe_travel_prompt,
                self.home_prompt,
                self.guard_provider_id,
                self.umo,
                self.context_rounds
            )
            msg = send_msg(
                msg, self.notify_qq,
                self.onebot_url,
                self.enable_segment
            )
            write_to_chat_history(
                self.db_path, self.notify_qq,
                "到家了", msg
            )
            self.last_alert = None
        except Exception as e:
            logger.error(
                "failed to send home msg: %s", e
            )

    @filter.command("location_report")
    async def report_location(
        self, event: AstrMessageEvent,
        lat: float, lng: float
    ):
        distance = self.calc_distance(
            lat, lng,
            self.home_lat, self.home_lng
        )
        if distance > self.alert_distance:
            yield event.plain_result(
                "离家" + str(int(distance))
                + "米了, 没有报备就偷偷跑出去了?"
            )
        else:
            yield event.plain_result(
                "在家附近, 距离"
                + str(int(distance))
                + "米, 乖乖的"
            )

    @filter.command("check_status")
    async def check_status(
        self, event: AstrMessageEvent
    ):
        if self.last_alert:
            yield event.plain_result(
                "最近一次警报: "
                + self.last_alert
            )
        else:
            yield event.plain_result(
                "暂时没有离家记录, 很乖"
            )

    @filter.command("get_umo")
    async def get_umo(
        self, event: AstrMessageEvent
    ):
        umo = event.unified_msg_origin
        yield event.plain_result(
            "your umo: " + str(umo)
        )

    @filter.command("test_config")
    async def test_config(
        self, event: AstrMessageEvent
    ):
        msg = (
            "home_lat: "
            + str(self.home_lat)
            + "\nhome_lng: "
            + str(self.home_lng)
            + "\nalert_distance: "
            + str(self.alert_distance)
            + "\nhttp_port: "
            + str(self.http_port)
            + "\nnotify_qq: "
            + str(self.notify_qq)
            + "\nbot_qq: "
            + str(self.bot_qq)
            + "\nonebot_url: "
            + str(self.onebot_url)
            + "\nenable_segment: "
            + str(self.enable_segment)
            + "\ncontext_rounds: "
            + str(self.context_rounds)
            + "\ndb_path: "
            + str(self.db_path)
            + "\numo: "
            + str(self.umo)
        )
        yield event.plain_result(msg)

    @filter.command("test_persona")
    async def test_persona(
        self, event: AstrMessageEvent
    ):
        try:
            persona_mgr = (
                self.context.persona_manager
            )
            all_personas = await (
                persona_mgr.get_all_personas()
            )
            persona_list = []
            for p in all_personas:
                persona_list.append(
                    p.persona_id + ": "
                    + str(len(p.system_prompt))
                    + " chars"
                )
            if persona_list:
                msg = (
                    "umo: " + self.umo
                    + "\n\nall personas:\n"
                    + "\n".join(persona_list)
                )
            else:
                msg = (
                    "umo: " + self.umo
                    + "\n\nno personas in db"
                )
        except Exception as e:
            msg = "error: " + str(e)
        yield event.plain_result(msg)

    @filter.command("test_write")
    async def test_write(
        self, event: AstrMessageEvent
    ):
        try:
            write_to_chat_history(
                self.db_path, self.notify_qq,
                "测试写入", "这是一条测试消息"
            )
            yield event.plain_result(
                "写入测试完成，检查数据库"
            )
        except Exception as e:
            yield event.plain_result(
                "写入失败: " + str(e)
            )
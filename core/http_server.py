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
import asyncio
from http.server import (
    HTTPServer, BaseHTTPRequestHandler
)
import logging

logger = logging.getLogger("location_guard")


class LocationHandler(BaseHTTPRequestHandler):
    plugin = None

    def do_POST(self):
        if self.path in ('/location', '/api/location/report'):
            content_length = int(
                self.headers['Content-Length']
            )
            post_data = self.rfile.read(
                content_length
            )
            try:
                data = json.loads(post_data)
                lat = float(data.get('lat', 0))
                lng = float(data.get('lng', 0))
                event = data.get('event', '')
                weather = data.get('weather', '')
                temperature = data.get(
                    'temperature', ''
                )
                device = data.get('device', '')
                distance = (
                    self.plugin.calc_distance(
                        lat, lng,
                        self.plugin.home_lat,
                        self.plugin.home_lng
                    )
                )

                # 设备过滤
                dev_filter = (
                    self.plugin.device_filter
                )
                if (dev_filter
                        and dev_filter != 'all'
                        and device
                        and device != dev_filter):
                    resp = {
                        "status": "filtered",
                        "device": device,
                        "filter": dev_filter
                    }
                    logger.info(
                        "device filtered: %s "
                        "(accept: %s)",
                        device, dev_filter
                    )
                    self.send_response(200)
                    self.send_header(
                        'Content-Type',
                        'application/json'
                    )
                    self.end_headers()
                    self.wfile.write(
                        json.dumps(resp).encode()
                    )
                    return
                is_far = (
                    distance
                    > self.plugin.alert_distance
                )

                # 离家判定: 之前在家, 现在超出范围
                if (not self.plugin.is_away
                        and (event == 'left_home'
                             or is_far)):
                    self.plugin.is_away = True
                    self.plugin.last_alert = (
                        "离家, 坐标: "
                        + str(lat)
                        + ", " + str(lng)
                    )
                    asyncio.run_coroutine_threadsafe(
                        self.plugin.send_alert(
                            distance, lat, lng,
                            weather, temperature
                        ),
                        self.plugin.main_loop
                    )
                    resp = {
                        "status": "alert",
                        "distance": int(distance),
                        "recv_lat": lat,
                        "recv_lng": lng,
                        "event": event
                    }

                # 到家判定: 之前离家, 现在回到范围内
                elif (self.plugin.is_away
                        and (event == 'arrived_home'
                             or not is_far)):
                    self.plugin.is_away = False
                    self.plugin.last_alert = None
                    asyncio.run_coroutine_threadsafe(
                        self.plugin.send_home_msg(
                            weather, temperature
                        ),
                        self.plugin.main_loop
                    )
                    resp = {
                        "status": "home",
                        "distance": int(distance),
                        "event": "arrived_home"
                    }

                # 持续在家或持续离家, 不发消息
                else:
                    status = (
                        "away" if self.plugin.is_away
                        else "safe"
                    )
                    # 首次上报且在家, 夸一句
                    if (self.plugin.first_report
                            and not self.plugin.is_away):
                        self.plugin.first_report = False
                        asyncio.run_coroutine_threadsafe(
                            self.plugin.send_home_msg(
                                weather, temperature
                            ),
                            self.plugin.main_loop
                        )
                        resp = {
                            "status": "first_safe",
                            "distance": int(distance)
                        }
                        logger.info(
                            "first report: at home, "
                            "distance=%s",
                            int(distance)
                        )
                    else:
                        self.plugin.first_report = False
                        resp = {
                            "status": status,
                            "distance": int(distance),
                            "is_away":
                                self.plugin.is_away
                        }
                        logger.info(
                            "%s: distance=%s, "
                            "no message sent",
                            status, int(distance)
                        )

                self.send_response(200)
                self.send_header(
                    'Content-Type',
                    'application/json'
                )
                self.end_headers()
                self.wfile.write(
                    json.dumps(resp).encode()
                )
            except Exception as e:
                self.send_response(400)
                self.send_header(
                    'Content-Type',
                    'application/json'
                )
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {"error": str(e)}
                    ).encode()
                )
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        logger.info("HTTP request: %s", args)


def start_http_server(port, plugin):
    LocationHandler.plugin = plugin
    server = HTTPServer(
        ('0.0.0.0', port),
        LocationHandler
    )
    server.serve_forever()

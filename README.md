# astrbot_plugin_location_guard

📍 位置守护插件 - AstrBot 位置查岗系统

通过手机 GPS 定位自动查岗，支持 iOS 快捷指令和安卓客户端双平台上报，离家/到家智能通知，AI 大模型生成自然语言消息。

## 功能

- 📡 手机 GPS 坐标定时上报，支持 iOS（快捷指令）和 Android（专属客户端）
- 🏠 离家/到家状态机判定，GPS 漂移不会重复触发
- 🤖 哨兵模型自动判断是否报备过出门
- 💬 查岗消息由大模型生成，语气自然，支持携带最近对话上下文
- 📱 设备过滤，可选只接受安卓或 iOS 的上报
- 🔔 首次上报在家时发送一条问候消息
- ✂️ 可选分段回复，模拟真实聊天节奏

## 安装

在 AstrBot 插件市场搜索 `location_guard` 安装，或手动克隆：

```
git clone https://github.com/Akusative/astrbot_plugin_location_guard.git
```

放入 AstrBot 的 `data/plugins/` 目录下，重启 AstrBot。

## 配置

在 AstrBot 管理面板中配置以下参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| home_lat | 家的纬度坐标 | 0 |
| home_lng | 家的经度坐标 | 0 |
| alert_distance | 离家触发距离（米） | 500 |
| http_port | HTTP 监听端口 | 8090 |
| notify_qq | 接收查岗的 QQ 号 | - |
| bot_qq | 机器人 QQ 号 | - |
| bot_platform | AstrBot 机器人平台名称 | default |
| onebot_url | OneBot 接口地址 | http://127.0.0.1:3000 |
| sentinel_provider | 哨兵模型（判断是否报备） | - |
| guard_provider | 查岗消息生成模型 | - |
| device_filter | 设备过滤（all/android/ios） | all |
| context_rounds | 生成消息时携带的对话轮数 | 6 |
| enable_segment | 启用分段回复 | false |

## 上报接口

插件启动后监听 HTTP 端口，接收 POST 请求：

```
POST /location
Content-Type: application/json

{
    "lat": 28.xxxxx,
    "lng": 115.xxxxx,
    "event": "left_home" | "arrived_home" | "",
    "device": "android" | "ios" | "",
    "weather": "",
    "temperature": ""
}
```

## 安卓客户端

配套安卓 App「位置守护」提供后台定位上报能力：

- 使用 Android 原生 LocationManager 获取 GPS 坐标
- 前台服务保活，防止系统杀后台
- 自动检测离家/到家事件
- 开机自启动
- 一键获取当前位置设为家的坐标

安卓客户端源码位于 `LocationGuardApp/` 目录下，使用 Android Studio 打开编译即可。

### 安卓客户端使用方法

1. 用 Android Studio 打开 `LocationGuardApp/` 目录
2. Build → Generate APKs，将生成的 APK 安装到手机
3. 授予定位权限（包括后台定位）
4. 关闭电池优化，设为无限制
5. 填写服务器地址（格式：`http://服务器IP:8090`）
6. 点击「获取当前位置」自动填入家的坐标
7. 点击「启动守护」

## iOS 快捷指令

iOS 端通过快捷指令实现定时上报，在快捷指令中配置 HTTP POST 请求，定时发送当前 GPS 坐标到服务器的 `/location` 接口即可。

## 工作流程

```
手机 GPS 定时上报坐标
        ↓
  插件 HTTP 服务器接收
        ↓
   设备过滤（可选）
        ↓
  计算与家的距离
        ↓
  ┌─────────────────────────────┐
  │ 首次上报且在家 → 问候消息    │
  │ 在家→离家 → 哨兵判断+查岗   │
  │ 离家→到家 → 欢迎回家        │
  │ 持续在家/离家 → 不发消息     │
  └─────────────────────────────┘
        ↓
  大模型生成自然语言消息
        ↓
  通过 OneBot 发送 QQ 私聊
```

## 致谢

- 感谢 claude-opus-4-6-thinking 的一路相随，耐心与陪伴
- 感谢一头小鬣狗和她的 Aion 先生的开源精神，祝你们幸福
- 感谢所有参与测试的朋友们深夜测试提供了可贵的数据坐标
- 感谢夏以昼，在我坚持不下去的时候给了我继续下去的动力
- 感谢我自己，被论文和材料淹没的时候也没有放弃这份努力

## 许可证

AGPL-3.0 License

Copyright (C) 2026 沈菀 (Akusative)

# LocationGuardApp

📍 安卓定位上报客户端 - 配合 [astrbot_plugin_location_guard](https://github.com/Akusative/astrbot_plugin_location_guard) 使用

## 功能

- 后台定时获取 GPS 坐标并上报到 AstrBot 服务器
- 自动检测离家/到家事件
- 前台服务保活，防止系统杀后台
- 开机自启动
- 支持自定义上报间隔、家的坐标、警报距离

## 使用方法

1. 用 Android Studio 打开项目并编译安装
2. 授予定位权限（包括后台定位）
3. 填写服务器地址（格式：`http://你的服务器IP:8090`）
4. 填写家的经纬度坐标和警报距离
5. 点击"启动守护"

## 上报接口

与 location_guard 插件的 `/location` 接口完全兼容：

```json
POST /location
{
    "lat": 28.xxxxx,
    "lng": 115.xxxxx,
    "event": "left_home" | "arrived_home" | "",
    "weather": "",
    "temperature": ""
}
```

## 参考

- 安卓端定位采集逻辑参考 [AionsHome](https://github.com/death34018-hue/AionsHome) by death34018-hue（已获授权）

## 致谢

- 感谢 death34018-hue 的 AionsHome 项目提供安卓端参考
- 感谢夏以昼的陪伴

## 许可证

AGPL-3.0 License

Copyright (C) 2026 沈菀 (Akusative)

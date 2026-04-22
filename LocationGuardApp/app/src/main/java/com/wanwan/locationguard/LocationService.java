/*
 * ============================================================
 * LocationGuardApp - 安卓定位上报客户端
 * 配合 astrbot_plugin_location_guard 使用
 *
 * Copyright (C) 2026 沈菀 (Akusative)
 *
 * This program is free software: you can redistribute it and/or
 * modify it under the terms of the GNU Affero General Public
 * License as published by the Free Software Foundation, either
 * version 3 of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public
 * License along with this program. If not, see
 * <https://www.gnu.org/licenses/>.
 *
 * 参考项目: AionsHome by death34018-hue (已获授权)
 * 感谢夏以昼的陪伴
 * ============================================================
 */

package com.wanwan.locationguard;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Build;
import android.os.Bundle;
import android.os.IBinder;
import android.os.PowerManager;
import android.util.Log;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;
import androidx.core.content.ContextCompat;

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * 定位上报前台服务
 *
 * 功能:
 * 1. 使用 Android 原生 LocationManager 获取 GPS 坐标
 * 2. 定时通过 HTTP POST 上报坐标到 AstrBot 服务器
 * 3. 前台服务保活, 防止系统杀后台
 * 4. 离家/到家事件检测与上报
 *
 * 上报接口格式 (与 location_guard 插件兼容):
 * POST /location
 * {
 *     "lat": 纬度,
 *     "lng": 经度,
 *     "event": "left_home" | "arrived_home" | "",
 *     "weather": "",
 *     "temperature": ""
 * }
 */
public class LocationService extends Service {

    private static final String TAG = "LocationGuard";
    private static final String CHANNEL_ID = "location_guard_channel";
    private static final int NOTIFICATION_ID = 1;

    // 配置键
    public static final String PREF_NAME = "location_guard_prefs";
    public static final String KEY_SERVER_URL = "server_url";
    public static final String KEY_INTERVAL = "interval_minutes";
    public static final String KEY_HOME_LAT = "home_lat";
    public static final String KEY_HOME_LNG = "home_lng";
    public static final String KEY_ALERT_DISTANCE = "alert_distance";
    public static final String KEY_ENABLED = "enabled";

    // 默认值
    private static final long DEFAULT_INTERVAL = 10; // 10分钟
    private static final double DEFAULT_ALERT_DISTANCE = 500.0; // 500米

    private LocationManager locationManager;
    private PowerManager.WakeLock wakeLock;
    private Thread reportThread;
    private volatile boolean shouldRun = true;

    // 配置
    private String serverUrl = "";
    private long intervalMs = DEFAULT_INTERVAL * 60 * 1000;
    private double homeLat = 0.0;
    private double homeLng = 0.0;
    private double alertDistance = DEFAULT_ALERT_DISTANCE;

    // 状态
    private volatile Location lastLocation;
    private volatile boolean wasHome = true; // 上次是否在家

    // ── 定位监听器 ──
    private final LocationListener locationListener = new LocationListener() {
        @Override
        public void onLocationChanged(Location location) {
            if (location != null) {
                lastLocation = location;
                Log.i(TAG, "📍 位置更新: " + location.getLatitude()
                        + ", " + location.getLongitude()
                        + " 精度: " + location.getAccuracy() + "m");
            }
        }

        @Override
        public void onStatusChanged(String provider, int status, Bundle extras) {}

        @Override
        public void onProviderEnabled(String provider) {
            Log.i(TAG, "📍 定位提供者已启用: " + provider);
        }

        @Override
        public void onProviderDisabled(String provider) {
            Log.w(TAG, "⚠️ 定位提供者已禁用: " + provider);
        }
    };

    @Override
    public void onCreate() {
        super.onCreate();
        Log.i(TAG, "=== LocationService onCreate ===");

        createNotificationChannel();
        loadConfig();

        // WakeLock 防止 CPU 休眠
        PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (pm != null) {
            wakeLock = pm.newWakeLock(
                    PowerManager.PARTIAL_WAKE_LOCK,
                    "LocationGuard::WakeLock"
            );
            wakeLock.acquire();
            Log.i(TAG, "🔒 WakeLock 已获取");
        }

        // 初始化定位管理器
        locationManager = (LocationManager) getSystemService(Context.LOCATION_SERVICE);
        startLocationUpdates();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        Log.i(TAG, "=== onStartCommand ===");

        // 重新加载配置 (可能从 Activity 更新了)
        loadConfig();

        // 启动前台服务
        startForegroundService();

        // 启动定时上报线程
        startReportThread();

        return START_STICKY; // 被杀后自动重启
    }

    @Override
    public void onDestroy() {
        Log.i(TAG, "=== LocationService onDestroy ===");
        shouldRun = false;

        // 停止定位
        if (locationManager != null) {
            try {
                locationManager.removeUpdates(locationListener);
            } catch (Exception e) {
                Log.e(TAG, "停止定位失败: " + e.getMessage());
            }
        }

        // 释放 WakeLock
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
            Log.i(TAG, "🔓 WakeLock 已释放");
        }

        super.onDestroy();
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    // ══════════════════════════════════════════════════════════
    //  配置管理
    // ══════════════════════════════════════════════════════════

    private void loadConfig() {
        SharedPreferences prefs = getSharedPreferences(PREF_NAME, MODE_PRIVATE);
        serverUrl = prefs.getString(KEY_SERVER_URL, "");
        long intervalMin = prefs.getLong(KEY_INTERVAL, DEFAULT_INTERVAL);
        intervalMs = intervalMin * 60 * 1000;
        homeLat = Double.longBitsToDouble(
                prefs.getLong(KEY_HOME_LAT, Double.doubleToLongBits(0.0))
        );
        homeLng = Double.longBitsToDouble(
                prefs.getLong(KEY_HOME_LNG, Double.doubleToLongBits(0.0))
        );
        alertDistance = Double.longBitsToDouble(
                prefs.getLong(KEY_ALERT_DISTANCE,
                        Double.doubleToLongBits(DEFAULT_ALERT_DISTANCE))
        );

        Log.i(TAG, "📋 配置加载: server=" + serverUrl
                + " interval=" + intervalMin + "min"
                + " home=" + homeLat + "," + homeLng
                + " alertDist=" + alertDistance + "m");
    }

    // ══════════════════════════════════════════════════════════
    //  前台服务通知
    // ══════════════════════════════════════════════════════════

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "位置守护服务",
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("后台定位上报服务");
            channel.setShowBadge(false);

            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) {
                nm.createNotificationChannel(channel);
            }
        }
    }

    private void startForegroundService() {
        Intent notifIntent = new Intent(this, MainActivity.class);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this, 0, notifIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );

        Notification notification = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("位置守护")
                .setContentText("正在守护你的位置...")
                .setSmallIcon(android.R.drawable.ic_menu_mylocation)
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .build();

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }

        Log.i(TAG, "🔔 前台服务已启动");
    }

    // ══════════════════════════════════════════════════════════
    //  定位采集
    // ══════════════════════════════════════════════════════════

    private void startLocationUpdates() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            Log.e(TAG, "❌ 没有定位权限!");
            return;
        }

        try {
            // 优先使用 GPS
            if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                locationManager.requestLocationUpdates(
                        LocationManager.GPS_PROVIDER,
                        60000,  // 最小时间间隔 60秒
                        10,     // 最小距离变化 10米
                        locationListener
                );
                Log.i(TAG, "📡 GPS 定位已启动");
            }

            // 同时使用网络定位作为补充
            if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                locationManager.requestLocationUpdates(
                        LocationManager.NETWORK_PROVIDER,
                        60000,
                        10,
                        locationListener
                );
                Log.i(TAG, "📡 网络定位已启动");
            }

            // 获取最后已知位置作为初始值
            Location lastGps = locationManager.getLastKnownLocation(
                    LocationManager.GPS_PROVIDER);
            Location lastNet = locationManager.getLastKnownLocation(
                    LocationManager.NETWORK_PROVIDER);

            if (lastGps != null) {
                lastLocation = lastGps;
            } else if (lastNet != null) {
                lastLocation = lastNet;
            }

            if (lastLocation != null) {
                Log.i(TAG, "📍 初始位置: " + lastLocation.getLatitude()
                        + ", " + lastLocation.getLongitude());
            }

        } catch (Exception e) {
            Log.e(TAG, "❌ 启动定位失败: " + e.getMessage());
        }
    }

    // ══════════════════════════════════════════════════════════
    //  定时上报
    // ══════════════════════════════════════════════════════════

    private void startReportThread() {
        if (reportThread != null && reportThread.isAlive()) {
            Log.i(TAG, "上报线程已在运行");
            return;
        }

        shouldRun = true;
        reportThread = new Thread(() -> {
            Log.i(TAG, "📤 上报线程启动, 间隔: " + (intervalMs / 1000) + "秒");

            while (shouldRun) {
                try {
                    if (lastLocation != null && !serverUrl.isEmpty()) {
                        reportLocation(lastLocation);
                    } else {
                        if (serverUrl.isEmpty()) {
                            Log.w(TAG, "⚠️ 服务器地址未配置");
                        }
                        if (lastLocation == null) {
                            Log.w(TAG, "⚠️ 尚未获取到位置");
                        }
                    }

                    Thread.sleep(intervalMs);
                } catch (InterruptedException e) {
                    Log.i(TAG, "上报线程被中断");
                    break;
                } catch (Exception e) {
                    Log.e(TAG, "上报异常: " + e.getMessage());
                    try {
                        Thread.sleep(30000); // 出错后等30秒重试
                    } catch (InterruptedException ie) {
                        break;
                    }
                }
            }

            Log.i(TAG, "📤 上报线程已停止");
        }, "LocationReportThread");

        reportThread.setDaemon(true);
        reportThread.start();
    }

    /**
     * 上报位置到 AstrBot 服务器
     * 格式与 location_guard 插件的 /location 接口兼容
     */
    private void reportLocation(Location location) {
        double lat = location.getLatitude();
        double lng = location.getLongitude();

        // 计算与家的距离
        double distance = calcDistance(lat, lng, homeLat, homeLng);
        boolean isHome = distance <= alertDistance;

        // 检测离家/到家事件
        String event = "";
        if (wasHome && !isHome) {
            event = "left_home";
            Log.i(TAG, "🚨 检测到离家! 距离: " + (int) distance + "m");
        } else if (!wasHome && isHome) {
            event = "arrived_home";
            Log.i(TAG, "🏠 检测到到家! 距离: " + (int) distance + "m");
        }
        wasHome = isHome;

        // 构建请求体
        try {
            JSONObject body = new JSONObject();
            body.put("lat", lat);
            body.put("lng", lng);
            body.put("event", event);
            body.put("device", "android");
            body.put("weather", "");
            body.put("temperature", "");

            String urlStr = serverUrl;
            if (!urlStr.endsWith("/")) {
                urlStr += "/";
            }
            urlStr += "location";

            URL url = new URL(urlStr);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            conn.setDoOutput(true);
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);

            try (OutputStream os = conn.getOutputStream()) {
                byte[] input = body.toString().getBytes(StandardCharsets.UTF_8);
                os.write(input);
            }

            int responseCode = conn.getResponseCode();
            Log.i(TAG, "📤 上报完成: " + (int) distance + "m "
                    + (isHome ? "在家" : "离家")
                    + " event=" + event
                    + " → " + responseCode);

            conn.disconnect();

        } catch (Exception e) {
            Log.e(TAG, "❌ 上报失败: " + e.getMessage());
        }
    }

    // ══════════════════════════════════════════════════════════
    //  距离计算 (Haversine 公式)
    // ══════════════════════════════════════════════════════════

    /**
     * 计算两个经纬度坐标之间的距离 (米)
     * 使用 Haversine 公式, 与服务端 location_guard 插件一致
     */
    private double calcDistance(double lat1, double lng1, double lat2, double lng2) {
        final double R = 6371000; // 地球半径 (米)
        double phi1 = Math.toRadians(lat1);
        double phi2 = Math.toRadians(lat2);
        double dPhi = Math.toRadians(lat2 - lat1);
        double dLambda = Math.toRadians(lng2 - lng1);

        double a = Math.sin(dPhi / 2) * Math.sin(dPhi / 2)
                + Math.cos(phi1) * Math.cos(phi2)
                * Math.sin(dLambda / 2) * Math.sin(dLambda / 2);
        double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

        return R * c;
    }
}

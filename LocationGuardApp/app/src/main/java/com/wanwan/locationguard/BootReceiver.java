/*
 * ============================================================
 * LocationGuardApp - 开机自启广播接收器
 * Copyright (C) 2026 沈菀 (Akusative)
 * AGPL-3.0 License
 * ============================================================
 */

package com.wanwan.locationguard;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.util.Log;

/**
 * 开机自启动接收器
 * 设备重启后自动恢复定位上报服务
 */
public class BootReceiver extends BroadcastReceiver {

    private static final String TAG = "LocationGuard";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            SharedPreferences prefs = context.getSharedPreferences(
                    LocationService.PREF_NAME, Context.MODE_PRIVATE);
            boolean enabled = prefs.getBoolean(LocationService.KEY_ENABLED, false);

            if (enabled) {
                Log.i(TAG, "📱 开机自启: 恢复定位上报服务");
                Intent serviceIntent = new Intent(context, LocationService.class);
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    context.startForegroundService(serviceIntent);
                } else {
                    context.startService(serviceIntent);
                }
            } else {
                Log.i(TAG, "📱 开机自启: 服务未启用, 跳过");
            }
        }
    }
}

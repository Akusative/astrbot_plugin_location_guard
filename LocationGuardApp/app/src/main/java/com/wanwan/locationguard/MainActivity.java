/*
 * ============================================================
 * LocationGuardApp - 安卓定位上报客户端
 * Copyright (C) 2026 沈菀 (Akusative)
 *
 * AGPL-3.0 License - see LICENSE file
 *
 * 参考项目: AionsHome by death34018-hue (已获授权)
 * 感谢夏以昼的陪伴
 * ============================================================
 */

package com.wanwan.locationguard;

import android.Manifest;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.PowerManager;
import android.provider.Settings;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import android.app.Activity;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;

public class MainActivity extends Activity {

    private static final String TAG = "LocationGuard";
    private static final int PERMISSION_REQUEST_CODE = 1001;

    private LocationManager locationManager;

    private EditText etServerUrl;
    private EditText etInterval;
    private EditText etHomeLat;
    private EditText etHomeLng;
    private EditText etAlertDistance;
    private Button btnStart;
    private Button btnStop;
    private TextView tvStatus;

    private boolean serviceRunning = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        initViews();
        loadSavedConfig();
        checkPermissions();
        requestBatteryOptimization();
    }

    private void initViews() {
        etServerUrl = findViewById(R.id.et_server_url);
        etInterval = findViewById(R.id.et_interval);
        etHomeLat = findViewById(R.id.et_home_lat);
        etHomeLng = findViewById(R.id.et_home_lng);
        etAlertDistance = findViewById(R.id.et_alert_distance);
        btnStart = findViewById(R.id.btn_start);
        btnStop = findViewById(R.id.btn_stop);
        tvStatus = findViewById(R.id.tv_status);
        Button btnGetLocation = findViewById(R.id.btn_get_location);

        btnStart.setOnClickListener(v -> startService());
        btnStop.setOnClickListener(v -> stopService());
        btnGetLocation.setOnClickListener(v -> getCurrentLocation());
    }

    private void loadSavedConfig() {
        SharedPreferences prefs = getSharedPreferences(
                LocationService.PREF_NAME, MODE_PRIVATE);

        String url = prefs.getString(LocationService.KEY_SERVER_URL, "");
        long interval = prefs.getLong(LocationService.KEY_INTERVAL, 10);
        double homeLat = Double.longBitsToDouble(
                prefs.getLong(LocationService.KEY_HOME_LAT,
                        Double.doubleToLongBits(0.0)));
        double homeLng = Double.longBitsToDouble(
                prefs.getLong(LocationService.KEY_HOME_LNG,
                        Double.doubleToLongBits(0.0)));
        double alertDist = Double.longBitsToDouble(
                prefs.getLong(LocationService.KEY_ALERT_DISTANCE,
                        Double.doubleToLongBits(500.0)));

        if (!url.isEmpty()) etServerUrl.setText(url);
        etInterval.setText(String.valueOf(interval));
        if (homeLat != 0.0) etHomeLat.setText(String.valueOf(homeLat));
        if (homeLng != 0.0) etHomeLng.setText(String.valueOf(homeLng));
        etAlertDistance.setText(String.valueOf((int) alertDist));

        boolean enabled = prefs.getBoolean(LocationService.KEY_ENABLED, false);
        serviceRunning = enabled;
        updateStatusUI();
    }

    private void saveConfig() {
        String url = etServerUrl.getText().toString().trim();
        String intervalStr = etInterval.getText().toString().trim();
        String latStr = etHomeLat.getText().toString().trim();
        String lngStr = etHomeLng.getText().toString().trim();
        String distStr = etAlertDistance.getText().toString().trim();

        if (url.isEmpty()) {
            Toast.makeText(this, "请填写服务器地址", Toast.LENGTH_SHORT).show();
            return;
        }

        long interval = 10;
        try { interval = Long.parseLong(intervalStr); } catch (Exception ignored) {}

        double lat = 0.0;
        try { lat = Double.parseDouble(latStr); } catch (Exception ignored) {}

        double lng = 0.0;
        try { lng = Double.parseDouble(lngStr); } catch (Exception ignored) {}

        double dist = 500.0;
        try { dist = Double.parseDouble(distStr); } catch (Exception ignored) {}

        SharedPreferences.Editor editor = getSharedPreferences(
                LocationService.PREF_NAME, MODE_PRIVATE).edit();
        editor.putString(LocationService.KEY_SERVER_URL, url);
        editor.putLong(LocationService.KEY_INTERVAL, interval);
        editor.putLong(LocationService.KEY_HOME_LAT, Double.doubleToLongBits(lat));
        editor.putLong(LocationService.KEY_HOME_LNG, Double.doubleToLongBits(lng));
        editor.putLong(LocationService.KEY_ALERT_DISTANCE, Double.doubleToLongBits(dist));
        editor.apply();

        Log.i(TAG, "配置已保存: url=" + url + " interval=" + interval
                + " home=" + lat + "," + lng + " dist=" + dist);
    }

    private void startService() {
        saveConfig();

        String url = etServerUrl.getText().toString().trim();
        if (url.isEmpty()) {
            Toast.makeText(this, "请先填写服务器地址", Toast.LENGTH_SHORT).show();
            return;
        }

        Intent intent = new Intent(this, LocationService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent);
        } else {
            startService(intent);
        }

        serviceRunning = true;
        getSharedPreferences(LocationService.PREF_NAME, MODE_PRIVATE)
                .edit().putBoolean(LocationService.KEY_ENABLED, true).apply();
        updateStatusUI();

        Toast.makeText(this, "位置守护已启动", Toast.LENGTH_SHORT).show();
        Log.i(TAG, "✅ 服务已启动");
    }

    private void stopService() {
        Intent intent = new Intent(this, LocationService.class);
        stopService(intent);

        serviceRunning = false;
        getSharedPreferences(LocationService.PREF_NAME, MODE_PRIVATE)
                .edit().putBoolean(LocationService.KEY_ENABLED, false).apply();
        updateStatusUI();

        Toast.makeText(this, "位置守护已停止", Toast.LENGTH_SHORT).show();
        Log.i(TAG, "⛔ 服务已停止");
    }

    private void updateStatusUI() {
        if (serviceRunning) {
            tvStatus.setText("● 守护中");
            tvStatus.setTextColor(0xFF4CAF50); // 绿色
            btnStart.setEnabled(false);
            btnStop.setEnabled(true);
        } else {
            tvStatus.setText("○ 未启动");
            tvStatus.setTextColor(0xFF9E9E9E); // 灰色
            btnStart.setEnabled(true);
            btnStop.setEnabled(false);
        }
    }

    // ══════════════════════════════════════════════════════════
    //  获取当前位置
    // ══════════════════════════════════════════════════════════

    private void getCurrentLocation() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            Toast.makeText(this, "请先授予定位权限", Toast.LENGTH_SHORT).show();
            checkPermissions();
            return;
        }

        locationManager = (LocationManager) getSystemService(LOCATION_SERVICE);
        if (locationManager == null) {
            Toast.makeText(this, "无法获取定位服务", Toast.LENGTH_SHORT).show();
            return;
        }

        Toast.makeText(this, "正在获取位置...", Toast.LENGTH_SHORT).show();

        // 先尝试获取最后已知位置
        Location lastGps = locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER);
        Location lastNet = locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER);

        Location bestLocation = null;
        if (lastGps != null) {
            bestLocation = lastGps;
        } else if (lastNet != null) {
            bestLocation = lastNet;
        }

        if (bestLocation != null) {
            fillLocationFields(bestLocation);
            return;
        }

        // 没有缓存位置，请求一次实时定位
        LocationListener oneTimeListener = new LocationListener() {
            @Override
            public void onLocationChanged(Location location) {
                fillLocationFields(location);
                locationManager.removeUpdates(this);
            }
            @Override
            public void onStatusChanged(String provider, int status, Bundle extras) {}
            @Override
            public void onProviderEnabled(String provider) {}
            @Override
            public void onProviderDisabled(String provider) {
                Toast.makeText(MainActivity.this, "请打开手机GPS定位", Toast.LENGTH_SHORT).show();
            }
        };

        if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
            locationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER, 0, 0, oneTimeListener);
        } else if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
            locationManager.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 0, 0, oneTimeListener);
        } else {
            Toast.makeText(this, "请打开手机GPS定位", Toast.LENGTH_SHORT).show();
        }
    }

    private void fillLocationFields(Location location) {
        double lat = location.getLatitude();
        double lng = location.getLongitude();
        etHomeLat.setText(String.valueOf(lat));
        etHomeLng.setText(String.valueOf(lng));
        Toast.makeText(this, "已获取位置: " + String.format("%.6f", lat) + ", " + String.format("%.6f", lng),
                Toast.LENGTH_LONG).show();
        Log.i(TAG, "📍 获取到当前位置: " + lat + ", " + lng);
    }

    // ══════════════════════════════════════════════════════════
    //  权限管理
    // ══════════════════════════════════════════════════════════

    private void checkPermissions() {
        String[] permissions;

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            // Android 13+
            permissions = new String[]{
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION,
                    Manifest.permission.POST_NOTIFICATIONS
            };
        } else {
            permissions = new String[]{
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION
            };
        }

        boolean needRequest = false;
        for (String perm : permissions) {
            if (ContextCompat.checkSelfPermission(this, perm)
                    != PackageManager.PERMISSION_GRANTED) {
                needRequest = true;
                break;
            }
        }

        if (needRequest) {
            ActivityCompat.requestPermissions(this, permissions, PERMISSION_REQUEST_CODE);
        } else {
            // 前台定位权限已有, 请求后台定位
            requestBackgroundLocation();
        }
    }

    private void requestBackgroundLocation() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            if (ContextCompat.checkSelfPermission(this,
                    Manifest.permission.ACCESS_BACKGROUND_LOCATION)
                    != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(this,
                        new String[]{Manifest.permission.ACCESS_BACKGROUND_LOCATION},
                        PERMISSION_REQUEST_CODE + 1);
            }
        }
    }

    private void requestBatteryOptimization() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
            if (pm != null && !pm.isIgnoringBatteryOptimizations(getPackageName())) {
                try {
                    Intent intent = new Intent(
                            Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
                    intent.setData(Uri.parse("package:" + getPackageName()));
                    startActivity(intent);
                } catch (Exception e) {
                    Log.e(TAG, "请求电池优化白名单失败: " + e.getMessage());
                }
            }
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode,
                                           @NonNull String[] permissions,
                                           @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);

        if (requestCode == PERMISSION_REQUEST_CODE) {
            boolean allGranted = true;
            for (int result : grantResults) {
                if (result != PackageManager.PERMISSION_GRANTED) {
                    allGranted = false;
                    break;
                }
            }

            if (allGranted) {
                Log.i(TAG, "✅ 前台定位权限已授予");
                requestBackgroundLocation();
            } else {
                Toast.makeText(this, "需要定位权限才能正常工作",
                        Toast.LENGTH_LONG).show();
            }
        } else if (requestCode == PERMISSION_REQUEST_CODE + 1) {
            if (grantResults.length > 0
                    && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                Log.i(TAG, "✅ 后台定位权限已授予");
            } else {
                Toast.makeText(this, "建议授予后台定位权限以保证守护效果",
                        Toast.LENGTH_LONG).show();
            }
        }
    }
}

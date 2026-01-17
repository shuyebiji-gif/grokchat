[app]
title = GrokChat
p4a.source_dir = /home/ye/grokchat/.buildozer/android/platform/python-for-android
# 国内镜像加速Android SDK/NDK下载
android.sdk_mirror = https://mirrors.tuna.tsinghua.edu.cn/android/repository/
android.ndk_mirror = https://mirrors.tuna.tsinghua.edu.cn/android/repository/
package.name = grokchat
package.domain = org.grokchat
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 0.1

# Android 14 适配核心配置
android.api = 33          # 目标Android 14（API 33）
android.minapi = 21       # 最低兼容Android 5.0（API 21）
android.ndk = 25b         

# 权限：仅保留网络请求必需的INTERNET（符合Android 14规范）
android.permissions = INTERNET

# 依赖（版本适配Android 14）
requirements = python3,kivy==2.3.0,aiohttp==3.9.1,plyer==2.1.0,python-dotenv==1.0.0

# 屏幕配置（微信风格竖屏）
android.fullscreen = 0
android.orientation = portrait

# 可选：添加图标（推荐，需在目录下放置512x512的icon.png）
# icon.filename = %(source.dir)s/icon.png

# 可选：启动屏（提升用户体验）
# presplash.filename = %(source.dir)s/splash.png

[buildozer]
log_level = 2             # Info级别日志，便于调试
warn_on_root = 1          # 提醒root用户风险


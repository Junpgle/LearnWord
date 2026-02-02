import ctypes
import json
import math
import os
import random
import subprocess
import sys
from typing import Any

import requests
from PySide6.QtCore import Qt, QUrl, QThread, QObject, Signal, Slot, QTimer, QSize, QVariantAnimation, QEasingCurve, \
    QRect
from PySide6.QtGui import (
    QFont, QDesktopServices, QFontDatabase, QIcon, QMovie,
    QPainter, QColor, QRadialGradient, QBrush, QPixmap
)
# 添加到现有的 imports 中
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLabel, QPushButton, QGridLayout, QHBoxLayout, QMessageBox, QDialog,
    QScrollArea, QFrame, QStackedWidget, QLineEdit, QCheckBox
)

from learn_window import LearnWindow
from review_window import ReviewWindow
from setting_window import SettingWindow
from test_window import TestWindow
from user_manager import UserManager
from vocab_model import VocabModel

# 设定当前程序版本号
CURRENT_VERSION = "v2.0.0"
CURRENT_VERSION_DATE = "20260202"


# ★★★ 资源路径获取函数 ★★★
def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_path = os.getcwd()
    return os.path.join(base_path, relative_path)


# =================================================================
# 账号状态组件 (AccountPanel) - 优化逻辑版
# =================================================================
class AccountPanel(QFrame):
    """
    状态区域：
    Index 0: 登录入口 (只有一个登录按钮)
    Index 1: 登录表单 (输入账号密码)
    Index 2: 已登录状态 (头像 + 昵称)
    """
    login_success = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 初始化用户管理器
        self.user_manager = UserManager()

        self.setFixedWidth(260)
        self.setObjectName("AccountPanel")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(15, 25, 15, 25)
        self.main_layout.setSpacing(10)

        self.stack = QStackedWidget()

        # --- 1. 登录入口页 (简洁) ---
        self.entry_page = QWidget()
        entry_lyt = QVBoxLayout(self.entry_page)
        entry_lyt.setAlignment(Qt.AlignmentFlag.AlignCenter)

        entry_icon = QLabel("👤")
        entry_icon.setStyleSheet("font-size: 48px; color: rgba(255,255,255,0.3); margin-bottom: 10px;")
        entry_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_goto_login = QPushButton("登录账户")
        self.btn_goto_login.setFixedSize(160, 45)
        self.btn_goto_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_goto_login.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.btn_goto_login.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 12px;
                color: white;
                font-weight: bold;
                font-size: 15px;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.15); border: 1px solid #3b82f6; }
        """)

        entry_lyt.addStretch()
        entry_lyt.addWidget(entry_icon)
        entry_lyt.addWidget(self.btn_goto_login)
        entry_lyt.addStretch()

        # 稍后添加其他页面之后，检查并恢复会话

        # --- 2. 登录表单页 ---
        self.form_page = QWidget()
        form_lyt = QVBoxLayout(self.form_page)
        form_lyt.setSpacing(12)

        title = QLabel("用户登录")
        title.setFont(QFont("MiSans", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: white; margin-bottom: 5px;")

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("用户名")
        self.pwd_input = QLineEdit()
        self.pwd_input.setPlaceholderText("密码")
        self.pwd_input.setEchoMode(QLineEdit.EchoMode.Password)

        input_style = """
            QLineEdit {
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 10px;
                color: white;
            }
            QLineEdit:focus { border: 1px solid #3b82f6; background: rgba(255, 255, 255, 0.12); }
        """
        self.user_input.setStyleSheet(input_style)
        self.pwd_input.setStyleSheet(input_style)

        # ★★★ 新增：记住密码复选框 ★★★
        self.remember_pwd_checkbox = QCheckBox("记住密码")
        self.remember_pwd_checkbox.setStyleSheet("""
            QCheckBox {
                color: rgba(255, 255, 255, 0.7);
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid rgba(255, 255, 255, 0.3);
                background: rgba(255, 255, 255, 0.05);
            }
            QCheckBox::indicator:checked {
                background: #3b82f6;
                border: 1px solid #3b82f6;
            }
        """)

        # 确认登录按钮
        btn_do_login = QPushButton("确认登录")
        btn_do_login.setFixedHeight(40)
        btn_do_login.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_do_login.clicked.connect(self._handle_login)
        btn_do_login.setStyleSheet("""
            QPushButton { background: #2563eb; color: white; border-radius: 8px; font-weight: bold; }
            QPushButton:hover { background: #3b82f6; }
        """)

        # ★★★ 新增：网页注册按钮 ★★★
        self.btn_web_register = QPushButton("还没有账号? 网页注册")
        self.btn_web_register.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_web_register.setStyleSheet("""
            QPushButton { 
                color: #3b82f6; 
                background: transparent; 
                border: none; 
                font-size: 12px; 
                text-decoration: underline; 
            }
            QPushButton:hover { color: #60a5fa; }
        """)
        # 绑定跳转逻辑（请替换为你的实际部署地址）
        reg_url = "https://junpgle.github.io/LearnWord/register.html"
        self.btn_web_register.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(reg_url)))

        btn_back = QPushButton("返回")
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        btn_back.setStyleSheet("color: #888; background: transparent; border: none; font-size: 12px;")
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)

        form_lyt.addWidget(title)
        form_lyt.addWidget(self.user_input)
        form_lyt.addWidget(self.pwd_input)
        form_lyt.addWidget(self.remember_pwd_checkbox)
        form_lyt.addWidget(btn_do_login)
        form_lyt.addWidget(self.btn_web_register, 0, Qt.AlignmentFlag.AlignCenter)  # 添加注册按钮
        form_lyt.addWidget(btn_back)
        form_lyt.addStretch()

        # --- 3. 个人信息页 (已登录) ---
        self.profile_page = QWidget()
        profile_lyt = QVBoxLayout(self.profile_page)
        profile_lyt.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self.avatar_lbl = QLabel()
        self.avatar_lbl.setFixedSize(80, 80)
        self.avatar_lbl.setObjectName("UserAvatar")
        self.avatar_lbl.setText("🌟")
        self.avatar_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_lbl.setStyleSheet("""
            #UserAvatar {
                background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 rgba(59, 130, 246, 0.4), stop:1 rgba(37, 99, 235, 0.1));
                border: 2px solid rgba(255, 255, 255, 0.2);
                border-radius: 40px;
                font-size: 40px;
            }
        """)

        self.username_lbl = QLabel("用户名")
        self.username_lbl.setFont(QFont("MiSans", 16, QFont.Weight.Bold))
        self.username_lbl.setStyleSheet("color: #ffffff; margin-top: 10px;")
        self.username_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status_tag = QLabel("同步已开启")
        self.status_tag.setStyleSheet("""
            color: #4ade80; background: rgba(74, 222, 128, 0.1); 
            padding: 2px 10px; border-radius: 10px; font-size: 11px; margin-top: 5px;
        """)
        self.status_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_logout = QPushButton("退出登录")
        btn_logout.setFixedWidth(100)
        btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_logout.clicked.connect(self._handle_logout)
        btn_logout.setStyleSheet("""
            QPushButton { background: transparent; color: #ff4d4f; border: 1px solid rgba(255,77,79,0.3); border-radius: 6px; padding: 4px; font-size: 12px; margin-top: 30px;}
            QPushButton:hover { background: rgba(255,77,79,0.1); border: 1px solid #ff4d4f; }
        """)

        profile_lyt.addSpacing(20)
        profile_lyt.addWidget(self.avatar_lbl, 0, Qt.AlignmentFlag.AlignCenter)
        profile_lyt.addWidget(self.username_lbl, 0, Qt.AlignmentFlag.AlignCenter)
        profile_lyt.addWidget(self.status_tag, 0, Qt.AlignmentFlag.AlignCenter)
        profile_lyt.addStretch()
        profile_lyt.addWidget(btn_logout, 0, Qt.AlignmentFlag.AlignCenter)

        self.stack.addWidget(self.entry_page)
        self.stack.addWidget(self.form_page)
        self.stack.addWidget(self.profile_page)
        self.main_layout.addWidget(self.stack)

        self.setStyleSheet("""
            #AccountPanel {
                background: rgba(20, 25, 40, 0.45);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 24px;
            }
        """)

        # ★★★ 启动时检查并恢复会话 ★★★
        self._check_and_restore_session()

    def _handle_login(self):
        user = self.user_input.text().strip()
        pwd = self.pwd_input.text().strip()
        if user and pwd:
            # 真正调用 UserManager 执行登录
            success, msg = self.user_manager.login(user, pwd)
            if success:
                # ★★★ 新增：如果勾选了"记住密码"，保存凭据 ★★★
                if self.remember_pwd_checkbox.isChecked():
                    self.user_manager.save_remember_password(user, pwd)
                else:
                    # 未勾选则清除之前保存的凭据
                    self.user_manager.clear_remember_password()

                self.username_lbl.setText(user)
                self.stack.setCurrentIndex(2)
                self.login_success.emit(user)
            else:
                QMessageBox.warning(self, "登录失败", msg)
        else:
            QMessageBox.warning(self, "提示", "请输入用户名和密码")

    def _check_and_restore_session(self):
        """启动时检查并恢复会话"""
        # 首先检查是否有有效的会话令牌
        if self.user_manager.is_logged_in():
            # 有有效的会话，直接显示已登录状态
            username = self.user_manager.get_username()
            if username:
                self.username_lbl.setText(username)
                self.stack.setCurrentIndex(2)
                self.login_success.emit(username)
                return

        # 没有会话令牌，尝试使用记住的凭据自动登录
        username, password = self.user_manager.get_remember_password()
        if username and password:
            print(f"[启动恢复] 发现保存的凭据，正在自动登录: {username}")
            # 自动填充用户名和密码
            self.user_input.setText(username)
            self.pwd_input.setText(password)
            self.remember_pwd_checkbox.setChecked(True)
            # 延迟 500ms 后自动提交登录，确保 UI 已渲染
            QTimer.singleShot(500, self._auto_login)
        else:
            # 无有效会话和记住的凭据，显示登录入口
            self.stack.setCurrentIndex(0)

    def _auto_login(self):
        """自动登录（从记住的凭据）"""
        user = self.user_input.text().strip()
        pwd = self.pwd_input.text().strip()
        if user and pwd:
            success, msg = self.user_manager.login(user, pwd)
            if success:
                print(f"[启动恢复] ✅ 自动登录成功: {user}")
                self.username_lbl.setText(user)
                self.stack.setCurrentIndex(2)
                self.login_success.emit(user)
            else:
                print(f"[启动恢复] ❌ 自动登录失败: {msg}")
                # 自动登录失败，清除保存的凭据，显示登录表单
                self.user_manager.clear_remember_password()
                self.user_input.setText("")
                self.pwd_input.setText("")
                self.remember_pwd_checkbox.setChecked(False)
                self.stack.setCurrentIndex(1)

    def _handle_logout(self):
        """处理退出登录"""
        self.user_manager.logout()
        self.user_input.setText("")
        self.pwd_input.setText("")
        self.stack.setCurrentIndex(0)


# =================================================================
# 梦幻背景组件 (DreamyBackground)
# =================================================================
class DreamyBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.wallpaper_pixmap = None
        self.current_video_frame = None  # 用于存储当前视频帧
        self.wallpaper_opacity = 0.0  # 透明度 (0.0 - 1.0)

        self.sentence_text = ""
        self.sentence_author = ""

        # --- 视频播放组件 ---
        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.video_sink = QVideoSink(self)

        # 设置静音 & 无限循环
        self.audio_output.setVolume(0)
        self.audio_output.setMuted(True)
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoSink(self.video_sink)
        self.media_player.setLoops(QMediaPlayer.Loops.Infinite)

        # 当视频帧更新时，刷新界面
        self.video_sink.videoFrameChanged.connect(self._on_video_frame_changed)

        # --- 动画相关 ---
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(33)
        self.time_offset = 0.0

        # 渐显动画
        self.fade_anim = QVariantAnimation(self)
        self.fade_anim.setDuration(1500)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_anim.valueChanged.connect(self._update_opacity)

    def set_wallpaper(self, pixmap):
        """设置静态图片壁纸"""
        self.media_player.stop()  # 停止视频
        self.current_video_frame = None

        if pixmap and not pixmap.isNull():
            self.wallpaper_pixmap = pixmap
            # 重新播放渐显动画
            self.fade_anim.stop()
            self.fade_anim.start()

    def set_video(self, video_path):
        """设置视频壁纸"""
        self.wallpaper_pixmap = None  # 清除图片

        if os.path.exists(video_path):
            self.media_player.setSource(QUrl.fromLocalFile(video_path))
            self.media_player.play()
            # 视频也播放渐显动画
            self.fade_anim.stop()
            self.fade_anim.start()

    def set_sentence(self, text, author=""):
        self.sentence_text = text
        self.sentence_author = author
        self.update()

    @Slot(object)
    def _update_opacity(self, value):
        self.wallpaper_opacity = float(value)
        self.update()

    @Slot()
    def _on_video_frame_changed(self):
        # 获取当前视频帧并转换为 QImage
        frame = self.video_sink.videoFrame()
        if frame.isValid():
            self.current_video_frame = frame.toImage()
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w = self.width()
        h = self.height()

        # --- 1. 绘制底层梦幻光晕 ---
        painter.fillRect(self.rect(), QColor(10, 12, 18))

        self.time_offset += 0.02

        def draw_halo(cx, cy, radius, color, alpha_base):
            breath = (math.sin(self.time_offset) + 1) / 2
            current_alpha = int(alpha_base + 30 * breath)
            gradient = QRadialGradient(cx, cy, radius)
            c = QColor(color)
            c.setAlpha(current_alpha)
            gradient.setColorAt(0, c)
            c_end = QColor(color)
            c_end.setAlpha(0)
            gradient.setColorAt(1, c_end)
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(self.rect())

        x1 = w * 0.2 + math.sin(self.time_offset * 0.5) * 50
        y1 = h * 0.3 + math.cos(self.time_offset * 0.3) * 30
        draw_halo(x1, y1, w * 0.8, QColor(0, 160, 255), 30)

        # --- 2. 绘制壁纸 OR 视频 (带透明度) ---
        painter.setOpacity(self.wallpaper_opacity)

        target_image = None

        # 优先判断视频帧
        if self.current_video_frame and not self.current_video_frame.isNull():
            target_image = self.current_video_frame
        elif self.wallpaper_pixmap and not self.wallpaper_pixmap.isNull():
            target_image = self.wallpaper_pixmap

        if target_image:
            # 无论是 QImage (视频) 还是 QPixmap (图片)，绘制逻辑是一样的
            # 计算保持比例填满窗口 (Cover模式)
            img_w = target_image.width()
            img_h = target_image.height()

            # 防止除以0
            if img_w > 0 and img_h > 0:
                scale = max(w / img_w, h / img_h)
                new_w = int(img_w * scale)
                new_h = int(img_h * scale)

                # 居中裁剪绘制
                x = (w - new_w) // 2
                y = (h - new_h) // 2

                # drawImage 支持 QImage, drawPixmap 支持 QPixmap
                if isinstance(target_image, QPixmap):
                    painter.drawPixmap(QRect(x, y, new_w, new_h), target_image)
                else:
                    painter.drawImage(QRect(x, y, new_w, new_h), target_image)

            # 绘制黑色遮罩 (让文字更清晰)
            painter.fillRect(self.rect(), QColor(0, 0, 0, int(90 * self.wallpaper_opacity)))

        painter.setOpacity(1.0)

        # --- 3. 绘制底部句子 (保持不变) ---
        if self.sentence_text:
            font = QFont("MiSans", 12)
            font.setItalic(True)
            painter.setFont(font)
            painter.setPen(QColor(240, 240, 240, 200))
            text_str = f"“ {self.sentence_text} ”"
            if self.sentence_author:
                text_str += f"\n— {self.sentence_author}"
            rect = QRect(40, h - 100, w - 80, 80)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text_str)


# =================================================================
# 壁纸加载器 (WallpaperLoader) - 修改版
# =================================================================
class WallpaperLoader(QObject):
    finished = Signal(str)

    def run_load(self):
        appdata = os.getenv('APPDATA')
        base_dir = os.path.join(appdata, 'LearnWord')
        cache_list_file = os.path.join(base_dir, 'data', 'wallpaper_list_cache.json')
        save_dir = os.path.join(base_dir, 'backgrounds')

        for d in [os.path.dirname(cache_list_file), save_dir]:
            if not os.path.exists(d):
                os.makedirs(d, exist_ok=True)

        download_url = None
        filename = None

        # 新增一个标志位：是否强制覆盖本地文件
        # 默认不覆盖 (False)，只有特定情况(如固定壁纸)才改为 True
        should_overwrite = False

        # 1. 尝试获取固定壁纸配置 (Manifest)
        try:
            manifest_url = "https://raw.githubusercontent.com/Junpgle/LearnWord/master/wallpaper_manifest.json"
            headers = {"User-Agent": "LearnWord-Client/1.0"}
            resp = requests.get(manifest_url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                fixed = data.get("fixed_wallpaper", {})

                # 如果启用固定壁纸，我们假设这是必须要展示的最新内容
                # 所以将 should_overwrite 设为 True
                if fixed.get("active") is True:
                    download_url = fixed.get("url")
                    filename = fixed.get("name")
                    should_overwrite = True  # <--- 关键修改：标记为强制覆盖

                    if not filename and download_url:
                        filename = download_url.split('/')[-1]
                        # 确保后缀合法
                        if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.webm', '.mkv')):
                            filename = "fixed_wallpaper.jpg"
        except Exception:
            pass

        # 2. 如果没有固定壁纸，则从 GitHub 列表随机获取 (保持原有缓存逻辑)
        if not download_url:
            try:
                # 注意：这里我们不需要 should_overwrite = True，随机图片依然优先用缓存
                api_url = "https://api.github.com/repos/Junpgle/LearnWord/contents/background"
                headers = {"User-Agent": "LearnWord-Client/1.0", "Accept": "application/vnd.github.v3+json"}
                resp = requests.get(api_url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    files = resp.json()
                    images = [f for f in files if
                              isinstance(f, dict) and f.get('type') == 'file' and f.get('name', '').lower().endswith(
                                  ('.jpg', '.jpeg', '.png', '.mp4', '.webm', '.mkv'))]
                    if images:
                        try:
                            with open(cache_list_file, 'w', encoding='utf-8') as f:
                                json.dump(images, f, ensure_ascii=False)
                        except Exception:
                            pass
                        target = random.choice(images)
                        download_url = target.get('download_url')
                        filename = target.get('name')
            except Exception:
                pass

        # 3. 如果 API 失败，尝试读取本地缓存列表
        if not download_url and os.path.exists(cache_list_file):
            try:
                with open(cache_list_file, 'r', encoding='utf-8') as f:
                    cached_images = json.load(f)
                if cached_images:
                    target = random.choice(cached_images)
                    download_url = target.get('download_url')
                    filename = target.get('name')
            except Exception:
                pass

        # 4. 如果还是没有，使用兜底随机
        if not download_url:
            idx = random.randint(1, 5)
            filename = f"{idx}.jpg"
            download_url = f"https://raw.githubusercontent.com/Junpgle/LearnWord/master/background/{filename}"
            # 兜底情况通常也建议覆盖一下，防止兜底图片更新了客户端没变
            # 但为了保险起见，这里也可以设为 True，或者保持 False
            should_overwrite = False

        # ★★ 核心下载逻辑修改 ★★★
        if download_url and filename:
            save_path = os.path.join(save_dir, filename)
            try:
                # 判断条件修改：
                # 如果文件不存在 (not exists) 或者 标记为强制覆盖 (should_overwrite)
                # 都要执行下载
                if not os.path.exists(save_path) or should_overwrite:
                    dl_headers = {"User-Agent": "LearnWord-Client/1.0"}
                    img_resp = requests.get(download_url, headers=dl_headers, timeout=15)
                    if img_resp.status_code == 200:
                        with open(save_path, 'wb') as f:
                            f.write(img_resp.content)
                        self.finished.emit(save_path)
                        return
            except Exception:
                pass

            # 如果下载失败（或者不需要下载），但本地文件存在，就用本地的
            if os.path.exists(save_path):
                self.finished.emit(save_path)
                return

        self.finished.emit("")


# =================================================================
# 句子加载器 (SentenceLoader)
# =================================================================
class SentenceLoader(QObject):
    finished = Signal(str, str)

    def run_load(self):
        url = "https://raw.githubusercontent.com/Junpgle/LearnWord/master/sentence_manifest.json"
        text = "Stay hungry, stay foolish."
        author = "Steve Jobs"
        try:
            headers = {"User-Agent": "LearnWord-Client/1.0"}
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                fixed = data.get("fixed_sentence", {})
                if fixed.get("active") is True:
                    text = fixed.get("text", text)
                    author = fixed.get("author", author)
                else:
                    pool = data.get("pool", [])
                    if pool:
                        item = random.choice(pool)
                        text = item.get("text", text)
                        author = item.get("author", "")
        except Exception:
            pass
        self.finished.emit(text, author)


# =================================================================
# UpdateChecker 和 AnnouncementLoader
# =================================================================
class UpdateChecker(QObject):
    signal_result = Signal(bool, object)

    def run_check(self):
        manifest_url = "https://raw.githubusercontent.com/Junpgle/LearnWord/refs/heads/master/update_manifest.json"
        try:
            headers = {"User-Agent": "LearnWord-Client/1.0"}
            response = requests.get(manifest_url, headers=headers, timeout=5)
            response.raise_for_status()
            self.signal_result.emit(True, response.json())
        except Exception as e:
            self.signal_result.emit(False, str(e))


class AnnouncementLoader(QObject):
    signal_result = Signal(bool, object)

    def run_load(self):
        url = "https://raw.githubusercontent.com/Junpgle/LearnWord/refs/heads/master/announcement.json"
        try:
            headers = {"User-Agent": "LearnWord-Client/1.0"}
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            self.signal_result.emit(True, response.json())
        except Exception as e:
            self.signal_result.emit(False, str(e))


# =================================================================
# ★★★ 公共基类: FramelessDialog ★★★
# =================================================================
class FramelessDialog(QDialog):
    """
    无边框对话框基类：
    1. 自动去除系统边框
    2. 提供透明背景支持
    3. 封装了拖动逻辑
    4. 提供一个内部容器 bg_widget 用于放置内容
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # 核心修复：必须显式添加 Qt.WindowType.Dialog，否则有父对象时会被视为子控件
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.drag_pos = None

        # 主布局：包含背景容器
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # 背景容器：实际显示圆角和背景色的部分
        self.bg_widget = QWidget(self)
        self.bg_widget.setObjectName("DialogBg")
        self.main_layout.addWidget(self.bg_widget)

        # 内容布局：子类将控件添加到这里
        self.content_layout = QVBoxLayout(self.bg_widget)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.setSpacing(15)

    def setup_title_bar(self, title_text):
        """为对话框添加统一风格的标题栏"""
        top_bar = QHBoxLayout()
        title_label = QLabel(title_text)
        title_label.setFont(QFont("MiSans", 16, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #eeeeee; background: transparent;")

        close_btn = QPushButton("×")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.reject)
        close_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #888; border-radius: 15px; font-size: 20px; font-weight: bold; padding-bottom: 3px;}
            QPushButton:hover { background-color: #e81123; color: white; }
        """)

        top_bar.addWidget(title_label)
        top_bar.addStretch()
        top_bar.addWidget(close_btn)

        # 插入到布局最前面
        self.content_layout.insertLayout(0, top_bar)

    # --- 拖动逻辑 ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.drag_pos:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    # --- 修复自动居中逻辑 ---
    def showEvent(self, event):
        super().showEvent(event)
        # 确保使用父窗口的几何信息进行居中
        if self.parent() and isinstance(self.parent(), QWidget):
            # 获取父窗口（通常是主窗口）的几何形状
            parent_geo = self.parent().window().geometry()
            self_geo = self.geometry()

            # 计算中心点 (屏幕坐标系)
            x = parent_geo.x() + (parent_geo.width() - self_geo.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - self_geo.height()) // 2
            self.move(x, y)
        else:
            # 如果没有父窗口，则居中于屏幕
            screen = QApplication.primaryScreen().availableGeometry()
            size = self.geometry()
            self.move((screen.width() - size.width()) // 2, (screen.height() - size.height()) // 2)

    # --- 统一样式 ---
    def set_dark_theme(self):
        """应用通用的深色主题样式"""
        self.setStyleSheet("""
            #DialogBg {
                background-color: #1a1a1a; 
                border: 1px solid #333333; 
                border-radius: 12px;
            }
            QLabel { color: #dddddd; background: transparent; }
            QPushButton { font-family: "MiSans"; }

            /* 滚动条美化 */
            QScrollBar:vertical { background: #222; width: 8px; border-radius: 4px; margin: 0px;}
            QScrollBar::handle:vertical { background: #555; border-radius: 4px; min-height: 20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollArea { border: none; background: transparent; }
        """)


# =================================================================
# 拟真飘落撒花特效 (ConfettiWidget - Fluttering Style)
# =================================================================
class ConfettiParticle:
    """物理粒子对象"""

    def __init__(self, w, h, pixmaps):
        # 1. 初始位置：从屏幕上方中心区域喷发，范围稍微宽一点
        self.x = random.randint(w // 5, w * 4 // 5)
        self.y = random.randint(h // 3, h // 2)  # 起始点放低一点，让喷射更明显

        # 2. 初始速度：模拟“爆炸式”喷射
        # 水平速度：向四周炸开，范围大一点 (-10 到 10)
        self.vx = random.uniform(-10, 30)
        # 垂直速度：猛烈向上喷射 (-15 到 -25)
        self.vy = random.uniform(-25, -10)

        # 3. 物理属性：每个粒子的“轻重”不一样
        self.gravity = random.uniform(0.15, 0.3)  # 重力较小，模拟纸片
        self.max_fall_speed = random.uniform(3, 10)  # 终端速度：限制最大下落速度，防止像石头一样砸下来
        self.sway_speed = random.uniform(0.05, 0.07)  # 左右摇摆的频率
        self.sway_offset = random.uniform(0, math.pi * 2)  # 摇摆相位

        # 4. 旋转
        self.rotation = random.randint(0, 360)
        self.rotation_speed = random.uniform(-3, 3)

        # 5. 图片
        self.pixmap = random.choice(pixmaps)
        # 随机缩放
        scale = random.uniform(0.3, 1.5)
        if scale != 1.0:
            self.pixmap = self.pixmap.scaled(
                QSize(int(self.pixmap.width() * scale), int(self.pixmap.height() * scale)),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
        self.half_w = self.pixmap.width() / 2
        self.half_h = self.pixmap.height() / 2

        # 标记是否已经进入“飘落阶段”
        self.is_falling = False


class ConfettiWidget(QWidget):
    """全屏撒花覆盖层 (拟真飘落版)"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        if parent:
            self.resize(parent.size())

        self.time_step = 0  # 用于计算正弦波

        # 预渲染 Emoji
        self.cached_pixmaps = self._cache_emojis(['🎉', '🎊', '✨', '🎁', '🎈'], size=48)

        # 生成 80 个粒子
        self.particles = [ConfettiParticle(self.width(), self.height(), self.cached_pixmaps) for _ in range(20)]

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_physics)
        self.timer.start(16)

    def _cache_emojis(self, emojis, size):
        pixmaps = []
        font = QFont("Segoe UI Emoji", size)
        if not font.exactMatch():
            font = QFont("Apple Color Emoji", size)
        font.setBold(True)

        for char in emojis:
            pix = QPixmap(size * 2, size * 2)
            pix.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            painter.setFont(font)
            painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, char)
            painter.end()
            pixmaps.append(pix)
        return pixmaps

    def update_physics(self):
        active_particles = False
        screen_h = self.height()
        self.time_step += 1

        for p in self.particles:
            # --- 阶段1：向上喷射 ---
            if p.vy < 0:
                # 只有在上升时才受较强的重力减速
                p.vy += p.gravity * 2
                p.x += p.vx
                p.y += p.vy
                # 空气阻力：水平速度衰减很快
                p.vx *= 0.95

                # --- 阶段2：向下飘落 ---
            else:
                p.is_falling = True

                # 垂直方向：加速下落，但不能超过最大飘落速度 (终端速度)
                if p.vy < p.max_fall_speed:
                    p.vy += p.gravity

                # 水平方向：加入正弦波摇摆 (Fluttering)
                # sway_amount 决定了摇摆的幅度
                sway_amount = math.sin(self.time_step * p.sway_speed + p.sway_offset) * 2

                p.x += sway_amount
                p.y += p.vy

            # 旋转永远都在发生
            p.rotation += p.rotation_speed

            # 边界检查
            if p.y < screen_h + 100:
                active_particles = True

        if not active_particles:
            self.timer.stop()
            self.deleteLater()
        else:
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        screen_h = self.height()

        for p in self.particles:
            if p.y < -100 or p.y > screen_h + 100: continue

            painter.save()
            painter.translate(p.x, p.y)
            painter.rotate(p.rotation)
            painter.drawPixmap(int(-p.half_w), int(-p.half_h), p.pixmap)
            painter.restore()


class AnnouncementDialog(FramelessDialog):
    def __init__(self, data, current_version, parent=None):
        super().__init__(parent)
        self.setFixedSize(600, 480)
        self.set_dark_theme()

        self.all_announcements = data.get("announcements", [])
        self.current_ver = current_version

        self.current_list = [a for a in self.all_announcements if a.get("version") == self.current_ver]
        self.history_list = [a for a in self.all_announcements if a.get("version") != self.current_ver]
        self.is_showing_history = False

        self.setup_ui()
        self.render_content()

        # ★★★ 新增：如果是显示最新版本，启动撒花特效 ★★★
        # 只有当 current_list 不为空（即有新版本公告）时才撒花
        if self.current_list:
            self.confetti = ConfettiWidget(self)
            self.confetti.show()
            self.confetti.raise_()  # 确保显示在最上层

    def setup_ui(self):
        # 1. 标题栏
        self.setup_title_bar("系统公告")

        # 2. 顶部 Header
        top_container = QWidget()
        top_layout = QHBoxLayout(top_container)
        top_layout.setContentsMargins(30, 5, 30, 5)
        top_layout.setSpacing(15)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(48, 48)
        self.icon_label.setScaledContents(True)

        gif_path = get_resource_path(os.path.join("Animation", "Announcement.gif"))
        if not os.path.exists(gif_path):
            gif_path = os.path.join(os.getcwd(), "Animation", "Announcement.gif")

        if os.path.exists(gif_path):
            self.movie = QMovie(gif_path)
            self.movie.setScaledSize(QSize(48, 48))
            self.icon_label.setMovie(self.movie)
            self.movie.start()
        else:
            self.icon_label.setText("📢")
            self.icon_label.setStyleSheet("font-size: 36px;")

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.lbl_main_title = QLabel("最新动态")
        self.lbl_main_title.setFont(QFont("MiSans", 22, QFont.Weight.Bold))
        self.lbl_main_title.setStyleSheet("color: white;")

        self.lbl_sub_title = QLabel(f"Version {self.current_ver}")
        self.lbl_sub_title.setStyleSheet("color: #3b82f6; font-weight: bold; font-size: 15px;")

        title_box.addWidget(self.lbl_main_title)
        title_box.addWidget(self.lbl_sub_title)

        top_layout.addWidget(self.icon_label)
        top_layout.addLayout(title_box)
        top_layout.addStretch()

        self.content_layout.addWidget(top_container)

        # 3. 滚动文本区
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 6px; background: transparent; }
            QScrollBar::handle:vertical { background: #444; border-radius: 3px; }
            QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical { height: 0px; }
        """)

        self.content_label = QLabel()
        self.content_label.setWordWrap(True)
        self.content_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.content_label.setOpenExternalLinks(True)
        self.content_label.setStyleSheet("padding: 5px 30px 10px 30px;")

        self.scroll_area.setWidget(self.content_label)
        self.content_layout.addWidget(self.scroll_area)

        # 4. 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(20, 5, 20, 10)

        self.btn_history = QPushButton("查看历史公告")
        self.btn_history.setFixedSize(120, 36)
        self.btn_history.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_history.clicked.connect(self.toggle_history)
        self.btn_history.setStyleSheet("""
            QPushButton { background: transparent; color: #888; border: none; font-size: 14px; text-align: left; font-weight: bold;}
            QPushButton:hover { color: #aaa; text-decoration: underline; }
        """)

        self.btn_ok = QPushButton("我知道了")
        self.btn_ok.setFixedSize(120, 40)
        self.btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_ok.setStyleSheet("""
            QPushButton { background-color: #2563eb; color: white; border: none; border-radius: 6px; font-weight: bold; font-size: 15px; }
            QPushButton:hover { background-color: #1d4ed8; }
        """)

        btn_layout.addWidget(self.btn_history)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_ok)

        self.content_layout.addLayout(btn_layout)

    def render_content(self):
        target_list = self.history_list if self.is_showing_history else self.current_list
        html_blocks = []

        if not target_list:
            html_blocks.append("""
            <div style='margin-top: 60px; text-align: center; color: #666;'>
                <span style='font-size: 48px;'>✨</span><br><br>
                <span style='font-size: 16px;'>暂无更多内容</span>
            </div>
            """)
        else:
            for i, item in enumerate(target_list):
                if self.is_showing_history:
                    ver_title = f"<h3 style='color: #60a5fa; margin-bottom: 8px; font-size: 18px;'>{item.get('version')}</h3>"
                    html_blocks.append(ver_title)

                content = item.get("content", "")
                processed_rows = ""
                lines = [line.strip() for line in content.split('\n') if line.strip()]

                for line in lines:
                    import re
                    match = re.match(r'^(\d+[\.\、\s]|\-)\s*(.*)', line)

                    if match:
                        bullet = match.group(1).strip()
                        text = match.group(2).strip()
                        processed_rows += f"""
                        <tr>
                            <td width='28' valign='top' style='color: #3b82f6; font-weight: bold; font-size: 15px; padding-top: 2px;'>{bullet}</td>
                            <td style='color: #e5e7eb; font-size: 15px; line-height: 1.5; padding-bottom: 8px;'>{text}</td>
                        </tr>
                        """
                    else:
                        if "欢迎" in line or "🎉" in line:
                            processed_rows += f"""
                            <tr><td colspan='2' style='color: #fbbf24; font-weight: bold; font-size: 17px; padding-bottom: 12px;'>{line}</td></tr>
                            """
                        elif "再会" in line or "燃尽" in line:
                            processed_rows += f"""
                            <tr><td colspan='2' style='color: #888; font-size: 13px; font-style: italic; padding-top: 10px;'>{line}</td></tr>
                            """
                        else:
                            processed_rows += f"""
                            <tr><td colspan='2' style='color: #d1d5db; font-size: 15px; line-height: 1.5; padding-bottom: 8px;'>{line}</td></tr>
                            """

                html_blocks.append(
                    f"<table width='100%' cellpadding='0' cellspacing='0' border='0' style='margin-bottom: 15px;'>{processed_rows}</table>")

                if i < len(target_list) - 1:
                    html_blocks.append("<hr style='border: 1px solid #444; margin: 10px 0 20px 0;'>")

        self.content_label.setText("".join(html_blocks))

        if self.is_showing_history:
            self.lbl_main_title.setText("历史公告")
            self.lbl_sub_title.setVisible(False)
            self.btn_history.setText("返回最新动态")
        else:
            self.lbl_main_title.setText("最新动态")
            self.lbl_sub_title.setVisible(True)
            self.lbl_sub_title.setText(f"Version {self.current_ver}")
            self.btn_history.setText("查看历史公告")

        self.scroll_area.verticalScrollBar().setValue(0)

    def toggle_history(self):
        self.is_showing_history = not self.is_showing_history
        self.render_content()


# =================================================================
# UpdateDialog (无边框更新提示窗口) - 新增
# =================================================================
class UpdateDialog(FramelessDialog):
    # 返回码：1=自动更新, 2=手动下载, 0=取消
    def __init__(self, current_ver, latest_ver, release_date, notes, download_url, updater_exists, parent=None):
        super().__init__(parent)
        self.setFixedSize(500, 420)
        self.set_dark_theme()
        self.result_code = 0
        self.download_url = download_url

        self.setup_title_bar("发现新版本")

        # 内容布局
        v_layout = QVBoxLayout()
        v_layout.setSpacing(10)

        # 版本信息
        info_lbl = QLabel(f"<b>LearnWord {latest_ver}</b> 现已发布！")
        info_lbl.setStyleSheet("font-size: 18px; color: #4ade80; margin-bottom: 5px;")

        date_lbl = QLabel(f"当前版本: {current_ver}  |  更新日期: {release_date}")
        date_lbl.setStyleSheet("color: #888; font-size: 12px;")

        v_layout.addWidget(info_lbl)
        v_layout.addWidget(date_lbl)

        # 更新日志
        notes_box = QLabel()
        notes_box.setWordWrap(True)
        notes_box.setAlignment(Qt.AlignmentFlag.AlignTop)
        formatted_notes = "<br>".join([f"• {n}" for n in notes])
        notes_box.setText(f"<div style='line-height:1.6;'>{formatted_notes}</div>")
        notes_box.setStyleSheet("color: #ddd; background: transparent;")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(notes_box)
        scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #333; border-radius: 6px; background-color: rgba(0,0,0,0.2); } QWidget { background: transparent; }")

        v_layout.addWidget(QLabel("更新内容："))
        v_layout.addWidget(scroll)

        self.content_layout.addLayout(v_layout)

        # 按钮
        btn_layout = QHBoxLayout()

        cancel_btn = QPushButton("暂不更新")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setFixedSize(80, 36)
        cancel_btn.setStyleSheet("""
            QPushButton { background-color: transparent; color: #aaa; border: 1px solid #444; border-radius: 6px; }
            QPushButton:hover { background-color: #333; color: white; }
        """)

        action_btn = QPushButton()
        # 修复更新按钮文字和宽度
        action_btn.setFixedSize(140, 36)

        if updater_exists:
            action_btn.setText("立即更新 (推荐)")
            action_btn.clicked.connect(self.on_auto_update)
            action_btn.setStyleSheet("""
                QPushButton { background-color: #16a34a; color: white; border: none; border-radius: 6px; font-weight: bold;}
                QPushButton:hover { background-color: #15803d; }
            """)

            manual_btn = QPushButton("手动下载")
            manual_btn.clicked.connect(self.on_manual_download)
            manual_btn.setFixedSize(80, 36)
            manual_btn.setStyleSheet("""
                QPushButton { background-color: #2563eb; color: white; border: none; border-radius: 6px; font-weight: bold;}
                QPushButton:hover { background-color: #1d4ed8; }
            """)
            btn_layout.addWidget(manual_btn)
        else:
            action_btn.setText("前往下载")
            action_btn.setFixedSize(120, 36)  # 没推荐文字时可以短一点
            action_btn.clicked.connect(self.on_manual_download)
            action_btn.setStyleSheet("""
                QPushButton { background-color: #2563eb; color: white; border: none; border-radius: 6px; font-weight: bold;}
                QPushButton:hover { background-color: #1d4ed8; }
            """)

        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addSpacing(10)
        btn_layout.addWidget(action_btn)

        self.content_layout.addLayout(btn_layout)

    def on_auto_update(self):
        self.result_code = 1
        self.accept()

    def on_manual_download(self):
        self.result_code = 2
        self.accept()


# =================================================================
# AboutDialog (无边框版)
# =================================================================
class AboutDialog(FramelessDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 修复：增加高度，防止遮挡
        self.setFixedSize(600, 360)
        self.set_dark_theme()

        self.setup_ui()

    def setup_ui(self):
        # 引入阴影特效需要的模块 (如果没有在文件头引入，请确保引入)
        from PySide6.QtWidgets import QGraphicsDropShadowEffect

        self.setup_title_bar("关于")

        # --- 主容器：水平布局 ---
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(40, 20, 40, 20)  # 增加边距，让呼吸感更强
        h_layout.setSpacing(30)  # 图标和文字的间距

        # ==========================
        # 1. 左侧：图标区域 (增加圆角容器和阴影)
        # ==========================
        icon_container = QWidget()
        icon_container.setFixedSize(120, 120)
        # 设置图标容器样式：圆角 + 边框 + 微弱背景
        icon_container.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 24px;
            }
        """)

        # 图标 Label
        icon_label = QLabel(icon_container)
        icon_label.setGeometry(10, 10, 100, 100)  # 在容器内部居中
        icon_label.setStyleSheet("border: none; background: transparent;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ★★★ 核心修复：高清图标加载 ★★★
        # 建议：将 icon.ico 换成一张 256x256 的 icon.png 效果最好
        # 如果必须用 ico，请确保 ico 里面包含大尺寸图层
        icon_path = get_resource_path("Animation/icon.png")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                # 使用 SmoothTransformation 进行平滑缩放，抗锯齿
                scaled_pixmap = pixmap.scaled(
                    100, 100,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                icon_label.setPixmap(scaled_pixmap)
            else:
                icon_label.setText("LOGO")

        # 添加阴影效果，增加立体感
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 80))
        icon_container.setGraphicsEffect(shadow)

        h_layout.addWidget(icon_container, 0, Qt.AlignmentFlag.AlignTop)

        # ==========================
        # 2. 右侧：文字信息 (优化排版)
        # ==========================
        text_layout = QVBoxLayout()
        text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        text_layout.setSpacing(8)

        # 2.1 标题
        title_label = QLabel("LearnWord")
        # 稍微加大字号，使用纯白
        title_label.setFont(QFont("MiSans", 32, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #ffffff; letter-spacing: 1px;")

        # 2.2 版本号 (做成胶囊标签样式)
        version_container = QWidget()
        version_layout = QHBoxLayout(version_container)
        version_layout.setContentsMargins(0, 0, 0, 0)
        version_layout.setSpacing(10)

        # 版本文字
        ver_lbl = QLabel(f"{CURRENT_VERSION}")
        ver_lbl.setStyleSheet("""
            background-color: #2563eb; 
            color: white; 
            padding: 2px 8px; 
            border-radius: 4px; 
            font-size: 12px; 
            font-weight: bold;
        """)
        # 日期文字
        date_lbl = QLabel(f"Build {CURRENT_VERSION_DATE}")
        date_lbl.setStyleSheet("color: #666; font-size: 12px;")

        version_layout.addWidget(ver_lbl)
        version_layout.addWidget(date_lbl)
        version_layout.addStretch()

        # 2.3 描述文字 (增加行高，调淡颜色)
        desc_label = QLabel("一款轻量级英语词汇学习工具\n支持学习、复习、测试与进度管理")
        desc_label.setFont(QFont("MiSans", 14))
        desc_label.setStyleSheet("""
            color: #cccccc; 
            line-height: 24px; 
            margin-top: 10px;
        """)

        text_layout.addWidget(title_label)
        text_layout.addWidget(version_container)
        text_layout.addWidget(desc_label)

        h_layout.addLayout(text_layout)

        # 将主要内容加入
        self.content_layout.addSpacing(10)
        self.content_layout.addLayout(h_layout)
        self.content_layout.addStretch()

        # ==========================
        # 3. 底部按钮 (保持原有逻辑，微调样式)
        # ==========================
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        style_link = """
            QPushButton { 
                background-color: rgba(255,255,255,0.08); 
                color: #ddd; 
                border: 1px solid rgba(255,255,255,0.1); 
                border-radius: 6px; 
                padding: 6px 16px; 
                font-size: 13px;
            }
            QPushButton:hover { 
                background-color: rgba(255,255,255,0.15); 
                color: white; 
                border: 1px solid rgba(255,255,255,0.3);
            }
        """

        web_btn = QPushButton("访问展示网页")
        web_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        web_btn.setStyleSheet(style_link)
        web_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://junpgle.github.io/LearnWord/")))

        git_btn = QPushButton("项目主页 (GitHub)")
        git_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        git_btn.setStyleSheet(style_link)
        git_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/Junpgle/LearnWord")))

        btn_layout.addStretch()
        btn_layout.addWidget(web_btn)
        btn_layout.addWidget(git_btn)
        btn_layout.addStretch()  # 让按钮居中可能好看点，或者去掉这个Stretch让按钮靠右

        self.content_layout.addLayout(btn_layout)
        self.content_layout.addSpacing(10)


# =================================================================
# 主窗口类 (MainWindow)
# =================================================================
class MainWindow(QMainWindow):
    def __init__(self, model: VocabModel):
        super().__init__()
        self.model = model
        self.setWindowTitle("LearnWord")
        self.setFixedSize(1000, 700)
        self.setWindowIcon(QIcon(get_resource_path("icon.ico")))

        # --- 窗口属性设置 ---
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowSystemMenuHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 梦幻背景作为中心控件
        self.central = DreamyBackground(self)
        self.setCentralWidget(self.central)

        self.ann_thread = None
        self.ann_worker = None

        # 状态变量
        self.is_manual_check = False
        self.is_manual_announcement_check = False
        self.drag_pos = None
        self.is_ann_loading = False

        # --- 布局构建 ---
        # 总布局 (垂直)：顶部栏 + 中间内容区
        self.main_v_layout = QVBoxLayout(self.central)
        self.main_v_layout.setContentsMargins(0, 0, 0, 0)
        self.main_v_layout.setSpacing(0)

        # 1. 初始化顶部工具栏
        self._setup_top_bar()

        # 2. 中间主体内容区 (水平布局)：左侧账号 + 右侧功能
        self.content_h_layout = QHBoxLayout()
        self.content_h_layout.setContentsMargins(50, 20, 50, 60)
        self.content_h_layout.setSpacing(60)

        # 2.1 添加左侧账号面板 (你要求的：登录在此显示)
        self.account_panel = AccountPanel(self)
        self.content_h_layout.addWidget(self.account_panel, 0, Qt.AlignmentFlag.AlignVCenter)

        # 2.2 添加右侧功能网格
        self._setup_grid_buttons()

        # 将水平内容区加入总布局
        self.main_v_layout.addLayout(self.content_h_layout, 1)

        # --- 样式应用 ---
        self._apply_styles()

        # --- 启动后台任务 ---
        self._start_wallpaper_load()
        self._start_sentence_load()
        self._start_announcement_load()
        self._start_update_check()

        # 初始化子窗口对象
        self.learn_win = None
        self.review_win = None
        self.test_win = None
        self.setting_win = None

    def _setup_top_bar(self):
        """构建窗口顶部栏：标题、公告、关于、控制按钮"""
        top_bar_widget = QWidget()
        top_bar_widget.setFixedHeight(90)
        layout = QHBoxLayout(top_bar_widget)
        layout.setContentsMargins(40, 30, 40, 0)

        # 标题
        self.title = QLabel("LearnWord")
        self.title.setFont(QFont("MiSans", 32, QFont.Weight.Bold))
        self.title.setStyleSheet("color: white; background: transparent;")
        layout.addWidget(self.title)

        layout.addStretch()

        # 公告、关于、检查更新 (做成小按钮)
        self.btn_announcement = QPushButton("公告")
        self.btn_announcement.clicked.connect(self._on_announcement_clicked)

        self.btn_about = QPushButton("关于")
        self.btn_about.clicked.connect(self._about)

        self.btn_update = QPushButton("检查更新")
        self.btn_update.clicked.connect(self._start_update_check)

        for btn in [self.btn_announcement, self.btn_about, self.btn_update]:
            btn.setFixedSize(80, 32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(btn)

        layout.addSpacing(20)

        # 系统控制
        self.btn_min = QPushButton("－")
        self.btn_min.setFixedSize(32, 32)
        self.btn_min.clicked.connect(self.showMinimized)

        self.btn_close = QPushButton("×")
        self.btn_close.setFixedSize(32, 32)
        self.btn_close.clicked.connect(self.close)

        layout.addWidget(self.btn_min)
        layout.addWidget(self.btn_close)

        self.main_v_layout.addWidget(top_bar_widget)

    def _setup_grid_buttons(self):
        """构建右侧四个功能大按钮"""
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(35)

        self.btn_learn = QPushButton("Learn")
        self.btn_review = QPushButton("Review")
        self.btn_test = QPushButton("Test")
        self.btn_setting = QPushButton("设置")

        # 绑定点击事件
        self.btn_learn.clicked.connect(self.open_learn)
        self.btn_review.clicked.connect(self.open_review)
        self.btn_test.clicked.connect(self.open_test)
        self.btn_setting.clicked.connect(self.open_setting)

        for i, b in enumerate([self.btn_learn, self.btn_review, self.btn_test, self.btn_setting]):
            b.setFixedSize(220, 115)
            b.setFont(QFont("MiSans", 18, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setObjectName(f"mode_btn_{i}")

        grid.addWidget(self.btn_learn, 0, 0)
        grid.addWidget(self.btn_review, 0, 1)
        grid.addWidget(self.btn_test, 1, 0)
        grid.addWidget(self.btn_setting, 1, 1)

        self.content_h_layout.addWidget(grid_widget, 1, Qt.AlignmentFlag.AlignCenter)

    def _apply_styles(self):
        """统一管理主界面 QSS"""
        self.setStyleSheet("""
            QLabel { background: transparent; }
            QPushButton { border: none; border-radius: 12px; color: white; background: rgba(255, 255, 255, 0.08); }
            QPushButton:hover { background: rgba(255, 255, 255, 0.15); }

            /* 功能按钮样式 */
            #mode_btn_0, #mode_btn_1, #mode_btn_2 { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(37, 99, 235, 0.6), stop:1 rgba(29, 78, 216, 0.4)); 
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            #mode_btn_0:hover, #mode_btn_1:hover, #mode_btn_2:hover { background: rgba(37, 99, 235, 0.85); }

            /* 设置按钮样式 */
            #mode_btn_3 { background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); }

            /* 顶部系统按钮 */
            QPushButton[text="－"], QPushButton[text="×"] { background: rgba(255, 255, 255, 0.1); border-radius: 16px; font-size: 18px; }
            QPushButton[text="×"]:hover { background: #e81123; }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.drag_pos:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def _start_wallpaper_load(self):
        self.wp_thread = QThread()
        self.wp_loader = WallpaperLoader()
        self.wp_loader.moveToThread(self.wp_thread)
        self.wp_thread.started.connect(self.wp_loader.run_load)
        self.wp_loader.finished.connect(self._on_wallpaper_loaded)
        self.wp_loader.finished.connect(self.wp_thread.quit)
        self.wp_thread.finished.connect(self.wp_thread.deleteLater)
        self.wp_loader.finished.connect(self.wp_loader.deleteLater)
        self.wp_thread.start()

    @Slot(str)
    def _on_wallpaper_loaded(self, path):
        if path:
            if path.lower().endswith(('.mp4', '.webm', '.mkv')):
                # 如果是视频
                self.central.set_video(path)
            else:
                # 如果是图片
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    self.central.set_wallpaper(pixmap)

    def _start_sentence_load(self):
        self.st_thread = QThread()
        self.st_loader = SentenceLoader()
        self.st_loader.moveToThread(self.st_thread)
        self.st_thread.started.connect(self.st_loader.run_load)
        self.st_loader.finished.connect(self._on_sentence_loaded)
        self.st_loader.finished.connect(self.st_thread.quit)
        self.st_thread.finished.connect(self.st_thread.deleteLater)
        self.st_loader.finished.connect(self.st_loader.deleteLater)
        self.st_thread.start()

    @Slot(str, str)
    def _on_sentence_loaded(self, text, author):
        self.central.set_sentence(text, author)

    def _load_announcement_state(self):
        data_dir = self.model.data_dir
        state_file = os.path.join(data_dir, "announcement_state.json")
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get("read_announcements", []))
            except Exception:
                pass
        return set()

    def _save_announcement_state(self, read_set: set):
        data_dir = self.model.data_dir
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        state_file = os.path.join(data_dir, "announcement_state.json")
        try:
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump({"read_announcements": list(read_set)}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)

    def open_learn(self):
        if self.learn_win is None or not self.learn_win.isVisible():
            self.model.load_progress()
            self.learn_win = LearnWindow(self.model, parent=self)
            self.learn_win.show()
        else:
            self.learn_win.activateWindow()

    def open_review(self):
        if self.review_win is None or not self.review_win.isVisible():
            self.model.load_progress()
            self.review_win = ReviewWindow(self.model, parent=self)
            self.review_win.show()
        else:
            self.review_win.activateWindow()

    def open_test(self):
        if self.test_win is None or not self.test_win.isVisible():
            self.model.load_progress()
            self.test_win = TestWindow(self.model, parent=self)
            self.test_win.show()
        else:
            self.test_win.activateWindow()

    def open_setting(self):
        if self.setting_win is None or not self.setting_win.isVisible():
            self.setting_win = SettingWindow(self.model, parent=self)
            self.setting_win.show()
        else:
            self.setting_win.activateWindow()
        if self.setting_win:
            self.model.load_progress()
            self.setting_win.refresh_view()

    def _about(self):
        about_dialog = AboutDialog(self)
        about_dialog.exec()

    @Slot()
    def _start_update_check(self):
        if self.sender() == self.btn_update:
            self.is_manual_check = True

        self.btn_update.setEnabled(False)
        self.btn_update.setText("检查中...")
        self.update_thread = QThread()
        self.update_worker = UpdateChecker()
        self.update_worker.moveToThread(self.update_thread)
        self.update_thread.started.connect(self.update_worker.run_check)
        self.update_worker.signal_result.connect(self._handle_update_result)
        self.update_worker.signal_result.connect(self.update_thread.quit)
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_worker.signal_result.connect(self.update_worker.deleteLater)
        self.update_thread.start()

    @Slot(bool, object)
    def _handle_update_result(self, success: bool, data_or_error: Any):
        self.btn_update.setEnabled(True)
        self.btn_update.setText("检查更新")
        is_manual = getattr(self, 'is_manual_check', False)

        if not success:
            if is_manual:
                QMessageBox.warning(self, "检查更新失败", str(data_or_error))
            self.is_manual_check = False
            return

        manifest = data_or_error
        latest_version_tag = manifest.get("latest_version", "v0.0.0")
        update_notes = manifest.get("update_notes", [])
        release_date = manifest.get("release_date", "")
        download_url = manifest.get("download_url", "")

        def clean_version(v):
            return str(v).lstrip('v').replace('.', '')

        try:
            if int(clean_version(latest_version_tag)) > int(clean_version(CURRENT_VERSION)):
                # 发现新版本：使用新的 UpdateDialog
                updater_exe = "Updater.exe"
                if getattr(sys, 'frozen', False):
                    updater_exe = os.path.join(os.path.dirname(sys.executable), "Updater.exe")
                else:
                    # 使用 abspath 和 __file__ 确保在源码运行时也能找到同级目录下的 Updater.exe
                    updater_exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Updater.exe")

                updater_exists = os.path.exists(updater_exe)

                # 弹出无边框更新窗口
                dlg = UpdateDialog(CURRENT_VERSION, latest_version_tag, release_date, update_notes, download_url,
                                   updater_exists, self)
                dlg.exec()

                # 处理结果
                # 确保这里逻辑与原始代码一致：如果用户选择了自动更新，就启动 Updater.exe
                if dlg.result_code == 1:  # 自动更新 (推荐)
                    subprocess.Popen([updater_exe])
                    QApplication.quit()
                elif dlg.result_code == 2:  # 手动下载
                    QDesktopServices.openUrl(QUrl(download_url))
            else:
                if is_manual:
                    QMessageBox.information(self, "检查更新", "当前已是最新版本。")
        except ValueError:
            pass
        self.is_manual_check = False

    @Slot()
    def _on_announcement_clicked(self):
        # 1. 只要点了按钮，必须立刻标记为“手动模式”
        # 这样等会线程结束时，才会强制弹出窗口
        self.is_manual_announcement_check = True

        # 2. 立刻把按钮设为“获取中...”，给用户反馈
        self.btn_announcement.setEnabled(False)
        self.btn_announcement.setText("获取中...")

        # 3. 此时再判断：如果已经在加载了（比如自动检查还在跑），就直接蹭它的车
        if self.is_ann_loading:
            # 直接返回，坐等正在跑的那个线程结束
            # 因为第1步已经把标记设为 True 了，所以它结束时会弹窗的
            return

        # 4. 如果当前没在加载，才启动新线程
        self._start_announcement_load()

    @Slot()
    def _start_announcement_load(self):
        self.is_ann_loading = True

        # ★★★ 优化：更安全的旧线程清理 ★★★
        if self.ann_thread is not None:
            try:
                if self.ann_worker is not None:
                    try:
                        self.ann_worker.signal_result.disconnect()
                    except (RuntimeError, TypeError):
                        pass

                if self.ann_thread.isRunning():
                    self.ann_thread.quit()
                    self.ann_thread.wait(1000)  # 等待最多1秒
            except RuntimeError:
                pass
            finally:
                self.ann_thread = None
                self.ann_worker = None

        # 3. 启动新线程 (保持不变)
        self.ann_thread = QThread()
        self.ann_worker = AnnouncementLoader()
        self.ann_worker.moveToThread(self.ann_thread)
        self.ann_thread.started.connect(self.ann_worker.run_load)
        self.ann_worker.signal_result.connect(self._handle_announcement_result)
        self.ann_worker.signal_result.connect(self.ann_thread.quit)
        self.ann_thread.finished.connect(self.ann_thread.deleteLater)
        self.ann_worker.signal_result.connect(self.ann_worker.deleteLater)
        self.ann_thread.start()

    @Slot(bool, object)
    def _handle_announcement_result(self, success: bool, data_or_error: Any):
        # ★★★ 核心：任务结束，释放标志位 ★★★
        self.is_ann_loading = False

        # 恢复按钮状态
        self.btn_announcement.setEnabled(True)
        self.btn_announcement.setText("公告")

        if not success:
            if self.is_manual_announcement_check:
                QMessageBox.warning(self, "获取失败", f"无法获取公告: {data_or_error}")
                self.is_manual_announcement_check = False
            return

        data = data_or_error
        announcements = data.get("announcements", [])

        if self.is_manual_announcement_check:
            if not announcements:
                QMessageBox.information(self, "公告", "暂无任何公告。")
            else:
                dialog = AnnouncementDialog(data, CURRENT_VERSION, self)
                dialog.exec()
            self.is_manual_announcement_check = False
            return

        read_ann_ids = self._load_announcement_state()
        has_unread = False
        for ann in announcements:
            if ann.get("version") != CURRENT_VERSION: continue
            title = ann.get("title", "公告")
            show_mode = ann.get("show_mode", "once")
            ann_id = f"{CURRENT_VERSION}||{title}"
            if show_mode == "always" or (show_mode == "once" and ann_id not in read_ann_ids):
                has_unread = True
                if show_mode == "once":
                    read_ann_ids.add(ann_id)

        if has_unread:
            self._save_announcement_state(read_ann_ids)
            dialog = AnnouncementDialog(data, CURRENT_VERSION, self)
            dialog.exec()


if __name__ == "__main__":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Junpgle.LearnWord")
    except AttributeError:
        pass

    try:
        appdata = os.getenv('APPDATA')
        version_dir = os.path.join(appdata, 'LearnWord', 'data')
        if not os.path.exists(version_dir):
            os.makedirs(version_dir, exist_ok=True)
        version_file = os.path.join(version_dir, "version.txt")
        with open(version_file, "w", encoding="utf-8") as f:
            f.write(CURRENT_VERSION)
    except Exception as e:
        print(f"Warning: Failed to write version file: {e}")

    app = QApplication(sys.argv)

    app_icon_path = get_resource_path("icon.ico")
    if os.path.exists(app_icon_path):
        app.setWindowIcon(QIcon(app_icon_path))

    font_path = get_resource_path("MiSans.ttf")
    font_id = QFontDatabase.addApplicationFont(font_path)
    if font_id != -1:
        font_families = QFontDatabase.applicationFontFamilies(font_id)
        if font_families:
            app.setFont(QFont(font_families[0], 10))

    model = VocabModel()
    model.load_all_data()

    if not model.words:
        QMessageBox.warning(None, "提示", "未找到默认词库，请在设置中手动导入。")

    mw = MainWindow(model)
    mw.show()
    sys.exit(app.exec())
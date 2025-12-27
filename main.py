import sys
import os
import json
import math
import random
import requests
import ctypes
import subprocess
from typing import Any
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLabel, QPushButton, QGridLayout, QHBoxLayout, QMessageBox, QDialog,
    QScrollArea
)
from PySide6.QtCore import Qt, QUrl, QThread, QObject, Signal, Slot, QTimer, QSize, QVariantAnimation, QEasingCurve, \
    QRect
from PySide6.QtGui import (
    QFont, QDesktopServices, QFontDatabase, QIcon, QMovie,
    QPainter, QColor, QRadialGradient, QBrush, QPen, QPalette, QPixmap
)

# 导入你的自定义模块 (确保这些文件在同级目录下)
from vocab_model import VocabModel
from learn_window import LearnWindow
from review_window import ReviewWindow
from test_window import TestWindow
from setting_window import SettingWindow

# 设定当前程序版本号
CURRENT_VERSION = "v1.2.0"
CURRENT_VERSION_DATE = "20251227-2"


# ★★★ 资源路径获取函数 ★★★
def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_path = os.getcwd()
    return os.path.join(base_path, relative_path)


# =================================================================
# 梦幻背景组件 (DreamyBackground) - 支持壁纸渐显和句子展示
# =================================================================
class DreamyBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.wallpaper_pixmap = None
        self.wallpaper_opacity = 0.0  # 壁纸透明度 (0.0 - 1.0)

        self.sentence_text = ""
        self.sentence_author = ""

        # 启动定时器用于梦幻光晕动画刷新
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(33)
        self.time_offset = 0.0

        # 壁纸渐显动画
        self.fade_anim = QVariantAnimation(self)
        self.fade_anim.setDuration(1500)  # 动画时长 1.5秒
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.fade_anim.valueChanged.connect(self._update_opacity)
        self.fade_anim.finished.connect(self._anim_finished)

    def set_wallpaper(self, pixmap):
        """设置壁纸并启动渐显动画"""
        if pixmap and not pixmap.isNull():
            self.wallpaper_pixmap = pixmap
            # 启动渐显动画
            self.fade_anim.start()

    def set_sentence(self, text, author=""):
        """设置底部显示的句子"""
        self.sentence_text = text
        self.sentence_author = author
        self.update()

    @Slot(object)
    def _update_opacity(self, value):
        self.wallpaper_opacity = float(value)
        self.update()

    @Slot()
    def _anim_finished(self):
        # 动画结束后，如果壁纸完全不透明，可以停止光晕计算的Timer以省电
        # 但为了保证文字或者其他动态效果，这里选择不停止，或者降低频率
        # self.timer.stop()
        pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        w = self.width()
        h = self.height()

        # --- 1. 始终绘制梦幻光晕作为底层 (即使有壁纸，淡入时也能看到底色) ---
        # 绘制深色底色
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
            painter.setPen(Qt.NoPen)
            painter.drawRect(self.rect())

        # 绘制三个光团
        x1 = w * 0.2 + math.sin(self.time_offset * 0.5) * 50
        y1 = h * 0.3 + math.cos(self.time_offset * 0.3) * 30
        draw_halo(x1, y1, w * 0.8, QColor(0, 160, 255), 30)

        x2 = w * 0.8 - math.cos(self.time_offset * 0.4) * 50
        y2 = h * 0.8 - math.sin(self.time_offset * 0.6) * 30
        draw_halo(x2, y2, w * 0.9, QColor(180, 40, 250), 25)

        draw_halo(w * 0.5, h * 0.9, w * 0.6, QColor(20, 50, 150), 40)

        # --- 2. 绘制壁纸 (带透明度) ---
        if self.wallpaper_pixmap and not self.wallpaper_pixmap.isNull():
            painter.setOpacity(self.wallpaper_opacity)

            scaled_pixmap = self.wallpaper_pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            px = (w - scaled_pixmap.width()) // 2
            py = (h - scaled_pixmap.height()) // 2
            painter.drawPixmap(px, py, scaled_pixmap)

            # 绘制遮罩 (透明度随壁纸一起变化，保证融合自然)
            # 遮罩稍微深一点，保证文字清晰
            painter.fillRect(self.rect(), QColor(0, 0, 0, int(90 * self.wallpaper_opacity)))

            painter.setOpacity(1.0)  # 重置画笔透明度

        # --- 3. 绘制底部句子 ---
        if self.sentence_text:
            # 字体设置
            font = QFont("MiSans", 12)
            font.setItalic(True)  # 斜体更有感觉
            painter.setFont(font)
            painter.setPen(QColor(240, 240, 240, 200))  # 略微透明的白色

            text_str = f"“ {self.sentence_text} ”"
            if self.sentence_author:
                text_str += f"\n— {self.sentence_author}"

            # 底部区域矩形
            rect = QRect(40, h - 100, w - 80, 80)

            # 绘制文字 (自动换行，居中)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, text_str)


# =================================================================
# 壁纸加载器 (WallpaperLoader)
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

        try:
            api_url = "https://api.github.com/repos/Junpgle/LearnWord/contents/background"
            headers = {"User-Agent": "LearnWord-Client/1.0", "Accept": "application/vnd.github.v3+json"}
            resp = requests.get(api_url, headers=headers, timeout=5)

            if resp.status_code == 200:
                files = resp.json()
                images = [f for f in files if
                          isinstance(f, dict) and f.get('type') == 'file' and f.get('name', '').lower().endswith(
                              ('.jpg', '.jpeg', '.png'))]

                if images:
                    try:
                        with open(cache_list_file, 'w', encoding='utf-8') as f:
                            json.dump(images, f, ensure_ascii=False)
                    except Exception as e:
                        print(f"Failed to write cache: {e}")

                    target = random.choice(images)
                    download_url = target.get('download_url')
                    filename = target.get('name')
            else:
                print(f"API Error: {resp.status_code}. Using fallback...")
        except Exception as e:
            print(f"Network error fetching list: {e}. Using fallback...")

        if not download_url and os.path.exists(cache_list_file):
            try:
                with open(cache_list_file, 'r', encoding='utf-8') as f:
                    cached_images = json.load(f)
                if cached_images:
                    target = random.choice(cached_images)
                    download_url = target.get('download_url')
                    filename = target.get('name')
            except Exception as e:
                print(f"Cache read error: {e}")

        if not download_url:
            idx = random.randint(1, 5)
            filename = f"{idx}.jpg"
            download_url = f"https://raw.githubusercontent.com/Junpgle/LearnWord/master/background/{filename}"

        if download_url and filename:
            save_path = os.path.join(save_dir, filename)
            try:
                if not os.path.exists(save_path):
                    dl_headers = {"User-Agent": "LearnWord-Client/1.0"}
                    img_resp = requests.get(download_url, headers=dl_headers, timeout=15)
                    if img_resp.status_code == 200:
                        with open(save_path, 'wb') as f:
                            f.write(img_resp.content)
                        self.finished.emit(save_path)
                        return
            except Exception as e:
                print(f"Download process error: {e}")

            # 如果本地存在或者下载失败但文件在，尝试返回路径
            if os.path.exists(save_path):
                self.finished.emit(save_path)
                return

        self.finished.emit("")


# =================================================================
# 句子加载器 (SentenceLoader) - 新增
# =================================================================
class SentenceLoader(QObject):
    # 信号：text, author
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

                # 1. 检查是否有强制/显式指定的句子
                # 逻辑：如果 'fixed_sentence' 存在且 'active' 为 True，则显示它
                fixed = data.get("fixed_sentence", {})
                if fixed.get("active") is True:
                    text = fixed.get("text", text)
                    author = fixed.get("author", author)
                else:
                    # 2. 否则从 'pool' 中随机选择
                    pool = data.get("pool", [])
                    if pool:
                        item = random.choice(pool)
                        text = item.get("text", text)
                        author = item.get("author", "")
            else:
                print(f"Sentence API error: {resp.status_code}")

        except Exception as e:
            print(f"Sentence load error: {e}")

        self.finished.emit(text, author)


# =================================================================
# UpdateChecker 和 AnnouncementLoader (逻辑保持不变)
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
# AnnouncementDialog
# =================================================================
class AnnouncementDialog(QDialog):
    def __init__(self, data, current_version, parent=None):
        super().__init__(parent)
        self.setWindowTitle("系统公告")
        self.setFixedSize(600, 450)
        self.setWindowModality(Qt.WindowModality.WindowModal)

        self.all_announcements = data.get("announcements", [])
        self.current_ver = current_version

        self.current_list = [a for a in self.all_announcements if a.get("version") == self.current_ver]
        self.history_list = [a for a in self.all_announcements if a.get("version") != self.current_ver]

        self.setup_ui()
        self.is_showing_history = False
        self.render_content()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # 顶部：图标 + 标题
        top_layout = QHBoxLayout()
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(64, 64)
        self.icon_label.setScaledContents(True)
        self.icon_label.setStyleSheet("background: transparent;")

        gif_filename = "Announcement.gif"
        gif_path = get_resource_path(os.path.join("Animation", gif_filename))
        if not os.path.exists(gif_path):
            gif_path = r"D:\Python code\LearnWord\Animation\Announcement.gif"

        if os.path.exists(gif_path):
            self.movie = QMovie(gif_path)
            self.movie.setCacheMode(QMovie.CacheMode.CacheAll)
            self.icon_label.setMovie(self.movie)
            self.movie.start()
        else:
            self.icon_label.setText("📢")
            self.icon_label.setStyleSheet("font-size: 40px; color: yellow; background: transparent;")

        title_layout = QVBoxLayout()
        self.main_title = QLabel("最新动态")
        self.main_title.setFont(QFont("MiSans", 18, QFont.Weight.Bold))
        self.main_title.setStyleSheet("color: white; background: transparent;")

        self.sub_title = QLabel(f"Version {self.current_ver}")
        self.sub_title.setFont(QFont("MiSans", 12))
        self.sub_title.setStyleSheet("color: #aaaaaa; background: transparent;")

        title_layout.addWidget(self.main_title)
        title_layout.addWidget(self.sub_title)

        top_layout.addWidget(self.icon_label)
        top_layout.addSpacing(15)
        top_layout.addLayout(title_layout)
        top_layout.addStretch()

        # 中间：内容
        self.content_browser = QLabel()
        self.content_browser.setWordWrap(True)
        self.content_browser.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.content_browser.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.content_browser.setOpenExternalLinks(True)
        self.content_browser.setStyleSheet("color: #dddddd; font-size: 14px; padding: 10px; background: transparent;")

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.content_browser)
        self.scroll_area.setStyleSheet("""
            QScrollArea { border: 1px solid #333; background-color: rgba(30, 30, 30, 0.8); border-radius: 8px; }
            QWidget { background-color: transparent; }
            QScrollBar:vertical { background: #222; width: 8px; }
            QScrollBar::handle:vertical { background: #555; border-radius: 4px; }
        """)

        # 底部：按钮
        btn_layout = QHBoxLayout()
        self.toggle_btn = QPushButton("查看历史公告")
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.setFixedSize(120, 35)
        self.toggle_btn.clicked.connect(self.toggle_view)

        close_btn = QPushButton("关闭")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFixedSize(80, 35)
        close_btn.clicked.connect(self.accept)

        for btn in [self.toggle_btn, close_btn]:
            btn.setStyleSheet("""
                QPushButton { background-color: #374151; color: white; border: none; border-radius: 6px; font-weight: bold; }
                QPushButton:hover { background-color: #4b5563; }
            """)
        self.toggle_btn.setStyleSheet("""
            QPushButton { background-color: #0969da; color: white; border: none; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background-color: #0757b7; }
        """)

        btn_layout.addStretch()
        btn_layout.addWidget(self.toggle_btn)
        btn_layout.addSpacing(10)
        btn_layout.addWidget(close_btn)

        layout.addLayout(top_layout)
        layout.addWidget(self.scroll_area)
        layout.addLayout(btn_layout)

        self.setStyleSheet("QDialog { background-color: #121212; border: 1px solid #333333; }")

    def render_content(self):
        target_list = self.history_list if self.is_showing_history else self.current_list
        if not target_list:
            html = "<div style='text-align:center; margin-top:50px; color:#888;'>无相关公告内容</div>"
        else:
            html = ""
            for item in target_list:
                ver = item.get("version", "")
                title = item.get("title", "无标题")
                content = item.get("content", "").replace("\n", "<br>")
                ver_tag = f"<span style='color: #3498db; font-weight:bold; font-size:12px;'>[{ver}]</span> " if self.is_showing_history else ""

                html += f"""
                <div style='margin-bottom: 20px;'>
                    <div style='font-size: 16px; font-weight: bold; color: #ffffff; margin-bottom: 8px;'>{ver_tag}{title}</div>
                    <div style='font-size: 14px; color: #cccccc; line-height: 1.6;'>{content}</div>
                    <hr style='border: 0; border-bottom: 1px solid #444; margin-top: 15px; margin-bottom: 15px;'>
                </div>"""

        self.content_browser.setText(html)
        if self.is_showing_history:
            self.main_title.setText("历史公告")
            self.sub_title.setText("Previous Updates")
            self.toggle_btn.setText("返回当前版本")
        else:
            self.main_title.setText("最新动态")
            self.sub_title.setText(f"Version {self.current_ver}")
            self.toggle_btn.setText("查看历史公告")

    def toggle_view(self):
        self.is_showing_history = not self.is_showing_history
        self.render_content()
        self.scroll_area.verticalScrollBar().setValue(0)


# =================================================================
# AboutDialog 类
# =================================================================
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 LearnWord")
        self.setFixedSize(600, 300)
        self.setWindowModality(Qt.WindowModality.WindowModal)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        title_label = QLabel("LearnWord")
        title_label.setFont(QFont("MiSans", 20, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: white; margin-top: 20px; background: transparent;")

        version_label = QLabel(f"版本: {CURRENT_VERSION}\n构建日期:{CURRENT_VERSION_DATE}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #cccccc; font-size: 14px; margin-top: 5px; background: transparent;")

        author_label = QLabel("作者: Junpgle")
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author_label.setStyleSheet("color: #cccccc; font-size: 14px; margin-top: 5px; background: transparent;")

        desc_label = QLabel("一款轻量级英语词汇学习工具，\n支持学习、复习、测试与进度管理。")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("color: #aaaaaa; font-size: 13px; margin: 15px 0; background: transparent;")

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        website_button = QPushButton("访问展示网页")
        website_button.setCursor(Qt.CursorShape.PointingHandCursor)
        website_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://junpgle.github.io/LearnWord/")))

        github_button = QPushButton("项目主页 (GitHub)")
        github_button.setCursor(Qt.CursorShape.PointingHandCursor)
        github_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/Junpgle/LearnWord")))

        close_button = QPushButton("关闭")
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(website_button)
        btn_layout.addWidget(github_button)
        btn_layout.addWidget(close_button)
        btn_layout.addStretch()

        layout.addWidget(title_label)
        layout.addWidget(version_label)
        layout.addWidget(author_label)
        layout.addWidget(desc_label)
        layout.addSpacing(20)
        layout.addLayout(btn_layout)
        layout.addSpacing(10)

        self.setStyleSheet("""
            QDialog { background-color: #121212; border: 1px solid #333333; }
            QPushButton { padding: 8px 12px; border-radius: 6px; font-weight: bold; background-color: #374151; color: white; }
            QPushButton:hover { background-color: #4b5563; }
        """)


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

        self.central = DreamyBackground(self)
        self.setCentralWidget(self.central)

        self.is_manual_check = False
        self.is_manual_announcement_check = False

        self.layout = QVBoxLayout(self.central)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # 1. 顶部栏
        top_bar_layout = QHBoxLayout()
        top_bar_layout.addSpacing(20)

        self.title = QLabel("LearnWord")
        self.title.setFont(QFont("MiSans", 34, QFont.Weight.Bold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet("background-color: transparent; color: #ffffff;")

        top_bar_layout.addWidget(self.title)
        top_bar_layout.addStretch()

        # 顶部小按钮
        self.btn_announcement = QPushButton("公告")
        self.btn_announcement.setObjectName("ann_btn")
        self.btn_announcement.clicked.connect(self._on_announcement_clicked)

        self.btn_about = QPushButton("关于")
        self.btn_about.setObjectName("about_btn")
        self.btn_about.clicked.connect(self._about)

        self.btn_update = QPushButton("检查更新")
        self.btn_update.setObjectName("update_check_btn")
        self.btn_update.clicked.connect(self._start_update_check)

        for btn in [self.btn_announcement, self.btn_about, self.btn_update]:
            btn.setFixedSize(90, 40)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_update.setFixedSize(100, 40)

        top_bar_layout.addWidget(self.btn_announcement)
        top_bar_layout.addWidget(self.btn_about)
        top_bar_layout.addWidget(self.btn_update)
        top_bar_layout.addSpacing(20)

        self.layout.addLayout(top_bar_layout)
        self.layout.addSpacing(30)
        self.layout.addStretch(1)

        # 2. 功能按钮网格
        grid = QGridLayout()
        grid.setSpacing(40)

        self.btn_learn = QPushButton("Learn")
        self.btn_review = QPushButton("Review")
        self.btn_test = QPushButton("Test")
        self.btn_setting = QPushButton("设置")

        for b in [self.btn_learn, self.btn_review, self.btn_test, self.btn_setting]:
            b.setFixedSize(200, 100)
            b.setFont(QFont("MiSans", 16, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setObjectName(f"mode_btn_{b.text().lower()}")

        grid.addWidget(self.btn_learn, 0, 0)
        grid.addWidget(self.btn_review, 0, 1)
        grid.addWidget(self.btn_test, 1, 0)
        grid.addWidget(self.btn_setting, 1, 1)

        grid_container = QHBoxLayout()
        grid_container.addStretch()
        grid_container.addLayout(grid)
        grid_container.addStretch()

        self.layout.addLayout(grid_container)
        self.layout.addStretch(1)

        self.learn_win = None
        self.review_win = None
        self.test_win = None
        self.setting_win = None

        self.btn_learn.clicked.connect(self.open_learn)
        self.btn_review.clicked.connect(self.open_review)
        self.btn_test.clicked.connect(self.open_test)
        self.btn_setting.clicked.connect(self.open_setting)

        self.center_on_screen()

        self.central.setStyleSheet("""
            /* 移除 QWidget 的纯黑背景，由 paintEvent 接管 */

            /* 标签：必须透明，否则会有黑框 */
            QLabel { color: #ffffff; background-color: transparent; }

            /* 按钮通用样式 */
            QPushButton {
                border: none; border-radius: 18px; font-weight: 700;
                /* 轻微的阴影 */
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3); 
            }

            /* 大按钮：带有半透明效果，让光晕透过来一点 (玻璃质感) */
            #mode_btn_learn, #mode_btn_review, #mode_btn_test { 
                background-color: rgba(0, 120, 215, 0.85); /* 蓝色半透明 */
                color: white; 
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            #mode_btn_learn:hover, #mode_btn_review:hover, #mode_btn_test:hover { 
                background-color: rgba(51, 154, 240, 0.95); /* 高亮时更不透明 */
            }

            #mode_btn_设置 { 
                background-color: rgba(149, 165, 166, 0.85); 
                color: white; 
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
            #mode_btn_设置:hover { 
                background-color: rgba(127, 140, 141, 0.95); 
            }

            /* 顶部小按钮样式 */
            #update_check_btn { background-color: rgba(231, 76, 60, 0.9); color: white; border-radius: 10px; font-size: 14px; }
            #update_check_btn:hover { background-color: #c0392b; }

            #about_btn { background-color: rgba(255, 165, 0, 0.9); color: white; border-radius: 10px; font-size: 14px; }
            #about_btn:hover { background-color: #e69500; }

            #ann_btn { background-color: rgba(46, 204, 113, 0.9); color: white; border-radius: 10px; font-size: 14px; }
            #ann_btn:hover { background-color: #27ae60; }
        """)

        # 启动后台任务：壁纸加载
        self._start_wallpaper_load()
        # 启动后台任务：句子加载
        self._start_sentence_load()
        # 启动后台任务：公告和更新
        self._start_announcement_load()
        self._start_update_check()

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
        except Exception as e:
            print(f"保存公告状态失败: {e}")

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
                updater_exe = "Updater.exe"
                if getattr(sys, 'frozen', False):
                    updater_exe = os.path.join(os.path.dirname(sys.executable), "Updater.exe")
                else:
                    updater_exe = os.path.join(os.getcwd(), "Updater.exe")

                updater_exists = os.path.exists(updater_exe)
                notes_text = "\n- " + "\n- ".join(update_notes)

                msg = QMessageBox(self)
                msg.setWindowTitle("发现新版本")
                msg.setIcon(QMessageBox.Icon.Information)
                msg.setText(f"发现新版本：{CURRENT_VERSION} -> {latest_version_tag}")
                msg.setInformativeText(f"更新日期: {release_date}\n\n更新内容：\n{notes_text}")

                if updater_exists:
                    auto_update_btn = msg.addButton("立即更新 (推荐)", QMessageBox.ButtonRole.AcceptRole)
                    manual_update_btn = msg.addButton("手动下载", QMessageBox.ButtonRole.ActionRole)
                    msg.addButton("取消", QMessageBox.ButtonRole.RejectRole)
                    msg.exec()
                    if msg.clickedButton() == auto_update_btn:
                        subprocess.Popen([updater_exe])
                        QApplication.quit()
                    elif msg.clickedButton() == manual_update_btn:
                        QDesktopServices.openUrl(QUrl(download_url))
                else:
                    dl_btn = QPushButton("前往下载")
                    dl_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(download_url)))
                    msg.addButton(dl_btn, QMessageBox.ButtonRole.AcceptRole)
                    msg.addButton(QPushButton("取消"), QMessageBox.ButtonRole.RejectRole)
                    msg.exec()
            else:
                if is_manual:
                    QMessageBox.information(self, "检查更新", "当前已是最新版本。")
        except ValueError:
            pass
        self.is_manual_check = False

    @Slot()
    def _on_announcement_clicked(self):
        self.is_manual_announcement_check = True
        self.btn_announcement.setEnabled(False)
        self.btn_announcement.setText("获取中...")
        self._start_announcement_load()

    @Slot()
    def _start_announcement_load(self):
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
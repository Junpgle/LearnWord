import sys
import os
import json
import requests
import ctypes  # ★★★ 新增：用于修复 Windows 任务栏图标显示
from typing import Any  # ★★★ 新增：用于类型标注，解决 object 无 get 方法的警告
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLabel, QPushButton, QGridLayout, QHBoxLayout, QMessageBox, QDialog
)
from PySide6.QtCore import Qt, QUrl, QThread, QObject, Signal, Slot
from PySide6.QtGui import QFont, QDesktopServices, QFontDatabase, QIcon  # ★★★ 新增：QIcon

from vocab_model import VocabModel
from learn_window import LearnWindow
from review_window import ReviewWindow
from test_window import TestWindow
from setting_window import SettingWindow

# 设定当前程序版本号
CURRENT_VERSION = "v1.1.0"
CURRENT_VERSION_DATE = "20251226-2"


# ★★★ 资源路径获取函数 (用于加载字体和图标) ★★★
def get_resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_path = os.getcwd()

    # 针对某些打包配置，尝试补全 _internal 路径
    full_path = os.path.join(base_path, relative_path)
    return full_path


# =================================================================
# UpdateChecker 和 AnnouncementLoader 保持不变
# =================================================================
class UpdateChecker(QObject):
    signal_result = Signal(bool, object)

    def run_check(self):
        manifest_url = "https://raw.githubusercontent.com/Junpgle/LearnWord/refs/heads/master/update_manifest.json"
        try:
            response = requests.get(manifest_url, timeout=5)
            response.raise_for_status()
            manifest = response.json()
            self.signal_result.emit(True, manifest)
        except Exception as e:
            self.signal_result.emit(False, str(e))


class AnnouncementLoader(QObject):
    signal_result = Signal(bool, object)

    def run_load(self):
        url = "https://raw.githubusercontent.com/Junpgle/LearnWord/refs/heads/master/announcement.json"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            self.signal_result.emit(True, data)
        except Exception as e:
            self.signal_result.emit(False, str(e))


# =================================================================
# AboutDialog 类
# =================================================================
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 LearnWord")
        self.setFixedSize(400, 300)
        self.setWindowModality(Qt.WindowModality.WindowModal)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        title_label = QLabel("LearnWord")
        title_label.setFont(QFont("MiSans", 20, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: white; margin-top: 20px;")

        version_label = QLabel(f"版本: {CURRENT_VERSION}\n构建日期:{CURRENT_VERSION_DATE}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #cccccc; font-size: 14px; margin-top: 5px;")

        author_label = QLabel("作者: Junpgle")
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        author_label.setStyleSheet("color: #cccccc; font-size: 14px; margin-top: 5px;")

        desc_label = QLabel("一款轻量级英语词汇学习工具，\n支持学习、复习、测试与进度管理。")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("color: #aaaaaa; font-size: 13px; margin: 15px 0;")

        github_button = QPushButton("访问项目主页 (GitHub)")
        github_button.setObjectName("github_btn")
        github_button.clicked.connect(self._open_github)

        close_button = QPushButton("关闭")
        close_button.setObjectName("close_button")
        close_button.clicked.connect(self.accept)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(github_button)
        btn_layout.addWidget(close_button)
        btn_layout.addStretch()

        layout.addWidget(title_label)
        layout.addWidget(version_label)
        layout.addWidget(author_label)
        layout.addWidget(desc_label)
        layout.addLayout(btn_layout)

        self.setStyleSheet("""
            QDialog { background-color: #000000; border: 1px solid #333333; }
            QLabel { color: white; }
            QPushButton { padding: 8px 16px; border-radius: 6px; font-weight: bold; }
            #github_btn { background-color: #0969da; color: white; }
            #github_btn:hover { background-color: #0757b7; }
            #close_button{ background-color: #0757b7; color: white; }
            #close_button:hover { background-color: #D3D3D3; }
        """)

    @staticmethod
    def _open_github():
        QDesktopServices.openUrl(QUrl("https://github.com/Junpgle/LearnWord"))


# =================================================================
# 主窗口类
# =================================================================
class MainWindow(QMainWindow):
    def __init__(self, model: VocabModel):
        super().__init__()
        self.model = model
        self.setWindowTitle("LearnWord")
        self.setFixedSize(1000, 700)

        # ★★★ 新增：设置窗口图标 ★★★
        icon_path = get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        # ==========================

        self.central = QWidget()
        self.setCentralWidget(self.central)

        # 标志位：判断是否是用户手动点击的更新检查
        self.is_manual_check = False

        self.layout = QVBoxLayout(self.central)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # 1. 顶部栏
        top_bar_layout = QHBoxLayout()
        top_bar_layout.addSpacing(20)

        self.title = QLabel("LearnWord")
        self.title.setFont(QFont("MiSans", 34, QFont.Weight.Bold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        top_bar_layout.addWidget(self.title)
        top_bar_layout.addStretch()

        self.btn_about = QPushButton("关于")
        self.btn_about.setObjectName("about_btn")
        self.btn_about.clicked.connect(self._about)
        self.btn_about.setFixedSize(100, 40)
        top_bar_layout.addWidget(self.btn_about)

        self.btn_update = QPushButton("检查更新")
        self.btn_update.setObjectName("update_check_btn")
        self.btn_update.clicked.connect(self._start_update_check)
        self.btn_update.setFixedSize(100, 40)
        top_bar_layout.addWidget(self.btn_update)

        top_bar_layout.addSpacing(20)
        self.layout.addLayout(top_bar_layout)

        self.layout.addSpacing(30)
        self.layout.addStretch(1)

        # Grid
        grid = QGridLayout()
        grid.setSpacing(40)

        self.btn_learn = QPushButton("Learn")
        self.btn_review = QPushButton("Review")
        self.btn_test = QPushButton("Test")
        self.btn_setting = QPushButton("设置")

        for b in [self.btn_learn, self.btn_review, self.btn_test, self.btn_setting]:
            b.setFixedSize(200, 100)
            b.setFont(QFont("MiSans", 16, QFont.Weight.Bold))
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

        # Windows
        self.learn_win = None
        self.review_win = None
        self.test_win = None
        self.setting_win = None

        self.btn_learn.clicked.connect(self.open_learn)
        self.btn_review.clicked.connect(self.open_review)
        self.btn_test.clicked.connect(self.open_test)
        self.btn_setting.clicked.connect(self.open_setting)

        self.center_on_screen()

        # Stylesheet
        self.central.setStyleSheet("""
            QWidget { background-color: #000000; }
            QLabel { color: #ffffff; }
            QPushButton {
                padding: 10px 20px; border: none; border-radius: 18px; font-weight: 700;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.5); transition: background-color 0.3s, box-shadow 0.3s;
            }
            #mode_btn_learn, #mode_btn_review, #mode_btn_test { background-color: #0078d7; color: white; }
            #mode_btn_learn:hover, #mode_btn_review:hover, #mode_btn_test:hover { background-color: #339af0; }
            #mode_btn_设置 { background-color: #95a5a6; color: white; }
            #mode_btn_设置:hover { background-color: #7f8c8d; }
            #update_check_btn { padding: 5px 10px; font-size: 14px; font-weight: 500; background-color: #e74c3c; color: white; border-radius: 10px; box-shadow: none; }
            #update_check_btn:hover { background-color: #c0392b; }
            #about_btn { padding: 5px 10px; font-size: 14px; font-weight: 500; background-color: #FFA500; color: white; border-radius: 10px; box-shadow: none; }
            #about_btn:hover { background-color: #c0392b; }
        """)

        # 启动后台任务 (自动检查)
        self._start_announcement_load()
        # 自动检查时，不认为是手动点击
        self.is_manual_check = False
        self._start_update_check()

    def _load_announcement_state(self):
        # 使用 model.data_dir 确保状态文件在正确位置
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
        # 判断调用者是否为按钮 (如果不是按钮调用的，比如是 __init__ 里的自动检查，sender() 为 None 或其他)
        if self.sender() == self.btn_update:
            self.is_manual_check = True
        # 注意：这里不需要 else: is_manual_check = False
        # 因为 __init__ 里已经显式调用了一次并手动设为了 False
        # 如果是其他地方调用（未来扩展），默认不会改变状态

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

    # 使用 Any 替换 object，解决 'object' 没有 'get' 方法的 IDE 警告
    @Slot(bool, object)
    def _handle_update_result(self, success: bool, data_or_error: Any):
        self.btn_update.setEnabled(True)
        self.btn_update.setText("检查更新")

        # 使用类变量判断是否是手动检查
        is_manual = getattr(self, 'is_manual_check', False)

        if not success:
            if is_manual:  # 只在手动点击时报错
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
                notes_text = "\n- " + "\n- ".join(update_notes)
                msg = QMessageBox(self)
                msg.setWindowTitle("发现新版本")
                msg.setIcon(QMessageBox.Icon.Information)
                msg.setText(f"发现新版本：{CURRENT_VERSION} -> {latest_version_tag}")
                msg.setInformativeText(f"更新日期:{release_date}\n\n更新内容：\n{notes_text}")
                dl_btn = QPushButton("前往下载")
                dl_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(download_url)))
                msg.addButton(dl_btn, QMessageBox.ButtonRole.AcceptRole)
                msg.addButton(QPushButton("取消"), QMessageBox.ButtonRole.RejectRole)
                msg.exec()
            else:
                if is_manual:  # 只在手动点击时提示最新
                    QMessageBox.information(self, "检查更新", "当前已是最新版本。")
        except ValueError:
            pass

        # 重置状态，防止自动检查的后续操作误判
        self.is_manual_check = False

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

    # 使用 Any 替换 object，解决 'object' 没有 'get' 方法的 IDE 警告
    @Slot(bool, object)
    def _handle_announcement_result(self, success: bool, data_or_error: Any):
        if not success: return

        announcements = data_or_error.get("announcements", [])
        read_ann_ids = self._load_announcement_state()

        for ann in announcements:
            if ann.get("version") != CURRENT_VERSION: continue
            title = ann.get("title", "公告")
            content = ann.get("content", "")
            show_mode = ann.get("show_mode", "once")
            ann_id = f"{CURRENT_VERSION}||{title}"

            if show_mode == "always" or (show_mode == "once" and ann_id not in read_ann_ids):
                QMessageBox.information(self, title, content)
                if show_mode == "once":
                    read_ann_ids.add(ann_id)
                    self._save_announcement_state(read_ann_ids)

if __name__ == "__main__":
    # ★★★ 强制 Windows 使用独立图标，解决任务栏图标显示为 Python 的问题 ★★★
    try:
        # 这里的字符串 ID 可以随意定义，但要保证唯一
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Junpgle.LearnWord.v1.0.8")
    except AttributeError:
        pass

    app = QApplication(sys.argv)

    # ★★★ 3. 设置应用程序全局图标 ★★★
    app_icon_path = get_resource_path("icon.ico")
    if os.path.exists(app_icon_path):
        app.setWindowIcon(QIcon(app_icon_path))
    else:
        print(f"⚠️ Warning: Application icon not found at {app_icon_path}")

    # ★★★ 2. 加载字体 ★★★
    font_path = get_resource_path("MiSans.ttf")
    font_id = QFontDatabase.addApplicationFont(font_path)
    if font_id != -1:
        font_families = QFontDatabase.applicationFontFamilies(font_id)
        if font_families:
            default_font = QFont(font_families[0], 10)
            app.setFont(default_font)
            print(f"Loaded font: {font_families[0]}")
    else:
        print(f"Failed to load font: {font_path}")

    model = VocabModel()
    model.load_all_data()  # 加载数据

    # 如果没有任何数据，提示错误
    if not model.words:
        QMessageBox.warning(None, "提示", "未找到默认词库，请在设置中手动导入。")

    mw = MainWindow(model)
    mw.show()
    sys.exit(app.exec())
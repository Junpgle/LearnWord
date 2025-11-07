import sys, os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QLabel, QPushButton, QGridLayout, QHBoxLayout, QMessageBox
)
# ✅ 修改：导入 QThread 和 Signal/Slot 机制所需的 QObject, Signal, Slot
from PySide6.QtCore import Qt, QPropertyAnimation, QRect, QUrl, QThread, QObject, Signal, Slot
from PySide6.QtGui import QFont, QDesktopServices
# ✅ 新增：导入 json 库用于解析远程更新清单
import json
import requests
# 假设 vocab_model 存在
from vocab_model import VocabModel  # , WordItem
from learn_window import LearnWindow
from review_window import ReviewWindow
from test_window import TestWindow
from setting_window import SettingWindow

# 设定当前程序版本号
CURRENT_VERSION = "v1.0.7"
CURRENT_VERSION_DATE = "20251107"


# =================================================================
# 1. 后台线程类：执行网络请求，保持 GUI 响应性
# =================================================================
class UpdateChecker(QObject):
    # 定义信号，用于通知主线程检查结果
    # signal_result: (success: bool, data: dict or error_message: str)
    signal_result = Signal(bool, object)

    def run_check(self):
        """执行检查更新的网络请求和数据处理"""
        manifest_url = "https://raw.githubusercontent.com/Junpgle/LearnWord/refs/heads/master/update_manifest.json"

        try:
            # 实际网络请求，设置超时 5 秒
            response = requests.get(manifest_url, timeout=5)
            response.raise_for_status()  # 对 4xx 或 5xx 状态码抛出异常

            # 解析 JSON 响应
            manifest = response.json()
            # 成功后发射信号，附带版本数据
            self.signal_result.emit(True, manifest)

        except requests.exceptions.RequestException as e:
            # 网络错误或HTTP错误
            self.signal_result.emit(False, f"无法获取更新信息。\n请检查您的网络连接或 URL 是否正确。\n错误: {e}")
        except json.JSONDecodeError:
            # JSON 解析错误
            self.signal_result.emit(False, "远程更新清单格式错误，无法解析。")
        except Exception as e:
            # 其他错误
            self.signal_result.emit(False, f"处理版本信息时发生未知错误。\n错误: {e}")

# =================================================================
# 2. 后台线程类：加载公告内容
# =================================================================
class AnnouncementLoader(QObject):
    signal_result = Signal(bool, object)  # (success, data or error_msg)

    def run_load(self):
        url = "https://raw.githubusercontent.com/Junpgle/LearnWord/refs/heads/master/announcement.json"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            self.signal_result.emit(True, data)
        except Exception as e:
            self.signal_result.emit(False, f"加载公告失败：{e}")

# =================================================================
# 3. 主窗口类：MainWindow
# =================================================================
class MainWindow(QMainWindow):
    def __init__(self, model: VocabModel):
        super().__init__()
        self.model = model
        self.setWindowTitle("LearnWord")
        self.setFixedSize(1000, 700)
        self.central = QWidget()
        self.setCentralWidget(self.central)

        # 主垂直布局，用于组织所有内容
        self.layout = QVBoxLayout(self.central)
        # 将布局内容整体居中，并保持对齐方式
        self.layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # ----------------------------------------------------
        # 1. 顶部栏 (包含标题和检查更新按钮)
        top_bar_layout = QHBoxLayout()

        # 顶部栏左侧间距（抵消主布局的 AlignTop | AlignHCenter 影响）
        top_bar_layout.addSpacing(20)

        # 1.1 程序标题
        self.title = QLabel("LearnWord")
        self.title.setFont(QFont("MiSans", 34, QFont.Bold))
        self.title.setAlignment(Qt.AlignCenter)

        # 1.2 标题占位（左侧）
        top_bar_layout.addWidget(self.title)
        top_bar_layout.addStretch()  # 伸缩项推开内容到右上角


        # 1.3 关于按钮
        self.btn_about = QPushButton("关于")
        self.btn_about.setObjectName("about_btn")
        self.btn_about.clicked.connect(self._about)
        self.btn_about.setFixedSize(100, 40)  # 设置一个固定大小
        top_bar_layout.addWidget(self.btn_about)

        # 1.4 检查更新按钮 (位于右上角)
        self.btn_update = QPushButton("检查更新")
        self.btn_update.setObjectName("update_check_btn")
        # 将按钮连接到新的启动线程的槽
        self.btn_update.clicked.connect(self._start_update_check)
        self.btn_update.setFixedSize(100, 40)  # 设置一个固定大小
        top_bar_layout.addWidget(self.btn_update)

        # 顶部栏右侧间距
        top_bar_layout.addSpacing(20)

        self.layout.addLayout(top_bar_layout)
        # ----------------------------------------------------

        self.layout.addSpacing(30)

        # 添加垂直弹簧，将所有内容向下推动 (现在用于将网格推到中央)
        self.layout.addStretch(1)

        # grid: 按钮网格布局
        grid = QGridLayout()
        grid.setSpacing(40)

        # buttons
        self.btn_learn = QPushButton("Learn");
        self.btn_review = QPushButton("Review")
        self.btn_test = QPushButton("Test");
        self.btn_setting = QPushButton("设置")

        # 统一设置按钮样式
        for b in [self.btn_learn, self.btn_review, self.btn_test, self.btn_setting]:
            b.setFixedSize(200, 100)
            b.setFont(QFont("MiSans", 16, QFont.Bold))
            # 设置对象名，用于QSS区分样式
            b.setObjectName(f"mode_btn_{b.text().lower()}")

        # 将按钮添加到网格布局
        grid.addWidget(self.btn_learn, 0, 0)
        grid.addWidget(self.btn_review, 0, 1)
        grid.addWidget(self.btn_test, 1, 0)
        grid.addWidget(self.btn_setting, 1, 1)

        # 创建一个居中的 QHBoxLayout 来放置 Grid
        grid_container = QHBoxLayout()
        grid_container.addStretch()
        grid_container.addLayout(grid)
        grid_container.addStretch()

        # 将居中后的网格布局添加到主布局
        self.layout.addLayout(grid_container)

        # 在内容底部也添加一个垂直弹簧
        self.layout.addStretch(1)

        # child windows placeholders
        self.learn_win = None;
        self.review_win = None;
        self.test_win = None;
        self.setting_win = None

        # connections
        self.btn_learn.clicked.connect(self.open_learn)
        self.btn_review.clicked.connect(self.open_review)
        self.btn_test.clicked.connect(self.open_test)
        self.btn_setting.clicked.connect(self.open_setting)

        # center on screen
        self.center_on_screen()

        # ----------------------------------------------------
        # 3. 样式表 (统一 QSS 样式)
        self.central.setStyleSheet("""
            QWidget {
                background-color: #000000; /* 黑色背景 */
            }

            QLabel {
                color: #ffffff; /* 白色文字 */
            }

            /* 模式按钮基础样式 */
            QPushButton {
                padding: 10px 20px;
                border: none;
                border-radius: 18px;
                font-weight: 700;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.5); /* 黑色背景下阴影更明显 */
                transition: background-color 0.3s, box-shadow 0.3s;
            }

            /* 主要按钮样式 (Learn, Review, Test) */
            #mode_btn_learn, #mode_btn_review, #mode_btn_test {
                background-color: #0078d7; 
                color: white;
            }
            #mode_btn_learn:hover, #mode_btn_review:hover, #mode_btn_test:hover {
                background-color: #339af0;
            }

            /* 设置按钮样式 */
            #mode_btn_设置 {
                background-color: #95a5a6; 
                color: white;
            }
            #mode_btn_设置:hover {
                background-color: #7f8c8d;
            }

            /* 检查更新按钮样式 (右上角) */
            #update_check_btn {
                padding: 5px 10px;
                font-size: 14px;
                font-weight: 500;
                background-color: #e74c3c; /* 红色 */
                color: white;
                border-radius: 10px;
                box-shadow: none;
            }
            #update_check_btn:hover {
                background-color: #c0392b;
            }
            
            
            /* 关于按钮样式 (右上角) */
            #about_btn {
                padding: 5px 10px;
                font-size: 14px;
                font-weight: 500;
                background-color: #FFA500; /* 橙色 */
                color: white;
                border-radius: 10px;
                box-shadow: none;
            }
            #about_btn:hover {
                background-color: #c0392b;
            }
        """)
        # ----------------------------------------------------

        # 在初始化结束时自动获取公告和检查更新
        self._start_announcement_load()
        self._start_update_check()

    def _load_announcement_state(self):
        """从本地文件加载已读公告 ID 列表"""
        state_file = "data/announcement_state.json"
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get("read_announcements", []))
            except Exception:
                pass
        return set()

    def _save_announcement_state(self, read_set: set):
        """保存已读公告 ID 到本地文件"""
        state_file = "data/announcement_state.json"
        try:
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump({"read_announcements": list(read_set)}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存公告状态失败: {e}")

    def center_on_screen(self):
        """将主窗口移动到屏幕中央"""
        screen = QApplication.primaryScreen().availableGeometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)

    def open_learn(self):
        """打开学习窗口"""
        if self.learn_win is None or not self.learn_win.isVisible():
            # 每次打开前加载最新进度，确保学习数据是最新的
            self.model.load_progress()
            self.learn_win = LearnWindow(self.model, parent=self)
            self.learn_win.show()
        else:
            self.learn_win.activateWindow()

    def open_review(self):
        """打开复习窗口"""
        if self.review_win is None or not self.review_win.isVisible():
            # 每次打开前加载最新进度
            self.model.load_progress()
            self.review_win = ReviewWindow(self.model, parent=self)
            self.review_win.show()
        else:
            self.review_win.activateWindow()

    def open_test(self):
        """打开测试窗口"""
        if self.test_win is None or not self.test_win.isVisible():
            # 每次打开前加载最新进度
            self.model.load_progress()
            self.test_win = TestWindow(self.model, parent=self)
            self.test_win.show()
        else:
            self.test_win.activateWindow()

    def open_setting(self):
        """打开设置窗口，并强制刷新进度显示"""
        if self.setting_win is None or not self.setting_win.isVisible():
            self.setting_win = SettingWindow(self.model, parent=self)
            self.setting_win.show()
        else:
            self.setting_win.activateWindow()

        if self.setting_win:
            # 步骤 1: 强制模型加载 TestWindow 刚刚保存的最新状态
            # 确保进度条能显示最新的测试结果
            self.model.load_progress()

            # 步骤 2: 刷新设置窗口，显示新状态
            self.setting_win.refresh_view()

    def _about(self):
        about_dialog = AboutDialog(self)
        about_dialog.exec()

    # 启动后台检查线程的槽函数
    @Slot()
    def _start_update_check(self):
        # 禁用按钮，避免重复点击
        self.btn_update.setEnabled(False)
        self.btn_update.setText("检查中...")

        # 1. 创建 QThread 实例
        self.update_thread = QThread()
        # 2. 创建工作对象（Worker）
        self.update_worker = UpdateChecker()

        # 3. 将工作对象移动到线程中
        self.update_worker.moveToThread(self.update_thread)

        # 4. 连接信号和槽：
        # 当线程启动时，执行 worker.run_check
        self.update_thread.started.connect(self.update_worker.run_check)
        # 当 worker 完成时，将结果连接到主线程的槽函数
        self.update_worker.signal_result.connect(self._handle_update_result)
        # 线程完成后自动退出并清理
        self.update_worker.signal_result.connect(self.update_thread.quit)
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_worker.signal_result.connect(self.update_worker.deleteLater)

        # 5. 启动线程
        self.update_thread.start()

    # 将检查逻辑主体槽函数
    @Slot(bool, object)
    def _handle_update_result(self, success: bool, data_or_error: object):
        """处理后台线程返回的检查结果"""

        # 检查完成后，重新启用按钮
        self.btn_update.setEnabled(True)
        self.btn_update.setText("检查更新")

        # 定义一个内部函数，用于清除版本号前的 'v' 前缀，方便比较
        def clean_version(v):
            # 确保版本号是字符串，并移除 'v' 和 '.'，方便整数比较
            return str(v).lstrip('v').replace('.', '')

        if not success:
            # 检查失败，data_or_error 是错误信息
            error_message = str(data_or_error)
            QMessageBox.warning(
                self,
                "检查更新失败",
                error_message,
                QMessageBox.Ok
            )
            return

        # 检查成功，data_or_error 是 JSON manifest 字典
        manifest = data_or_error
        latest_version_tag = manifest.get("latest_version", "v0.0.0")
        update_notes = manifest.get("update_notes", [])
        release_date = manifest.get("release_date", "")
        download_url = manifest.get("download_url", "")  # 失败时为空字符串

        # 进行版本比较
        current_version = CURRENT_VERSION

        try:
            clean_latest = int(clean_version(latest_version_tag))
            clean_current = int(clean_version(current_version))
        except ValueError:
            # 如果版本号格式不正确，则跳过比较
            print("Warning: Version tag is not numeric for comparison.")
            return

        if clean_latest > clean_current:
            # 发现新版本
            notes_text = "\n- " + "\n- ".join(update_notes)

            #
            informative_text = (
                f"更新日期:{release_date}\n"
                f"\n更新内容：\n{notes_text}"

            )

            msg = QMessageBox(self)
            msg.setWindowTitle("发现新版本")
            msg.setIcon(QMessageBox.Information)
            msg.setText(f"发现新版本：{current_version}->{latest_version_tag}")
            msg.setInformativeText(informative_text)

            # === 按钮设置 START ===

            # 1. 定义自定义按钮 "前往下载"
            download_button = QPushButton("前往下载")
            # 关联点击事件到打开 URL
            download_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(download_url)))

            # 2. 将按钮添加到 QMessageBox
            msg.addButton(download_button, QMessageBox.AcceptRole)

            # 3. 汉化 Cancel 按钮：使用自定义 QPushButton 并赋予 RejectRole
            cancel_button = QPushButton("取消")
            msg.addButton(cancel_button, QMessageBox.RejectRole)
            # === 按钮设置 END ===

            msg.exec()

        else:
            # 当前已是最新版本
            # 只有手动点击按钮时才弹出提示。
            # 我们通过检查按钮文本状态来简单区分
            if self.btn_update.text() == "检查更新":  # 如果按钮文本已经恢复，说明是手动点击后结束
                QMessageBox.information(
                    self,
                    "检查更新",
                    f"当前版本 ({current_version}) 已经是最新版本。",
                    QMessageBox.Ok
                )

    @Slot()
    def _start_announcement_load(self):
        """启动后台线程加载公告"""
        self.announcement_thread = QThread()
        self.announcement_worker = AnnouncementLoader()
        self.announcement_worker.moveToThread(self.announcement_thread)

        self.announcement_thread.started.connect(self.announcement_worker.run_load)
        self.announcement_worker.signal_result.connect(self._handle_announcement_result)
        self.announcement_worker.signal_result.connect(self.announcement_thread.quit)
        self.announcement_thread.finished.connect(self.announcement_thread.deleteLater)
        self.announcement_worker.signal_result.connect(self.announcement_worker.deleteLater)

        self.announcement_thread.start()

    @Slot(bool, object)
    def _handle_announcement_result(self, success: bool, data_or_error: object):
        """处理公告加载结果，并根据 show_mode 决定是否显示"""
        if not success:
            print(data_or_error)
            return

        announcements = data_or_error.get("announcements", [])
        current_version = CURRENT_VERSION

        # 加载本地已读公告 ID 集合
        read_ann_ids = self._load_announcement_state()

        showed_any = False  # 可选：避免重复弹窗（按需）

        for ann in announcements:
            if ann.get("version") != current_version:
                continue

            title = ann.get("title", "公告")
            content = ann.get("content", "暂无内容。")
            show_mode = ann.get("show_mode", "once")  # 默认 once

            # 生成唯一 ID：建议用 version + title（简单且可读）
            ann_id = f"{current_version}||{title}"

            should_show = False
            if show_mode == "always":
                should_show = True
            elif show_mode == "once":
                if ann_id not in read_ann_ids:
                    should_show = True

            if should_show:
                QMessageBox.information(self, title, content, QMessageBox.Ok)
                if show_mode == "once":
                    read_ann_ids.add(ann_id)
                    self._save_announcement_state(read_ann_ids)
                showed_any = True

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 LearnWord")
        self.setFixedSize(400, 300)
        self.setWindowModality(Qt.WindowModal)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)

        # 标题
        title_label = QLabel("LearnWord")
        title_label.setFont(QFont("MiSans", 20, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: white; margin-top: 20px;")

        # 版本信息
        version_label = QLabel(f"版本: {CURRENT_VERSION}\n"
                               f"构建日期:{CURRENT_VERSION_DATE}")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #cccccc; font-size: 14px; margin-top: 5px;")


        # 作者信息
        author_label = QLabel("作者: Junpgle")
        author_label.setAlignment(Qt.AlignCenter)
        author_label.setStyleSheet("color: #cccccc; font-size: 14px; margin-top: 5px;")

        # 项目描述
        desc_label = QLabel(
            "一款轻量级英语词汇学习工具，\n"
            "支持学习、复习、测试与进度管理。"
        )
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setStyleSheet("color: #aaaaaa; font-size: 13px; margin: 15px 0;")

        # GitHub 链接按钮
        github_button = QPushButton("访问项目主页 (GitHub)")
        github_button.setObjectName("github_btn")
        github_button.clicked.connect(self._open_github)

        # 关闭按钮
        close_button = QPushButton("关闭")
        close_button.setObjectName("close_button")
        close_button.clicked.connect(self.accept)

        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(github_button)
        btn_layout.addWidget(close_button)
        btn_layout.addStretch()

        # 添加到主布局
        layout.addWidget(title_label)
        layout.addWidget(version_label)
        layout.addWidget(author_label)
        layout.addWidget(desc_label)
        layout.addLayout(btn_layout)

        # 设置样式
        self.setStyleSheet("""
            QDialog {
                background-color: #000000;
                border: 1px solid #333333;
            }
            QLabel {
                color: white;
            }
            QPushButton {
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
            }
            #github_btn {
                background-color: #0969da;
                color: white;
            }
            #github_btn:hover {
                background-color: #0757b7;
            }
            
            #close_button{
                background-color: #0757b7;
                color: white;
            }
            #close_button:hover {
                background-color: #D3D3D3;
            }
            
        """)

    def _open_github(self):
        QDesktopServices.openUrl(QUrl("https://github.com/Junpgle/LearnWord"))


if __name__ == "__main__":
    # QApplication 初始化
    app = QApplication(sys.argv)
    app.setFont(QFont("MiSans", 11, QFont.Bold))

    # 初始化数据模型
    model = VocabModel()

    # 🚨 关键修改：调用统一的加载方法，实现自动加载和默认词库的兜底逻辑
    model.load_all_data()

    # 检查是否成功加载了单词
    if not model.words:
        QMessageBox.critical(
            None,
            "致命错误",
            "未能加载任何单词。请确保 '六级.csv' 文件存在且格式正确，或导入其他词库。",
            QMessageBox.Ok
        )
        sys.exit(1)

    # 创建并显示主窗口
    mw = MainWindow(model)
    mw.show()

    # 执行应用
    sys.exit(app.exec())

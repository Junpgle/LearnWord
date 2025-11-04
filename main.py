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
from vocab_model import VocabModel
from learn_window import LearnWindow
from review_window import ReviewWindow
from test_window import TestWindow
from setting_window import SettingWindow

# 设定当前程序版本号
CURRENT_VERSION = "v1.0.0"


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
# 2. 主窗口类：MainWindow
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

        # 1.3 检查更新按钮 (位于右上角)
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

        # ✅ 关键修改 1: 添加垂直弹簧，将所有内容向下推动 (现在用于将网格推到中央)
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

        # ✅ 关键修改 2: 在内容底部也添加一个垂直弹簧
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
                border-radius: 8px;
                box-shadow: none;
            }
            #update_check_btn:hover {
                background-color: #c0392b;
            }
        """)
        # ----------------------------------------------------

        # ✅ 新增：在初始化结束时自动检查更新
        self._start_update_check()

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

    # ✅ 新增：启动后台检查线程的槽函数
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

    # ✅ 修改：将检查逻辑主体移动到这个槽函数中
    @Slot(bool, object)
    def _handle_update_result(self, success: bool, data_or_error: object):
        """处理后台线程返回的检查结果"""

        # 检查完成后，重新启用按钮
        self.btn_update.setEnabled(True)
        self.btn_update.setText("检查更新")

        # 定义一个内部函数，用于清除版本号前的 'v' 前缀，方便比较
        def clean_version(v):
            return v.lstrip('v').replace('.', '')

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
        download_url = manifest.get("download_url", "")  # 失败时为空字符串

        # 进行版本比较
        current_version = CURRENT_VERSION
        clean_latest = clean_version(latest_version_tag)
        clean_current = clean_version(current_version)

        if int(clean_latest) > int(clean_current):
            # 发现新版本
            notes_text = "\n- " + "\n- ".join(update_notes)

            # ✅ 修改 1: 将下载链接整合到 informativeText 中，并移除 setDetailedText() 调用
            informative_text = (
                f"更新内容：\n{notes_text}"
                f"\n\n下载链接：{download_url}"
            )

            msg = QMessageBox(self)
            msg.setWindowTitle("发现新版本")
            msg.setIcon(QMessageBox.Information)
            msg.setText(f"版本更新:\n{current_version}->{latest_version_tag}")
            msg.setInformativeText(informative_text)

            # === 按钮设置 START ===

            # 移除 setDetailedText()，因此不再创建“显示详情”按钮

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
            # 只有用户点击按钮时才弹出提示。如果是自动启动，则保持静默。
            # 这里我假设您希望手动点击时显示“已是最新”信息。
            if not self.update_thread.isRunning():  # 只有非自动启动时才显示
                QMessageBox.information(
                    self,
                    "检查更新",
                    f"当前版本 ({current_version}) 已经是最新版本。",
                    QMessageBox.Ok
                )

    # ✅ 移除旧的 check_for_updates 方法，它的功能已被拆分到 _start_update_check 和 _handle_update_result
    # def check_for_updates(self):
    #     """... (旧逻辑被移除) ..."""
    #     pass


if __name__ == "__main__":
    # QApplication 初始化
    app = QApplication(sys.argv)
    app.setFont(QFont("MiSans", 11, QFont.Bold))

    # 初始化数据模型
    model = VocabModel()
    model.load_settings()

    # 启动加载逻辑：按优先级加载进度文件、最新词库文件、或默认词库文件
    if os.path.exists(os.path.join("data", "progress.json")):
        # 如果存在进度文件，先加载进度，进度文件中包含词库信息
        model.load_progress(os.path.join("data", "progress.json"))
    elif os.path.exists(os.path.join("data", "last_words.csv")):
        # 如果没有进度文件，加载上次导入的词库
        model.load_words_from_csv(os.path.join("data", "last_words.csv"))
    elif os.path.exists("words.csv"):
        # 如果都没有，加载根目录下的默认词库
        model.load_words_from_csv("words.csv")

    # 创建并显示主窗口
    mw = MainWindow(model)
    mw.show()

    # 执行应用
    sys.exit(app.exec())

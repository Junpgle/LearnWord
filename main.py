import sys, os
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QGridLayout
from PySide6.QtCore import Qt, QPropertyAnimation, QRect
from PySide6.QtGui import QFont
from vocab_model import VocabModel
from learn_window import LearnWindow
from review_window import ReviewWindow
from test_window import TestWindow
from setting_window import SettingWindow


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

        # ✅ 关键修改 1: 添加垂直弹簧，将所有内容向下推动
        # 权重设为 1，确保其能占据顶部多余空间，从而实现内容的整体下移。
        self.layout.addStretch(1)

        # Title
        self.title = QLabel("LearnWord")
        self.title.setFont(QFont("MiSans", 34, QFont.Bold))
        self.title.setAlignment(Qt.AlignCenter)

        # 初始的 20px 间距，可保留或删除
        # self.layout.addSpacing(20)

        self.layout.addWidget(self.title)

        # 标题和按钮网格之间的间距
        self.layout.addSpacing(60)

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
            b.setStyleSheet(
                "QPushButton{background-color:#0078d7;color:white;border:none;border-radius:18px;} QPushButton:hover{background-color:#339af0;}")

        # 将按钮添加到网格布局
        grid.addWidget(self.btn_learn, 0, 0)
        grid.addWidget(self.btn_review, 0, 1)
        grid.addWidget(self.btn_test, 1, 0)
        grid.addWidget(self.btn_setting, 1, 1)

        # 将网格布局添加到主布局
        self.layout.addLayout(grid)

        # ✅ 关键修改 2: 在内容底部也添加一个垂直弹簧
        # 如果您希望内容在中央偏下的位置，可以添加一个较小权重的弹簧。
        # 如果您只想要下移而不是居中，可以移除这一行，或者保持其权重小于顶部的弹簧。
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

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
        self.setWindowTitle("")
        self.setFixedSize(1000, 700)
        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.layout = QVBoxLayout(self.central)
        self.layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        # Title
        self.title = QLabel("LearnWord")
        self.title.setFont(QFont("MiSans", 34, QFont.Bold))
        self.title.setAlignment(Qt.AlignCenter)
        self.layout.addSpacing(20)
        self.layout.addWidget(self.title)
        self.layout.addSpacing(60)
        # grid
        grid = QGridLayout()
        grid.setSpacing(40)
        # buttons
        self.btn_learn = QPushButton("Learn"); self.btn_review = QPushButton("Review")
        self.btn_test = QPushButton("Test"); self.btn_setting = QPushButton("设置")
        for b in [self.btn_learn, self.btn_review, self.btn_test, self.btn_setting]:
            b.setFixedSize(200, 100)
            b.setFont(QFont("MiSans", 16, QFont.Bold))
            b.setStyleSheet("QPushButton{background-color:#0078d7;color:white;border:none;border-radius:18px;} QPushButton:hover{background-color:#339af0;}")
        grid.addWidget(self.btn_learn, 0, 0)
        grid.addWidget(self.btn_review, 0, 1)
        grid.addWidget(self.btn_test, 1, 0)
        grid.addWidget(self.btn_setting, 1, 1)
        self.layout.addLayout(grid)
        # child windows placeholders
        self.learn_win = None; self.review_win = None; self.test_win = None; self.setting_win = None
        # connections
        self.btn_learn.clicked.connect(self.open_learn)
        self.btn_review.clicked.connect(self.open_review)
        self.btn_test.clicked.connect(self.open_test)
        self.btn_setting.clicked.connect(self.open_setting)
        # center on screen
        self.center_on_screen()

    def center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        size = self.geometry()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        self.move(x, y)

    def open_learn(self):
        if self.learn_win is None or not self.learn_win.isVisible():
            self.learn_win = LearnWindow(self.model, parent=self)
            self.learn_win.show()
        else:
            self.learn_win.activateWindow()

    def open_review(self):
        if self.review_win is None or not self.review_win.isVisible():
            self.review_win = ReviewWindow(self.model, parent=self)
            self.review_win.show()
        else:
            self.review_win.activateWindow()

    def open_test(self):
        if self.test_win is None or not self.test_win.isVisible():
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("MiSans", 11, QFont.Bold))
    model = VocabModel()
    # load progress if exists, else last_words, else default words.csv
    if os.path.exists(os.path.join("data","progress.json")):
        model.load_progress(os.path.join("data","progress.json"))
    elif os.path.exists(os.path.join("data","last_words.csv")):
        model.load_words_from_csv(os.path.join("data","last_words.csv"))
    elif os.path.exists("words.csv"):
        model.load_words_from_csv("words.csv")
    mw = MainWindow(model)
    mw.show()
    sys.exit(app.exec())

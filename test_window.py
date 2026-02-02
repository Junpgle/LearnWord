import csv
import os
import random

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QHBoxLayout, QSizePolicy,
    QScrollArea, QFrame
)

# 引入 VocabModel 和 通用富文本工具函数
from vocab_model import VocabModel, get_word_rich_text


class TestWindow(QMainWindow):
    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.model.load_settings()
        self.setWindowTitle("单词测试模式")
        self.setFixedSize(1000, 750)  # 稍微增加高度以适应内容
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # 返回按钮布局
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_return = QPushButton("返回主页面")
        self.btn_return.clicked.connect(self.close)
        btn_row.addWidget(self.btn_return)
        layout.addLayout(btn_row)

        # 1. 顶部：拼写填空提示 (例如: a _ _ l e)
        self.cloze = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self.cloze.setFont(QFont("MiSans", 26, QFont.Weight.Bold))
        self.cloze.setWordWrap(True)
        # 设置策略防止被过度压缩
        self.cloze.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.cloze)

        # 2. 中间：富文本提示区域 (使用 QScrollArea 包裹)
        # 这里显示释义、词源和短语(关键词被遮盖)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.hint_label = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        # 字体稍小一点，区别于顶部的填空题
        self.hint_label.setFont(QFont("MiSans", 16))
        self.hint_label.setWordWrap(True)
        self.hint_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.scroll_layout.addWidget(self.hint_label)
        self.scroll_area.setWidget(self.scroll_content)

        # 添加到布局，设置伸缩因子为 2，占据主要空间
        layout.addWidget(self.scroll_area, 2)

        # 用户输入框
        self.input = QLineEdit()
        self.input.setObjectName("test_input")
        self.input.setMaximumWidth(600)

        input_row = QHBoxLayout()
        input_row.addStretch()
        input_row.addWidget(self.input)
        input_row.addStretch()
        layout.addLayout(input_row)

        # 提交和下一题按钮布局
        row = QHBoxLayout()
        row.addStretch(1)

        self.submit = QPushButton("提交")
        self.submit.setObjectName("submit_btn")

        self.next_btn = QPushButton("下一题")
        self.next_btn.setObjectName("next_btn")
        self.next_btn.setEnabled(False)

        row.addWidget(self.submit)
        row.addWidget(self.next_btn)
        row.addStretch(1)
        layout.addLayout(row)

        # 计分板
        self.score = QLabel("0 / 0 (0.00%)", alignment=Qt.AlignmentFlag.AlignCenter)
        self.score.setFont(QFont("MiSans", 18, QFont.Weight.Bold))
        layout.addWidget(self.score)

        # 信号连接
        self.submit.clicked.connect(self.on_submit)
        self.next_btn.clicked.connect(self.next_q)
        self.input.returnPressed.connect(self.on_submit)

        # 数据初始化
        self.words = []
        self.test_list = []
        self.current = None
        self.total = 0
        self.correct = 0

        self._prepare_and_start()

        # 样式表
        central.setStyleSheet("""
            QPushButton {
                padding: 12px 24px;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 600;
                margin: 5px;
                box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.1);
                transition: background-color 0.3s;
            }
            #submit_btn {
                background-color: #0078d7; 
                color: #ffffff;
            }
            #submit_btn:hover {
                background-color: #005bb5;
            }
            #next_btn {
                background-color: #e8e8e8; 
                color: #333333;
            }
            #next_btn:hover {
                background-color: #d1d1d1;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #999999;
                box-shadow: none;
            }
            QLineEdit {
                padding: 12px 10px;
                border: 2px solid #ccc;
                border-radius: 8px;
                font-size: 18px;
            }
            /* 滚动区域标签行高 */
            QLabel {
                line-height: 1.5;
            }
        """)

    def _prepare_and_start(self):
        count = self.model.settings.get("test_count", 20)
        # 获取未测试过的单词
        pool = [w for w in self.model.words if not w.tested]

        if not pool:
            QMessageBox.information(self, "提示", "词库为空或所有单词已测试完毕。")
            # 延时关闭防止闪退
            QTimer.singleShot(100, self.close)
            return

        random.shuffle(pool)
        self.test_list = pool[:min(count, len(pool))]

        self.total = 0
        self.correct = 0
        self._update_score()
        self.next_q()

    def next_q(self):
        self.next_btn.setEnabled(False)

        if not self.test_list:
            self.cloze.setText("🎉 本次测试完成！ 🎉")
            self.hint_label.setText(f"最终得分：{self.correct} / {self.total}")
            self.submit.hide()
            self.next_btn.hide()
            self.input.hide()
            self.score.hide()
            self.current = None
            QTimer.singleShot(3000, self.close)
            return

        self.current = self.test_list.pop(0)

        # 1. 设置顶部的填空文本 (例如: a _ _ l e)
        cloze_str = self._make_cloze(self.current.word)
        self.cloze.setText(cloze_str)

        # 2. 设置中间的富文本提示 (Mode='hint' 会隐藏短语中的目标单词)
        self.hint_label.setText(get_word_rich_text(self.current, mode="hint"))

        self.input.setText("")
        self.input.setFocus()

    def on_submit(self):
        if not self.current: return

        s = self.input.text().strip()
        if s == "":
            QMessageBox.warning(self, "提示", "请输入答案")
            return

        self.total += 1

        if s.lower() == self.current.word.lower():
            self.correct += 1
            QMessageBox.information(self, "正确", "回答正确！")

            # 标记为已测试
            tested_word_str = self.current.word
            model_word = next(
                (w for w in self.model.words if w.word.lower() == tested_word_str.lower()),
                None
            )
            if model_word:
                model_word.tested = True
            self.model.save_progress()

            QTimer.singleShot(600, self.next_q)
        else:
            QMessageBox.information(self, "错误", f"正确答案是: {self.current.word}")
            self.next_btn.setEnabled(True)

        self._update_score()

    def _update_score(self):
        pct = (self.correct / self.total * 100) if self.total > 0 else 0.0
        self.score.setText(f"{self.correct} / {self.total} ({pct:.2f}%)")

    def _make_cloze(self, word):
        chars = list(word)
        import random as _r
        if len(chars) == 0: return ""
        n = max(1, min(len(chars) - 1, _r.randint(1, max(1, len(chars) // 2))))
        idxs = _r.sample(range(len(chars)), n)
        return ' '.join([('_' if i in idxs else c) for i, c in enumerate(chars)])
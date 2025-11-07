import csv
import os
import random

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, \
    QHBoxLayout

from vocab_model import VocabModel


class TestWindow(QMainWindow):
    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.model.load_settings()
        self.setWindowTitle("单词测试模式")  # Add window title
        self.setFixedSize(1000, 700)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 返回按钮布局
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_return = QPushButton("返回主页面")
        btn_row.addWidget(self.btn_return)
        layout.addLayout(btn_row)

        layout.addStretch(1)  # 添加伸缩项，使内容居中

        # 填空/释义显示区域
        self.cloze = QLabel("", alignment=Qt.AlignCenter)
        self.cloze.setFont(QFont("MiSans", 22, QFont.Bold))
        layout.addWidget(self.cloze)

        # 用户输入框 (修改点 1: 居中和最大宽度)
        self.input = QLineEdit()
        self.input.setObjectName("test_input")  # 设置对象名
        self.input.setMaximumWidth(600)  # 限制最大宽度

        input_row = QHBoxLayout()
        input_row.addStretch()
        input_row.addWidget(self.input)
        input_row.addStretch()
        layout.addLayout(input_row)  # 将居中布局添加到主布局

        # 提交和下一题按钮布局
        row = QHBoxLayout()
        row.addStretch(1)

        # 设置对象名以便在 QSS 中单独设置样式
        self.submit = QPushButton("提交")
        self.submit.setObjectName("submit_btn")  # 设置对象名

        self.next_btn = QPushButton("下一题")
        self.next_btn.setObjectName("next_btn")  # 设置对象名
        self.next_btn.setEnabled(False)

        row.addWidget(self.submit)
        row.addWidget(self.next_btn)
        row.addStretch(1)
        layout.addLayout(row)

        # 计分板 (修改为居中、加粗、放大)
        self.score = QLabel("0 / 0 (0.00%)", alignment=Qt.AlignCenter)  # 居中
        self.score.setFont(QFont("MiSans", 18, QFont.Bold))  # 加粗放大
        layout.addWidget(self.score)

        layout.addStretch(1)  # 添加伸缩项，使内容居中

        # 信号连接
        self.btn_return.clicked.connect(self.close)
        self.submit.clicked.connect(self.on_submit)
        self.next_btn.clicked.connect(self.next_q)
        # Enter 键绑定到提交
        self.input.returnPressed.connect(self.on_submit)

        # 数据初始化
        self.words = []

        self.test_list = []
        self.current = None
        self.total = 0
        self.correct = 0

        self._prepare_and_start()

        # 按钮样式美化
        central.setStyleSheet("""
            QPushButton {
                /* 基础样式：统一大小和圆角 */
                padding: 12px 24px;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 600;
                margin: 5px;
                box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.1);
                transition: background-color 0.3s; /* 增加过渡效果 */
            }

            /* 提交按钮样式 (主操作：蓝色) */
            #submit_btn {
                background-color: #0078d7; 
                color: #ffffff;
            }
            #submit_btn:hover {
                background-color: #005bb5;
            }

            /* 下一题按钮样式 (辅助操作：灰色) */
            #next_btn {
                background-color: #e8e8e8; 
                color: #333333;
            }
            #next_btn:hover {
                background-color: #d1d1d1;
            }

            /* 禁用状态 */
            QPushButton:disabled {
                background-color: #cccccc;
                color: #999999;
                box-shadow: none;
            }

            /* 输入框样式 (修改点 2: 统一 padding) */
            QLineEdit {
                padding: 12px 10px; /* 统一 LearnWindow 的大内边距 */
                border: 2px solid #ccc;
                border-radius: 8px;
                font-size: 18px;
            }
        """)

    def _prepare_and_start(self):
        """
        根据设置准备测试单词列表，并开始测试。
        """
        # 从 VocabModel 的设置中获取单次测试数量
        count = self.model.settings.get("test_count", 20)
        pool = [w for w in self.model.words if not w.tested] # 只测试未测试过的单词

        if not pool:
            QMessageBox.information(self, "提示", "词库为空，请导入单词库。")
            return

        # 随机打乱单词，并根据设置的数量抽取
        random.shuffle(pool)
        self.test_list = pool[:min(count, len(pool))]

        self.total = 0
        self.correct = 0
        self._update_score()  # 初始化分数显示
        self.next_q()

    def next_q(self):
        """
        切换到下一个单词进行测试。
        """
        self.next_btn.setEnabled(False)  # 禁用下一题按钮

        if not self.test_list:
            self.cloze.setText(f"🎉 本次复习完成！ 🎉\n" f"得分：{self.correct} / {self.total}")
            self.submit.hide()
            self.next_btn.hide()
            self.input.hide()
            self.score.hide()
            self.current = None  # 标记测试结束
            # 3 秒后自动关闭窗口
            QTimer.singleShot(3000, self.close)
            return

        # 弹出测试列表的第一个单词
        self.current = self.test_list.pop(0)

        # 制作填空提示
        cloze = self._make_cloze(self.current.word)

        # 在界面上显示填空提示和词性和释义
        if self.current.definition:
            # 移除释义中的换行符，确保显示在一行
            clean_definition = self.current.definition.replace('\n', ' / ')
            pos = self.current.pos
            self.cloze.setText(f"{cloze}\n\n词性:{pos}.\n释义: {clean_definition}\n")
        else:
            self.cloze.setText(cloze)

        self.input.setText("")  # 清空输入框
        self.input.setFocus()  # 设置焦点到输入框

    def on_submit(self):
        """
        处理用户提交的答案。
        """
        if not self.current: return

        s = self.input.text().strip()
        if s == "":
            QMessageBox.warning(self, "提示", "请输入答案")
            return

        self.total += 1

        # 核心判断逻辑：不区分大小写
        if s.lower() == self.current.word.lower():
            self.correct += 1
            QMessageBox.information(self, "正确", "回答正确！")

            # --- 更新 VocabModel 状态的关键逻辑 ---
            tested_word_str = self.current.word  # 当前正确单词

            # 1. 在 VocabModel 的总单词列表中查找匹配的 WordItem 对象
            model_word = next(
                (w for w in self.model.words if w.word.lower() == tested_word_str.lower()),
                None
            )

            if model_word:
                # 2. 更新对应 WordItem 的 tested 状态为 True
                model_word.tested = True

            # 3. 保存模型的进度，将更新后的状态持久化
            self.model.save_progress()

            # 延时 600ms 自动跳转到下一题
            QTimer.singleShot(600, self.next_q)

        else:
            # 回答错误
            QMessageBox.information(self, "错误", f"正确答案是: {self.current.word}")
            self.next_btn.setEnabled(True)  # 启用下一题按钮，让用户手动跳过

        self._update_score()

    def _update_score(self):
        """
        更新计分板上的分数和正确率。
        """
        pct = (self.correct / self.total * 100) if self.total > 0 else 0.0
        self.score.setText(f"{self.correct} / {self.total} ({pct:.2f}%)")

    def _make_cloze(self, word):
        """
        生成填空提示，随机将单词的部分字母替换为下划线。
        - 至少替换 1 个字母。
        - 最多替换单词长度的一半。
        """
        chars = list(word)
        import random as _r

        # 确保单词不为空
        if len(chars) == 0: return ""

        # 随机确定要替换的字母数量 n
        n = max(1, min(len(chars) - 1, _r.randint(1, max(1, len(chars) // 2))))

        # 随机选择要替换的字母索引
        idxs = _r.sample(range(len(chars)), n)

        # 生成填空字符串，用 '_' 替换被选中的字母
        return ' '.join([('_' if i in idxs else c) for i, c in enumerate(chars)])

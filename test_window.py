import random
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QHBoxLayout, QSizePolicy,
    QScrollArea, QFrame
)

from vocab_model import VocabModel, get_word_rich_text


class TestWindow(QMainWindow):
    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.model.load_settings()
        self.setWindowTitle("单词测试模式")
        self.setFixedSize(1000, 750)

        # 1. 检测当前主题模式 (亮/暗)
        self.is_dark = self.palette().window().color().lightness() < 128

        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(30, 20, 30, 20)

        # # 返回按钮布局
        # btn_row = QHBoxLayout()
        # btn_row.addStretch()
        # self.btn_return = QPushButton("返回主页面")
        # self.btn_return.setObjectName("return_btn")
        # self.btn_return.clicked.connect(self.close)
        # btn_row.addWidget(self.btn_return)
        # layout.addLayout(btn_row)

        # 顶部弹簧
        layout.addStretch(1)

        # 1. 顶部：拼写填空提示 (例如: a _ _ l e)
        self.cloze = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self.cloze.setFont(QFont("MiSans", 28, QFont.Weight.Bold))
        self.cloze.setWordWrap(True)
        self.cloze.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.cloze)

        # 2. 中间：富文本提示区域 (使用 QScrollArea 包裹)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        # 隐藏滚动条
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        # 初始对齐方式，会在 next_q 中根据状态动态调整
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.scroll_layout.setContentsMargins(0, 10, 0, 10)

        self.hint_label = QLabel("", alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.hint_label.setFont(QFont("MiSans", 16))
        self.hint_label.setWordWrap(True)
        self.hint_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.hint_label.setOpenExternalLinks(True)

        self.scroll_layout.addWidget(self.hint_label)
        self.scroll_area.setWidget(self.scroll_content)

        # 占据主要空间 (80%左右)
        layout.addWidget(self.scroll_area, 8)

        # 3. 结果反馈标签 (新增，用于显示回答正确/错误)
        self.result_label = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self.result_label.setFont(QFont("MiSans", 18, QFont.Weight.Bold))
        self.result_label.hide()
        layout.addWidget(self.result_label)

        # 用户输入框
        self.input = QLineEdit()
        self.input.setObjectName("test_input")
        self.input.setMaximumWidth(600)

        input_row = QHBoxLayout()
        input_row.addStretch()
        input_row.addWidget(self.input)
        input_row.addStretch()
        layout.addLayout(input_row)

        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.submit = QPushButton("提交")
        self.submit.setObjectName("submit_btn")

        self.next_btn = QPushButton("下一题")
        self.next_btn.setObjectName("next_btn")
        self.next_btn.hide()  # 初始隐藏

        btn_layout.addWidget(self.submit)
        btn_layout.addWidget(self.next_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 计分板
        self.score = QLabel("0 / 0 (0.00%)", alignment=Qt.AlignmentFlag.AlignCenter)
        self.score.setFont(QFont("MiSans", 16, QFont.Weight.Bold))
        layout.addWidget(self.score)

        # 底部弹簧
        layout.addStretch(1)

        # 信号连接
        self.submit.clicked.connect(self.on_submit)
        self.next_btn.clicked.connect(self.next_q)

        # 数据初始化
        self.words = []
        self.test_list = []
        self.current = None
        self.total = 0
        self.correct = 0
        self.answered = False  # 标记当前题是否已回答

        self._prepare_and_start()
        self._apply_adaptive_stylesheet()

    def _apply_adaptive_stylesheet(self):
        """应用自适应样式"""
        if self.is_dark:
            bg_color = "#2d2d2d"
            text_color = "#ecf0f1"
            border_color = "#444444"
            hover_bg = "#3d3d3d"
            input_bg = "#2d2d2d"
            input_border = "#444444"
            primary_bg = "#2980b9"
            main_bg = "#1e1e1e"
            score_color = "#bdc3c7"
        else:
            bg_color = "#ffffff"
            text_color = "#2c3e50"
            border_color = "#bdc3c7"
            hover_bg = "#ecf0f1"
            input_bg = "#ffffff"
            input_border = "#bdc3c7"
            primary_bg = "#3498db"
            main_bg = "#f8f9fa"
            score_color = "#7f8c8d"

        self.centralWidget().setStyleSheet(f"#CentralWidget {{ background-color: {main_bg}; }}")

        # 顶部填空文字颜色
        self.cloze.setStyleSheet(f"color: {text_color}; margin-bottom: 10px;")
        self.score.setStyleSheet(f"color: {score_color}; margin-top: 10px;")

        self.setStyleSheet(f"""
            QPushButton {{
                padding: 10px 24px;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 600;
                margin: 5px;
                box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.1);
            }}
            #return_btn {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                min-height: 28px;
                max-height: 28px;
                padding: 2px 10px;
                font-size: 12px;
            }}
            #return_btn:hover {{
                background-color: {hover_bg};
            }}
            #submit_btn, #next_btn {{
                background-color: {primary_bg}; 
                color: #ffffff;
            }}
            #submit_btn:hover, #next_btn:hover {{
                background-color: {primary_bg}AA;
            }}
            QLineEdit {{
                padding: 12px 10px;
                border: 2px solid {input_border};
                border-radius: 8px;
                font-size: 18px;
                color: {text_color};
                background-color: {input_bg};
            }}
            QLineEdit:focus {{
                border-color: {primary_bg};
            }}
            QLabel {{
                line-height: 1.5;
            }}
        """)

    def _get_adaptive_rich_text(self, item, mode):
        html = get_word_rich_text(item, mode)
        if self.is_dark:
            html = html.replace("#2c3e50", "#ecf0f1")
            html = html.replace("#7f8c8d", "#bdc3c7")
            html = html.replace("#34495e", "#dcdcdc")
            html = html.replace("#555", "#aaa")
            html = html.replace("#2980b9", "#5dade2")
            html = html.replace("#e67e22", "#f39c12")
        return html

    def _prepare_and_start(self):
        count = self.model.settings.get("test_count", 20)
        pool = [w for w in self.model.words if not w.tested]

        if not pool:
            QMessageBox.information(self, "提示", "词库为空或所有单词已测试完毕。")
            QTimer.singleShot(100, self.close)
            return

        random.shuffle(pool)
        self.test_list = pool[:min(count, len(pool))]

        self.total = 0
        self.correct = 0
        self._update_score()
        self.next_q()

    def keyPressEvent(self, event):
        # 回车键逻辑：如果没回答，触发提交；如果已回答，触发下一题
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.answered:
                self.next_q()
            else:
                self.on_submit()
        else:
            super().keyPressEvent(event)

    def next_q(self):
        self.answered = False
        self.next_btn.hide()
        self.submit.show()
        self.result_label.hide()
        self.input.setEnabled(True)
        self.input.setFocus()

        # ★★★ 确保填空标签显示 ★★★
        self.cloze.show()

        if not self.test_list:
            self.cloze.setText("🎉 本次测试完成！ 🎉")
            # 显示总结
            summary_html = f"<div style='text-align:center; font-size:24px; color:{'#ecf0f1' if self.is_dark else '#2c3e50'};'>最终得分：{self.correct} / {self.total}</div>"

            # 总结时居中
            self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.hint_label.setText(summary_html)
            self.submit.hide()
            self.input.hide()
            self.score.hide()
            self.current = None
            QTimer.singleShot(3000, self.close)
            return

        self.current = self.test_list.pop(0)

        # 1. 顶部：显示填空 (a _ _ l e)
        cloze_str = self._make_cloze(self.current.word)
        self.cloze.setText(cloze_str)

        # 2. 中间：仅显示释义 (mode="spelling" 仅返回核心词义提示)
        # ★★★ 关键修改：输入阶段，将对齐方式改为 Bottom，紧贴输入框 ★★★
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
        self.hint_label.setText(self._get_adaptive_rich_text(self.current, mode="spelling"))

        self.input.setText("")

    def on_submit(self):
        if not self.current: return

        s = self.input.text().strip()
        if s == "":
            return

        self.answered = True
        self.total += 1
        self.input.setEnabled(False)  # 禁止修改
        self.submit.hide()
        self.next_btn.show()
        self.next_btn.setFocus()  # 焦点给下一题按钮

        is_correct = (s.lower() == self.current.word.lower())

        # 1. 显示完整富文本 (包含词源、短语)
        # ★★★ 关键修改：展示阶段，将对齐方式改为 Top，方便阅读长文本 ★★★
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.hint_label.setText(self._get_adaptive_rich_text(self.current, mode="full"))

        # 2. ★★★ 关键修改：隐藏顶部的重复单词，避免和富文本中的单词重复 ★★★
        self.cloze.hide()

        # 3. 显示结果反馈
        if is_correct:
            self.correct += 1
            self.result_label.setText("✅ 回答正确")
            self.result_label.setStyleSheet("color: #2ecc71; margin-bottom: 10px;")  # 绿色

            # 更新模型状态
            tested_word_str = self.current.word
            model_word = next(
                (w for w in self.model.words if w.word.lower() == tested_word_str.lower()),
                None
            )
            if model_word:
                model_word.tested = True
            self.model.save_progress()
        else:
            self.result_label.setText(f"❌ 错误 (正确: {self.current.word})")
            self.result_label.setStyleSheet("color: #e74c3c; margin-bottom: 10px;")  # 红色

        self.result_label.show()
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
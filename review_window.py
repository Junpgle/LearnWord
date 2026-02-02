import random
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
                               QHBoxLayout, QLineEdit, QMessageBox, QScrollArea, QFrame)

# 导入 VocabModel 和 新增的工具函数
from vocab_model import VocabModel, get_word_rich_text


class ReviewWindow(QMainWindow):
    """
    复习窗口：实现两阶段复习模式 (识别 -> 拼写)，主要针对 learned=True 的单词，
    目标是更新单词的 reviewed 状态和 stage 进度。
    """

    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("单词复习模式")
        self.setFixedSize(1000, 750)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # 顶部阶段指示器
        self.stage_row = QHBoxLayout()
        self.stage_row.setSpacing(8)
        self.stage_indicators = []
        for i in range(2):
            dot = QLabel()
            dot.setFixedSize(20, 20)
            dot.setStyleSheet("border:2px solid #555; border-radius:10px; background-color:transparent;")
            self.stage_row.addWidget(dot)
            self.stage_indicators.append(dot)
        self.stage_row.addStretch()
        layout.addLayout(self.stage_row)

        # 返回按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_return = QPushButton("返回主页面")
        self.btn_return.setObjectName("return_btn")
        btn_row.addWidget(self.btn_return)
        layout.addLayout(btn_row)

        # 主要内容：单词/释义 显示区域 (使用 QScrollArea 包裹)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.word_label = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self.word_label.setFont(QFont("MiSans", 26, QFont.Weight.Bold))
        self.word_label.setWordWrap(True)
        self.word_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self.scroll_layout.addWidget(self.word_label)
        self.scroll_area.setWidget(self.scroll_content)

        layout.addWidget(self.scroll_area, 2)

        # --- 第二阶段控件 (阶段一操作：认识/不认识) ---
        self.phase2_widget = QWidget()
        know_row = QHBoxLayout(self.phase2_widget)
        know_row.addStretch()

        self.know_btn = QPushButton("认识")
        self.know_btn.setObjectName("know_btn")
        self.unknow_btn = QPushButton("不认识")
        self.unknow_btn.setObjectName("unknow_btn")

        self.phase2_wrong_btn = QPushButton("我记错了")
        self.phase2_wrong_btn.setObjectName("wrong_btn")
        self.phase2_wrong_btn.hide()
        self.phase2_wrong_btn.clicked.connect(self.on_phase1_wrong)

        self.phase2_next_btn = QPushButton("下一个")
        self.phase2_next_btn.setObjectName("next_btn")
        self.phase2_next_btn.hide()
        self.phase2_next_btn.clicked.connect(self.on_phase2_next)

        know_row.addWidget(self.know_btn)
        know_row.addWidget(self.unknow_btn)
        know_row.addWidget(self.phase2_wrong_btn)
        know_row.addWidget(self.phase2_next_btn)
        know_row.addStretch()
        layout.addWidget(self.phase2_widget)

        # --- 第三阶段控件 (阶段二操作：拼写/提交) ---
        self.phase3_widget = QWidget()
        p3_layout = QVBoxLayout(self.phase3_widget)

        self.cloze = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self.cloze.setFont(QFont("MiSans", 20, QFont.Weight.Bold))
        p3_layout.addWidget(self.cloze)

        self.input = QLineEdit()
        self.input.setObjectName("review_input")
        self.input.setMaximumWidth(600)

        input_row = QHBoxLayout()
        input_row.addStretch()
        input_row.addWidget(self.input)
        input_row.addStretch()
        p3_layout.addLayout(input_row)

        submit_row = QHBoxLayout()
        submit_row.addStretch()
        self.submit_btn = QPushButton("提交")
        self.submit_btn.setObjectName("submit_btn")
        self.idk_btn = QPushButton("我不会")
        self.idk_btn.setObjectName("idk_btn")

        submit_row.addWidget(self.submit_btn)
        submit_row.addWidget(self.idk_btn)
        submit_row.addStretch()
        p3_layout.addLayout(submit_row)

        layout.addWidget(self.phase3_widget)

        # --- 连接信号 ---
        self.btn_return.clicked.connect(self.close)
        self.know_btn.clicked.connect(self.on_know)
        self.unknow_btn.clicked.connect(self.on_unknow)
        self.submit_btn.clicked.connect(self.on_submit)
        self.idk_btn.clicked.connect(self.on_idk)

        # 队列和当前单词初始化
        self.queue = []
        self.phase2_queue = []
        self.current = None
        self.in_phase2 = False
        self.last_action = None
        self._prepare_and_start()

        # 样式表 (与之前一致)
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
            #know_btn, #submit_btn, #next_btn {
                background-color: #0078d7; 
                color: #ffffff;
            }
            #know_btn:hover, #submit_btn:hover, #next_btn:hover {
                background-color: #005bb5;
            }
            #unknow_btn, #wrong_btn, #idk_btn {
                background-color: #dc3545;
                color: #ffffff;
            }
            #unknow_btn:hover, #wrong_btn:hover, #idk_btn:hover {
                background-color: #c82333;
            }
            #return_btn {
                padding: 8px 16px; 
                background-color: #f0f0f0;
                color: #333333;
                box-shadow: none;
            }
            #return_btn:hover {
                background-color: #e0e0e0;
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
            QLabel {
                line-height: 1.5;
            }
        """)

    def _prepare_and_start(self):
        count = self.model.settings.get("review_count", 15)
        pool = self.model.words
        to_review_pool = [w for w in pool if getattr(w, "learned", False) and not getattr(w, "reviewed", False)]

        if not to_review_pool:
            QMessageBox.information(self, "提示", "没有单词需要复习。")
            QTimer.singleShot(100, self.close)
            return

        random.shuffle(to_review_pool)
        self.queue = to_review_pool[:min(count, len(to_review_pool))]
        self.phase2_queue = []
        self.in_phase2 = False
        self._show_next()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not self.current:
                return
            if self.phase2_widget.isVisible():
                if self.phase2_next_btn.isVisible():
                    self.on_phase2_next()
                else:
                    self.on_know()
            elif self.phase3_widget.isVisible():
                self.on_submit()
        else:
            super().keyPressEvent(event)

    def _update_stage_indicator(self, phase):
        for i, dot in enumerate(self.stage_indicators, start=1):
            if i <= phase:
                dot.setStyleSheet("border:2px solid #555; border-radius:10px; background-color:#0078d7;")
            else:
                dot.setStyleSheet("border:2px solid #555; border-radius:10px; background-color:transparent;")

    def _show_next(self):
        # 若在第一阶段
        if not self.in_phase2:
            if not self.queue:
                # 第一阶段结束，进入第二阶段
                if not self.phase2_queue:
                    self.word_label.setText("🎉 本次复习完成！ 🎉")
                    self.phase2_widget.hide()
                    self.phase3_widget.hide()
                    QTimer.singleShot(3000, self.close)
                    return
                self.in_phase2 = True
                self.phase2_widget.hide()
                self.phase3_widget.show()
                self._update_stage_indicator(2)

                self.current = self.phase2_queue.pop(0)
                # ★★★ 调用通用富文本函数 (Mode: hint) ★★★
                self.word_label.setText(get_word_rich_text(self.current, mode="hint"))

                self.cloze.setText(self._make_cloze(self.current.word))
                self.input.setText("")
                self.input.setFocus()
                return

            self.current = self.queue.pop(0)
            # ★★★ 调用通用富文本函数 (Mode: simple) ★★★
            self.word_label.setText(get_word_rich_text(self.current, mode="simple"))

            self.phase2_widget.show()
            self.know_btn.show()
            self.unknow_btn.show()
            self.phase2_wrong_btn.hide()
            self.phase2_next_btn.hide()
            self.phase3_widget.hide()
            self._update_stage_indicator(1)
            return

        # 第二阶段流程
        if not self.phase2_queue and not self.current:
            self.word_label.setText("🎉 本次复习完成！ 🎉")
            self.phase2_widget.hide()
            self.phase3_widget.hide()
            QTimer.singleShot(3000, self.close)
            return

        if not self.current:
            self.current = self.phase2_queue.pop(0)

        self.phase2_widget.hide()
        self.phase3_widget.show()
        self._update_stage_indicator(2)

        # ★★★ 调用通用富文本函数 (Mode: hint) ★★★
        self.word_label.setText(get_word_rich_text(self.current, mode="hint"))

        self.cloze.setText(self._make_cloze(self.current.word))
        self.input.setText("")
        self.input.setFocus()

    def on_know(self):
        if not self.current: return
        self.last_action = "know"

        # ★★★ 调用通用富文本函数 (Mode: full) ★★★
        self.word_label.setText(get_word_rich_text(self.current, mode="full"))

        self.know_btn.hide()
        self.unknow_btn.hide()
        self.phase2_wrong_btn.show()
        self.phase2_next_btn.show()

        self.phase2_widget.show()
        self.phase3_widget.hide()
        self._update_stage_indicator(1)

    def on_unknow(self):
        if not self.current: return
        self.last_action = "unknow"

        self.current.stage = 1
        self.current.attempts += 1

        # ★★★ 调用通用富文本函数 (Mode: full) ★★★
        self.word_label.setText(get_word_rich_text(self.current, mode="full"))

        self.know_btn.hide()
        self.unknow_btn.hide()
        self.phase2_wrong_btn.hide()
        self.phase2_next_btn.show()

        self.phase2_widget.show()
        self.phase3_widget.hide()
        self._update_stage_indicator(1)

    def on_phase1_wrong(self):
        if not self.current: return
        self.queue.append(self.current)
        self.model.save_progress()
        self.phase2_wrong_btn.hide()
        self.phase2_next_btn.hide()
        self.current = None
        self._show_next()

    def on_phase2_next(self):
        if not self.current: return

        if self.last_action == "know":
            self.phase2_queue.append(self.current)
        elif self.last_action == "unknow":
            self.queue.append(self.current)

        self.model.save_progress()
        self.phase2_wrong_btn.hide()
        self.phase2_next_btn.hide()
        self.current = None
        self._show_next()

    def _advance_phase2_or_finish(self):
        if not self.phase2_queue:
            self.word_label.setText("🎉 本次复习完成！ 🎉")
            self.phase2_widget.hide()
            self.phase3_widget.hide()
            QTimer.singleShot(3000, self.close)
            return
        self._show_next()

    def on_submit(self):
        if not self.current: return
        s = self.input.text().strip()

        if s.lower() == self.current.word.lower():
            QMessageBox.information(self, "正确", "拼写正确！")
            self.current.learned = True
            self.current.reviewed = True
            self.current.stage = min(3, self.current.stage + 1)
            self.model.save_progress()
            self.current = None
            QTimer.singleShot(150, self._advance_phase2_or_finish)
        else:
            QMessageBox.information(self, "错误", f"正确答案: {self.current.word}")
            self.current.stage = 1
            self.phase2_queue.append(self.current)
            self.model.save_progress()
            self.current = None
            QTimer.singleShot(150, self._advance_phase2_or_finish)

    def on_idk(self):
        if not self.current: return
        QMessageBox.information(self, "提示", f"正确答案是: {self.current.word}")
        self.current.stage = 1
        self.phase2_queue.append(self.current)
        self.model.save_progress()
        self.current = None
        QTimer.singleShot(150, self._advance_phase2_or_finish)

    def _make_cloze(self, word):
        chars = list(word)
        import random as _r
        if len(chars) == 0: return ""
        n = max(1, min(len(chars) - 1, _r.randint(1, max(1, len(chars) // 2))))
        idxs = _r.sample(range(len(chars)), n)
        return " ".join([("_" if i in idxs else c) for i, c in enumerate(chars)])
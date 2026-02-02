import random
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
                               QHBoxLayout, QLineEdit, QMessageBox, QScrollArea, QFrame, QSizePolicy)

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

        # 1. 检测当前主题模式 (亮/暗)
        self.is_dark = self.palette().window().color().lightness() < 128

        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        # 移除强制背景色，由 _apply_adaptive_stylesheet 处理

        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(30, 20, 30, 20)

        # 顶部阶段指示器
        self.stage_row = QHBoxLayout()
        self.stage_row.setSpacing(8)
        self.stage_indicators = []

        dot_border = "#555555" if self.is_dark else "#bdc3c7"

        for i in range(2):
            dot = QLabel()
            dot.setFixedSize(20, 20)
            dot.setStyleSheet(f"border:2px solid {dot_border}; border-radius:10px; background-color:transparent;")
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

        # 顶部弹簧 (权重 1) - 用于垂直居中
        layout.addStretch(1)

        # --- 主要内容区 ---

        # 1. 滚动区域 (Phase 1 Reveal - 详细展示)
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
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.scroll_layout.setContentsMargins(0, 10, 0, 10)

        self.word_label = QLabel("", alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.word_label.setFont(QFont("MiSans", 26, QFont.Bold))
        self.word_label.setWordWrap(True)
        self.word_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.word_label.setOpenExternalLinks(True)

        self.scroll_layout.addWidget(self.word_label)
        self.scroll_area.setWidget(self.scroll_content)

        # ScrollArea 占据主要空间 - 权重 8 (约占 80%)，用于展示大量文本时
        layout.addWidget(self.scroll_area, 8)

        # 2. 拼写专用提示标签 (替代 ScrollArea 以去除空白)
        # ★★★ 修改：恢复 AlignCenter，权重设为 0。这样它只占实际高度，上下弹簧会将其推至垂直居中 ★★★
        self.phase3_hint_label = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self.phase3_hint_label.setWordWrap(True)
        self.phase3_hint_label.setOpenExternalLinks(True)
        self.phase3_hint_label.hide()
        # 设置权重 0 (不抢占空间)，让上下弹簧发挥作用实现整体居中
        layout.addWidget(self.phase3_hint_label, 0)

        # 3. 单词/填空标签 (Phase 1 Start / Phase 2 Blanks)
        self.cloze_label = QLabel("", alignment=Qt.AlignCenter)
        self.cloze_label.setFont(QFont("MiSans", 28, QFont.Bold))
        self.cloze_label.setWordWrap(True)

        text_color = "#ffffff" if self.is_dark else "#2c3e50"
        self.cloze_label.setStyleSheet(f"color: {text_color}; margin-bottom: 20px;")

        layout.addWidget(self.cloze_label)

        # --- 第二阶段控件 (Phase 1: 认识/不认识) ---
        self.phase2_widget = QWidget()
        know_row = QHBoxLayout(self.phase2_widget)
        know_row.setContentsMargins(0, 10, 0, 10)
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

        # --- 第三阶段控件 (Phase 2: 拼写/提交) ---
        self.phase3_widget = QWidget()
        p3_layout = QVBoxLayout(self.phase3_widget)
        p3_layout.setContentsMargins(0, 10, 0, 10)

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

        # 底部弹簧 (权重 1) - 与顶部弹簧配合实现整体垂直居中
        layout.addStretch(1)

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

        # Apply styles
        self._apply_adaptive_stylesheet()

    def _apply_adaptive_stylesheet(self):
        """根据 is_dark 状态应用不同的样式表"""
        if self.is_dark:
            bg_color = "#2d2d2d"
            text_color = "#ecf0f1"
            border_color = "#444444"
            hover_bg = "#3d3d3d"
            input_bg = "#2d2d2d"
            input_border = "#444444"
            primary_bg = "#2980b9"
            danger_bg = "#c0392b"
            main_bg = "#1e1e1e"
        else:
            bg_color = "#ffffff"
            text_color = "#2c3e50"
            border_color = "#bdc3c7"
            hover_bg = "#ecf0f1"
            input_bg = "#ffffff"
            input_border = "#bdc3c7"
            primary_bg = "#3498db"
            danger_bg = "#e74c3c"
            main_bg = "#f8f9fa"

        self.centralWidget().setStyleSheet(f"#CentralWidget {{ background-color: {main_bg}; }}")

        self.setStyleSheet(f"""
            QPushButton {{
                padding: 12px 24px;
                border: none;
                border-radius: 12px;
                font-size: 16px;
                font-weight: 600;
                margin: 5px;
                box-shadow: 2px 2px 5px rgba(0, 0, 0, 0.1);
            }}
            /* 返回按钮：更小巧 */
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
            #know_btn, #submit_btn, #next_btn {{
                background-color: {primary_bg}; 
                color: #ffffff;
            }}
            #know_btn:hover, #submit_btn:hover, #next_btn:hover {{
                background-color: {primary_bg}AA;
            }}
            #unknow_btn, #wrong_btn, #idk_btn {{
                background-color: {danger_bg}; 
                color: #ffffff;
            }}
            #unknow_btn:hover, #wrong_btn:hover, #idk_btn:hover {{
                background-color: {danger_bg}AA;
            }}
            QPushButton:disabled {{
                background-color: {hover_bg};
                color: #888888;
                border: 1px solid {border_color};
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
        # 激活颜色
        active_border = "#2980b9" if self.is_dark else "#2980b9"
        active_bg = "#3498db" if self.is_dark else "#3498db"
        # 非激活颜色
        inactive_border = "#555555" if self.is_dark else "#bdc3c7"

        for i, dot in enumerate(self.stage_indicators, start=1):
            if i <= phase:
                dot.setStyleSheet(
                    f"border:2px solid {active_border}; border-radius:10px; background-color:{active_bg};")
            else:
                dot.setStyleSheet(
                    f"border:2px solid {inactive_border}; border-radius:10px; background-color:transparent;")

    def _show_next(self):
        # 若在第一阶段 (Recognition)
        if not self.in_phase2:
            if not self.queue:
                # 第一阶段结束，进入第二阶段
                if not self.phase2_queue:
                    self._show_completion()
                    return
                self.in_phase2 = True
                # 切到第二阶段视图
                self.phase2_widget.hide()
                self.phase3_widget.show()
                self._update_stage_indicator(2)

                self.current = self.phase2_queue.pop(0)

                # Spell Mode
                self.scroll_area.hide()
                self.phase3_hint_label.show()
                self.phase3_hint_label.setText(self._get_adaptive_rich_text(self.current, mode="spelling"))

                self.cloze_label.show()
                text_color = "#ffffff" if self.is_dark else "#2c3e50"
                self.cloze_label.setStyleSheet(
                    f"color: {text_color}; font-size: 28px; font-weight: bold; letter-spacing: 4px; margin-bottom: 20px;")
                self.cloze_label.setText(self._make_cloze(self.current.word))

                self.input.setText("")
                self.input.setFocus()
                return

            self.current = self.queue.pop(0)

            # Phase 1 Start: Show Word only
            self.scroll_area.hide()
            self.phase3_hint_label.hide()

            self.cloze_label.show()
            text_color = "#ffffff" if self.is_dark else "#2c3e50"
            self.cloze_label.setStyleSheet(
                f"color: {text_color}; font-size: 40px; font-weight: bold; margin-bottom: 20px;")
            self.cloze_label.setText(self.current.word)

            self.phase2_widget.show()
            self.know_btn.show()
            self.unknow_btn.show()
            self.phase2_wrong_btn.hide()
            self.phase2_next_btn.hide()
            self.phase3_widget.hide()
            self._update_stage_indicator(1)
            return

        # 第二阶段流程 (Spelling)
        if not self.phase2_queue and not self.current:
            self._show_completion()
            return

        if not self.current:
            self.current = self.phase2_queue.pop(0)

        self.phase2_widget.hide()
        self.phase3_widget.show()
        self._update_stage_indicator(2)

        # Spell Mode
        self.scroll_area.hide()
        self.phase3_hint_label.show()
        self.phase3_hint_label.setText(self._get_adaptive_rich_text(self.current, mode="spelling"))

        self.cloze_label.show()
        text_color = "#ffffff" if self.is_dark else "#2c3e50"
        self.cloze_label.setStyleSheet(
            f"color: {text_color}; font-size: 28px; font-weight: bold; letter-spacing: 4px; margin-bottom: 20px;")
        self.cloze_label.setText(self._make_cloze(self.current.word))

        self.input.setText("")
        self.input.setFocus()

    def _show_completion(self):
        self.phase2_widget.hide()
        self.phase3_widget.hide()
        self.scroll_area.hide()
        self.phase3_hint_label.hide()

        text_color = "#ffffff" if self.is_dark else "#2c3e50"
        self.cloze_label.show()
        self.cloze_label.setStyleSheet(f"color: {text_color}; font-size: 32px; font-weight: bold;")
        self.cloze_label.setText("🎉 本次复习完成！ 🎉")

        QTimer.singleShot(3000, self.close)

    def on_know(self):
        if not self.current: return
        self.last_action = "know"

        # Show Full Info
        self.cloze_label.hide()
        self.phase3_hint_label.hide()
        self.scroll_area.show()
        self.word_label.setText(self._get_adaptive_rich_text(self.current, mode="full"))

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

        # Show Full Info
        self.cloze_label.hide()
        self.phase3_hint_label.hide()
        self.scroll_area.show()
        self.word_label.setText(self._get_adaptive_rich_text(self.current, mode="full"))

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
            self._show_completion()
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
        return "".join([("_" if i in idxs else c) for i, c in enumerate(chars)])
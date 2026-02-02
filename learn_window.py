import random, os, csv
import datetime
import re
from collections import deque
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
                               QHBoxLayout, QLineEdit, QMessageBox, QFrame, QGridLayout,
                               QScrollArea)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPalette, QColor

# 导入 VocabModel 和 通用富文本工具函数
from vocab_model import VocabModel, get_word_rich_text


class LearnWindow(QMainWindow):
    """
    单词学习窗口，实现了三阶段学习法：
    阶段1: 词义选择题 (Phase 1)
    阶段2: 认识/不认识自测 (Phase 2)
    阶段3: 拼写填空 (Phase 3)
    """

    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.model.load_settings()
        self.setWindowTitle("单词学习")
        self.setFixedSize(1000, 750)

        # 1. 检测当前主题模式 (亮/暗)
        # 通过检查窗口背景色的亮度来判断。< 128 认为是深色模式。
        self.is_dark = self.palette().window().color().lightness() < 128

        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        # 移除强制背景色，允许继承系统或父窗口背景
        # central.setStyleSheet(...)

        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(40, 30, 30, 30)

        # --- 顶部区域 ---

        # 左上角阶段指示器布局
        self.stage_row = QHBoxLayout()
        self.stage_row.setSpacing(8)
        self.stage_indicators = []

        # 根据主题设置指示器边框颜色
        dot_border = "#555555" if self.is_dark else "#bdc3c7"

        # 创建 3 个圆形指示灯
        for i in range(3):
            dot = QLabel()
            dot.setFixedSize(20, 20)
            dot.setStyleSheet(f"border:2px solid {dot_border}; border-radius:10px; background-color:transparent;")
            self.stage_row.addWidget(dot)
            self.stage_indicators.append(dot)
        self.stage_row.addStretch()  # 将指示灯推到左侧
        layout.addLayout(self.stage_row)

        # # 返回按钮
        # btn_row = QHBoxLayout()
        # btn_row.addStretch()
        # self.btn_return = QPushButton("返回主页面")
        # self.btn_return.setObjectName("return_btn")
        # btn_row.addWidget(self.btn_return)
        # layout.addLayout(btn_row)

        # ★★★ 布局修改：添加顶部弹簧，实现垂直居中 ★★★
        layout.addStretch(1)

        # --- 中央主要内容区 ---

        # 1. 滚动区域 (Phase 2 Reveal 专用 - 详细展示)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent; border: none;")
        # ★★★ 隐藏滚动条 ★★★
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


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

        # ScrollArea 占据主要空间 - 调整权重为 15 (约占 88%)
        layout.addWidget(self.scroll_area, 15)

        # ★★★ Phase 3 专用提示标签 (替代 ScrollArea 以避免大片空白) ★★★
        self.phase3_hint_label = QLabel("", alignment=Qt.AlignCenter)
        self.phase3_hint_label.setWordWrap(True)
        self.phase3_hint_label.setOpenExternalLinks(True)
        self.phase3_hint_label.hide()  # 默认隐藏
        layout.addWidget(self.phase3_hint_label)  # 不设 stretch，由内容撑开，垂直居中由上下弹簧控制

        # 2. 单词/填空标签 (Phase 1/2 Start, Phase 3 Blanks)
        self.cloze_label = QLabel("", alignment=Qt.AlignCenter)
        self.cloze_label.setFont(QFont("MiSans", 28, QFont.Bold))
        self.cloze_label.setWordWrap(True)

        # 根据主题设置文字颜色
        text_color = "#ffffff" if self.is_dark else "#2c3e50"
        self.cloze_label.setStyleSheet(f"color: {text_color}; margin-bottom: 20px;")

        layout.addWidget(self.cloze_label)

        # 3. 阶段内容框架 (按钮区域)
        self.phase_frame = QFrame()
        self.phase_layout = QVBoxLayout(self.phase_frame)
        self.phase_layout.setContentsMargins(0, 10, 0, 10)
        layout.addWidget(self.phase_frame)

        # 4. 输入框 (Phase 3)
        self.spell_input = QLineEdit()
        self.spell_input.setMaximumWidth(600)
        self.spell_input.setFocus()
        input_row = QHBoxLayout()
        input_row.addStretch()
        input_row.addWidget(self.spell_input)
        input_row.addStretch()
        layout.addLayout(input_row)

        # 5. 提交按钮 (Phase 3)
        submit_row = QHBoxLayout()
        submit_row.addStretch()
        self.submit_btn = QPushButton("提交")
        self.submit_btn.setObjectName("submit_btn")
        self.idk_btn = QPushButton("我不会")
        self.idk_btn.setObjectName("idk_btn")
        submit_row.addWidget(self.submit_btn)
        submit_row.addWidget(self.idk_btn)
        submit_row.addStretch()
        layout.addLayout(submit_row)

        # ★★★ 布局修改：保留底部弹簧，与顶部弹簧配合实现居中 ★★★
        layout.addStretch(1)

        # --- 控件初始化 (Phase 1) ---
        self.opt_grid = QGridLayout()
        self.opt_buttons = [QPushButton() for _ in range(4)]
        for i, b in enumerate(self.opt_buttons):
            b.setObjectName("choice_btn")
            b.setFixedHeight(80)
            # 允许文字换行
            b.setStyleSheet("text-align: center; white-space: normal;")
            b.setMinimumWidth(300)
            b.clicked.connect(self.on_choice)
            row = i // 2
            col = i % 2
            self.opt_grid.addWidget(b, row, col)

        self.opt_grid.setAlignment(Qt.AlignCenter)
        self.phase_layout.addLayout(self.opt_grid)
        self.phase_layout.setAlignment(self.opt_grid, Qt.AlignCenter)

        # --- 控件初始化 (Phase 2) ---
        know_row = QHBoxLayout()
        know_row.addStretch()
        self.know_btn = QPushButton("认识")
        self.know_btn.setObjectName("know_btn")
        self.unknow_btn = QPushButton("不认识")
        self.unknow_btn.setObjectName("unknow_btn")
        know_row.addWidget(self.know_btn)
        know_row.addWidget(self.unknow_btn)
        know_row.addStretch()
        self.phase_layout.addLayout(know_row)

        self.know_btn.clicked.connect(self.on_know)
        self.unknow_btn.clicked.connect(self.on_unknow)

        # --- 状态与连接 ---
        self.submit_btn.clicked.connect(self.on_submit)
        self.idk_btn.clicked.connect(self.on_idk)
        # self.btn_return.clicked.connect(self.close)

        self.queue = deque()
        self.current = None
        self.phase2_known_state = True

        self._prepare_queue_and_start()

        # 应用自适应样式表
        self._apply_adaptive_stylesheet()

    def _apply_adaptive_stylesheet(self):
        """根据 is_dark 状态应用不同的样式表"""
        if self.is_dark:
            # 深色模式配色
            bg_color = "#2d2d2d"  # 按钮背景
            text_color = "#ecf0f1"  # 按钮文字
            border_color = "#444444"  # 按钮边框
            hover_bg = "#3d3d3d"  # 悬停背景
            input_bg = "#2d2d2d"
            input_border = "#444444"
            primary_bg = "#2980b9"  # 主要按钮
            danger_bg = "#c0392b"  # 危险按钮
        else:
            # 浅色模式配色
            bg_color = "#ffffff"
            text_color = "#2c3e50"
            border_color = "#bdc3c7"
            hover_bg = "#ecf0f1"
            input_bg = "#ffffff"
            input_border = "#bdc3c7"
            primary_bg = "#3498db"
            danger_bg = "#e74c3c"

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
            #choice_btn {{
                background-color: {bg_color};
                color: {text_color};
                border: 2px solid {border_color};
                min-height: 50px;
            }}
            #return_btn {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                min-height: 32px;
                padding: 4px 12px;
                font-size: 13px;
            }}
            #choice_btn:hover, #return_btn:hover {{
                background-color: {hover_bg};
            }}

            #know_btn, #submit_btn, #next_btn {{
                background-color: {primary_bg}; 
                color: #ffffff;
            }}
            #know_btn:hover, #submit_btn:hover, #next_btn:hover {{
                background-color: {primary_bg}AA; /* 稍微透明一点 */
            }}

            #unknow_btn, #idk_btn, #wrong_btn {{
                background-color: {danger_bg}; 
                color: #ffffff;
            }}
            #unknow_btn:hover, #idk_btn:hover, #wrong_btn:hover {{
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
        """
        获取自适应颜色的富文本。
        如果是深色模式，将生成的 HTML 中的深色字体替换为浅色。
        """
        html = get_word_rich_text(item, mode)
        if self.is_dark:
            # 简单的颜色反转逻辑，适配深色背景
            html = html.replace("#2c3e50", "#ecf0f1")  # 单词深蓝 -> 浅白
            html = html.replace("#7f8c8d", "#bdc3c7")  # 灰色 -> 浅灰
            html = html.replace("#34495e", "#dcdcdc")  # 深灰内容 -> 亮灰
            html = html.replace("#555", "#aaa")
            html = html.replace("#2980b9", "#5dade2")  # 蓝色 -> 亮蓝
            html = html.replace("#e67e22", "#f39c12")  # 橙色 -> 亮橙
        return html

    def _prepare_queue_and_start(self):
        """准备学习队列"""
        today_str = datetime.date.today().isoformat()
        last_date = self.model.settings.get("daily_date", "")
        saved_batch_words = self.model.settings.get("daily_batch", [])
        learn_count = self.model.settings.get("learn_count", 10)

        if last_date != today_str:
            saved_batch_words = []
            self.model.settings["daily_date"] = today_str

        current_batch_objects = []
        if saved_batch_words:
            for w_str in saved_batch_words:
                found = next((w for w in self.model.words if w.word == w_str), None)
                if found and not found.learned:
                    current_batch_objects.append(found)

        if current_batch_objects:
            target_words = current_batch_objects
        else:
            all_unlearned = [w for w in self.model.words if not w.learned]

            if not all_unlearned:
                QMessageBox.information(self, "提示", "恭喜！词库已全部学完。")
                self.close()
                return

            all_unlearned.sort(key=lambda x: x.stage, reverse=True)
            target_words = random.sample(all_unlearned, min(learn_count, len(all_unlearned)))

            new_batch_ids = [w.word for w in target_words]
            self.model.settings["daily_batch"] = new_batch_ids
            self.model.settings["daily_date"] = today_str
            self.model.save_settings()

        stages = {}
        for w in target_words:
            stages.setdefault(w.stage, []).append(w)

        self.queue = deque()
        for st in sorted(stages.keys(), reverse=False):
            grp = stages[st]
            random.shuffle(grp)
            for w in grp:
                self.queue.append(w)

        self._show_next()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.current is None:
                return

            phase = min(max(1, self.current.stage), 3)

            if phase == 1:
                pass
            elif phase == 2:
                if self.know_btn.isVisible() and self.unknow_btn.isVisible():
                    self._phase2_handle(self.current, known=True)
                elif hasattr(self, 'next_btn') and self.next_btn.isVisible():
                    self._phase2_next()
            elif phase == 3:
                self.on_submit()
        else:
            super().keyPressEvent(event)

    def _show_next(self):
        if not self.queue:
            self._hide_all()
            msg = "<span style='color: white;'>🎉 本次学习完成！ 🎉</span>" if self.is_dark else "🎉 本次学习完成！ 🎉"
            self.word_label.setText(msg)
            self.scroll_area.show()
            self.phase3_hint_label.hide()
            self.cloze_label.hide()
            QTimer.singleShot(3000, self.close)
            return

        self.current = self.queue.popleft()
        phase = min(max(1, self.current.stage), 3)
        self._update_stage_indicator(phase)

        if phase == 1:
            self._enter_phase1(self.current)
        elif phase == 2:
            self._enter_phase2(self.current)
        else:
            self._enter_phase3(self.current)

    def _hide_all(self):
        """隐藏所有控件"""
        for b in self.opt_buttons: b.hide()
        self.know_btn.hide()
        self.unknow_btn.hide()
        self.cloze_label.hide()
        self.spell_input.hide()
        self.submit_btn.hide()
        self.idk_btn.hide()
        self.word_label.setText("")
        self.cloze_label.setText("")
        self.phase3_hint_label.hide()
        self.phase3_hint_label.clear()

        if hasattr(self, 'next_btn'): self.next_btn.hide()
        if hasattr(self, 'wrong_btn'): self.wrong_btn.hide()

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

    def _enter_phase1(self, item):
        """进入阶段 1：词义选择题"""
        self._hide_all()

        # 1. 隐藏 ScrollArea (中间空白)
        self.scroll_area.hide()
        self.phase3_hint_label.hide()

        # 2. 显示单词 (使用紧凑 Label，根据主题设置颜色)
        self.cloze_label.show()
        text_color = "#ffffff" if self.is_dark else "#2c3e50"
        self.cloze_label.setStyleSheet(f"color: {text_color}; font-size: 40px; font-weight: bold; margin-bottom: 20px;")
        self.cloze_label.setText(item.word)

        # 3. 显示按钮容器
        self.phase_frame.show()
        for b in self.opt_buttons: b.show()

        correct = item.pos + "." + item.definition or ""
        distract = [w.pos + "." + w.definition for w in self.model.words if w.word != item.word and w.definition]
        distract = list(dict.fromkeys(distract))
        random.shuffle(distract)

        opts = [correct] + distract[:3]
        while len(opts) < 4: opts.append("")
        random.shuffle(opts)

        for b, t in zip(self.opt_buttons, opts): b.setText(t)

    def _enter_phase2(self, item):
        """进入阶段 2：认识/不认识自测"""
        self._hide_all()

        # 1. 隐藏 ScrollArea
        self.scroll_area.hide()
        self.phase3_hint_label.hide()

        # 2. 显示单词
        self.cloze_label.show()
        text_color = "#ffffff" if self.is_dark else "#2c3e50"
        self.cloze_label.setStyleSheet(f"color: {text_color}; font-size: 40px; font-weight: bold; margin-bottom: 20px;")
        self.cloze_label.setText(item.word)

        # 3. 显示按钮容器
        self.phase_frame.show()
        for b in self.opt_buttons: b.hide()
        self.spell_input.hide()
        self.submit_btn.hide()
        self.idk_btn.hide()

        self.know_btn.show()
        self.unknow_btn.show()

        try:
            self.know_btn.clicked.disconnect()
            self.unknow_btn.clicked.disconnect()
        except:
            pass

        self.know_btn.clicked.connect(lambda checked=False, i=item: self._phase2_handle(i, known=True))
        self.unknow_btn.clicked.connect(lambda checked=False, i=item: self._phase2_handle(i, known=False))

    def _phase2_handle(self, item, known=True):
        """处理阶段 2 首次点击后的界面切换"""
        self.phase2_known_state = known
        self.know_btn.hide()
        self.unknow_btn.hide()

        # ★★★ 揭晓后：隐藏紧凑标签，显示完整富文本 ScrollArea (使用自适应模式) ★★★
        self.cloze_label.hide()
        self.phase3_hint_label.hide()
        self.scroll_area.show()
        self.word_label.setText(self._get_adaptive_rich_text(item, mode="full"))

        if not hasattr(self, 'next_btn'):
            self.next_btn = QPushButton("下一个")
            self.next_btn.setObjectName("next_btn")
            self.wrong_btn = QPushButton("我记错了")
            self.wrong_btn.setObjectName("wrong_btn")

            self.phase2_btn_row = QHBoxLayout()
            self.phase2_btn_row.addStretch()
            self.phase2_btn_row.addWidget(self.next_btn)
            self.phase2_btn_row.addWidget(self.wrong_btn)
            self.phase2_btn_row.addStretch()
            self.phase_layout.addLayout(self.phase2_btn_row)

            self.next_btn.clicked.connect(self._phase2_next)
            self.wrong_btn.clicked.connect(lambda checked=False, i=item: self._phase2_wrong(i))

        self.next_btn.show()

        if known:
            self.wrong_btn.show()
        else:
            self.wrong_btn.hide()

    def _phase2_next(self):
        self.next_btn.hide()
        self.wrong_btn.hide()

        if self.current:
            if self.phase2_known_state:
                self.current.stage = min(3, self.current.stage + 1)
                self.queue.append(self.current)
                self.model.save_progress()
            else:
                self.current.stage = 1
                self.current.attempts += 1
                self.queue.append(self.current)
                self.model.save_progress()

                size = len(self.queue)
                rotated = 0
                while rotated < size:
                    if len(self.queue) == 0: break
                    if getattr(self.queue[0], "stage", 1) == 1:
                        break
                    self.queue.append(self.queue.popleft())
                    rotated += 1

        self._show_next()

    def _phase2_wrong(self, item):
        item.stage = 1
        item.attempts += 1
        self.queue.append(item)
        self.model.save_progress()
        self.next_btn.hide()
        self.wrong_btn.hide()
        self._show_next()

    def _enter_phase3(self, item):
        """进入阶段 3：拼写填空"""
        self._hide_all()
        # 隐藏 Phase 1/2 的按钮框架
        self.phase_frame.hide()

        self.cloze_label.show()
        self.spell_input.show()
        self.submit_btn.show()
        self.idk_btn.show()

        # Phase 3: 显示填空横线
        text_color = "#ffffff" if self.is_dark else "#2c3e50"
        self.cloze_label.setStyleSheet(
            f"color: {text_color}; font-size: 28px; font-weight: bold; letter-spacing: 4px; margin-bottom: 20px;")
        self.cloze_label.setText(self._make_cloze(item.word))

        # ★★★ Phase 3: 隐藏 ScrollArea (去除空白)，使用紧凑的 Label 显示提示 ★★★
        self.scroll_area.hide()
        self.phase3_hint_label.show()
        self.phase3_hint_label.setText(self._get_adaptive_rich_text(item, mode="spelling"))

        self.spell_input.setText("")
        self.spell_input.setFocus()

    def on_choice(self):
        btn = self.sender()
        if not self.current: return

        if btn.text().strip() == (self.current.pos + "." + self.current.definition or "").strip():
            self.current.stage = min(3, self.current.stage + 1)
            QMessageBox.information(self, "正确", "回答正确")
        else:
            self.current.stage = max(1, self.current.stage - 1)
            self.current.attempts += 1
            QMessageBox.warning(self, "错误", f"正确释义: {self.current.pos + '.' + self.current.definition or ''}")

        self.queue.append(self.current)
        self.model.save_progress()
        QTimer.singleShot(100, self._show_next)

    def on_know(self):
        if not self.current: return
        self.current.stage = min(3, self.current.stage + 1)
        self.queue.append(self.current)
        self.model.save_progress()
        QTimer.singleShot(100, self._show_next)

    def on_unknow(self):
        if not self.current: return
        self.current.stage = max(1, self.current.stage - 1)
        self.current.attempts += 1
        self.queue.append(self.current)
        self.model.save_progress()
        QTimer.singleShot(100, self._show_next)

    def on_submit(self):
        if not self.current: return
        s = self.spell_input.text().strip()
        self.current.attempts += 1

        if s.lower() == (self.current.word or "").lower():
            self.current.learned = True
            self.current.stage = min(3, self.current.stage + 0)
            self.model.save_progress()
            QMessageBox.information(self, "正确", "拼写正确")
            QTimer.singleShot(200, self._show_next)
        else:
            QMessageBox.information(self, "错误", f"正确: {self.current.word}")
            self.current.learned = False
            self.current.stage = 1
            self.queue.append(self.current)
            self.model.save_progress()
            QTimer.singleShot(100, self._show_next)

    def on_idk(self):
        if not self.current: return
        QMessageBox.information(self, "提示", f"正确: {self.current.word}")
        self.current.stage = 1
        self.queue.append(self.current)
        self.model.save_progress()
        QTimer.singleShot(200, self._show_next)

    def _make_cloze(self, word):
        chars = list(word)
        import random as _r
        if len(chars) == 0: return ""
        n = max(1, min(len(chars) - 1, _r.randint(1, max(1, len(chars) // 2))))
        idxs = _r.sample(range(len(chars)), n)
        return " ".join([("_" if i in idxs else c) for i, c in enumerate(chars)])
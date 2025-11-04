import os, csv, json
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, \
    QSpinBox, QTextEdit, QGroupBox, QFileDialog, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from vocab_model import VocabModel  # 假设 VocabModel 和 WordItem 都在 vocab_model.py 中


class SettingWindow(QMainWindow):
    """
    设置窗口：用于管理单词库导入、学习进度保存/加载，以及配置学习、复习、测试的单次单词数量。
    同时显示当前的学习、复习和测试进度。
    """

    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("设置与进度管理")
        self.setFixedSize(1000, 700)
        self.central = QWidget()
        self.setCentralWidget(self.central)

        font = QFont("MiSans", 11, QFont.Bold)
        main_layout = QVBoxLayout(self.central)

        # --- 顶部操作区域：导入/导出/加载 ---
        top_group = QGroupBox()
        top_group.setStyleSheet("QGroupBox{border:1px solid #ccc;border-radius:12px;padding:10px;}")
        top_layout = QHBoxLayout(top_group)

        # 按钮定义
        self.btn_import = QPushButton("导入单词库")
        self.btn_open = QPushButton("打开单词库")
        self.btn_save = QPushButton("保存学习进度")
        self.btn_load = QPushButton("加载学习进度")

        # 统一设置按钮样式
        for b in [self.btn_import, self.btn_open, self.btn_save, self.btn_load]:
            b.setFont(font)
            b.setFixedHeight(36)
            b.setStyleSheet(
                "QPushButton{background-color:#0078d7;color:white;border:none;border-radius:8px;} QPushButton:hover{background-color:#339af0;}")
            top_layout.addWidget(b)

        main_layout.addWidget(top_group)

        # --- 底部布局：左侧进度/设置，右侧单词列表 ---
        bottom_layout = QHBoxLayout()

        # --- 左侧区域：进度条 + 数量设置 ---
        left_group = QGroupBox()
        left_group.setStyleSheet("QGroupBox{border:1px solid #ddd;border-radius:12px;padding:12px;}")
        left_layout = QVBoxLayout(left_group)

        # 1. 学习进度条
        self.progress = QProgressBar()
        self.progress.setFixedHeight(28)
        self.progress.setStyleSheet(
            "QProgressBar{border:1px solid #aaa;border-radius:10px;text-align:center;} QProgressBar::chunk{background-color:#0078d7;border-radius:10px;}")

        # 2. 新增复习进度条 (橙色)
        self.review_progress = QProgressBar()
        self.review_progress.setFixedHeight(28)
        self.review_progress.setStyleSheet(
            "QProgressBar{border:1px solid #aaa;border-radius:10px;text-align:center;} QProgressBar::chunk{background-color:#ffa500;border-radius:10px;}")

        # 3. 新增测试进度条 (绿色)
        self.test_progress = QProgressBar()
        self.test_progress.setFixedHeight(28)
        self.test_progress.setStyleSheet(
            "QProgressBar{border:1px solid #aaa;border-radius:10px;text-align:center;} QProgressBar::chunk{background-color:#32cd32;border-radius:10px;}")

        # 将进度条添加到布局
        left_layout.addWidget(QLabel("学习进度 (已学 / 全部)："))
        left_layout.addWidget(self.progress)
        left_layout.addWidget(QLabel("复习进度 (已复习 / 已学习)："))
        left_layout.addWidget(self.review_progress)
        left_layout.addWidget(QLabel("测试进度 (已测试 / 全部)："))
        left_layout.addWidget(self.test_progress)

        # --- 数量设置 SpinBox ---
        # 学习数量设置
        self.learn_spin = QSpinBox()
        self.learn_spin.setMaximum(999)
        self.learn_spin.setValue(self.model.settings.get("learn_count", 10))

        # 复习数量设置
        self.review_spin = QSpinBox()
        self.review_spin.setMaximum(999)
        self.review_spin.setValue(self.model.settings.get("review_count", 15))

        # 测试数量设置
        self.test_spin = QSpinBox()
        self.test_spin.setMaximum(999)
        self.test_spin.setValue(self.model.settings.get("test_count", 20))

        # 绑定值变化信号到自动保存函数
        self.learn_spin.valueChanged.connect(lambda v: self._auto_save_setting("learn_count", v))
        self.review_spin.valueChanged.connect(lambda v: self._auto_save_setting("review_count", v))
        self.test_spin.valueChanged.connect(lambda v: self._auto_save_setting("test_count", v))

        # 封装 SpinBox 到 QGroupBox
        for title, spin in [("学习模式", self.learn_spin), ("复习模式", self.review_spin),
                            ("测试模式", self.test_spin)]:
            gb = QGroupBox(title)
            gb.setStyleSheet("QGroupBox{border:1px solid #eee;border-radius:10px;padding:8px;}")
            gbl = QHBoxLayout(gb)
            gbl.addWidget(QLabel("单次单词数："))
            gbl.addWidget(spin)
            left_layout.addWidget(gb)

        bottom_layout.addWidget(left_group, 2)  # 左侧权重 2

        # --- 右侧区域：当前单词库列表 ---
        right_group = QGroupBox("当前单词库")
        right_group.setStyleSheet("QGroupBox{border:1px solid #ccc;border-radius:12px;padding:10px;}")
        right_layout = QVBoxLayout(right_group)
        self.words_view = QTextEdit()
        self.words_view.setReadOnly(True)  # 设置为只读
        right_layout.addWidget(self.words_view)
        bottom_layout.addWidget(right_group, 3)  # 右侧权重 3

        main_layout.addLayout(bottom_layout)

        # --- 信号连接 ---
        self.btn_import.clicked.connect(self.import_csv)
        self.btn_open.clicked.connect(self.open_csv)
        self.btn_save.clicked.connect(self.save_progress)
        self.btn_load.clicked.connect(self.load_progress)

        # 初始化视图
        self.refresh_view()

    def import_csv(self):
        """导入新的 CSV 单词库，替换现有数据并保存进度。"""
        # 打开文件对话框，筛选 CSV 文件
        path, _ = QFileDialog.getOpenFileName(self, "选择 CSV 单词库文件", "", "CSV Files (*.csv);;All Files (*)")
        if not path: return

        # 加载新的词库
        self.model.load_words_from_csv(path)
        # 立即保存进度，将新的词库作为当前进度的一部分保存
        self.model.save_progress()

        QMessageBox.information(self, "导入成功",
                                f"成功导入 {len(self.model.words)} 个单词并保存到 data/last_words.csv")
        self.refresh_view()  # 刷新界面显示新的统计数据和单词列表

    def open_csv(self):
        """打开并预览当前单词库的内容。"""
        # 尝试获取上次导入的 CSV 路径
        path = self.model.last_words_path if os.path.exists(self.model.last_words_path) else None

        # 如果路径不存在，让用户选择一个文件
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "选择 CSV 单词库文件进行预览", "",
                                                  "CSV Files (*.csv);;All Files (*)")
            if not path: return

        try:
            # 读取文件内容
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()

            # 使用 QTextEdit 弹窗展示内容
            dlg = QTextEdit()
            dlg.setReadOnly(True)
            dlg.setPlainText(data)
            dlg.setWindowTitle(f"词库内容预览: {os.path.basename(path)}")
            dlg.resize(640, 420)
            dlg.show()

            # 保持对弹窗的引用，防止被垃圾回收
            self._preview = dlg
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开文件失败: {str(e)}")

    def save_progress(self):
        """保存当前的所有设置（SpinBox 值）和单词学习进度（Stage、Learned 状态）。"""
        # 1. 保存设置 (Settings.json)
        self.model.settings["learn_count"] = self.learn_spin.value()
        self.model.settings["review_count"] = self.review_spin.value()
        self.model.settings["test_count"] = self.test_spin.value()
        self.model.save_settings()

        # 2. 保存学习进度 (Progress.json)
        self.model.save_progress()

        QMessageBox.information(self, "保存成功", "设置与学习进度已保存到 data/ 目录")
        self.refresh_view()

    def load_progress(self):
        """从 progress.json 文件中加载单词学习进度。"""
        path = os.path.join("data", "progress.json")
        if os.path.exists(path):
            self.model.load_progress(path)
            QMessageBox.information(self, "加载成功", "已从 data/progress.json 加载进度")
            self.refresh_view()  # 刷新界面显示加载后的数据
        else:
            QMessageBox.information(self, "加载失败", "没有找到 data/progress.json 进度文件")

    def refresh_view(self):
        """更新所有进度条和单词列表的显示。"""
        # 获取基础统计数据
        learned, total = self.model.get_stats()

        # --- 学习进度条 (蓝色) ---
        self.progress.setMaximum(total if total > 0 else 1)
        self.progress.setValue(learned)
        self.progress.setFormat(f"已学习 {learned} / 全部 {total}")

        # 筛选不同状态的单词
        learned_words = [w for w in self.model.words if w.learned]
        reviewed_words = [w for w in learned_words if w.reviewed]
        tested_words = [w for w in self.model.words if w.tested]

        learned_count = len(learned_words)
        reviewed_count = len(reviewed_words)
        tested_count = len(tested_words)

        # --- 复习进度条 (橙色) ---
        # 复习进度：已复习 (reviewed) ÷ 已学习 (learned)
        self.review_progress.setMaximum(learned_count if learned_count > 0 else 1)
        self.review_progress.setValue(reviewed_count)
        self.review_progress.setFormat(f"已复习 {reviewed_count} / 已学习 {learned_count}")

        # --- 测试进度条 (绿色) ---
        # 测试进度：已测试 (tested) ÷ 全部单词 (total)
        self.test_progress.setMaximum(total if total > 0 else 1)
        self.test_progress.setValue(tested_count)
        self.test_progress.setFormat(f"已测试 {tested_count} / 全部 {total}")

        # --- 单词列表视图 ---
        # 格式化单词列表 (单词, 释义)
        lines = [f"[{w.stage}] {w.word} : {w.definition}" for w in self.model.words]
        self.words_view.setPlainText("\n".join(lines))

    def _auto_save_setting(self, key, value):
        """当 SpinBox 改变时自动保存单个设置到 settings.json 文件。"""
        self.model.settings[key] = value
        self.model.save_settings()  # 即时写入 settings.json

import os, csv, json
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QSpinBox, QTextEdit, QGroupBox, QFileDialog, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from vocab_model import VocabModel

class SettingWindow(QMainWindow):
    def __init__(self, model: VocabModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("")
        self.setFixedSize(1000,700)
        self.central = QWidget(); self.setCentralWidget(self.central)
        font = QFont("MiSans", 11, QFont.Bold)
        main_layout = QVBoxLayout(self.central)
        # top operations
        top_group = QGroupBox()
        top_group.setStyleSheet("QGroupBox{border:1px solid #ccc;border-radius:12px;padding:10px;}")
        top_layout = QHBoxLayout(top_group)
        self.btn_import = QPushButton("导入单词库"); self.btn_open = QPushButton("打开单词库"); self.btn_save = QPushButton("保存学习进度"); self.btn_load = QPushButton("加载学习进度")
        for b in [self.btn_import, self.btn_open, self.btn_save, self.btn_load]:
            b.setFont(font); b.setFixedHeight(36)
            b.setStyleSheet("QPushButton{background-color:#0078d7;color:white;border:none;border-radius:8px;} QPushButton:hover{background-color:#339af0;}")
            top_layout.addWidget(b)
        main_layout.addWidget(top_group)
        # bottom split
        bottom_layout = QHBoxLayout()
        # left box: progress + settings
        left_group = QGroupBox(); left_group.setStyleSheet("QGroupBox{border:1px solid #ddd;border-radius:12px;padding:12px;}")
        left_layout = QVBoxLayout(left_group)
        self.progress = QProgressBar(); self.progress.setFixedHeight(28)
        self.progress.setStyleSheet("QProgressBar{border:1px solid #aaa;border-radius:10px;text-align:center;} QProgressBar::chunk{background-color:#0078d7;border-radius:10px;}")
        left_layout.addWidget(QLabel("学习进度：")); left_layout.addWidget(self.progress)
        # mode settings
        self.learn_spin = QSpinBox(); self.learn_spin.setMaximum(999)
        self.learn_spin.setValue(self.model.settings.get("learn_count", 10))
        self.review_spin = QSpinBox(); self.review_spin.setMaximum(999); self.review_spin.setValue(self.model.settings.get("review_count",15))
        self.test_spin = QSpinBox(); self.test_spin.setMaximum(999); self.test_spin.setValue(self.model.settings.get("test_count",20))

        self.learn_spin.valueChanged.connect(lambda v: self._auto_save_setting("learn_count", v))
        self.review_spin.valueChanged.connect(lambda v: self._auto_save_setting("review_count", v))
        self.test_spin.valueChanged.connect(lambda v: self._auto_save_setting("test_count", v))

        for title, spin in [("Learn", self.learn_spin), ("Review", self.review_spin), ("Test", self.test_spin)]:
            gb = QGroupBox(title); gb.setStyleSheet("QGroupBox{border:1px solid #eee;border-radius:10px;padding:8px;}")
            gbl = QHBoxLayout(gb)
            gbl.addWidget(QLabel("单次学习单词数：")); gbl.addWidget(spin)
            left_layout.addWidget(gb)
        bottom_layout.addWidget(left_group,2)
        # right box: current word list
        right_group = QGroupBox("当前单词库"); right_group.setStyleSheet("QGroupBox{border:1px solid #ccc;border-radius:12px;padding:10px;}")
        right_layout = QVBoxLayout(right_group)
        self.words_view = QTextEdit(); self.words_view.setReadOnly(True)
        right_layout.addWidget(self.words_view)
        bottom_layout.addWidget(right_group,3)
        main_layout.addLayout(bottom_layout)
        # connect signals
        self.btn_import.clicked.connect(self.import_csv)
        self.btn_open.clicked.connect(self.open_csv)
        self.btn_save.clicked.connect(self.save_progress)
        self.btn_load.clicked.connect(self.load_progress)
        # initialize view
        self.refresh_view()

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 CSV", "", "CSV Files (*.csv);;All Files (*)")
        if not path: return
        self.model.load_words_from_csv(path)
        self.model.save_progress()
        QMessageBox.information(self, "导入", f"导入 {len(self.model.words)} 个单词并保存到 data/last_words.csv")
        self.refresh_view()

    def open_csv(self):
        path = self.model.last_words_path if os.path.exists(self.model.last_words_path) else None
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "打开 CSV", "", "CSV Files (*.csv);;All Files (*)")
            if not path: return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
            # show preview dialog
            dlg = QTextEdit(); dlg.setReadOnly(True); dlg.setPlainText(data)
            dlg.setWindowTitle("词库内容预览"); dlg.resize(640,420); dlg.show()
            self._preview = dlg
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))

    def save_progress(self):
        # 先保存设置
        self.model.settings["learn_count"] = self.learn_spin.value()
        self.model.settings["review_count"] = self.review_spin.value()
        self.model.settings["test_count"] = self.test_spin.value()
        self.model.save_settings()  # ✅ 保存 settings.json

        # 再保存学习进度（单词状态）
        self.model.save_progress()

        QMessageBox.information(self, "保存", "设置与学习进度已保存到 data/")
        self.refresh_view()

    def load_progress(self):
        path = os.path.join("data","progress.json")
        if os.path.exists(path):
            self.model.load_progress(path)
            QMessageBox.information(self, "加载", "已从 data/progress.json 加载进度")
            self.refresh_view()
        else:
            QMessageBox.information(self, "加载", "没有找到 data/progress.json")

    def refresh_view(self):
        learned, total = self.model.get_stats()
        self.progress.setMaximum(total if total>0 else 1)
        self.progress.setValue(learned)
        self.progress.setFormat(f"已学习 {learned} / 全部 {total}")
        # word list plain lines
        lines = [f"{w.word} , {w.definition}" for w in self.model.words]
        self.words_view.setPlainText("\n".join(lines))

    def _auto_save_setting(self, key, value):
        """当 SpinBox 改变时自动保存设置"""
        self.model.settings[key] = value
        self.model.save_settings()  # ✅ 即时写入 settings.json


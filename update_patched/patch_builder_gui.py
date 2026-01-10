import sys
import os
import hashlib
import time
import zipfile
import json
import re
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QFileDialog, QTextEdit, QGroupBox, QMessageBox, QProgressBar, QGridLayout)
from PySide6.QtCore import QThread, Signal
import fnmatch


# ==========================================
# 核心工作线程 (后台处理)
# ==========================================
class PatchWorker(QThread):
    log_signal = Signal(str)  # 日志信号
    progress_signal = Signal(int)  # 进度信号
    finished_signal = Signal(bool, str)  # 完成信号

    def __init__(self, old_dir, new_dir, output_name, new_version, exclude_patterns=None):
        super().__init__()
        self.old_dir = old_dir
        self.new_dir = new_dir
        self.output_name = output_name
        self.new_version = new_version
        self._is_running = True
        self.exclude_patterns = exclude_patterns or []

    def _excluded(self, rel_path):
        """是否命中排除模式（相对路径或文件名）"""
        for pat in self.exclude_patterns:
            if not pat: continue
            if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(os.path.basename(rel_path), pat):
                return True
        return False

    def get_file_md5(self, filepath):
        """计算文件 MD5"""
        if not os.path.isfile(filepath):
            return None
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def scan_directory(self, directory):
        """扫描目录并返回 {相对路径: MD5}，支持排除模式"""
        file_map = {}
        directory = os.path.normpath(directory)

        # 预先计算文件总数用于进度条
        total_files = sum([len(files) for r, d, files in os.walk(directory)])
        scanned_count = 0

        for root, _, files in os.walk(directory):
            for file in files:
                if not self._is_running: return {}

                full_path = os.path.join(root, file)
                rel_path = str(os.path.relpath(full_path, directory))

                # 忽略一些不需要打包的文件
                if file.endswith('.pyc') or '__pycache__' in rel_path or file.endswith('.DS_Store'):
                    continue

                # 应用排除模式
                if self._excluded(rel_path):
                    continue

                file_map[rel_path] = self.get_file_md5(full_path)

                scanned_count += 1
                # 扫描过程占总进度的 40%
                if total_files > 0:
                    self.progress_signal.emit(int((scanned_count / total_files) * 40))

        return file_map

    def run(self):
        try:
            self.log_signal.emit(f"🔍 开始扫描旧版本: {self.old_dir}")
            old_files = self.scan_directory(self.old_dir)

            self.log_signal.emit(f"🔍 开始扫描新版本: {self.new_dir}")
            self.progress_signal.emit(40)  # 重置进度起点
            new_files = self.scan_directory(self.new_dir)

            added = []
            modified = []
            deleted = []

            # 1. 比对差异
            self.log_signal.emit("⚖️ 正在比对文件差异...")
            for file_path, new_md5 in new_files.items():
                if file_path not in old_files:
                    added.append(file_path)
                elif old_files[file_path] != new_md5:
                    modified.append(file_path)

            for file_path in old_files:
                if file_path not in new_files:
                    deleted.append(file_path)

            # 如果排除了文件，输出提示
            if self.exclude_patterns:
                self.log_signal.emit(f"🧹 已应用排除模式: {', '.join(self.exclude_patterns)}")

            self.log_signal.emit("-" * 40)
            self.log_signal.emit(f"📊 [新增]: {len(added)} 个文件")
            self.log_signal.emit(f"📊 [修改]: {len(modified)} 个文件")
            self.log_signal.emit(f"📊 [删除]: {len(deleted)} 个文件")
            self.log_signal.emit("-" * 40)

            files_to_pack = added + modified

            if not files_to_pack and not deleted:
                self.finished_signal.emit(True, "✅ 没有检测到文件变化，无需生成补丁。")
                return

            # 2. 生成清单
            manifest = {
                "version": self.new_version,
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "actions": {
                    "delete": deleted
                }
            }

            # 3. 打包 Zip
            self.log_signal.emit(f"📦 正在打包至: {self.output_name} ...")

            with zipfile.ZipFile(self.output_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                total_pack = len(files_to_pack)
                for idx, file_path in enumerate(files_to_pack):
                    if not self._is_running: return

                    src_path = os.path.join(self.new_dir, file_path)
                    self.log_signal.emit(f"  + 添加: {file_path}")
                    zipf.write(str(src_path), arcname=str(file_path))

                    # 打包过程占总进度的剩余 20% (80% -> 100%)
                    progress = 80 + (int(((idx + 1) / total_pack) * 20) if total_pack > 0 else 20)
                    self.progress_signal.emit(progress)

                # 写入清单文件
                zipf.writestr("patch_manifest.json", json.dumps(manifest, indent=2))
                self.log_signal.emit("  + 添加: patch_manifest.json")

            self.progress_signal.emit(100)
            self.finished_signal.emit(True, f"✅ 补丁包生成成功！\n文件: {self.output_name}")

        except Exception as e:
            self.finished_signal.emit(False, str(e))

    def stop(self):
        self._is_running = False


# ==========================================
# 主界面 UI
# ==========================================
class PatchBuilderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LearnWord 增量补丁生成器")
        self.setFixedSize(700, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- 1. 目录选择区域 ---
        dir_group = QGroupBox("1. 版本目录选择")
        dir_layout = QVBoxLayout(dir_group)

        # 旧版本
        h1 = QHBoxLayout()
        self.old_dir_edit = QLineEdit()
        self.old_dir_edit.setPlaceholderText("选择旧版本的文件夹 (例如 dist_v1.0/LearnWord)")
        btn_old = QPushButton("浏览...")
        btn_old.clicked.connect(lambda: self.select_dir_with_version(self.old_dir_edit, self.old_ver_edit))
        h1.addWidget(QLabel("旧版目录:"))
        h1.addWidget(self.old_dir_edit)
        h1.addWidget(btn_old)
        dir_layout.addLayout(h1)

        # 新版本
        h2 = QHBoxLayout()
        self.new_dir_edit = QLineEdit()
        self.new_dir_edit.setPlaceholderText("选择新版本的文件夹 (例如 dist_v1.1/LearnWord)")
        btn_new = QPushButton("浏览...")
        btn_new.clicked.connect(lambda: self.select_dir_with_version(self.new_dir_edit, self.new_ver_edit))
        h2.addWidget(QLabel("新版目录:"))
        h2.addWidget(self.new_dir_edit)
        h2.addWidget(btn_new)
        dir_layout.addLayout(h2)

        layout.addWidget(dir_group)

        # --- 2. 版本号与文件名 ---
        ver_group = QGroupBox("2. 版本信息与输出")
        ver_layout = QGridLayout(ver_group)

        self.old_ver_edit = QLineEdit("v1.0.0")
        self.new_ver_edit = QLineEdit("v1.1.0")
        self.output_edit = QLineEdit()
        self.output_edit.setReadOnly(False)  # 允许手动微调
        self.output_edit.setPlaceholderText("将自动生成文件名...")

        # 排除模式输入（分号分隔，支持通配符）
        self.exclude_edit = QLineEdit("updater.exe;*.ico;*.mp4")
        self.exclude_edit.setPlaceholderText("可选：排除的文件模式，如 updater.exe;*.ico;*.mp4")

        # 绑定自动重命名逻辑
        self.old_ver_edit.textChanged.connect(self.update_filename)
        self.new_ver_edit.textChanged.connect(self.update_filename)

        # 初始化一次文件名
        self.update_filename()

        ver_layout.addWidget(QLabel("旧版本号:"), 0, 0)
        ver_layout.addWidget(self.old_ver_edit, 0, 1)
        ver_layout.addWidget(QLabel("新版本号:"), 0, 2)
        ver_layout.addWidget(self.new_ver_edit, 0, 3)

        ver_layout.addWidget(QLabel("输出文件:"), 1, 0)
        ver_layout.addWidget(self.output_edit, 1, 1, 1, 3)

        ver_layout.addWidget(QLabel("排除模式:"), 2, 0)
        ver_layout.addWidget(self.exclude_edit, 2, 1, 1, 3)

        layout.addWidget(ver_group)

        # --- 3. 操作区域 ---
        self.btn_build = QPushButton("开始生成补丁包")
        self.btn_build.setMinimumHeight(45)
        self.btn_build.setStyleSheet("""
            QPushButton {
                background-color: #0078d7; 
                color: white; 
                font-weight: bold; 
                font-size: 15px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #0063b1; }
            QPushButton:disabled { background-color: #cccccc; }
        """)
        self.btn_build.clicked.connect(self.start_build)
        layout.addWidget(self.btn_build)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            "QProgressBar { height: 5px; border: none; background: #e0e0e0; } QProgressBar::chunk { background: #0078d7; }")
        layout.addWidget(self.progress_bar)

        # --- 4. 日志区域 ---
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas; font-size: 12px;")
        log_layout.addWidget(self.log_view)
        layout.addWidget(log_group)

        # 全局样式
        self.setStyleSheet("""
            QGroupBox { font-weight: bold; border: 1px solid #ccc; border-radius: 5px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
            QLineEdit { padding: 5px; border: 1px solid #ccc; border-radius: 3px; }
        """)

    def update_filename(self):
        """根据版本号自动更新输出文件名"""
        old_v = self.old_ver_edit.text().strip()
        new_v = self.new_ver_edit.text().strip()
        # 自动生成格式: update_patch_v1.0to_v1.1.zip
        filename = f"update_patch_{old_v}to_{new_v}.zip"
        self.output_edit.setText(filename)

    def extract_version_from_path(self, path):
        """从路径中提取版本号，支持 'v1.1.0' 或 'LearnWord v1.1.0' 等格式"""
        if not path:
            return None

        # 获取路径的最后一个目录名
        folder_name = os.path.basename(os.path.normpath(path))

        # 支持的版本号模式：v1.2.3 或 v1.2 等
        version_patterns = [
            r'v(\d+\.\d+\.\d+)',  # v1.2.3
            r'v(\d+\.\d+)',        # v1.2
            r'(\d+\.\d+\.\d+)',    # 1.2.3 (无 v 前缀)
            r'(\d+\.\d+)',         # 1.2 (无 v 前缀)
        ]

        for pattern in version_patterns:
            match = re.search(pattern, folder_name)
            if match:
                version = match.group(1)
                # 如果原始匹配中有 'v'，则保留；否则添加 'v'
                if 'v' in match.group(0):
                    return f"v{version}"
                else:
                    # 检查原始字符串是否有 v 前缀
                    if folder_name.lower().find('v' + version) >= 0:
                        return f"v{version}"
                    return f"v{version}"

        return None

    def select_dir(self, line_edit):
        path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if path:
            line_edit.setText(path)

    def select_dir_with_version(self, dir_edit, ver_edit):
        """选择目录并自动提取版本号"""
        path = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if path:
            dir_edit.setText(path)
            # 尝试从路径提取版本号
            version = self.extract_version_from_path(path)
            if version:
                ver_edit.setText(version)
                self.log(f"✅ 自动识别版本号: {version}")

    def log(self, msg):
        self.log_view.append(msg)
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def start_build(self):
        old_dir = self.old_dir_edit.text().strip()
        new_dir = self.new_dir_edit.text().strip()
        out_name = self.output_edit.text().strip()
        new_ver = self.new_ver_edit.text().strip()

        if not old_dir or not new_dir:
            QMessageBox.warning(self, "提示", "请先选择旧版本和新版本的目录！")
            return

        if not os.path.exists(old_dir) or not os.path.exists(new_dir):
            QMessageBox.warning(self, "错误", "所选路径不存在，请检查。")
            return

        # 解析排除模式
        exclude_patterns = [p.strip() for p in self.exclude_edit.text().split(';') if p.strip()]

        # 锁定界面
        self.btn_build.setEnabled(False)
        self.log_view.clear()
        self.progress_bar.setValue(0)
        self.log(f"准备生成补丁: {new_ver}")
        if exclude_patterns:
            self.log(f"应用排除模式: {', '.join(exclude_patterns)}")

        # 启动后台线程
        self.worker = PatchWorker(old_dir, new_dir, out_name, new_ver, exclude_patterns)
        self.worker.log_signal.connect(self.log)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, success, msg):
        self.btn_build.setEnabled(True)
        if success:
            QMessageBox.information(self, "成功", msg)
            self.log(f"\n✅ 操作完成")
        else:
            QMessageBox.critical(self, "失败", msg)
            self.log(f"\n❌ 操作失败: {msg}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PatchBuilderWindow()
    window.show()
    sys.exit(app.exec())
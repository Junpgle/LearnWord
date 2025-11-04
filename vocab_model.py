import csv, json, os, shutil
from dataclasses import dataclass, asdict
from typing import List


@dataclass
class WordItem:
    """
    单词数据结构：使用 dataclass 简化定义，存储单词的全部状态和信息。
    """
    word: str
    definition: str = ""  # 释义
    pos: str = ""  # 词性 (Part of Speech)
    example: str = ""  # 例句
    stage: int = 1  # 学习阶段 (1: 选择题, 2: 自测, 3: 拼写)
    learned: bool = False  # 是否已完成学习 (通过 Stage 3 拼写)
    attempts: int = 0  # 尝试次数 (用于统计和调整难度)
    reviewed: bool = False  # 是否已在复习模式中复习过
    tested: bool = False  # 是否已在测试模式中测试过

    def to_dict(self):
        """将 WordItem 实例转换为字典，用于 JSON 序列化保存。"""
        return asdict(self)

    @staticmethod
    def from_dict(d):
        """
        从字典加载数据，创建 WordItem 实例。
        使用 .get() 方法确保即使字典缺少某些键，也能提供默认值，增强健壮性。
        """
        item = WordItem(
            word=d.get("word", ""),
            definition=d.get("definition", ""),
            pos=d.get("pos", ""),
            example=d.get("example", ""),
            # 确保 stage 和 attempts 是整数
            stage=int(d.get("stage", 1)),
            attempts=int(d.get("attempts", 0)),
            # 确保 learned, reviewed, tested 是布尔值
            learned=bool(d.get("learned", False)),
            reviewed=bool(d.get("reviewed", False)),
            tested=bool(d.get("tested", False))
        )
        return item


class VocabModel:
    """
    词汇数据模型：管理单词列表、文件路径、设置以及数据的加载和保存。
    """

    def __init__(self):
        self.words: List[WordItem] = []  # 存储 WordItem 对象的列表

        # 文件路径配置
        self.last_words_path = os.path.join("data", "last_words.csv")  # 最近一次导入的 CSV 文件的拷贝路径
        self.progress_path = os.path.join("data", "progress.json")  # 学习进度保存路径
        self.settings_path = os.path.join("data", "settings.json")  # 应用设置保存路径

        # 默认设置
        self.settings = {"learn_count": 10, "review_count": 15, "test_count": 20}

        self.load_settings()  # 应用启动时，自动加载用户上次保存的设置

    # =============== 设置相关 ===============
    def save_settings(self):
        """将当前设置保存到 settings.json 文件。"""
        os.makedirs("data", exist_ok=True)  # 确保 data 目录存在
        with open(self.settings_path, "w", encoding="utf-8") as f:
            # 使用 indent=2 格式化 JSON，使其可读
            json.dump(self.settings, f, ensure_ascii=False, indent=2)

    def load_settings(self):
        """从 settings.json 文件加载设置，并更新默认设置。"""
        if os.path.exists(self.settings_path):
            with open(self.settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 使用 update() 方法，加载文件中的设置，同时保留默认设置中未在文件中出现的项
            self.settings.update(data)

    # =============== 单词库相关 ===============
    def load_words_from_csv(self, path):
        """
        从指定的 CSV 文件加载单词。
        CSV 文件格式期望至少包含：单词, 词性, 释义, 例句。
        """
        if not os.path.exists(path):
            return []

        try:
            os.makedirs("data", exist_ok=True)
            # 复制导入的文件到 data 目录，作为下次启动的默认词库
            shutil.copy(path, self.last_words_path)
        except Exception:
            # 如果复制失败 (如权限问题)，忽略
            pass

        self.words = []
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            start = 0
            # 尝试识别是否有表头，如果有 '单词' 或 'word' 字段，则跳过第一行
            if rows and any('单词' in c or 'word' in c.lower() for c in rows[0]):
                start = 1

            for row in rows[start:]:
                if not row: continue
                # 假设单词在第 0 列
                w = row[0].strip()
                # 假设词性在第 1 列，释义在第 2 列，例句在第 3 列
                pos = row[1].strip() if len(row) > 1 else ""
                d = row[2].strip() if len(row) > 2 else ""
                ex = row[3].strip() if len(row) > 3 else ""

                if w:
                    # 创建新的 WordItem 实例 (所有状态都将是默认值)
                    self.words.append(WordItem(word=w, definition=d, pos=pos, example=ex))
        return self.words

    def load_last_words(self):
        """加载最近一次成功导入的 CSV 单词库 (last_words.csv)。"""
        if os.path.exists(self.last_words_path):
            return self.load_words_from_csv(self.last_words_path)
        return []

    # =============== 学习进度相关 ===============
    def save_progress(self, path=None):
        """将当前单词列表的所有状态 (stage, learned, attempts 等) 保存到 JSON 文件。"""
        os.makedirs("data", exist_ok=True)
        path = path or self.progress_path

        data = {
            "words": [w.to_dict() for w in self.words],  # 序列化单词列表
            "settings": self.settings  # 附带保存当前设置，便于兼容和恢复
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_progress(self, path=None):
        """从 progress.json 文件加载单词状态和进度。"""
        path = path or self.progress_path
        if not os.path.exists(path):
            return []

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            # 兼容旧版本只保存 list 的情况
            self.words = [WordItem.from_dict(d) for d in data]
        else:
            # 加载新版本保存的格式 (包含 words 列表和 settings)
            self.words = [WordItem.from_dict(d) for d in data.get("words", [])]
            # 尝试更新设置
            self.settings.update(data.get("settings", {}))

        return self.words

    def get_stats(self):
        """获取学习统计数据。"""
        total = len(self.words)
        # 计算已学习 (learned=True) 的单词数量
        learned = sum(1 for w in self.words if w.learned)
        return learned, total

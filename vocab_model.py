import csv, json, os, shutil
from dataclasses import dataclass, asdict
from typing import List
import requests
import random  # 导入 random 用于后面构建选项
from io import StringIO  # 新增：用于处理内存中的 CSV 字符串


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
            # ** 确保从进度文件加载时能正确处理缺失的字段 **
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
        self.current_wordlist_name = "未加载"  # 新增：用于跟踪当前加载的词库文件名

        # 文件路径配置
        self.last_words_path = os.path.join("data", "last_words.csv")  # 最近一次导入的 CSV 文件的拷贝路径
        # 新增一个路径来保存上次导入的 JSON 文件名，以便下次启动时尝试加载
        self.last_json_path = os.path.join("data", "last_words.json")
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

    # =============== 单词库相关 - 基于文件路径 ===============

    # **新增辅助函数：从 JSON 字符串内容解析并加载单词**
    def _parse_json_content(self, content: str) -> List[WordItem]:
        """
        从 JSON 字符串内容解析单词列表。
        返回解析出的 WordItem 列表。
        """
        words_list = []
        try:
            data = json.loads(content)

            if not isinstance(data, list):
                print("JSON 内容格式错误: 根元素不是列表。")
                return []

            for item in data:
                word = item.get('word', '').strip()
                translations = item.get('translations', [])

                if not word or not translations:
                    continue

                definition_parts = []
                pos_parts = []
                for t in translations:
                    part_of_speech = t.get('type', 'n/a')
                    translation = t.get('translation', '')

                    if translation:
                        definition_parts.append(translation)
                        if part_of_speech != 'n/a':
                            pos_parts.append(part_of_speech)

                pos = ", ".join(sorted(list(set(pos_parts))))
                definition = "; ".join(definition_parts)

                words_list.append(WordItem(
                    word=word,
                    definition=definition,
                    pos=pos,
                    example=""
                ))
            return words_list

        except json.JSONDecodeError as e:
            print(f"解析 JSON 内容时发生错误: {e}")
            return []
        except Exception as e:
            print(f"处理 JSON 单词数据时发生未知错误: {e}")
            return []

    # **新增辅助函数：从 CSV 字符串内容解析并加载单词**
    def _parse_csv_content(self, content: str) -> List[WordItem]:
        """
        从 CSV 字符串内容解析单词列表。
        返回解析出的 WordItem 列表。
        """
        words_list = []
        try:
            # 使用 StringIO 将字符串内容模拟成文件
            f = StringIO(content)
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
                    words_list.append(WordItem(word=w, definition=d, pos=pos, example=ex))
            return words_list

        except Exception as e:
            print(f"解析 CSV 内容时发生错误: {e}")
            return []

    # **新增方法：基于内存中的 JSON 字符串内容导入单词**
    def load_words_from_json_content(self, content: str) -> List[WordItem]:
        """
        从 JSON 字符串内容加载单词，替换现有数据。用于网络下载导入。
        """
        self.words = self._parse_json_content(content)

        # 成功加载后，将内容保存到 last_json_path 作为持久化备份
        if self.words:
            os.makedirs("data", exist_ok=True)
            with open(self.last_json_path, "w", encoding="utf-8") as f:
                f.write(content)
            # 清理 CSV 备份
            if os.path.exists(self.last_words_path):
                os.remove(self.last_words_path)
            print(f"成功从 JSON 内容加载 {len(self.words)} 个单词。")
            return self.words
        return []

    # **新增方法：基于内存中的 CSV 字符串内容导入单词**
    def load_words_from_csv_content(self, content: str) -> List[WordItem]:
        """
        从 CSV 字符串内容加载单词，替换现有数据。用于网络下载导入。
        """
        self.words = self._parse_csv_content(content)

        # 成功加载后，将内容保存到 last_words_path 作为持久化备份
        if self.words:
            os.makedirs("data", exist_ok=True)
            with open(self.last_words_path, "w", encoding="utf-8") as f:
                f.write(content)
            # 清理 JSON 备份
            if os.path.exists(self.last_json_path):
                os.remove(self.last_json_path)
            print(f"成功从 CSV 内容加载 {len(self.words)} 个单词。")
            return self.words
        return []

    # **修改 load_words_from_json 方法，使其调用 _parse_json_content**
    def load_words_from_json(self, path: str) -> List[WordItem]:
        """
        从指定的 JSON 文件加载单词。
        JSON 文件格式期望包含：[{"word": "...", "translations": [...]}, ...]
        """
        if not os.path.exists(path):
            return []

        print(f"尝试从 JSON 文件加载: {path}")

        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()

            self.words = self._parse_json_content(content)

            # 成功加载后，执行文件复制和名称更新
            if self.words:
                os.makedirs("data", exist_ok=True)
                # 复制导入的文件到 data 目录，作为下次启动的默认词库
                if os.path.abspath(path) != os.path.abspath(self.last_json_path):
                    shutil.copy(path, self.last_json_path)
                # 移除上次导入的 CSV 文件的记录，以 JSON 为准
                if os.path.exists(self.last_words_path):
                    os.remove(self.last_words_path)

                # 关键修改：成功加载后，更新词库名称
                self.current_wordlist_name = os.path.basename(path)
                print(f"成功从 JSON 文件加载 {len(self.words)} 个单词。")
                return self.words

            return []

        except Exception as e:
            print(f"加载 JSON 文件时发生错误: {e}")
            return []

    # **修改 load_words_from_csv 方法，使其调用 _parse_csv_content**
    def load_words_from_csv(self, path):
        """
        从指定的 CSV 文件加载单词。
        CSV 文件格式期望至少包含：单词, 词性, 释义, 例句。
        """
        if not os.path.exists(path):
            return []

        print(f"尝试从 CSV 文件加载: {path}")

        try:
            with open(path, newline='', encoding='utf-8') as f:
                content = f.read()

            self.words = self._parse_csv_content(content)

            # 成功加载后，执行文件复制和名称更新
            if self.words:
                os.makedirs("data", exist_ok=True)
                # 复制导入的文件到 data 目录，作为下次启动的默认词库
                if os.path.abspath(path) != os.path.abspath(self.last_words_path):
                    # 移除上次导入的 JSON 文件的记录，以 CSV 为准
                    if os.path.exists(self.last_json_path):
                        os.remove(self.last_json_path)
                    shutil.copy(path, self.last_words_path)

                # 关键修改：成功加载后，更新词库名称
                self.current_wordlist_name = os.path.basename(path)
                print(f"成功从 CSV 文件加载 {len(self.words)} 个单词。")
                return self.words

            return []

        except Exception as e:
            print(f"加载 CSV 文件时发生错误: {e}")
            return []

    def load_last_words(self):
        """加载最近一次成功导入的 CSV 或 JSON 单词库。"""
        # 优先加载上次导入的 JSON 文件
        if os.path.exists(self.last_json_path):
            return self.load_words_from_json(self.last_json_path)
        # 其次加载上次导入的 CSV 文件
        elif os.path.exists(self.last_words_path):
            return self.load_words_from_csv(self.last_words_path)
        return []

    # =============== 学习进度相关 ===============
    def save_progress(self, path=None):
        """
        将当前单词列表的所有状态 (stage, learned, attempts 等) 保存到 JSON 文件。
        如果 path 为 None，则保存到默认路径。
        """
        # 确保保存路径有效，如果传入 None 则使用默认路径
        path = path or self.progress_path

        # 如果是默认路径，确保 data 目录存在
        if path == self.progress_path:
            os.makedirs("data", exist_ok=True)

        data = {
            "words": [w.to_dict() for w in self.words],  # 序列化单词列表
            "settings": self.settings,  # 附带保存当前设置，便于兼容和恢复
            "current_wordlist_name": self.current_wordlist_name  # 保存当前词库名称
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_progress(self, path=None):
        """
        从 progress.json 文件加载单词状态和进度。
        如果 path 为 None，则从默认路径加载。
        """
        path = path or self.progress_path
        if not os.path.exists(path):
            return []

        # 检查文件是否存在，如果不存在则引发异常，由调用方处理
        if not os.path.exists(path):
            raise FileNotFoundError(f"进度文件未找到: {path}")

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
            # 新增：加载词库名称
            self.current_wordlist_name = data.get("current_wordlist_name", "来自进度文件")

        # 兼容旧版本进度文件，确保每个 WordItem 都有 reviewed 和 tested 属性
        for w in self.words:
            if not hasattr(w, "reviewed"):
                w.reviewed = False
            if not hasattr(w, "tested"):
                w.tested = False

        # 保持词库同步：将加载的进度文件中的单词库内容同步到 last_words.csv 或 last_words.json
        if self.words:
            os.makedirs("data", exist_ok=True)
            # 统一同步到 CSV 格式，方便下一次 load_all_data 的逻辑
            with open(self.last_words_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["单词", "词性", "释义", "例句"])
                for w in self.words:
                    writer.writerow(
                        [w.word, getattr(w, "pos", ""), getattr(w, "definition", ""), getattr(w, "example", "")])

            # 如果是成功加载了进度，就移除上次记录的 JSON 文件，避免冲突
            if os.path.exists(self.last_json_path):
                os.remove(self.last_json_path)

        return self.words

    def get_stats(self):
        """获取学习统计数据。"""
        total = len(self.words)
        # 计算已学习 (learned=True) 的单词数量
        learned = sum(1 for w in self.words if w.learned)
        return learned, total

    def load_all_data(self):
        """
        统一加载所有数据：尝试加载进度 -> 尝试加载上次词库 (JSON/CSV) -> 强制加载默认文件 (JSON/CSV)
        此方法应在应用程序启动时调用。
        """
        self.load_settings()
        self.current_wordlist_name = "未加载"  # 重置名称

        # 1. 尝试加载进度文件 (包含词库和状态)
        if os.path.exists(self.progress_path):
            # load_progress 会更新 self.current_wordlist_name
            try:
                self.load_progress(self.progress_path)
                if self.words:
                    print("Data loaded from progress file.")
                    return True
            except Exception as e:
                print(f"Error loading default progress file: {e}. Attempting next method.")

        # 2. 尝试加载上次导入的词库文件 (JSON 或 CSV)
        if self.load_last_words():
            print("Data loaded from last used dictionary.")
            return True

        # 3. 如果前面都没加载成功, 尝试加载默认文件
        DEFAULT_JSON_PATH = "4-CET6-顺序.json"  # 您提供的 JSON 文件
        default_csv_path = "六级.csv"
        # 修正：使用 raw.githubusercontent.com 获取原始文件内容
        DEFAULT_CSV_URL = "https://raw.githubusercontent.com/Junpgle/LearnWord/master/%E8%AF%8D%E5%BA%93/%E5%85%AD%E7%BA%A7-%E4%B9%B1%E5%BA%8F.csv"

        # 3a. **新增：尝试加载默认 JSON 文件**
        if os.path.exists(DEFAULT_JSON_PATH):
            print(f"Loading default JSON dictionary locally: {DEFAULT_JSON_PATH}")
            # load_words_from_json 会更新 self.current_wordlist_name
            self.load_words_from_json(DEFAULT_JSON_PATH)
            if self.words:
                return True

        # 3b. 尝试加载默认 CSV 文件 (本地)
        if os.path.exists(default_csv_path):
            print(f"Loading default CSV dictionary locally: {default_csv_path}")
            # load_words_from_csv 会更新 self.current_wordlist_name
            self.load_words_from_csv(default_csv_path)
            if self.words:
                return True

        # 3c. 如果本地文件不存在或加载失败，尝试网络下载 CSV
        if not self.words:
            print(f"本地文件不存在,尝试从GitHub拉取默认词库")
            try:
                # 设置超时 10 秒
                response = requests.get(DEFAULT_CSV_URL, timeout=10)
                response.raise_for_status()  # 检查 HTTP 错误

                # 成功下载，直接使用内容加载
                content = response.text

                print(f"Download successful. Loading new dictionary from network content.")
                # 使用新的 content 方法加载，并设置临时名称
                self.load_words_from_csv_content(content)
                self.current_wordlist_name = f"[下载] 六级.csv"

            except requests.exceptions.RequestException as e:
                # 网络连接或 HTTP 错误
                print(f"Error downloading default dictionary: {e}")
            except Exception as e:
                # 其他文件操作错误
                print(f"Error processing downloaded file: {e}")

        if not self.words:
            print(f"Error: No words loaded. Could not load/download any default file.")
            self.current_wordlist_name = "加载失败"  # 最终失败状态
            return False

        return True
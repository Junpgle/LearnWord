import csv, json, os, shutil, sys
from dataclasses import dataclass, asdict
from typing import List
import requests
import random
from io import StringIO


# ==========================================
# ★★★ 核心路径处理函数 ★★★
# ==========================================

def get_user_data_dir():
    """获取 Windows 用户 AppData 目录，避免权限问题"""
    # 获取 C:\Users\用户名\AppData\Roaming
    appdata = os.getenv('APPDATA')
    # 定义本程序的专属文件夹
    data_dir = os.path.join(appdata, 'LearnWord', 'data')

    # 如果目录不存在（第一次运行），则创建它
    if not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir, exist_ok=True)
        except OSError:
            pass
    return data_dir


def get_resource_path(relative_path):
    """
    获取内置资源路径 (只读)。
    - 打包后: 从 PyInstaller 的临时目录 (_MEIPASS) 读取。
    - 开发时: 从当前目录读取。
    """
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.getcwd()
    return os.path.join(base_path, relative_path)


# ==========================================

@dataclass
class WordItem:
    """单词数据结构"""
    word: str
    definition: str = ""
    pos: str = ""
    example: str = ""
    stage: int = 1
    learned: bool = False
    attempts: int = 0
    reviewed: bool = False
    tested: bool = False

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return WordItem(
            word=d.get("word", ""),
            definition=d.get("definition", ""),
            pos=d.get("pos", ""),
            example=d.get("example", ""),
            stage=int(d.get("stage", 1)),
            attempts=int(d.get("attempts", 0)),
            learned=bool(d.get("learned", False)),
            reviewed=bool(d.get("reviewed", False)),
            tested=bool(d.get("tested", False))
        )


class VocabModel:
    """词汇数据模型"""

    def __init__(self):
        self.words: List[WordItem] = []
        self.current_wordlist_name = "未加载"

        # ★★★ 使用 get_user_data_dir() 确定数据保存位置 ★★★
        self.data_dir = get_user_data_dir()

        self.last_words_path = os.path.join(self.data_dir, "last_words.csv")
        self.last_json_path = os.path.join(self.data_dir, "last_words.json")
        self.progress_path = os.path.join(self.data_dir, "progress.json")
        self.settings_path = os.path.join(self.data_dir, "settings.json")

        # 默认设置
        self.settings = {"learn_count": 10, "review_count": 15, "test_count": 20}

        self.load_settings()

    # =============== 设置相关 ===============
    def save_settings(self):
        """保存设置到用户数据目录"""
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存设置失败: {e}")

    def load_settings(self):
        """加载设置"""
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.settings.update(data)
            except Exception:
                pass

    # =============== 单词库相关 ===============

    def _parse_json_content(self, content: str) -> List[WordItem]:
        words_list = []
        try:
            data = json.loads(content)
            # 兼容两种 JSON 格式: 列表 或 {"words": [...]}
            items = data if isinstance(data, list) else data.get("words", [])

            for item in items:
                # 兼容 WordItem 字典格式 或 原始 JSON 格式
                if "translations" in item:
                    # 原始格式
                    word = item.get('word', '').strip()
                    translations = item.get('translations', [])
                    if not word: continue

                    definition_parts = []
                    pos_parts = []
                    for t in translations:
                        translation = t.get('translation', '')
                        if translation:
                            definition_parts.append(translation)
                            pos_parts.append(t.get('type', 'n/a'))

                    words_list.append(WordItem(
                        word=word,
                        definition="; ".join(definition_parts),
                        pos=", ".join(sorted(list(set(pos_parts)))),
                    ))
                else:
                    # WordItem 格式
                    words_list.append(WordItem.from_dict(item))
            return words_list
        except Exception as e:
            print(f"解析 JSON 出错: {e}")
            return []

    def _parse_csv_content(self, content: str) -> List[WordItem]:
        words_list = []
        try:
            f = StringIO(content)
            reader = csv.reader(f)
            rows = list(reader)
            start = 0
            if rows and any('单词' in c or 'word' in c.lower() for c in rows[0]):
                start = 1

            for row in rows[start:]:
                if not row: continue
                w = row[0].strip()
                pos = row[1].strip() if len(row) > 1 else ""
                d = row[2].strip() if len(row) > 2 else ""
                ex = row[3].strip() if len(row) > 3 else ""
                if w:
                    words_list.append(WordItem(word=w, definition=d, pos=pos, example=ex))
            return words_list
        except Exception:
            return []

    def load_words_from_json_content(self, content: str) -> List[WordItem]:
        self.words = self._parse_json_content(content)
        if self.words:
            self._backup_file(self.last_json_path, content)
            # 移除冲突的备份
            if os.path.exists(self.last_words_path): os.remove(self.last_words_path)
        return self.words

    def load_words_from_csv_content(self, content: str) -> List[WordItem]:
        self.words = self._parse_csv_content(content)
        if self.words:
            self._backup_file(self.last_words_path, content)
            if os.path.exists(self.last_json_path): os.remove(self.last_json_path)
        return self.words

    def _backup_file(self, path, content):
        """辅助函数：备份文件内容到数据目录"""
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            print(f"备份文件失败: {e}")

    def load_words_from_json(self, path: str) -> List[WordItem]:
        if not os.path.exists(path): return []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return self.load_words_from_json_content(f.read())
        except Exception:
            return []

    def load_words_from_csv(self, path: str) -> List[WordItem]:
        if not os.path.exists(path): return []
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                return self.load_words_from_csv_content(f.read())
        except Exception:
            return []

    # =============== 学习进度相关 ===============

    def save_progress(self, path=None):
        """保存进度到文件"""
        # 如果未指定路径，使用默认的用户数据目录下的 progress.json
        target_path = path if path else self.progress_path

        # 确保目录存在
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        data = {
            "words": [w.to_dict() for w in self.words],
            "settings": self.settings,
            "current_wordlist_name": self.current_wordlist_name
        }
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"进度已保存: {target_path}")
        except Exception as e:
            print(f"保存进度失败: {e}")

    def load_progress(self, path=None):
        """加载进度"""
        target_path = path if path else self.progress_path

        if not os.path.exists(target_path):
            return False

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 恢复设置
            self.settings.update(data.get("settings", {}))
            self.current_wordlist_name = data.get("current_wordlist_name", "未知词库")

            # 恢复单词列表
            words_data = data.get("words", [])
            # 兼容旧版本可能直接是 list 的情况
            if isinstance(data, list): words_data = data

            self.words = [WordItem.from_dict(w) for w in words_data]
            return True
        except Exception as e:
            print(f"加载进度出错: {e}")
            return False

    def load_all_data(self):
        """
        程序启动时的统一加载逻辑：
        1. 尝试加载用户进度 (progress.json)
        2. 尝试加载上次导入的词库 (last_words)
        3. 尝试加载内置默认词库 (资源文件)
        """
        self.load_settings()
        self.current_wordlist_name = "未加载"

        # 1. 尝试加载进度 (位于用户数据目录)
        if self.load_progress():
            print("已加载用户进度")
            return True

        # 2. 尝试加载上次导入的文件 (位于用户数据目录)
        if os.path.exists(self.last_json_path):
            self.load_words_from_json(self.last_json_path)
            self.current_wordlist_name = "上次导入 (JSON)"
            return True
        elif os.path.exists(self.last_words_path):
            self.load_words_from_csv(self.last_words_path)
            self.current_wordlist_name = "上次导入 (CSV)"
            return True

        # 3. 尝试加载内置默认词库 (位于资源目录 _MEIPASS)
        # 注意：这里使用 get_resource_path 来获取打包进去的文件
        # 文件名必须与 PyInstaller 命令中的源文件名一致
        default_csv = get_resource_path("六级-乱序.csv")

        if os.path.exists(default_csv):
            print(f"加载内置默认词库: {default_csv}")
            self.load_words_from_csv(default_csv)
            self.current_wordlist_name = "默认词库 (六级)"
            self.save_progress()  # 初始化后立即保存一份到用户目录
            return True

        print("未找到任何数据，请手动导入。")
        return False

    def get_stats(self):
        learned = sum(1 for w in self.words if w.learned)
        return learned, len(self.words)
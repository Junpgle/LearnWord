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

        self.data_dir = get_user_data_dir()

        self.last_words_path = os.path.join(self.data_dir, "last_words.csv")
        self.last_json_path = os.path.join(self.data_dir, "last_words.json")
        self.progress_path = os.path.join(self.data_dir, "progress.json")
        self.settings_path = os.path.join(self.data_dir, "settings.json")

        # --- 修改处：增加 daily_date 和 daily_batch 的默认值 ---
        self.settings = {
            "learn_count": 10,
            "review_count": 15,
            "test_count": 20,
            "daily_date": "",  # 记录日期
            "daily_batch": []  # 记录今日单词ID列表
        }

        # 注意：这里不要直接调用 load_settings，统一放在 load_all_data 中处理
        # self.load_settings() <--- 建议删掉这行，由 load_all_data 统一管理

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
        4. 最后加载独立设置 (settings.json)，确保每日计划是最新的
        """
        # self.load_settings()  <--- 删除这行 (原来在这里)
        self.current_wordlist_name = "未加载"

        data_loaded = False

        # 1. 尝试加载进度 (位于用户数据目录)
        if self.load_progress():
            print("已加载用户进度")
            data_loaded = True

        # 2. 如果没进度，尝试加载上次导入的文件
        if not data_loaded:
            if os.path.exists(self.last_json_path):
                self.load_words_from_json(self.last_json_path)
                self.current_wordlist_name = "上次导入 (JSON)"
                data_loaded = True
            elif os.path.exists(self.last_words_path):
                self.load_words_from_csv(self.last_words_path)
                self.current_wordlist_name = "上次导入 (CSV)"
                data_loaded = True

        # 3. 还没数据，尝试加载内置默认词库
        if not data_loaded:
            default_csv = get_resource_path("六级-乱序.csv")
            if os.path.exists(default_csv):
                print(f"加载内置默认词库: {default_csv}")
                self.load_words_from_csv(default_csv)
                self.current_wordlist_name = "默认词库 (六级)"
                self.save_progress()
                data_loaded = True

        # --- 修改处：最后加载 settings.json ---
        # 无论前面加载了什么数据，settings.json 里保存的 "daily_batch" 应该是最新的
        # 这样可以防止 load_progress 中的旧 settings 覆盖掉今天的计划
        self.load_settings()

        if not data_loaded:
            print("未找到任何数据，请手动导入。")
            return False

        return True

    def get_stats(self):
        learned = sum(1 for w in self.words if w.learned)
        return learned, len(self.words)

    def get_backup_list(self) -> list:
        backup_dir = os.path.join(self.data_dir, "backup")
        if not os.path.exists(backup_dir):
            return []

        backups = []
        for filename in os.listdir(backup_dir):
            if filename.endswith(".json"):
                path = os.path.join(backup_dir, filename)
                try:
                    # 获取文件创建时间 [cite: 204]
                    ctime = os.path.getctime(path)
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        words = data.get("words", [])
                        learned = sum(1 for w in words if w.get("learned", False))
                        backups.append({
                            "filename": filename,
                            "path": path,
                            "time": ctime,
                            "wordlist": data.get("current_wordlist_name", "未知"),
                            "progress": f"{learned}/{len(words)}"
                        })
                except Exception:
                    continue
        # 按时间降序排列 [cite: 33]
        return sorted(backups, key=lambda x: x['time'], reverse=True)
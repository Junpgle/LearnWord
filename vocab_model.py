import csv, json, os, shutil, sys
import re
from dataclasses import dataclass, asdict
from typing import List
import requests
import random
from io import StringIO

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
    # --- 新增字段 ---
    etymology: str = ""  # 词根词源 (存储为多行字符串)
    phrases: str = ""  # 短语搭配 (存储为多行字符串)
    # ----------------
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
            # --- 读取新增字段，提供默认空值以兼容旧存档 ---
            etymology=d.get("etymology", ""),
            phrases=d.get("phrases", ""),
            # ----------------------------------------
            stage=int(d.get("stage", 1)),
            attempts=int(d.get("attempts", 0)),
            learned=bool(d.get("learned", False)),
            reviewed=bool(d.get("reviewed", False)),
            tested=bool(d.get("tested", False))
        )


import re


def get_word_rich_text(item: WordItem, mode="simple") -> str:
    """
    构造单词显示的富文本 (HTML)，采用左右分栏布局。
    mode: "simple" | "full" | "hint" | "spelling"
    ✅ 已优化：无滚动条 | 无多余空行 | 行距精准控制
    """
    definition = item.definition or "[无释义]"
    etymology = getattr(item, 'etymology', '')
    phrases = getattr(item, 'phrases', '')

    # =============== 核心修复：最外层容器禁用滚动条 ===============
    # 所有内容包裹在此div中，彻底消除滚动条
    def wrap_content(html: str) -> str:
        return f"""
        <div style='overflow: hidden; padding: 0; margin: 0; width: 100%;'>
            {html}
        </div>
        """

    # 2. Simple 模式
    if mode == "simple":
        content = f"""
        <div style='text-align: center; margin-top: 30px; padding: 0;'>
            <div style='font-size: 40pt; font-weight: bold; color: #2c3e50; line-height: 1.0; padding: 0; margin: 0;'>{item.word}</div>
        </div>
        """
        return wrap_content(content)

    # 3. 左侧核心词义（精准行距：8px → 6px）
    if mode in ("hint", "spelling"):
        left_top_html = f"""
        <div style='font-size: 16pt; color: #e67e22; font-weight: bold; margin-bottom: 8px; padding: 0;'>请拼写单词：</div>
        <div style='font-size: 14pt; color: #7f8c8d; font-style: italic; margin-top: 8px; padding: 0;'>{item.pos}</div>
        <div style='font-size: 16pt; color: #2980b9; font-weight: bold; line-height: 1.2; margin-top: 6px; padding: 0;'>{definition}</div>
        """
    else:
        left_top_html = f"""
        <div style='font-size: 32pt; font-weight: bold; color: #2c3e50; line-height: 1.0; padding: 0; margin: 0;'>{item.word}</div>
        <div style='font-size: 14pt; color: #7f8c8d; font-style: italic; margin-top: 8px; padding: 0;'>{item.pos}</div>
        <div style='font-size: 16pt; color: #2980b9; font-weight: bold; line-height: 1.2; margin-top: 6px; padding: 0;'>{definition}</div>
        """

    # 4. Spelling 模式：仅返回核心词义
    if mode == "spelling":
        content = f"<div style='padding: 10px 0; margin: 0;'>{left_top_html}</div>"
        return wrap_content(content)

    # 5. 左侧短语（语义化列表 + 紧凑间距）
    left_bottom_html = ""
    if phrases:
        phrases_text = phrases.strip()
        if mode == "hint":
            try:
                pattern = re.compile(re.escape(item.word), re.IGNORECASE)
                phrases_text = pattern.sub("<b>_____</b>", phrases_text)
            except Exception:
                pass

        p_lines = [line.strip() for line in phrases_text.splitlines() if line.strip()]
        if p_lines:
            ul_items = "".join(f"<li style='margin: 2px 0; padding: 0;'>{p}</li>" for p in p_lines)
            left_bottom_html = f"""
            <div style='margin-top: 20px; padding: 0;'>
                <div style='font-size: 12pt; color: #e67e22; font-weight: bold; margin-bottom: 8px; border-bottom: 1px solid #eee; padding-bottom: 3px; padding-top: 0;'>🔗 短语搭配</div>
                <ul style='list-style-type: disc; margin: 0; padding-left: 18px; line-height: 1.4; color: #34495e; font-size: 11pt;'>
                    {ul_items}
                </ul>
            </div>
            """
        else:
            left_bottom_html = "<div style='margin-top: 20px; color: #ccc; font-size: 10pt;'>(暂无短语)</div>"
    else:
        left_bottom_html = "<div style='margin-top: 20px; color: #ccc; font-size: 10pt;'>(暂无短语)</div>"

    # 6. 右侧词源（✅ 修复来源 / 释义之间的视觉空行）
    right_html = ""
    if etymology:
        limit = 1200
        display_ety = etymology.strip()
        is_truncated = len(display_ety) > limit
        if is_truncated:
            display_ety = display_ety[:limit]

        e_lines = [line.strip() for line in display_ety.splitlines() if line.strip()]
        ety_divs = []
        header_keys = ["词根：", "词根:", "前缀：", "前缀:", "后缀：", "后缀:", "词根词缀：", "词根词缀:"]

        for line in e_lines:
            # --- 词根 / 前缀 / 后缀标题 ---
            if any(line.startswith(key) for key in header_keys):
                mt = "0px" if not ety_divs else "16px"
                ety_divs.append(
                    f"""
                    <div style='margin-top: {mt};
                                font-weight: bold;
                                color: #d35400;
                                font-size: 11pt;
                                border-left: 3px solid #d35400;
                                padding-left: 7px;
                                padding-top: 1px;
                                padding-bottom: 1px;'>
                        {line}
                    </div>
                    """
                )

            # --- 【来源及含义】块（✅ 关键修复点） ---
            elif "【来源及含义】" in line:
                content = line.replace("【来源及含义】", "").strip()
                if ":" in content:
                    src, mean = content.split(":", 1)
                    ety_divs.append(
                        f"""
                        <div style='margin-top: 3px; color: #555;'>
                            <div style='margin: 0;'>
                                <span style='color: #7f8c8d; font-weight: bold;'>• 来源：</span>
                                {src.strip()}
                            </div>
                            <div style='margin-top: 2px;'>
                                <span style='color: #7f8c8d; font-weight: bold;'>• 释义：</span>
                                {mean.strip()}
                            </div>
                        </div>
                        """
                    )
                else:
                    ety_divs.append(
                        f"""
                        <div style='margin-top: 3px; color: #555;'>
                            <span style='color: #7f8c8d; font-weight: bold;'>• 来源及含义：</span>
                            {content}
                        </div>
                        """
                    )

            # --- 普通说明行 ---
            else:
                mt = "3px" if ety_divs else "0px"
                ety_divs.append(
                    f"<div style='margin-top: {mt}; color: #666; font-size: 10pt;'>{line}</div>"
                )

        formatted_ety = "".join(ety_divs)

        if is_truncated:
            formatted_ety += (
                "<div style='margin-top: 3px; color: #95a5a6; font-style: italic; font-size: 9.5pt;'>"
                "... [内容过长已折叠]</div>"
            )

        right_html = f"""
        <div style='font-size: 12pt;
                    color: #e67e22;
                    font-weight: bold;
                    margin-bottom: 8px;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 3px;
                    padding-top: 0;'>
            🌱 来源及含义
        </div>
        <div style='font-size: 10pt;
                    color: #34495e;
                    line-height: 1.45;
                    margin: 0;
                    padding: 0;'>
            {formatted_ety}
        </div>
        """

    # 7. 最终组装（表格布局 + 紧凑内边距）
    if not right_html or not right_html.strip():
        content = f"""
        <div style='padding: 8px 0; margin: 0;'>
            {left_top_html}
            {left_bottom_html}
        </div>
        """
        return wrap_content(content)

    content = f"""
    <table width='100%' border='0' cellspacing='0' cellpadding='0' style='margin: 0; padding: 0; border-collapse: collapse;'>
        <tr>
            <td width='45%' valign='top' style='padding-right: 25px; padding-top: 0; padding-bottom: 0; margin: 0;'>
                {left_top_html}
                {left_bottom_html}
            </td>
            <td width='55%' valign='top' style='border-left: 1px solid #ecf0f1; padding-left: 25px; padding-top: 0; padding-bottom: 0; margin: 0;'>
                {right_html}
            </td>
        </tr>
    </table>
    """
    return wrap_content(content)

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

        self.settings = {
            "learn_count": 10,
            "review_count": 15,
            "test_count": 20,
            "daily_date": "",  # 记录日期
            "daily_batch": []  # 记录今日单词ID列表
        }

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
        """
        解析 JSON 内容，支持原有格式和带有词根/短语的新格式
        """
        words_list = []
        try:
            data = json.loads(content)
            # 兼容两种 JSON 格式: 列表 或 {"words": [...]}
            items = data if isinstance(data, list) else data.get("words", [])

            for item in items:
                # 检查是否为包含 translations 的详细格式 (新词库格式)
                if "translations" in item:
                    word = item.get('word', '').strip()
                    if not word: continue

                    # 1. 解析翻译和词性
                    translations = item.get('translations', [])
                    definition_parts = []
                    pos_parts = []
                    for t in translations:
                        translation = t.get('translation', '')
                        if translation:
                            definition_parts.append(translation)
                            pos_parts.append(t.get('type', 'n/a'))

                    definition_str = "; ".join(definition_parts)
                    pos_str = ", ".join(sorted(list(set(pos_parts))))

                    # 2. 解析词源 (Etymology) - 列表转字符串
                    etymology_data = item.get('etymology', [])
                    etymology_str = ""
                    if isinstance(etymology_data, list):
                        # 将列表中的每一项用换行符连接
                        etymology_str = "\n".join([str(e) for e in etymology_data if e])
                    elif isinstance(etymology_data, str):
                        etymology_str = etymology_data

                    # 3. 解析短语 (Phrases) - 列表对象转格式化字符串
                    phrases_data = item.get('phrases', [])
                    phrases_str = ""
                    if isinstance(phrases_data, list):
                        p_lines = []
                        for p in phrases_data:
                            # 格式示例: "make up (组成)"
                            p_content = p.get('phrase', '')
                            p_trans = p.get('translation', '')
                            if p_content:
                                if p_trans:
                                    p_lines.append(f"{p_content} ({p_trans})")
                                else:
                                    p_lines.append(p_content)
                        phrases_str = "\n".join(p_lines)
                    elif isinstance(phrases_data, str):
                        phrases_str = phrases_data

                    # 创建对象
                    words_list.append(WordItem(
                        word=word,
                        definition=definition_str,
                        pos=pos_str,
                        etymology=etymology_str,
                        phrases=phrases_str
                    ))
                else:
                    # 兼容旧的简单 WordItem 字典格式 (可能是直接从 progress.json 导入的)
                    words_list.append(WordItem.from_dict(item))
            return words_list
        except Exception as e:
            print(f"解析 JSON 出错: {e}")
            import traceback
            traceback.print_exc()
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

        # 最后加载 settings.json
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
                    # 获取文件创建时间
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
        return sorted(backups, key=lambda x: x['time'], reverse=True)
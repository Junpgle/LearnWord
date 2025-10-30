import csv, json, os, shutil
from dataclasses import dataclass, asdict
from typing import List

@dataclass
class WordItem:
    word: str
    definition: str = ""
    pos: str = ""
    example: str = ""
    stage: int = 1
    learned: bool = False
    attempts: int = 0
    def to_dict(self): return asdict(self)
    @staticmethod
    def from_dict(d):
        return WordItem(
            word=d.get("word",""),
            definition=d.get("definition",""),
            pos=d.get("pos",""),
            example=d.get("example",""),
            stage=int(d.get("stage",1)),
            learned=bool(d.get("learned",False)),
            attempts=int(d.get("attempts",0))
        )

class VocabModel:
    def __init__(self):
        self.words: List[WordItem] = []
        self.last_words_path = os.path.join("data","last_words.csv")
        self.progress_path = os.path.join("data","progress.json")
        self.settings = {"learn_count":10, "review_count":15, "test_count":20}

    def load_words_from_csv(self, path):
        if not os.path.exists(path):
            return []
        # copy to data/last_words.csv
        try:
            shutil.copy(path, self.last_words_path)
        except Exception:
            pass
        self.words = []
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            start = 0
            if rows and any('单词' in c or 'word' in c.lower() for c in rows[0]):
                start = 1
            for row in rows[start:]:
                if not row: continue
                w = row[0].strip()
                pos = row[1].strip() if len(row)>1 else ""
                d = row[2].strip() if len(row)>2 else ""
                ex = row[3].strip() if len(row)>3 else ""
                if w:
                    self.words.append(WordItem(word=w, definition=d, pos=pos, example=ex))
        return self.words

    def load_last_words(self):
        if os.path.exists(self.last_words_path):
            return self.load_words_from_csv(self.last_words_path)
        return []

    def save_progress(self, path=None):
        path = path or self.progress_path
        with open(path, "w", encoding="utf-8") as f:
            json.dump([w.to_dict() for w in self.words], f, ensure_ascii=False, indent=2)

    def load_progress(self, path=None):
        path = path or self.progress_path
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.words = [WordItem.from_dict(d) for d in data]
        return self.words

    def get_stats(self):
        total = len(self.words)
        learned = sum(1 for w in self.words if w.learned)
        return learned, total

"""
rotation/evolution/log_store.py — 进化日志存储 (JSONL)

每次模型变更一行，可追加，可直接 cat/grep/jq 分析
"""
import json, os
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_PATH = os.path.join(ROOT, "rotation", "evolution", "logs", "evolution_log.jsonl")


@dataclass
class EvolutionRecord:
    timestamp: str
    model_version: str
    change_type: str          # feature | weight | data | structure | initial
    change_summary: str
    ic: float
    precision_top10: float
    max_drawdown: float
    ic_delta: float = 0.0     # vs previous version
    precision_delta: float = 0.0
    ci_pass: bool = False
    drift_score: float = 0.0
    git_commit: str = ""
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = str(d["timestamp"])
        return d


def append_record(record: EvolutionRecord):
    """追加一条进化记录到 JSONL"""
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, 'a') as f:
        f.write(json.dumps(record.to_dict(), ensure_ascii=False) + '\n')


def read_all_records() -> List[dict]:
    """读取所有进化记录"""
    if not os.path.exists(LOG_PATH):
        return []
    records = []
    with open(LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except:
                    pass
    return records


def get_latest_record() -> Optional[dict]:
    """最新一条记录"""
    records = read_all_records()
    return records[-1] if records else None


def get_version_history() -> List[str]:
    """所有版本号列表"""
    return [r["model_version"] for r in read_all_records()]

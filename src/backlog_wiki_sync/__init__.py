"""Backlog Wiki Sync - Backlog Wikiとローカル環境を同期するツール"""

import json
from pathlib import Path
from typing import Any

__version__ = "1.1.0"

CONFIG_FILENAME = ".backlog-wiki-sync.json"


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """
    設定ファイルを読み込む

    Args:
        config_path: 設定ファイルのパス（省略時はカレントディレクトリの.backlog-wiki-sync.json）

    Returns:
        設定の辞書（ファイルがない場合は空の辞書）
    """
    if config_path is None:
        config_path = Path.cwd() / CONFIG_FILENAME

    if not config_path.exists():
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        print(f"Loaded config from: {config_path}")
        return config
    except Exception as e:
        print(f"Warning: Failed to load config file: {e}")
        return {}

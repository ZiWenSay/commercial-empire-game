import os
from typing import Any, Dict, Optional

import yaml


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    """Load YAML settings from disk. Defaults to app/config.yaml."""
    default_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    cfg_path = path or os.environ.get("EMPIRE_CONFIG", default_path)
    with open(cfg_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("settings", {})


SETTINGS = load_config()

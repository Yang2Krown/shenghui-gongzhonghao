"""
Multi-account manager for Xiaohongshu publishing.
Adapted from post-to-xhs skill with macOS support.
"""

import json
import os
import sys
import shutil
from typing import Optional

CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
ACCOUNTS_FILE = os.path.join(CONFIG_DIR, "accounts.json")

if sys.platform == "darwin":
    PROFILES_BASE = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Google", "Chrome", "XiaohongshuProfiles")
else:
    PROFILES_BASE = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Google", "Chrome", "XiaohongshuProfiles")

DEFAULT_PROFILE_NAME = "default"


def _ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def _load_accounts() -> dict:
    _ensure_config_dir()
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "default_account": DEFAULT_PROFILE_NAME,
        "accounts": {
            DEFAULT_PROFILE_NAME: {
                "alias": "默认账号",
                "profile_dir": os.path.join(PROFILES_BASE, DEFAULT_PROFILE_NAME),
                "created_at": None,
            }
        }
    }


def _save_accounts(data: dict):
    _ensure_config_dir()
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_profile_dir(account_name: Optional[str] = None) -> str:
    data = _load_accounts()
    if account_name is None:
        account_name = data.get("default_account", DEFAULT_PROFILE_NAME)
    if account_name not in data["accounts"]:
        account_name = DEFAULT_PROFILE_NAME
        if account_name not in data["accounts"]:
            data["accounts"][account_name] = {
                "alias": "默认账号",
                "profile_dir": os.path.join(PROFILES_BASE, account_name),
                "created_at": None,
            }
            _save_accounts(data)
    return data["accounts"][account_name]["profile_dir"]


def list_accounts() -> list:
    data = _load_accounts()
    default = data.get("default_account", DEFAULT_PROFILE_NAME)
    result = []
    for name, info in data["accounts"].items():
        result.append({
            "name": name,
            "alias": info.get("alias", ""),
            "profile_dir": info.get("profile_dir", ""),
            "is_default": name == default,
        })
    return result


def add_account(name: str, alias: Optional[str] = None) -> bool:
    data = _load_accounts()
    if name in data["accounts"]:
        return False
    from datetime import datetime
    profile_dir = os.path.join(PROFILES_BASE, name)
    os.makedirs(profile_dir, exist_ok=True)
    data["accounts"][name] = {
        "alias": alias or name,
        "profile_dir": profile_dir,
        "created_at": datetime.now().isoformat(),
    }
    _save_accounts(data)
    return True


def set_default_account(account_name: str) -> bool:
    data = _load_accounts()
    if account_name not in data["accounts"]:
        return False
    data["default_account"] = account_name
    _save_accounts(data)
    return True

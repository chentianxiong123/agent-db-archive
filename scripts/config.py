"""Configuration - edit paths for your environment"""
import os, json

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

DEFAULT_CONFIG = {
    "db_path": "%APPDATA%\\Trae CN\\ModularData\\ai-agent\\database.db",
    "key": "",
    "proc_name": "Trae CN",
    "dll_name": "ai_agent.dll",
    "output_dir": "",
}

def init_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"[+] Config created: {CONFIG_PATH}")
        print("    Edit paths if needed, then run again.")
    return CONFIG_PATH
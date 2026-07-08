"""One-shot: find key -> decrypt -> export chat JSONL"""
import os, json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.config import init_config
from scripts.one_shot import run_all

if __name__ == "__main__":
    run_all()
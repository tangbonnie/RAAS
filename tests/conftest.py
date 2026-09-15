"""Pytest 配置：把仓库根目录加入 sys.path，这样测试可以 import root_analysis."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

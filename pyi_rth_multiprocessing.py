"""
PyInstaller Runtime Hook — multiprocessing spawn 修复 & numba 加速。

--onedir 模式下文件直接装在 Program Files，无需 TEMP 解压，
本钩子只需做两件事：
  1. 禁用 numba JIT（skan 依赖 numba，首次 JIT 编译耗时较长）
  2. 修复 spawn 子进程的可执行文件路径
"""
import sys
import os
import multiprocessing
import multiprocessing.spawn

if getattr(sys, 'frozen', False):
    # 禁用 numba JIT：以纯 Python 模式运行 skan，避免首次启动卡顿
    os.environ.setdefault('NUMBA_DISABLE_JIT', '1')

    # 修复 spawn 子进程路径（ProcessPoolExecutor 并行处理所需）
    multiprocessing.set_executable(sys.executable)

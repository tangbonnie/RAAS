# -*- mode: python ; coding: utf-8 -*-


# A venv based on Conda does not expose its base DLL directory to PyInstaller.
import sys
from pathlib import Path
base_bin = Path(sys.base_prefix) / 'Library' / 'bin'
base_dlls = [(str(base_bin / name), '.') for name in
             ('ffi.dll', 'libmpdec-4.dll', 'sqlite3.dll') if (base_bin / name).is_file()]

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=base_dlls,
    datas=[('assets/xjn.png', 'assets'), ('assets/icon.ico', 'assets')],
    hiddenimports=['root_gui', 'preprocess', 'root_analysis', 'root_topology', 'root_crown', 'root_segmentation', 'calibration', 'app_version', 'release_check', 'skimage', 'skimage.io', 'skimage.filters', 'skimage.morphology', 'skimage.measure', 'skimage.graph', 'skimage.transform', 'skimage.color', 'skimage.util', 'skan', 'scipy.ndimage', 'scipy.stats', 'pandas', 'numpy', 'matplotlib', 'matplotlib.backends.backend_qt5agg', 'PyQt5', 'PyQt5.QtWidgets', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PIL', 'openpyxl', 'multiprocessing', 'multiprocessing.spawn', 'multiprocessing.forkserver', 'multiprocessing.reduction', 'multiprocessing.resource_tracker', 'concurrent.futures', 'concurrent.futures.process'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_rth_multiprocessing.py'],
    excludes=['license_manager', 'tkinter', 'tkinter.ttk', '_tkinter', 'IPython', 'jupyter', 'notebook', 'zmq', 'PyQt4', 'wx', 'gtk', 'gi'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RootArchitecture',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.ico'],
    version='assets/version_info.txt',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RootArchitecture',
)

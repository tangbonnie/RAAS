#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动器 / Launcher
-----------------
作为编译版（exe/app）的入口脚本。

执行顺序：
  1. 仅导入 PyQt5（极轻量，< 0.5 s）
  2. 立即显示启动画面（含机构 Logo、软件名称）
  3. 调用 `import root_gui`，触发所有重型库加载
     （numpy / scipy / skimage / matplotlib / pandas …）
     此时启动画面持续可见，用户不会误以为程序未响应
  4. 创建主窗口，关闭启动画面

直接开发调试时请运行 root_gui.py，无需通过本文件。
"""

import sys
import os

from app_version import APP_VERSION
from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtGui import QPixmap, QColor, QPainter, QPen, QFont, QFontDatabase
from PyQt5.QtCore import Qt


# ── 资源路径（兼容 PyInstaller）────────────────────────────────────────────
def _resource_path(name: str) -> str:
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


# ── 查找系统中可用的 CJK 字体 ─────────────────────────────────────────────
def _find_cjk_font() -> str:
    """返回系统中第一个可用的 CJK 字体名称；找不到则返回空串。"""
    candidates = [
        'Microsoft YaHei', '微软雅黑',
        'SimHei', '黑体',
        'PingFang SC', 'Heiti SC',
        'Noto Sans CJK SC', 'WenQuanYi Micro Hei',
        'Arial Unicode MS',
    ]
    db = QFontDatabase()
    available = set(db.families())
    for name in candidates:
        if name in available:
            return name
    return ''


def _make_splash_pixmap(cjk_font: str) -> QPixmap:
    """绘制启动画面位图，纯 PyQt5 绘图，无外部依赖。

    所有字体使用 setPixelSize() 而非点大小，确保在任意屏幕 DPI 缩放
    （100%/125%/150%/200%）下字体渲染高度不变，不会撑出矩形框被截断。
    底部区域（版本号 + 加载提示）从画布底部向上定位，不受顶部内容高度影响。
    """
    W, H = 560, 360
    BAR  = 7     # 顶/底绿色装饰条高度

    pm = QPixmap(W, H)
    pm.fill(QColor('#1a3a5c'))

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)

    # ── 顶部绿色装饰条 ────────────────────────────────────────────────
    p.fillRect(0, 0, W, BAR, QColor('#2e8b57'))

    # ── 机构 Logo（xjn.png）──────────────────────────────────────────
    logo_path = _resource_path('assets/xjn.png')
    logo_drawn = False
    if os.path.exists(logo_path):
        logo_pm = QPixmap(logo_path)
        if not logo_pm.isNull():
            logo_pm = logo_pm.scaledToHeight(44, Qt.SmoothTransformation)
            lx = (W - logo_pm.width()) // 2
            p.drawPixmap(lx, 14, logo_pm)
            logo_drawn = True

    # ── 主标题（像素字号，不受 DPI 影响）──────────────────────────────
    title_y = 72 if logo_drawn else 34
    p.setPen(QColor('#ffffff'))
    if cjk_font:
        f = QFont(cjk_font); f.setPixelSize(26); f.setBold(True)
        p.setFont(f)
        p.drawText(0, title_y, W, 36, Qt.AlignHCenter | Qt.AlignVCenter,
                   '根系构型参数量化分析系统')
    else:
        f = QFont('Arial'); f.setPixelSize(22); f.setBold(True)
        p.setFont(f)
        p.drawText(0, title_y,      W, 30, Qt.AlignHCenter | Qt.AlignVCenter,
                   'Root Architecture')
        p.drawText(0, title_y + 30, W, 28, Qt.AlignHCenter | Qt.AlignVCenter,
                   'Quantification System')

    # ── 英文副标题 ────────────────────────────────────────────────────
    sub_y = title_y + 48
    f = QFont('Arial'); f.setPixelSize(13)
    p.setFont(f); p.setPen(QColor('#90caf9'))
    p.drawText(0, sub_y, W, 26, Qt.AlignHCenter | Qt.AlignVCenter,
               'Root Architecture Quantification System')

    # ── 底部固定区域（从画布底部向上定位，与顶部内容无关）────────────
    # 加载提示：紧贴底部装饰条上方
    load_y = H - BAR - 36
    f = QFont(cjk_font if cjk_font else 'Arial'); f.setPixelSize(14)
    p.setFont(f); p.setPen(QColor('#c0d8ee'))
    loading_text = '正在加载，请稍候…' if cjk_font else 'Loading, please wait…'
    p.drawText(0, load_y, W, 32, Qt.AlignHCenter | Qt.AlignVCenter, loading_text)

    # 版本号：加载提示上方
    ver_y = load_y - 32
    f2 = QFont('Arial'); f2.setPixelSize(12)
    p.setFont(f2); p.setPen(QColor('#7fb3d3'))
    p.drawText(0, ver_y, W, 28, Qt.AlignHCenter | Qt.AlignVCenter,
               f'v{APP_VERSION}    |    2026')

    # 分隔线：版本号上方
    sep_y = ver_y - 10
    p.setPen(QPen(QColor('#2e5a8a'), 1))
    p.drawLine(40, sep_y, W - 40, sep_y)

    # ── 底部绿色装饰条 ────────────────────────────────────────────────
    p.fillRect(0, H - BAR, W, BAR, QColor('#2e8b57'))

    p.end()
    return pm


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # ── 1. 查找 CJK 字体（在 QApplication 创建后才能查询字体数据库）
    cjk = _find_cjk_font()

    # Show the application directly; this distribution has no activation gate.
    splash = QSplashScreen(_make_splash_pixmap(cjk), Qt.WindowStaysOnTopHint)
    splash.show()
    splash.showMessage('正在加载模块，首次启动需 1–3 分钟，请耐心等待…',
                       Qt.AlignBottom | Qt.AlignHCenter, QColor('#c0d8ee'))
    app.processEvents()          # 强制渲染，确保 splash 立刻出现

    # ── 5. 加载主模块（此时重型库才开始 import） ────────────────────
    #   numpy / scipy / skimage / matplotlib / pandas 等全部在此触发
    from root_gui import MainWindow, LIGHT_QSS  # noqa: E402

    # ── 6. 应用字体和样式 ────────────────────────────────────────────
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)
    app.setStyleSheet(LIGHT_QSS)

    # ── 6b. 设置应用图标（任务栏、标题栏、Alt+Tab 均从此读取）───────
    from PyQt5.QtGui import QIcon as _QIcon
    _ico = _resource_path('assets/icon.ico')
    if os.path.exists(_ico):
        app.setWindowIcon(_QIcon(_ico))

    # ── 7. 创建主窗口，关闭启动画面 ─────────────────────────────────
    window = MainWindow()
    window.show()
    splash.finish(window)

    # Exercise the normal startup path without user interaction during builds.
    if len(sys.argv) == 3 and sys.argv[1] == '--smoke-test':
        import json
        from pathlib import Path
        from PyQt5.QtCore import QTimer
        def finish_smoke_test():
            target = Path(sys.argv[2])
            target.mkdir(parents=True, exist_ok=True)
            app.processEvents()
            (target / 'startup.json').write_text(json.dumps({
                'version': APP_VERSION,
                'frozen': bool(getattr(sys, 'frozen', False)),
                'main_window_created': window.isVisible(),
                'activation_required': False,
                'root_model_default': window.an_root_model.currentData(),
            }, indent=2), encoding='utf-8')
            window.grab().save(str(target / 'main-window.png'))
            app.quit()
        QTimer.singleShot(500, finish_smoke_test)
    sys.exit(app.exec_())


if __name__ == '__main__':
    # 必须在任何 multiprocessing 使用前调用（ProcessPoolExecutor 并行处理所需）
    import multiprocessing
    multiprocessing.freeze_support()
    if len(sys.argv) == 3 and sys.argv[1] in ('--self-test', '--smoke-test'):
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from release_check import run
        try:
            sys.exit(run(sys.argv[2]))
        except Exception:
            import traceback
            from pathlib import Path
            target = Path(sys.argv[2])
            target.mkdir(parents=True,exist_ok=True)
            (target/'self-test-error.txt').write_text(traceback.format_exc(),encoding='utf-8')
            sys.exit(1)
    main()

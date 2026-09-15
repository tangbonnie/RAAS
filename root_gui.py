#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根系构型参数量化分析系统 (GUI)
Maize Root Architecture Quantification System

作者：唐清芸（石河子大学农学院、新疆农垦科学院）
软件版权人：王国栋（新疆农垦科学院）
    新疆农垦科学院 (Xinjiang Academy of Agricultural Reclamation Sciences)
"""

import sys
import os
from app_version import APP_VERSION
import traceback
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import numpy as np
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMenuBar, QMenu, QAction, QStatusBar, QLabel,
    QPushButton, QFileDialog, QComboBox, QSpinBox, QDoubleSpinBox,
    QTextEdit, QTableWidget, QTableWidgetItem, QTabWidget,
    QGroupBox, QFormLayout, QProgressBar, QMessageBox, QDialog,
    QSplitter, QHeaderView, QAbstractItemView, QScrollArea,
    QGridLayout, QCheckBox, QFrame, QRadioButton, QButtonGroup,
    QListWidget, QListWidgetItem, QSlider
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QImage, QIcon

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.patches import Circle as _MplCircle
import matplotlib.font_manager as fm

# ── 全局字体配置 ────────────────────────────────────────────────────────────
# 优先使用支持中文的系统字体（Windows: Microsoft YaHei / SimHei；
# macOS: PingFang SC；Linux: Noto Sans CJK SC）
# 若均不可用，退回 DejaVu Sans（纯英文，不显示乱码方块）
def _find_cjk_font():
    candidates = [
        'Microsoft YaHei', '微软雅黑',
        'SimHei', '黑体',
        'PingFang SC', 'Heiti SC',
        'Noto Sans CJK SC', 'WenQuanYi Micro Hei',
        'Arial Unicode MS',
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            return name
    return None

_CJK_FONT = _find_cjk_font()

# 只有找到 CJK 字体才设置，否则保持 DejaVu Sans 避免方块
if _CJK_FONT:
    matplotlib.rcParams['font.sans-serif'] = [_CJK_FONT, 'DejaVu Sans', 'Arial']
else:
    matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial']
matplotlib.rcParams['axes.unicode_minus'] = False  # 负号正常显示

# 导入后端模块
import preprocess
import root_analysis


# ============================================================================
# 资源路径工具（兼容 PyInstaller 打包）
# ============================================================================
def _resource_path(relative_name: str) -> str:
    """返回资源文件的绝对路径，兼容开发模式和 PyInstaller 打包模式。"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 运行时：资源解压至临时目录
        return os.path.join(sys._MEIPASS, relative_name)
    # 开发模式：与本脚本同目录
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_name)

# ============================================================================
# 国际化字符串 / i18n strings
# ============================================================================
_STRINGS = {
    'zh': {
        'win_title': '根系构型参数量化分析系统',
        # menus
        'menu_file': '文件(&F)', 'menu_open_csv': '打开结果 CSV(&O)...',
        'menu_save_csv': '另存为 CSV(&S)...', 'menu_export_excel': '导出 Excel(&E)...',
        'menu_exit': '退出(&Q)', 'menu_tools': '工具(&T)',
        'menu_preprocess_action': '图像预处理(&P)...', 'menu_analysis_action': '根系构型分析(&A)...',
        'menu_view_image': '查看图像(&I)...', 'menu_view': '查看(&V)',
        'menu_data_table': '结果数据表(&D)', 'menu_chart_view': '图表可视化(&C)',
        'menu_stats': '描述性统计(&S)', 'menu_log': '日志面板(&L)',
        'menu_lang': '语言 / Language', 'menu_lang_zh': '中文', 'menu_lang_en': 'English',
        'menu_theme': '界面主题', 'menu_theme_light': '浅色模式', 'menu_theme_dark': '深色模式',
        'menu_about': '帮助(&H)', 'menu_about_app': '关于本软件(&A)...', 'menu_help': '使用说明(&H)...',
        # tabs
        'tab_preprocess': '图像预处理', 'tab_analysis': '根系构型分析',
        'tab_data': '结果数据表', 'tab_chart': '图表可视化', 'tab_log': '操作日志',
        # preprocess tab
        'pp_dir_group': '目录设置', 'pp_input_dir': '原始图像目录:', 'pp_output_dir': '输出目录:',
        'pp_browse': '📂 浏览', 'pp_preview_group': '单张预览', 'pp_select_img': '选择图像:',
        'pp_preview_btn': '👁 预览当前图像', 'pp_preview_hint': '请先选择输入目录',
        'pp_param_group': '分割参数', 'pp_method_lbl': '分割方法:',
        'pp_window_lbl': '纹理窗口 (px):', 'pp_min_size_lbl': '最小连通域 (px):',
        'pp_hole_size_lbl': '填孔阈值 (px):', 'pp_close_radius_lbl': '闭运算半径:',
        'pp_bright_thresh_lbl': '亮边阈值 (0-1):', 'pp_border_margin_lbl': '边缘噪声宽度 (px):',
        'pp_isolation_lbl': '散点噪声距离 (px):',
        'pp_batch_group': '批量处理', 'pp_run_btn': '▶  批量处理全部图像', 'pp_ready': '就绪',
        'pp_workers_lbl': '并行线程数:',
        'an_workers_lbl': '并行线程数:',
        # parameter tooltips (preprocess)
        'tt_method':        "选择根系二值化分割算法\nmultiscale：多尺度纹理，同时检测粗根与细根（推荐）\ntexture：单尺度纹理，速度较快，适合结构均匀的根系\notsu：全局阈值，最快，适合对比度高的样本\nadaptive：自适应局部阈值，适合光照不均匀的图像",
        'tt_window':        "纹理计算窗口大小（像素）\nmultiscale 模式：此为粗尺度窗口（主根），细尺度自动设为 1/3\n推荐：根系较细 15-25，根系粗壮 25-51",
        'tt_min_size':      "小于此像素数的连通域将被删除（视为噪声碎片）\n推荐: 300DPI → 500，600DPI → 2000\n过小会保留噪点，过大会删除细根末端",
        'tt_hole_size':     "面积小于此值的内部空洞（黑色孔洞）将被填充为前景\n推荐: 200–500 px²；有髓腔结构的粗根可适当调大\n0 = 不执行",
        'tt_close_radius':  "形态学闭运算（先膨胀后腐蚀）的圆盘半径（像素）\n用于弥合根系中的微小断裂，使边缘更平滑\n推荐: 2–5；0 = 不执行",
        'tt_bright_thresh': "亮度超过此阈值的区域视为扫描纸张背景，在纹理计算前排除\n推荐: 白色背景扫描仪 0.90–0.95，默认 0.92\n调低可保留更多灰色区域参与纹理计算",
        'tt_border_margin': "删除与四边 N 像素带相交的小连通域（边框噪声）\n大组件受保护不会被删除  推荐: 300DPI→20, 600DPI→40\n0=不执行",
        'tt_isolation':     "剔除远离主根系的散点噪声\n小组件距主根区域超过 N 像素则删除\n推荐: 300DPI→150 (≈1.3cm)  0=不执行",
        'tt_workers':       "同时处理的图像数量；建议不超过 CPU 核心数",
        # parameter tooltips (analysis)
        'tt_csv_name':      "批量分析结果将保存为此文件名的 CSV 文件\n保存位置: 所选输出目录下\n可直接输入新文件名，无需包含路径",
        # analysis tab
        'an_dir_group': '输入目录',
        'an_binary_dir': '二值化图像目录:', 'an_skel_dir': '骨架图像目录:',
        'an_output_dir_lbl': '结果输出目录:',
        'an_not_selected': '（未选择）', 'an_select_sample': '选择样本:', 'an_refresh_btn': '↺ 刷新',
        'an_param_group': '分析参数',
        'an_csv_lbl': '输出文件名:',
        'an_run_group': '运行控制',
        'an_run_single_btn': '▶  分析当前样本', 'an_run_batch_btn': '▶▶  批量分析全部样本',
        'an_ready': '就绪',
        'msg_no_work_dir': '请先选择包含 binary/ 和 skeleton/ 子目录的预处理输出目录。',
        'msg_no_samples': '未找到任何样本。请先完成图像预处理，或检查目录是否正确。',
        # data tab
        'data_no_data': '暂无数据。请先运行根系构型分析，或通过【文件 > 打开结果 CSV】加载。',
        'data_stats_btn': '📊 描述性统计',
        # log tab
        'log_panel_title': '操作日志', 'log_clear_btn': '🗑 清除日志',
        # chart panel
        'chart_metric_lbl': '指标:', 'chart_type_lbl': '图表类型:', 'chart_group_lbl': '分组:',
        'chart_plot_btn': '📈 绘图', 'chart_save_btn': '💾 保存图表',
        'chart_types': ['箱线图', '柱状图', '散点图', '小提琴图', '直方图'],
        'chart_groups': ['按处理分组', '按品种分组', '按年份分组', '品种×处理×年份', '无分组'],
        'chart_no_group': '无分组',
        'chart_multi_group': '品种×处理×年份',
        # chart plot strings
        'chart_frequency':      '频次',
        'chart_sample':         '样本',
        'chart_sample_idx':     '样本序号',
        'chart_no_data':        '暂无可绘图的数据',
        'chart_missing_cols':   '数据中缺少列: {cols}',
        'chart_multi_xlabel':   '品种-处理（年份）',
        'chart_col_not_found':  '数据中不存在列 "{col}"',
        # chart log messages
        'chart_log_boxplot':    '箱线图：中线=中位数，箱体=四分位距(IQR, Q1–Q3)，须=1.5×IQR范围，圆点=离群值',
        'chart_log_bar':        '柱状图：柱高=均值，误差线=标准差(SD)，反映各组均值±变异水平',
        'chart_log_scatter':    '散点图：每点=一个样本，横向轻微抖动(jitter)避免重叠，可观察数据分布形态',
        'chart_log_violin':     '小提琴图：外形轮廓=核密度估计(KDE)，内部横线=均值，虚线=中位数，宽处数据更密集',
        'chart_log_hist':       '直方图：X轴=指标值，Y轴=频次，区间宽度由Sturges规则自动确定',
        'chart_log_plotted':    '已绘图 — 指标: {metric}，图表类型: {ctype}，分组: {group}',
        'chart_no_valid_data':  '列 "{col}" 中无有效数据',
        'chart_plot_error':     '绘图出错:\n{err}',
        'chart_title_grouped':  '{metric}  |  分组: {group}',
        'chart_title_nogroup':  '{metric}  |  全部样本',
        # erase tab
        'tab_erase':           '图像擦除',
        'er_input_group':      '输入目录',
        'er_binary_dir_lbl':   '二值化图像目录:',
        'er_skel_dir_lbl':     '骨架图像目录:',
        'er_select_sample':    '选择样本:',
        'er_refresh_btn':      '↺ 刷新',
        'er_no_dir':           '（未选择）',
        'er_brush_lbl':        '橡皮擦大小:',
        'er_undo_btn':         '↩ 撤销',
        'er_save_btn':         '💾 保存修改',
        'er_binary_title':     '二值化图像',
        'er_skel_title':       '骨架图像',
        'er_status_ready':     '就绪 — 请选择目录并加载图像',
        'er_status_erased':    '已擦除 — 可继续操作或保存',
        'er_status_saved':     '已保存: {path}',
        'er_status_load_err':  '加载失败: {err}',
        # about dialog
        'about_close': '确  定',
        # status / messages
        'status_ready': '就绪',
        'msg_warn': '警告', 'msg_error': '错误', 'msg_info': '提示',
        'msg_no_binary': '请先选择预处理工作目录。', 'msg_no_skel': '请先选择预处理工作目录。',
        'msg_no_input': '请先选择原始图像输入目录。', 'msg_no_output': '请先选择输出目录。',
        'msg_no_data': '暂无数据。', 'msg_done': '分析完成',
        'msg_analysis_done': '分析完成!\n共 {n} 个样本\n结果已保存至:\n{path}',
        'msg_save_ok': '保存成功', 'msg_saved_to': '已保存至:\n{path}',
        'msg_export_ok': 'Excel 已导出至:\n{path}',
        'msg_no_img': '请先选择原始图像目录并加载图像列表。',
        'msg_previewing': '预览中，请稍候...',
        'msg_preview_ok': '预览完成: {f}',
        'msg_batch_done': '批量处理完成: 成功 {ok} 张，失败 {fail} 张',
        'msg_pp_no_files': '未找到任何原始图像文件。',
        'help_title': '使用帮助',
        'dlg_stats_title': '描述性统计 / Descriptive Statistics',
        'dlg_stats_export': '导出统计结果',
        'dlg_save_chart': '保存图表', 'dlg_save_chart_ok': '图表已保存至:\n{path}',
        'dlg_open_csv': '打开 CSV 文件', 'dlg_save_csv': '另存 CSV',
        'dlg_save_excel': '导出 Excel',
        'dlg_img_filter': '图像 (*.jpg *.jpeg *.png *.tif *.tiff *.bmp);;所有文件 (*)',
        'dlg_open_img': '选择图像文件',
        # analysis result viewer overlay controls
        'viz_tips': '根尖', 'viz_forks': '分支点', 'viz_crossings': '交叉点',
        'viz_strahler': 'Strahler 级序', 'viz_angles': '分支角向量',
        'viz_diameter': '直径热力图', 'viz_boxgrid': '盒计数格网',
        'viz_marker_size': '标记大小:',
    },
    'en': {
        'win_title': 'Root Architecture Quantification System',
        # menus
        'menu_file': '&File', 'menu_open_csv': '&Open Results CSV...',
        'menu_save_csv': '&Save as CSV...', 'menu_export_excel': 'Export &Excel...',
        'menu_exit': '&Quit', 'menu_tools': '&Tools',
        'menu_preprocess_action': '&Image Preprocessing...', 'menu_analysis_action': '&Root Architecture Analysis...',
        'menu_view_image': 'View &Image...', 'menu_view': '&View',
        'menu_data_table': '&Results Table', 'menu_chart_view': '&Chart Visualization',
        'menu_stats': '&Descriptive Statistics', 'menu_log': '&Log Panel',
        'menu_lang': 'Language / 语言', 'menu_lang_zh': '中文', 'menu_lang_en': 'English',
        'menu_theme': 'Theme', 'menu_theme_light': 'Light Mode', 'menu_theme_dark': 'Dark Mode',
        'menu_about': '&Help', 'menu_about_app': '&About...', 'menu_help': '&User Manual...',
        # tabs
        'tab_preprocess': 'Image Preprocessing', 'tab_analysis': 'Root Architecture Analysis',
        'tab_data': 'Results Table', 'tab_chart': 'Chart Visualization', 'tab_log': 'Operation Log',
        # preprocess tab
        'pp_dir_group': 'Directory Settings', 'pp_input_dir': 'Raw Image Directory:', 'pp_output_dir': 'Output Directory:',
        'pp_browse': '📂 Browse', 'pp_preview_group': 'Single Image Preview', 'pp_select_img': 'Select Image:',
        'pp_preview_btn': '👁 Preview Selected Image', 'pp_preview_hint': 'Select an input directory first',
        'pp_param_group': 'Segmentation Parameters', 'pp_method_lbl': 'Segmentation Method:',
        'pp_window_lbl': 'Texture Window (px):', 'pp_min_size_lbl': 'Min Connected Region (px):',
        'pp_hole_size_lbl': 'Fill Holes Threshold (px):', 'pp_close_radius_lbl': 'Closing Radius:',
        'pp_bright_thresh_lbl': 'Bright Border Threshold (0-1):', 'pp_border_margin_lbl': 'Border Noise Width (px):',
        'pp_isolation_lbl': 'Isolated Noise Distance (px):',
        'pp_batch_group': 'Batch Processing', 'pp_run_btn': '▶  Process All Images', 'pp_ready': 'Ready',
        'pp_workers_lbl': 'Parallel Threads:',
        'an_workers_lbl': 'Parallel Threads:',
        # parameter tooltips (preprocess)
        'tt_method':        "Segmentation algorithm for root binarization\nmultiscale: multi-scale texture, detects thick & thin roots simultaneously (recommended)\ntexture: single-scale texture, faster, for uniform root systems\notsu: global threshold, fastest, for high-contrast samples\nadaptive: local adaptive threshold, for uneven illumination",
        'tt_window':        "Texture computation window size (pixels)\nIn multiscale mode: coarse-scale window for main roots; fine scale = 1/3 of this\nRecommended: thin roots 15-25, thick roots 25-51",
        'tt_min_size':      "Connected regions smaller than this (pixels) are removed as noise\nRecommended: 300DPI → 500, 600DPI → 2000\nToo small: noise retained; too large: fine root tips removed",
        'tt_hole_size':     "Internal holes (dark regions) smaller than this area are filled\nRecommended: 200–500 px²; increase for roots with large medullary cavities\n0 = disabled",
        'tt_close_radius':  "Disk radius for morphological closing (dilation then erosion)\nBridges small gaps in the root mask and smooths edges\nRecommended: 2–5; 0 = disabled",
        'tt_bright_thresh': "Regions brighter than this threshold are treated as scanner paper background\nRecommended: 0.90–0.95 for white-background scanners, default 0.92\nLower values include more grey regions in texture computation",
        'tt_border_margin': "Remove small connected regions touching the N-pixel border strip\nLarge components are protected  Recommended: 300DPI→20, 600DPI→40\n0 = disabled",
        'tt_isolation':     "Remove scattered noise far from the main root mass\nSmall components farther than N pixels from main roots are deleted\nRecommended: 300DPI→150 (≈1.3cm)  0 = disabled",
        'tt_workers':       "Number of images processed simultaneously; should not exceed CPU core count",
        # parameter tooltips (analysis)
        'tt_csv_name':      "Batch analysis results are saved as a CSV file with this name\nLocation: inside the selected output directory\nType a new filename directly; no path needed",
        # analysis tab
        'an_dir_group': 'Input Directories',
        'an_binary_dir': 'Binary Image Directory:', 'an_skel_dir': 'Skeleton Image Directory:',
        'an_output_dir_lbl': 'Results Output Directory:',
        'an_not_selected': '(not selected)', 'an_select_sample': 'Select Sample:', 'an_refresh_btn': '↺ Refresh',
        'an_param_group': 'Analysis Parameters',
        'an_csv_lbl': 'Output Filename:',
        'an_run_group': 'Run Control',
        'an_run_single_btn': '▶  Analyze Current Sample', 'an_run_batch_btn': '▶▶  Analyze All Samples',
        'an_ready': 'Ready',
        'msg_no_work_dir': 'Please select the preprocessing output directory (containing binary/ and skeleton/ subdirs).',
        'msg_no_samples': 'No samples found. Please complete image preprocessing or check the directory.',
        # data tab
        'data_no_data': 'No data available. Run root architecture analysis first, or open a CSV via [File > Open Results CSV].',
        'data_stats_btn': '📊 Descriptive Statistics',
        # log tab
        'log_panel_title': 'Operation Log', 'log_clear_btn': '🗑 Clear Log',
        # chart panel
        'chart_metric_lbl': 'Metric:', 'chart_type_lbl': 'Chart Type:', 'chart_group_lbl': 'Group by:',
        'chart_plot_btn': '📈 Plot', 'chart_save_btn': '💾 Save Chart',
        'chart_types': ['Boxplot', 'Bar Chart', 'Scatter', 'Violin', 'Histogram'],
        'chart_groups': ['By Treatment', 'By Variety', 'By Year', 'Variety×Treatment×Year', 'No Grouping'],
        'chart_no_group': 'No Grouping',
        'chart_multi_group': 'Variety×Treatment×Year',
        # chart plot strings
        'chart_frequency':      'Frequency',
        'chart_sample':         'Sample',
        'chart_sample_idx':     'Sample Index',
        'chart_no_data':        'No valid data to plot',
        'chart_missing_cols':   'Missing columns: {cols}',
        'chart_multi_xlabel':   'Variety-Treatment (Year)',
        'chart_col_not_found':  'Column "{col}" not found in data',
        # chart log messages
        'chart_log_boxplot':    'Boxplot: center line=median, box=IQR (Q1–Q3), whiskers=1.5×IQR, dots=outliers',
        'chart_log_bar':        'Bar chart: bar height=mean, error bar=standard deviation (SD)',
        'chart_log_scatter':    'Scatter: each point=one sample, horizontal jitter applied to avoid overlap',
        'chart_log_violin':     'Violin: outline=kernel density estimate (KDE), inner line=mean, dashed=median',
        'chart_log_hist':       'Histogram: X=metric value, Y=frequency, bin width by Sturges rule',
        'chart_log_plotted':    'Plotted — metric: {metric}, type: {ctype}, group: {group}',
        'chart_no_valid_data':  'No valid data in column "{col}"',
        'chart_plot_error':     'Plot error:\n{err}',
        'chart_title_grouped':  '{metric}  |  group: {group}',
        'chart_title_nogroup':  '{metric}  |  all samples',
        # about dialog
        # erase tab
        'tab_erase':           'Image Erasing',
        'er_input_group':      'Input Directories',
        'er_binary_dir_lbl':   'Binary Image Directory:',
        'er_skel_dir_lbl':     'Skeleton Image Directory:',
        'er_select_sample':    'Select Sample:',
        'er_refresh_btn':      '↺ Refresh',
        'er_no_dir':           '(not selected)',
        'er_brush_lbl':        'Eraser Size:',
        'er_undo_btn':         '↩ Undo',
        'er_save_btn':         '💾 Save Changes',
        'er_binary_title':     'Binary Image',
        'er_skel_title':       'Skeleton Image',
        'er_status_ready':     'Ready — select directories and load images',
        'er_status_erased':    'Erased — continue or save changes',
        'er_status_saved':     'Saved: {path}',
        'er_status_load_err':  'Load failed: {err}',
        'about_close': 'OK',
        # status / messages
        'status_ready': 'Ready',
        'msg_warn': 'Warning', 'msg_error': 'Error', 'msg_info': 'Info',
        'msg_no_binary': 'Please select the preprocessing work directory first.',
        'msg_no_skel': 'Please select the preprocessing work directory first.',
        'msg_no_input': 'Please select an input image directory first.',
        'msg_no_output': 'Please select an output directory first.',
        'msg_no_data': 'No data available.', 'msg_done': 'Analysis complete',
        'msg_analysis_done': 'Analysis complete!\n{n} samples processed\nResults saved to:\n{path}',
        'msg_save_ok': 'Saved', 'msg_saved_to': 'Saved to:\n{path}',
        'msg_export_ok': 'Excel exported to:\n{path}',
        'msg_no_img': 'Please select an input directory and load images first.',
        'msg_previewing': 'Previewing, please wait...',
        'msg_preview_ok': 'Preview done: {f}',
        'msg_batch_done': 'Batch done: {ok} succeeded, {fail} failed',
        'msg_pp_no_files': 'No raw image files found.',
        'help_title': 'User Guide',
        'dlg_stats_title': 'Descriptive Statistics',
        'dlg_stats_export': 'Export Statistics',
        'dlg_save_chart': 'Save Chart', 'dlg_save_chart_ok': 'Chart saved to:\n{path}',
        'dlg_open_csv': 'Open CSV File', 'dlg_save_csv': 'Save CSV As',
        'dlg_save_excel': 'Export Excel',
        'dlg_img_filter': 'Images (*.jpg *.jpeg *.png *.tif *.tiff *.bmp);;All Files (*)',
        'dlg_open_img': 'Select Image File(s)',
        # analysis result viewer overlay controls
        'viz_tips': 'Tips', 'viz_forks': 'Forks', 'viz_crossings': 'Crossings',
        'viz_strahler': 'Strahler', 'viz_angles': 'Branch Angle',
        'viz_diameter': 'Diameter Map', 'viz_boxgrid': 'Box Grid',
        'viz_marker_size': 'Marker Size:',
    },
}

_LANG = ['zh']  # mutable so tr() always reads the current value


def tr(key, **kw):
    """Return translated string. Optional keyword format args."""
    s = _STRINGS[_LANG[0]].get(key, key)
    return s.format(**kw) if kw else s


# ============================================================================
# 主题 QSS / Theme stylesheets
# ============================================================================
DARK_QSS = """
/* ── Global ─────────────────────────────────────────────────────── */
QMainWindow, QDialog, QWidget {
    background-color: #1e1f26;
    color: #e2e4e9;
    font-size: 13px;
}

/* ── Menu bar ────────────────────────────────────────────────────── */
QMenuBar {
    background-color: #252730;
    color: #c8cad0;
    border-bottom: 1px solid #3a3d4a;
    padding: 2px 4px;
}
QMenuBar::item { padding: 4px 10px; border-radius: 4px; }
QMenuBar::item:selected { background-color: #2d4f7a; color: #80b8ff; }
QMenu {
    background-color: #252730;
    color: #c8cad0;
    border: 1px solid #3a3d4a;
    border-radius: 6px;
    padding: 4px 0;
}
QMenu::item { padding: 6px 22px 6px 14px; border-radius: 4px; margin: 1px 4px; }
QMenu::item:selected { background-color: #2d4f7a; color: #80b8ff; }
QMenu::separator { height: 1px; background: #3a3d4a; margin: 4px 8px; }

/* ── Tab widget ──────────────────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #3a3d4a;
    border-radius: 0 6px 6px 6px;
    background-color: #252730;
    top: -1px;
}
QTabBar::tab {
    background-color: #2a2d38;
    color: #8890a0;
    padding: 8px 12px;
    min-width: 110px;
    min-height: 28px;
    border: 1px solid #3a3d4a;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    margin-right: 2px;
    font-weight: 500;
    font-size: 13px;
}
QTabBar::tab:selected {
    background-color: #252730;
    color: #80b8ff;
    border-bottom: 2px solid #4d9de0;
    font-weight: 700;
}
QTabBar::tab:hover:!selected { background-color: #2d3140; color: #a0b8d8; }
QTabBar QToolButton { width: 0px; height: 0px; border: none; background: transparent; }

/* ── Group box ───────────────────────────────────────────────────── */
QGroupBox {
    background-color: #252730;
    border: 1px solid #3a3d4a;
    border-radius: 8px;
    margin-top: 14px;
    padding: 8px 6px 6px 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #4d9de0;
    font-weight: 700;
    font-size: 12px;
}

/* ── Buttons — default ───────────────────────────────────────────── */
QPushButton {
    background-color: #2a2d38;
    color: #c8cad0;
    border: 1px solid #4a4f60;
    padding: 5px 14px;
    border-radius: 6px;
    font-weight: 500;
    min-height: 26px;
}
QPushButton:hover { background-color: #2d4f7a; border-color: #4d9de0; color: #80b8ff; }
QPushButton:pressed { background-color: #1e3d60; border-color: #3a7abf; }
QPushButton:disabled { color: #505568; background-color: #222530; border-color: #383c4a; }

/* ── Primary action buttons ──────────────────────────────────────── */
QPushButton#primary {
    background-color: #1967d2;
    color: #ffffff;
    border: none;
    padding: 7px 20px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 13px;
    min-height: 30px;
}
QPushButton#primary:hover { background-color: #2277e8; }
QPushButton#primary:pressed { background-color: #1256b0; }
QPushButton#primary:disabled { background-color: #1e3b6e; color: #5a7aaa; }

/* ── Input controls ──────────────────────────────────────────────── */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #1a1c24;
    color: #e2e4e9;
    border: 1px solid #3a3d4a;
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: #2d4f7a;
}
QLineEdit:focus, QTextEdit:focus { border-color: #4d9de0; }

QComboBox {
    background-color: #1a1c24;
    color: #e2e4e9;
    border: 1px solid #3a3d4a;
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 24px;
}
QComboBox:hover { border-color: #4d9de0; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #252730;
    color: #e2e4e9;
    border: 1px solid #3a3d4a;
    border-radius: 4px;
    selection-background-color: #2d4f7a;
    selection-color: #80b8ff;
}

QSpinBox, QDoubleSpinBox {
    background-color: #1a1c24;
    color: #e2e4e9;
    border: 1px solid #3a3d4a;
    border-radius: 6px;
    padding: 4px 6px;
}
QSpinBox:hover, QDoubleSpinBox:hover { border-color: #4d9de0; }
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: #2a2d38;
    border: none;
    border-left: 1px solid #3a3d4a;
    border-radius: 0 6px 6px 0;
}

/* ── Table ───────────────────────────────────────────────────────── */
QTableWidget {
    background-color: #1e1f26;
    color: #e2e4e9;
    gridline-color: #30333e;
    border: 1px solid #3a3d4a;
    border-radius: 6px;
    alternate-background-color: #22242f;
}
QTableWidget::item:selected { background-color: #2d4f7a; color: #e2e4e9; }
QHeaderView::section {
    background-color: #252730;
    color: #8890a0;
    border: none;
    border-bottom: 2px solid #3a3d4a;
    border-right: 1px solid #30333e;
    padding: 5px 8px;
    font-weight: 700;
}

/* ── Scrollbar ───────────────────────────────────────────────────── */
QScrollBar:vertical {
    background-color: #1e1f26;
    width: 10px;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background-color: #404455;
    min-height: 24px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover { background-color: #4d9de0; }
QScrollBar:horizontal {
    background-color: #1e1f26;
    height: 10px;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background-color: #404455;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover { background-color: #4d9de0; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }

/* ── Splitter ────────────────────────────────────────────────────── */
QSplitter::handle { background-color: #3a3d4a; }
QSplitter::handle:hover { background-color: #4d9de0; }

/* ── Progress bar ────────────────────────────────────────────────── */
QProgressBar {
    background-color: #2a2d38;
    color: #c8cad0;
    border: none;
    border-radius: 5px;
    text-align: center;
    min-height: 12px;
    font-size: 11px;
}
QProgressBar::chunk { background-color: #4d9de0; border-radius: 5px; }

/* ── Labels ──────────────────────────────────────────────────────── */
QLabel { color: #e2e4e9; }
QLabel[class="hint"] { color: #6b7280; font-size: 11px; }

/* ── Status bar ──────────────────────────────────────────────────── */
QStatusBar {
    background-color: #1560c0;
    color: #c8dff8;
    font-size: 12px;
    padding: 0 8px;
}
QStatusBar::item { border: none; }

/* ── Toolbar ─────────────────────────────────────────────────────── */
QToolBar { background-color: #252730; border: none; spacing: 4px; }

/* ── CheckBox ────────────────────────────────────────────────────── */
QCheckBox { color: #e2e4e9; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 2px solid #4a4f60;
    border-radius: 3px;
    background-color: #1a1c24;
}
QCheckBox::indicator:checked {
    background-color: #4d9de0;
    border-color: #4d9de0;
}

/* ── Frame separators ────────────────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] { color: #3a3d4a; }
"""

LIGHT_QSS = """
/* ── Global ─────────────────────────────────────────────────────── */
QMainWindow, QDialog, QWidget {
    background-color: #f5f6f8;
    color: #1a1a2e;
    font-size: 13px;
}

/* ── Menu bar ────────────────────────────────────────────────────── */
QMenuBar {
    background-color: #ffffff;
    color: #333333;
    border-bottom: 1px solid #dde1e7;
    padding: 2px 4px;
}
QMenuBar::item { padding: 4px 10px; border-radius: 4px; }
QMenuBar::item:selected { background-color: #e8f0fe; color: #1967d2; }
QMenu {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #dde1e7;
    border-radius: 6px;
    padding: 4px 0;
}
QMenu::item { padding: 6px 22px 6px 14px; border-radius: 4px; margin: 1px 4px; }
QMenu::item:selected { background-color: #e8f0fe; color: #1967d2; }
QMenu::separator { height: 1px; background: #e0e0e0; margin: 4px 8px; }

/* ── Tab widget ──────────────────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #dde1e7;
    border-radius: 0 6px 6px 6px;
    background-color: #ffffff;
    top: -1px;
}
QTabBar::tab {
    background-color: #edf0f5;
    color: #555566;
    padding: 8px 12px;
    min-width: 110px;
    min-height: 28px;
    border: 1px solid #dde1e7;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    margin-right: 2px;
    font-weight: 500;
    font-size: 13px;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #1967d2;
    border-bottom: 2px solid #1967d2;
    font-weight: 700;
}
QTabBar::tab:hover:!selected { background-color: #e2e8f5; color: #1967d2; }
QTabBar QToolButton { width: 0px; height: 0px; border: none; background: transparent; }

/* ── Group box ───────────────────────────────────────────────────── */
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #dde1e7;
    border-radius: 8px;
    margin-top: 14px;
    padding: 8px 6px 6px 6px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #1967d2;
    font-weight: 700;
    font-size: 12px;
}

/* ── Buttons — default ───────────────────────────────────────────── */
QPushButton {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #c4cad6;
    padding: 5px 14px;
    border-radius: 6px;
    font-weight: 500;
    min-height: 26px;
}
QPushButton:hover { background-color: #e8f0fe; border-color: #1967d2; color: #1967d2; }
QPushButton:pressed { background-color: #d2e3fc; border-color: #1565c0; }
QPushButton:disabled { color: #aaaaaa; background-color: #f0f0f0; border-color: #dddddd; }

/* ── Primary action buttons (object name "primary") ──────────────── */
QPushButton#primary {
    background-color: #1967d2;
    color: #ffffff;
    border: none;
    padding: 7px 20px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 13px;
    min-height: 30px;
}
QPushButton#primary:hover { background-color: #1558b0; }
QPushButton#primary:pressed { background-color: #0d47a1; }
QPushButton#primary:disabled { background-color: #a8c4e8; color: #ffffff; }

/* ── Input controls ──────────────────────────────────────────────── */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    color: #1a1a2e;
    border: 1px solid #c4cad6;
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: #d2e3fc;
}
QLineEdit:focus, QTextEdit:focus { border-color: #1967d2; }

QComboBox {
    background-color: #ffffff;
    color: #1a1a2e;
    border: 1px solid #c4cad6;
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 24px;
}
QComboBox:hover { border-color: #1967d2; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1a1a2e;
    border: 1px solid #c4cad6;
    border-radius: 4px;
    selection-background-color: #e8f0fe;
    selection-color: #1967d2;
}

QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    color: #1a1a2e;
    border: 1px solid #c4cad6;
    border-radius: 6px;
    padding: 4px 6px;
}
QSpinBox:hover, QDoubleSpinBox:hover { border-color: #1967d2; }
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: #edf0f5;
    border: none;
    border-left: 1px solid #c4cad6;
    border-radius: 0 6px 6px 0;
}

/* ── Table ───────────────────────────────────────────────────────── */
QTableWidget {
    background-color: #ffffff;
    color: #1a1a2e;
    gridline-color: #e8eaed;
    border: 1px solid #dde1e7;
    border-radius: 6px;
    alternate-background-color: #f8f9fc;
}
QTableWidget::item:selected { background-color: #d2e3fc; color: #1a1a2e; }
QHeaderView::section {
    background-color: #f0f3f8;
    color: #555566;
    border: none;
    border-bottom: 2px solid #dde1e7;
    border-right: 1px solid #e8eaed;
    padding: 5px 8px;
    font-weight: 700;
}

/* ── Scrollbar ───────────────────────────────────────────────────── */
QScrollBar:vertical {
    background-color: #f5f6f8;
    width: 10px;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background-color: #c4cad6;
    min-height: 24px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover { background-color: #1967d2; }
QScrollBar:horizontal {
    background-color: #f5f6f8;
    height: 10px;
    border-radius: 5px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background-color: #c4cad6;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover { background-color: #1967d2; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }

/* ── Splitter ────────────────────────────────────────────────────── */
QSplitter::handle { background-color: #dde1e7; }
QSplitter::handle:hover { background-color: #1967d2; }

/* ── Progress bar ────────────────────────────────────────────────── */
QProgressBar {
    background-color: #e8eaed;
    color: #333333;
    border: none;
    border-radius: 5px;
    text-align: center;
    min-height: 12px;
    font-size: 11px;
}
QProgressBar::chunk { background-color: #1967d2; border-radius: 5px; }

/* ── Labels ──────────────────────────────────────────────────────── */
QLabel { color: #1a1a2e; }
QLabel[class="hint"] { color: #6b7280; font-size: 11px; }

/* ── Status bar ──────────────────────────────────────────────────── */
QStatusBar {
    background-color: #1967d2;
    color: #e8f0fe;
    font-size: 12px;
    padding: 0 8px;
}
QStatusBar::item { border: none; }

/* ── Toolbar ─────────────────────────────────────────────────────── */
QToolBar { background-color: #f5f6f8; border: none; spacing: 4px; }

/* ── CheckBox ────────────────────────────────────────────────────── */
QCheckBox { color: #1a1a2e; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 2px solid #c4cad6;
    border-radius: 3px;
    background-color: #ffffff;
}
QCheckBox::indicator:checked {
    background-color: #1967d2;
    border-color: #1967d2;
}

/* ── Frame separators ────────────────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] { color: #dde1e7; }
"""


# ============================================================================
# 工作线程
# ============================================================================

class PreprocessWorker(QThread):
    """批量预处理工作线程"""
    progress    = pyqtSignal(int, int, str)        # current, total, filename
    finished    = pyqtSignal(int, list)            # success_count, failed_list
    error       = pyqtSignal(str)
    log         = pyqtSignal(str)
    sample_done = pyqtSignal(str, str, str, str)   # raw_path, bin_path, skel_path, fname

    def __init__(self, input_dirs, output_dir, method='texture',
                 window_size=25, block_size=51, offset=10,
                 min_size=500, hole_size=200, close_radius=3,
                 bright_thresh=0.92, border_margin=20, isolation_distance=150,
                 num_workers=4, repair_proximal_stem=False, stem_direction='top'):
        super().__init__()
        self.input_dirs = input_dirs
        self.output_dir = output_dir
        self.method = method
        self.window_size = window_size
        self.block_size = block_size
        self.offset = offset
        self.min_size = min_size
        self.hole_size = hole_size
        self.close_radius = close_radius
        self.bright_thresh = bright_thresh
        self.border_margin = border_margin
        self.isolation_distance = isolation_distance
        self.num_workers = num_workers
        self.repair_proximal_stem = repair_proximal_stem
        self.stem_direction = stem_direction

    def run(self):
        try:
            raw_files = preprocess.find_raw_images(self.input_dirs)
            if not raw_files:
                self.error.emit("未找到任何原始图像文件。")
                return

            total = len(raw_files)
            n_workers = max(1, min(self.num_workers, total))
            self.log.emit(f"找到 {total} 张原始图像，并行线程数: {n_workers}")
            # 列出待处理文件（最多显示 10 条，超出时省略中间部分）
            show = raw_files if total <= 10 else raw_files[:5] + ['…'] + raw_files[-3:]
            for item in show:
                name = os.path.basename(item) if item != '…' else '…'
                self.log.emit(f"  待处理: {name}")

            success = 0
            failed = []
            done = 0

            self.log.emit("正在初始化并行进程池（spawn 模式，首次启动约 30–60 秒）…")
            ctx = multiprocessing.get_context('spawn')
            with ProcessPoolExecutor(max_workers=n_workers, mp_context=ctx) as pool:
                args_list = [
                    (fp, self.output_dir, self.method,
                     self.window_size, self.block_size, self.offset,
                     self.min_size, self.hole_size, self.close_radius,
                     self.bright_thresh, self.border_margin, self.isolation_distance,
                     'auto', None, self.repair_proximal_stem, self.stem_direction)
                    for fp in raw_files
                ]
                futures = {pool.submit(preprocess._preprocess_worker_task, a): a
                           for a in args_list}
                self.log.emit(f"进程池就绪，{n_workers} 个子进程并行处理中，请耐心等待…")
                for future in as_completed(futures):
                    done += 1
                    args = futures[future]
                    fpath = args[0]
                    fname = os.path.basename(fpath)
                    try:
                        future.result()   # 检查是否有异常
                        # 构造输出路径
                        basename = os.path.splitext(fname)[0]
                        for suffix in ['-rgb', '_rgb', '-raw', '_raw', '-original', '_original']:
                            if basename.lower().endswith(suffix):
                                basename = basename[:-len(suffix)]
                                break
                        bp = os.path.join(self.output_dir, 'binary',   f'{basename}.png')
                        sp = os.path.join(self.output_dir, 'skeleton', f'{basename}.png')
                        success += 1
                        self.log.emit(f"  [{fname}] 成功 ({done}/{total})")
                        self.progress.emit(done, total, fname)
                        self.sample_done.emit(fpath, bp, sp, fname)
                    except Exception as e:
                        failed.append((fname, str(e)))
                        self.log.emit(f"  [{fname}] 失败: {e}")
                        self.progress.emit(done, total, fname)

            self.finished.emit(success, failed)
        except Exception as e:
            self.error.emit(f"预处理出错: {traceback.format_exc()}")


class SinglePreprocessWorker(QThread):
    """单张图像预览线程（用于参数调试）"""
    # 返回: raw_array, binary_array, skeleton_array (均为 numpy uint8 0/255)
    finished = pyqtSignal(object, object, object, str)  # raw, binary, skel, filepath
    error = pyqtSignal(str)

    def __init__(self, img_path, output_dir, method='texture',
                 window_size=25, block_size=51, offset=10,
                 min_size=500, hole_size=200, close_radius=3,
                 bright_thresh=0.92, border_margin=20, isolation_distance=150,
                 repair_proximal_stem=False, stem_direction='top'):
        super().__init__()
        self.img_path = img_path
        self.repair_proximal_stem = repair_proximal_stem
        self.stem_direction = stem_direction
        self.output_dir = output_dir
        self.method = method
        self.window_size = window_size
        self.block_size = block_size
        self.offset = offset
        self.min_size = min_size
        self.hole_size = hole_size
        self.close_radius = close_radius
        self.bright_thresh = bright_thresh
        self.border_margin = border_margin
        self.isolation_distance = isolation_distance

    def run(self):
        try:
            from skimage import io, color
            import tempfile

            # 加载原图
            img = io.imread(self.img_path)

            # 灰度化用于分割，但保留彩色原图用于展示
            if img.ndim == 3:
                gray = color.rgb2gray(img)
            else:
                if img.dtype == np.uint8:
                    gray = img.astype(float) / 255.0
                elif img.dtype == np.uint16:
                    gray = img.astype(float) / 65535.0
                elif np.issubdtype(img.dtype, np.integer):
                    gray = img.astype(float) / np.iinfo(img.dtype).max
                else:
                    gray = img.astype(float)
                    if gray.max() > 1.0:
                        gray = gray / gray.max()

            if self.method == 'line_art':
                binary = gray < (128 / 255)
            elif self.method == 'intensity':
                from root_segmentation import segment_root_intensity
                binary, _ = segment_root_intensity(gray, foreground='auto', low_ratio=0.8)
            else:
                # 检测边框（暗边 + 亮边）
                border_mask = preprocess.detect_scanner_border(
                    gray, bright_thresh=self.bright_thresh)

                # 分割
                if self.method == 'multiscale':
                    binary = preprocess.segment_multiscale(
                        gray, window_size=self.window_size, border_mask=border_mask)
                elif self.method == 'texture':
                    binary = preprocess.segment_texture(
                        gray, window_size=self.window_size, border_mask=border_mask)
                elif self.method == 'otsu':
                    binary = preprocess.segment_otsu(gray, border_mask=border_mask)
                elif self.method == 'adaptive':
                    binary = preprocess.segment_adaptive(
                        gray, block_size=self.block_size,
                        offset=self.offset, border_mask=border_mask)
                else:
                    binary = preprocess.segment_multiscale(gray, border_mask=border_mask)

                # 后处理
                binary = preprocess.postprocess_binary(
                    binary,
                    min_size=self.min_size,
                    hole_size=self.hole_size,
                    close_radius=self.close_radius,
                )

                # 移除边缘噪声
                binary = preprocess.remove_border_objects(
                    binary, border_margin=self.border_margin)

                # 移除离散噪点
                binary = preprocess.remove_isolated_noise(
                    binary, isolation_distance=self.isolation_distance)

            if self.repair_proximal_stem:
                from root_stem import repair_proximal_stem
                binary, _, _ = repair_proximal_stem(
                    binary, self.stem_direction, enabled=True)

            # 骨架化
            skeleton = preprocess.compute_skeleton(binary)

            # 转 uint8 (0/255) 返回
            raw_out = img  # 原图保持原样
            bin_out = (binary.astype(np.uint8) * 255)
            skel_out = (skeleton.astype(np.uint8) * 255)

            self.finished.emit(raw_out, bin_out, skel_out, self.img_path)
        except Exception as e:
            self.error.emit(f"预览出错:\n{traceback.format_exc()}")


class AnalysisWorker(QThread):
    """分析工作线程"""
    progress    = pyqtSignal(int, int, str)
    finished    = pyqtSignal(object, str)       # DataFrame, csv_path
    error       = pyqtSignal(str)
    log         = pyqtSignal(str)
    image_ready  = pyqtSignal(str, str)          # binary_path, skeleton_path  (分析前预览)
    result_ready = pyqtSignal(str, str, dict)    # binary_path, skeleton_path, result_dict

    def __init__(self, binary_dirs, skeleton_dirs, output_dir, dpi=None,
                 output_name='root_architecture_metrics.csv',
                 pairs_override=None, num_workers=4, root_direction='top',
                 root_model='general', crossing_context=True):
        """
        Parameters
        ----------
        pairs_override : list of dict, optional
            直接传入已构造好的 image-pairs（单样本模式）。
            若为 None，则用 find_image_pairs(binary_dirs, skeleton_dirs) 自动搜索。
        """
        super().__init__()
        self.binary_dirs = binary_dirs
        self.skeleton_dirs = skeleton_dirs
        self.output_dir = output_dir
        self.dpi = dpi
        self.output_name = output_name
        self.root_direction = root_direction
        self.root_model = root_model
        self.crossing_context = crossing_context
        self.pairs_override = pairs_override
        self.num_workers = num_workers

    @staticmethod
    def _enrich_result(result, pair):
        """将年份/品种/处理/重复信息写入 result dict（纯计算，线程安全）。

        支持两种文件名格式:
          新格式 (优先): Year-Variety-Treatment-Replicate
                        例: 2023-DH-P1-1, 2024-XY-W2-3
          旧格式 (兼容): Year_Variety-Treatment-Replicate
                        例: 2023_DH-P1-1, 2023_XYP1-2
        """
        sid_str = pair['sample_id']
        hyp_parts = sid_str.split('-')

        # ── 新格式: 第一段为4位年份数字 ──────────────────────────────────
        if len(hyp_parts) >= 4 and len(hyp_parts[0]) == 4 and hyp_parts[0].isdigit():
            result['Year']      = hyp_parts[0]
            result['Variety']   = hyp_parts[1]
            result['Treatment'] = hyp_parts[2]
            result['Replicate'] = '-'.join(hyp_parts[3:])
            return result

        # ── 旧格式: Year_Name-Treatment-Replicate ────────────────────────
        result['Year'] = pair['year']
        parts = sid_str.split('_', 1)
        if len(parts) == 2:
            name = parts[1]
            if name.startswith('DH-') or name.startswith('XY-'):
                sub_parts = name.split('-')
                result['Variety'] = sub_parts[0]
                result['Treatment'] = sub_parts[1] if len(sub_parts) > 1 else ''
                result['Replicate'] = sub_parts[2] if len(sub_parts) > 2 else ''
            elif name.startswith('DHP') or name.startswith('XYP'):
                result['Variety'] = 'DH' if name.startswith('DHP') else 'XY'
                rest = name[3:]
                rest_parts = rest.split('-')
                result['Treatment'] = 'P' + rest_parts[0] if rest_parts else ''
                result['Replicate'] = rest_parts[1] if len(rest_parts) > 1 else ''
            else:
                result['Variety'] = name
                result['Treatment'] = ''
                result['Replicate'] = ''
        else:
            result['Variety'] = ''
            result['Treatment'] = ''
            result['Replicate'] = ''
        return result

    def run(self):
        try:
            if self.pairs_override is not None:
                pairs = self.pairs_override
            else:
                pairs = root_analysis.find_image_pairs(self.binary_dirs, self.skeleton_dirs)
            if not pairs:
                self.error.emit("未找到任何图像对，请检查目录结构；两个目录中的样本文件名（不含扩展名）须相同。")
                return

            total = len(pairs)
            # 单样本时保留 step_log，多样本并行时关闭
            if total == 1:
                pair = pairs[0]
                sid = pair['sample_id']
                self.log.emit(f"[1/1] 分析: {sid}")
                self.image_ready.emit(pair['binary_path'], pair['skeleton_path'])
                try:
                    result = root_analysis.analyze_root_image(
                        binary_path=pair['binary_path'],
                        skeleton_path=pair['skeleton_path'],
                        dpi=self.dpi,
                        sample_id=sid,
                        step_log=self.log.emit,
                        root_direction=self.root_direction,
                        root_model=self.root_model,
                        crossing_context=self.crossing_context,
                    )
                    result = self._enrich_result(result, pair)
                    results = [result]
                    self.progress.emit(1, 1, sid)
                    self.log.emit(f"  [{sid}] 完成")
                    self.result_ready.emit(pair['binary_path'], pair['skeleton_path'], dict(result))
                except Exception as e:
                    self.error.emit(f"分析失败: {traceback.format_exc()}")
                    return
            else:
                n_workers = max(1, min(self.num_workers, total))
                self.log.emit(f"找到 {total} 对图像，并行线程数: {n_workers}")
                # 列出待分析样本（最多显示 10 条）
                sids = [p['sample_id'] for p in pairs]
                show = sids if total <= 10 else sids[:5] + ['…'] + sids[-3:]
                for s in show:
                    self.log.emit(f"  待分析: {s}")
                results = []
                done = 0

                self.log.emit("正在初始化并行进程池（spawn 模式，首次启动约 30–60 秒）…")
                ctx = multiprocessing.get_context('spawn')
                with ProcessPoolExecutor(max_workers=n_workers, mp_context=ctx) as pool:
                    args_list = [
                        (p['binary_path'], p['skeleton_path'], self.dpi, p['sample_id'],
                         self.root_direction, None, None, self.root_model, self.crossing_context)
                        for p in pairs
                    ]
                    futures = {pool.submit(root_analysis._analysis_worker_task, a): pairs[i]
                               for i, a in enumerate(args_list)}
                    self.log.emit(f"进程池就绪，{n_workers} 个子进程并行分析中，请耐心等待…")
                    for future in as_completed(futures):
                        done += 1
                        pair = futures[future]
                        sid = pair['sample_id']
                        try:
                            result = future.result()
                            result = self._enrich_result(result, pair)
                            results.append(result)
                            self.log.emit(f"  [{sid}] 完成 ({done}/{total})")
                            self.progress.emit(done, total, sid)
                            self.result_ready.emit(
                                pair['binary_path'], pair['skeleton_path'], dict(result))
                        except Exception as e:
                            self.log.emit(f"  [{sid}] 失败: {e}")
                            self.progress.emit(done, total, sid)

            # 构建 DataFrame
            df = pd.DataFrame(results)
            meta_cols = ['Sample_ID', 'Year', 'Variety', 'Treatment', 'Replicate', 'DPI', 'Scale_Source', 'Topology_Status', 'Root_Direction', 'Cycle_Rank', 'Num_Bases', 'Root_Length_px', 'Avg_Root_Diameter_px', 'Root_Surface_Area_px2', 'Root_Volume_px3']
            metric_cols = [
                'Fractal_Dimension', 'Fractal_Abundance',
                'MF_D0_Capacity', 'MF_D1_Information', 'MF_D2_Correlation',
                'MF_Delta_alpha', 'MF_Delta_f', 'MF_alpha_0', 'MF_f_alpha_0',
                'Root_Length_cm', 'Root_Surface_Area_cm2', 'Avg_Root_Diameter_mm',
                'Root_Volume_cm3', 'Num_Tips', 'Num_Forks', 'Num_Crossings',
                'Avg_Branch_Angle_deg', 'Tip_Density_per_cm', 'Branch_Density_per_cm',
                'Avg_Link_Length_cm',
                'Topological_Index', 'TI_Altitude', 'TI_Magnitude',
                'Strahler_Max_Order', 'Strahler_Bifurcation_Ratio', 'Strahler_Length_Ratio',
            ]
            strahler_detail_cols = sorted(
                [c for c in df.columns if c.startswith('Strahler_Order')],
                key=lambda x: (int(x.split('Order')[1].split('_')[0]), x.split('_')[-1])
            )
            col_order = meta_cols + metric_cols + strahler_detail_cols
            col_order = [c for c in col_order if c in df.columns]
            col_order += [c for c in df.columns if c not in col_order and not c.startswith('_')]
            df = df[col_order]

            os.makedirs(self.output_dir, exist_ok=True)
            csv_path = os.path.join(self.output_dir, self.output_name)
            df.to_csv(csv_path, index=False, encoding='utf-8-sig')

            self.finished.emit(df, csv_path)
        except Exception as e:
            self.error.emit(f"分析出错:\n{traceback.format_exc()}")


# ============================================================================
# 图像查看器
# ============================================================================

class ImageViewer(QWidget):
    """图像查看面板，支持缩放"""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.fig = Figure(figsize=(6, 5), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.ax = self.fig.add_subplot(111)
        self.ax.axis('off')
        self.fig.tight_layout()

    def show_image(self, img_path):
        """显示图像文件"""
        self.ax.clear()
        self.ax.axis('off')
        try:
            from skimage import io
            img = io.imread(img_path)
            if img.ndim == 2:
                self.ax.imshow(img, cmap='gray')
            else:
                self.ax.imshow(img)
            self.ax.set_title(os.path.basename(img_path), fontsize=9)
        except Exception as e:
            self.ax.text(0.5, 0.5, f'Cannot load image:\n{e}',
                        transform=self.ax.transAxes, ha='center', va='center')
        self.fig.tight_layout()
        self.canvas.draw()

    def show_comparison(self, img_path1, img_path2, title1='二值化', title2='骨架'):
        """并排显示两张图像"""
        self.fig.clear()
        ax1 = self.fig.add_subplot(121)
        ax2 = self.fig.add_subplot(122)
        from skimage import io
        try:
            img1 = io.imread(img_path1)
            ax1.imshow(img1, cmap='gray' if img1.ndim == 2 else None)
            ax1.set_title(title1, fontsize=9)
        except Exception:
            ax1.text(0.5, 0.5, 'Cannot load', ha='center', va='center', transform=ax1.transAxes)
        try:
            img2 = io.imread(img_path2)
            ax2.imshow(img2, cmap='gray' if img2.ndim == 2 else None)
            ax2.set_title(title2, fontsize=9)
        except Exception:
            ax2.text(0.5, 0.5, 'Cannot load', ha='center', va='center', transform=ax2.transAxes)
        ax1.axis('off')
        ax2.axis('off')
        self.fig.tight_layout()
        self.canvas.draw()

    def clear(self):
        self.ax = self.fig.add_subplot(111)
        self.ax.clear()
        self.ax.axis('off')
        self.canvas.draw()


# ============================================================================
# 三联图预览器 (原图 | 二值化 | 骨架)
# ============================================================================

class TripleImageViewer(QWidget):
    """
    三联图查看器，左→中→右分别显示：原图 / 二值化 / 骨架
    支持直接传入 numpy 数组（实时预览）或文件路径。
    批量处理完成的样本会缓存，可通过 ◀/▶ 左右切换回看。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.fig = Figure(figsize=(12, 4), dpi=90)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 1)

        # ── 导航栏 ──────────────────────────────────────────────────
        nav_bar = QWidget()
        nav_bar.setFixedHeight(36)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(8, 2, 8, 2)
        nav_layout.setSpacing(6)

        self._btn_prev = QPushButton("◀  Prev")
        self._btn_prev.setMinimumWidth(80)
        self._btn_prev.setEnabled(False)
        self._btn_prev.clicked.connect(self._go_prev)

        self._nav_label = QLabel("—")
        self._nav_label.setAlignment(Qt.AlignCenter)
        _f = self._nav_label.font(); _f.setBold(True)
        self._nav_label.setFont(_f)

        self._btn_next = QPushButton("Next  ▶")
        self._btn_next.setMinimumWidth(80)
        self._btn_next.setEnabled(False)
        self._btn_next.clicked.connect(self._go_next)

        nav_layout.addStretch()
        nav_layout.addWidget(self._btn_prev)
        nav_layout.addWidget(self._nav_label)
        nav_layout.addWidget(self._btn_next)
        nav_layout.addStretch()
        layout.addWidget(nav_bar)

        # 样本缓存（仅文件路径，批量处理完的样本）
        self._samples = []   # list of (raw_path, bin_path, skel_path, label)
        self._cur = 0

        self._init_axes()

    def _init_axes(self):
        self.fig.clear()
        self.ax_raw  = self.fig.add_subplot(131)
        self.ax_bin  = self.fig.add_subplot(132)
        self.ax_skel = self.fig.add_subplot(133)
        for ax, title in zip(
            [self.ax_raw, self.ax_bin, self.ax_skel],
            ['Raw Image', 'Binary', 'Skeleton']
        ):
            ax.axis('off')
            ax.set_title(title, fontsize=10, pad=4)
        self.fig.tight_layout(pad=1.5)
        self.canvas.draw()

    def show_arrays(self, raw, binary, skeleton, filename=''):
        """传入 numpy 数组显示（直接预览，不写文件）"""
        self.fig.clear()
        ax_r = self.fig.add_subplot(131)
        ax_b = self.fig.add_subplot(132)
        ax_s = self.fig.add_subplot(133)

        ax_r.imshow(raw, cmap='gray' if raw.ndim == 2 else None)
        ax_r.set_title(f'Raw Image\n{filename}', fontsize=9, pad=4)
        ax_r.axis('off')

        ax_b.imshow(binary, cmap='gray')
        ax_b.set_title('Binary', fontsize=9, pad=4)
        ax_b.axis('off')

        ax_s.imshow(skeleton, cmap='gray')
        ax_s.set_title('Skeleton', fontsize=9, pad=4)
        ax_s.axis('off')

        self.fig.tight_layout(pad=1.5)
        self.canvas.draw()

    def show_files(self, raw_path, binary_path=None, skeleton_path=None):
        """从文件路径显示，binary/skeleton 可为 None（仅显示原图）"""
        from skimage import io as skio
        self.fig.clear()
        ax_r = self.fig.add_subplot(131)
        ax_b = self.fig.add_subplot(132)
        ax_s = self.fig.add_subplot(133)

        def _load(path):
            try:
                return skio.imread(path)
            except Exception:
                return None

        img_r = _load(raw_path) if raw_path else None
        img_b = _load(binary_path) if binary_path else None
        img_s = _load(skeleton_path) if skeleton_path else None

        fname = os.path.basename(raw_path) if raw_path else ''

        if img_r is not None:
            ax_r.imshow(img_r, cmap='gray' if img_r.ndim == 2 else None)
        else:
            ax_r.text(0.5, 0.5, 'Cannot load', ha='center', va='center',
                      transform=ax_r.transAxes)
        ax_r.set_title(f'Raw Image\n{fname}', fontsize=9, pad=4)
        ax_r.axis('off')

        if img_b is not None:
            ax_b.imshow(img_b, cmap='gray')
        else:
            ax_b.text(0.5, 0.5, '(N/A)', ha='center', va='center',
                      transform=ax_b.transAxes, color='gray')
        ax_b.set_title('Binary', fontsize=9, pad=4)
        ax_b.axis('off')

        if img_s is not None:
            ax_s.imshow(img_s, cmap='gray')
        else:
            ax_s.text(0.5, 0.5, '(N/A)', ha='center', va='center',
                      transform=ax_s.transAxes, color='gray')
        ax_s.set_title('Skeleton', fontsize=9, pad=4)
        ax_s.axis('off')

        self.fig.tight_layout(pad=1.5)
        self.canvas.draw()

    def clear(self):
        self._init_axes()

    # ------------------------------------------------------------------
    # 批量处理导航接口
    # ------------------------------------------------------------------
    def clear_samples(self):
        """新一轮批量开始前清空缓存"""
        self._samples = []
        self._cur = 0
        self._update_nav()
        self._init_axes()

    def add_file_sample(self, raw_path, binary_path, skel_path, label=''):
        """批量处理完一张后调用：缓存路径并跳到该样本"""
        if not label:
            label = os.path.basename(raw_path) if raw_path else ''
        self._samples.append((raw_path, binary_path, skel_path, label))
        self._cur = len(self._samples) - 1
        self.show_files(raw_path, binary_path, skel_path)
        self._update_nav()

    def _show_current(self):
        if not self._samples:
            return
        raw, bp, sp, _ = self._samples[self._cur]
        self.show_files(raw, bp, sp)
        self._update_nav()

    def _update_nav(self):
        n = len(self._samples)
        if n == 0:
            self._nav_label.setText("—")
        else:
            label = self._samples[self._cur][3]
            self._nav_label.setText(f"  {self._cur + 1} / {n}   |   {label}  ")
        self._btn_prev.setEnabled(n > 1 and self._cur > 0)
        self._btn_next.setEnabled(n > 1 and self._cur < n - 1)

    def _go_prev(self):
        if self._cur > 0:
            self._cur -= 1
            self._show_current()

    def _go_next(self):
        if self._cur < len(self._samples) - 1:
            self._cur += 1
            self._show_current()


# ══════════════════════════════════════════════════════════════════════════════
# 擦除标签页
# ══════════════════════════════════════════════════════════════════════════════

class EraseTab(QWidget):
    """
    擦除标签页：同步手动擦除二值化图和骨架图中的噪声像素。

    工作流程：
      1. 选择二值化目录和骨架目录，下拉选择样本
      2. 左键拖动 → 在两张图上同步标记待擦除区域（红色预览）
      3. 松开鼠标 → 立即应用擦除并刷新
      4. Ctrl+Z 撤销上一笔
      5. 点击「保存」覆盖写回原文件

    骨架显示与根系分析页完全一致：skio.imread(as_gray=True) + imshow(cmap='gray')
    """

    log_message = pyqtSignal(str)
    _IMG_EXTS = ('*.png', '*.jpg', '*.jpeg', '*.tif', '*.tiff', '*.bmp')

    def __init__(self, parent=None):
        super().__init__(parent)
        # 目录
        self._er_binary_dir = ''
        self._er_skel_dir   = ''
        # 图像数据（float64 [0,1]，与分析页加载方式完全相同）
        self._bin_work  = None
        self._skel_work = None
        self._bin_path  = None
        self._skel_path = None
        self._bin_dpi   = None   # 原始文件 DPI 元数据（保存时写回）
        self._skel_dpi  = None
        # 擦除
        self._erase_mask = None  # bool (h, w)，当次笔画累积区域，全分辨率
        self._painting   = False
        self._brush_r    = 20
        self._last_mark_t = 0.0  # 时间节流：上次 _mark_at 时间戳
        self._OVL_DS = 4         # overlay 显示降采样倍数（仅影响预览，不影响分析）
        # 撤销栈
        self._history    = []
        self._max_history = 30
        # matplotlib 对象（按画布分）
        self._ax_b = self._ax_s = None
        self._fig_b = self._fig_s = None
        self._cvs_b = self._cvs_s = None
        self._base_b  = self._base_s  = None   # 底图 AxesImage
        self._ovl_arr_b = self._ovl_arr_s = None  # RGBA overlay ndarray
        self._ovl_b   = self._ovl_s   = None   # overlay AxesImage (animated)
        self._cur_b   = self._cur_s   = None   # cursor Circle (animated)
        self._bg_b    = self._bg_s    = None   # blit 背景缓存
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 6)
        root.setSpacing(6)

        # ── 输入区（与根系构型分析页样式完全一致）────────────────────────
        input_grp = QGroupBox(tr('er_input_group'))
        self._input_grp = input_grp
        ig = QVBoxLayout(input_grp)
        ig.setSpacing(4)
        ig.setContentsMargins(8, 6, 8, 6)

        def _path_row(layout, lbl_key, slot):
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(tr(lbl_key))
            lbl.setMinimumWidth(130)
            lbl.setMaximumWidth(165)
            path_lbl = QLabel(tr('er_no_dir'))
            path_lbl.setStyleSheet('font-style: italic; opacity: 0.7;')
            path_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            btn = QPushButton(tr('pp_browse'))
            btn.setMinimumWidth(82)
            btn.clicked.connect(slot)
            h.addWidget(lbl)
            h.addWidget(path_lbl, 1)
            h.addWidget(btn)
            layout.addWidget(row)
            return path_lbl, btn

        self._lbl_bin,  self._btn_bin  = _path_row(ig, 'er_binary_dir_lbl', self._browse_binary)
        self._lbl_skel, self._btn_skel = _path_row(ig, 'er_skel_dir_lbl',   self._browse_skel)

        sel_row = QHBoxLayout()
        self._sel_lbl = QLabel(tr('er_select_sample'))
        self._sel_lbl.setMinimumWidth(130)
        self._sel_lbl.setMaximumWidth(165)
        self._sample_combo = QComboBox()
        self._sample_combo.setToolTip('选择目录后自动填充样本列表')
        self._sample_combo.currentIndexChanged.connect(self._on_sample_changed)
        self._refresh_btn = QPushButton(tr('er_refresh_btn'))
        self._refresh_btn.setMinimumWidth(78)
        self._refresh_btn.clicked.connect(self._scan_samples)
        sel_row.addWidget(self._sel_lbl)
        sel_row.addWidget(self._sample_combo, 1)
        sel_row.addWidget(self._refresh_btn)
        ig.addLayout(sel_row)
        root.addWidget(input_grp)

        # ── 工具栏 ────────────────────────────────────────────────────
        tb = QHBoxLayout()
        tb.setSpacing(8)

        self._brush_lbl_w = QLabel(tr('er_brush_lbl'))
        tb.addWidget(self._brush_lbl_w)

        self._brush_slider = QSlider(Qt.Horizontal)
        self._brush_slider.setRange(2, 150)
        self._brush_slider.setValue(self._brush_r)
        self._brush_slider.setFixedWidth(160)
        self._brush_slider.valueChanged.connect(self._on_brush_changed)
        tb.addWidget(self._brush_slider)

        self._brush_px_lbl = QLabel(f'{self._brush_r} px')
        self._brush_px_lbl.setMinimumWidth(48)
        tb.addWidget(self._brush_px_lbl)

        tb.addSpacing(12)

        self._undo_btn = QPushButton(tr('er_undo_btn'))
        self._undo_btn.setMinimumWidth(90)
        self._undo_btn.setEnabled(False)
        self._undo_btn.clicked.connect(self._undo)
        tb.addWidget(self._undo_btn)

        tb.addSpacing(12)

        self._prev_btn = QPushButton('◀ 上一个')
        self._prev_btn.setMinimumWidth(80)
        self._prev_btn.setEnabled(False)
        self._prev_btn.clicked.connect(self._go_prev)
        tb.addWidget(self._prev_btn)

        self._next_btn = QPushButton('下一个 ▶')
        self._next_btn.setMinimumWidth(80)
        self._next_btn.setEnabled(False)
        self._next_btn.clicked.connect(self._go_next)
        tb.addWidget(self._next_btn)

        tb.addStretch()

        self._status_lbl = QLabel(tr('er_status_ready'))
        self._status_lbl.setStyleSheet('color: gray;')
        tb.addWidget(self._status_lbl)

        tb.addStretch()

        self._save_btn = QPushButton(tr('er_save_btn'))
        self._save_btn.setObjectName('primary')
        self._save_btn.setMinimumWidth(100)
        self._save_btn.setMinimumHeight(34)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save)
        tb.addWidget(self._save_btn)

        root.addLayout(tb)

        # ── 双联画布（两个独立 Figure，放在 Splitter 中）────────────────
        splitter = QSplitter(Qt.Horizontal)

        self._fig_b = Figure(figsize=(5, 8), dpi=90)
        self._cvs_b = FigureCanvas(self._fig_b)
        self._ax_b  = self._fig_b.add_subplot(111)

        self._fig_s = Figure(figsize=(5, 8), dpi=90)
        self._cvs_s = FigureCanvas(self._fig_s)
        self._ax_s  = self._fig_s.add_subplot(111)

        splitter.addWidget(self._cvs_b)
        splitter.addWidget(self._cvs_s)
        splitter.setSizes([600, 600])
        root.addWidget(splitter, 1)

        # Ctrl+Z 撤销
        from PyQt5.QtWidgets import QShortcut
        from PyQt5.QtGui import QKeySequence
        self._sc_undo = QShortcut(QKeySequence('Ctrl+Z'), self)
        self._sc_undo.activated.connect(self._undo)

        # 连接鼠标事件
        for cvs in (self._cvs_b, self._cvs_s):
            cvs.mpl_connect('button_press_event',   self._on_press)
            cvs.mpl_connect('motion_notify_event',  self._on_move)
            cvs.mpl_connect('button_release_event', self._on_release)

        self._draw_placeholder()

    # ------------------------------------------------------------------
    # 目录浏览
    # ------------------------------------------------------------------
    def _browse_binary(self):
        d = QFileDialog.getExistingDirectory(self, tr('er_binary_dir_lbl'))
        if not d:
            return
        self._er_binary_dir = d
        self._lbl_bin.setText(d)
        self._lbl_bin.setStyleSheet('')
        self._lbl_bin.setToolTip(d)
        self._log(f"已选择二值化目录: {d}")
        self._scan_samples()

    def _browse_skel(self):
        d = QFileDialog.getExistingDirectory(self, tr('er_skel_dir_lbl'))
        if not d:
            return
        self._er_skel_dir = d
        self._lbl_skel.setText(d)
        self._lbl_skel.setStyleSheet('')
        self._lbl_skel.setToolTip(d)
        self._log(f"已选择骨架目录: {d}")

    # ------------------------------------------------------------------
    # 样本扫描 & 切换（与根系分析页逻辑完全一致）
    # ------------------------------------------------------------------
    def _scan_samples(self):
        import glob as _glob
        self._sample_combo.blockSignals(True)
        self._sample_combo.clear()
        if os.path.isdir(self._er_binary_dir):
            files = sorted([
                f for ext in self._IMG_EXTS
                for f in _glob.glob(os.path.join(self._er_binary_dir, ext))
            ])
            for f in files:
                self._sample_combo.addItem(os.path.splitext(os.path.basename(f))[0])
        self._sample_combo.blockSignals(False)
        n = self._sample_combo.count()
        self._log(f"扫描完成: 找到 {n} 个样本")
        if n > 0:
            self._sample_combo.setCurrentIndex(0)
            self._on_sample_changed(0)
        self._update_nav_btns()

    def _update_nav_btns(self):
        idx = self._sample_combo.currentIndex()
        n   = self._sample_combo.count()
        self._prev_btn.setEnabled(n > 1 and idx > 0)
        self._next_btn.setEnabled(n > 1 and idx < n - 1)

    def _go_prev(self):
        idx = self._sample_combo.currentIndex()
        if idx > 0:
            self._sample_combo.setCurrentIndex(idx - 1)

    def _go_next(self):
        idx = self._sample_combo.currentIndex()
        if idx < self._sample_combo.count() - 1:
            self._sample_combo.setCurrentIndex(idx + 1)

    def _on_sample_changed(self, index):
        if index < 0 or index >= self._sample_combo.count():
            return
        self._update_nav_btns()
        stem = self._sample_combo.itemText(index)
        img_exts = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp')

        def _find(d, stem):
            for ext in img_exts:
                p = os.path.join(d, stem + ext)
                if os.path.exists(p):
                    return p
            return None

        bin_p  = _find(self._er_binary_dir, stem) if self._er_binary_dir else None
        skel_p = _find(self._er_skel_dir,   stem) if self._er_skel_dir   else None
        self._load_pair(bin_p, skel_p)

    # ------------------------------------------------------------------
    # 图像加载（与根系分析页 show_pair 相同的读取方式）
    # ------------------------------------------------------------------
    @staticmethod
    def _pil_load(path):
        """用 PIL 读取图像，返回 (float64_array, dpi_tuple)。
        PIL 能保留 JPEG 文件头中的 DPI 元数据，供保存时写回。
        """
        from PIL import Image as _PilImage
        img = _PilImage.open(path).convert('L')   # 灰度
        from calibration import image_scale
        value, _ = image_scale(path)
        dpi = (value,value) if value is not None else None
        arr = np.array(img).astype(np.float64) / 255.0
        return arr, dpi

    def _load_pair(self, bin_path, skel_path):
        try:
            bin_changed  = bin_path  and bin_path  != self._bin_path
            skel_changed = skel_path and skel_path != self._skel_path
            if bin_changed:
                self._bin_work, self._bin_dpi = self._pil_load(bin_path)
                self._bin_path  = bin_path
                self._history.clear()
                self._undo_btn.setEnabled(False)
            if skel_changed:
                self._skel_work, self._skel_dpi = self._pil_load(skel_path)
                self._skel_path = skel_path
        except Exception as e:
            self._status_lbl.setText(tr('er_status_load_err', err=str(e)))
            return

        if self._bin_work is not None and self._skel_work is not None:
            h, w = self._bin_work.shape
            if self._erase_mask is None or self._erase_mask.shape != (h, w):
                self._erase_mask = np.zeros((h, w), dtype=bool)
            self._refresh_canvases()
            self._save_btn.setEnabled(True)
            stem = os.path.splitext(os.path.basename(self._bin_path))[0]
            self._log(f"已加载样本: {stem}")
            self._status_lbl.setText(tr('er_status_ready'))

    # ------------------------------------------------------------------
    # 画布绘制
    # ------------------------------------------------------------------
    def _draw_placeholder(self):
        for ax, fig, cvs in [
            (self._ax_b, self._fig_b, self._cvs_b),
            (self._ax_s, self._fig_s, self._cvs_s),
        ]:
            ax.clear()
            ax.text(0.5, 0.5, '请先加载图像',
                    ha='center', va='center', fontsize=10,
                    color='gray', transform=ax.transAxes)
            ax.axis('off')
            fig.subplots_adjust(left=0.01, right=0.99, top=0.96, bottom=0.01)
            cvs.draw()
        self._base_b = self._base_s = None
        self._ovl_b  = self._ovl_s  = None
        self._cur_b  = self._cur_s  = None
        self._bg_b   = self._bg_s   = None

    def _refresh_canvases(self):
        """全量重绘两个画布，建立 blit 缓存。"""
        self._init_canvas(self._ax_b, self._fig_b, self._cvs_b,
                          self._bin_work,  tr('er_binary_title'), 'b')
        self._init_canvas(self._ax_s, self._fig_s, self._cvs_s,
                          self._skel_work, tr('er_skel_title'),   's')

    def _init_canvas(self, ax, fig, cvs, img, title, side):
        """初始化单个画布：底图 + 透明覆盖层 + 光标圆，缓存 blit 背景。"""
        h, w = img.shape
        ax.clear()
        # 底图：与根系分析页 show_pair 完全相同的显示方式
        # 不指定 interpolation，使用 matplotlib 默认的 'antialiased'（面积平均下采样）
        # 避免 'nearest' 在缩小显示时跳过 1px 骨架线导致断续
        base = ax.imshow(img, cmap='gray', aspect='equal')
        # 覆盖层（animated=True 用于 blit）
        # 降采样存储以减小 set_data 传输量（显示时 extent 拉伸覆盖全图，不影响分析）
        ds = self._OVL_DS
        ovl_arr = np.zeros((max(1, h // ds), max(1, w // ds), 4), dtype=np.uint8)
        ovl = ax.imshow(ovl_arr, interpolation='nearest', aspect='equal',
                        extent=[0, w, h, 0], animated=True)
        # 光标圆（animated=True）
        cur = _MplCircle((0, 0), radius=1, fill=False, color='red',
                         linewidth=1.5, linestyle='--', visible=False, animated=True)
        ax.add_patch(cur)
        ax.set_title(title, fontsize=10, pad=4)
        ax.axis('off')
        fig.subplots_adjust(left=0.01, right=0.99, top=0.96, bottom=0.01)
        cvs.draw()
        bg = cvs.copy_from_bbox(fig.bbox)

        if side == 'b':
            self._base_b, self._ovl_arr_b, self._ovl_b, self._cur_b, self._bg_b = \
                base, ovl_arr, ovl, cur, bg
        else:
            self._base_s, self._ovl_arr_s, self._ovl_s, self._cur_s, self._bg_s = \
                base, ovl_arr, ovl, cur, bg

    # ------------------------------------------------------------------
    # 鼠标事件
    # ------------------------------------------------------------------
    def _get_scale(self):
        try:
            bbox = self._ax_b.get_window_extent()
            xlim = self._ax_b.get_xlim()
            return bbox.width / max(abs(xlim[1] - xlim[0]), 1)
        except Exception:
            return 1.0

    def _on_press(self, event):
        if self._bin_work is None:
            return
        if event.button == 1 and event.inaxes in (self._ax_b, self._ax_s):
            self._push_history()
            self._painting = True
            self._mark_at(event.xdata, event.ydata)

    def _on_move(self, event):
        on_b = event.inaxes is self._ax_b
        on_s = event.inaxes is self._ax_s
        x, y = event.xdata, event.ydata

        if not (on_b or on_s) or x is None:
            # 离开画布：隐藏光标
            for cur, bg, cvs, fig in [
                (self._cur_b, self._bg_b, self._cvs_b, self._fig_b),
                (self._cur_s, self._bg_s, self._cvs_s, self._fig_s),
            ]:
                if cur and cur.get_visible():
                    cur.set_visible(False)
                    if bg:
                        cvs.restore_region(bg)
                        cvs.blit(fig.bbox)
            return

        if self._painting:
            import time
            now = time.monotonic()
            if now - self._last_mark_t >= 0.016:   # ~60 fps 节流
                self._last_mark_t = now
                self._mark_at(x, y)
        else:
            self._blit_cursors_only(x, y)

    def _on_release(self, event):
        if event.button == 1 and self._painting:
            self._painting = False
            self._apply_stroke()

    def _mark_at(self, cx, cy):
        """将圆形笔刷写入 erase_mask（全分辨率），并 blit 实时预览（降采样）。"""
        if cx is None or cy is None or self._bin_work is None:
            return
        h, w = self._bin_work.shape
        scale = self._get_scale()
        r = max(1.0, self._brush_r / scale)

        # ── 全分辨率 erase_mask 更新（决定分析结果，不降采样）──────────
        y0 = max(0, int(cy - r) - 1)
        y1 = min(h, int(cy + r) + 2)
        x0 = max(0, int(cx - r) - 1)
        x1 = min(w, int(cx + r) + 2)
        if y0 >= y1 or x0 >= x1:
            return
        yy, xx = np.ogrid[y0:y1, x0:x1]
        self._erase_mask[y0:y1, x0:x1] |= (xx - cx) ** 2 + (yy - cy) ** 2 <= r ** 2

        # ── 降采样坐标（仅用于 overlay 显示）────────────────────────────
        ds = self._OVL_DS
        oh, ow = max(1, h // ds), max(1, w // ds)
        cy_ds, cx_ds = cy / ds, cx / ds
        r_ds = max(1.0, r / ds)
        oy0 = max(0, int(cy_ds - r_ds) - 1)
        oy1 = min(oh, int(cy_ds + r_ds) + 2)
        ox0 = max(0, int(cx_ds - r_ds) - 1)
        ox1 = min(ow, int(cx_ds + r_ds) + 2)
        if oy0 >= oy1 or ox0 >= ox1:
            return
        oyy, oxx = np.ogrid[oy0:oy1, ox0:ox1]
        new_circle_ds = (oxx - cx_ds) ** 2 + (oyy - cy_ds) ** 2 <= r_ds ** 2
        self._blit_overlay(cx, cy, patch=(oy0, oy1, ox0, ox1, new_circle_ds))

    def _blit_overlay(self, cx, cy, patch=None):
        """用 blit 绘制擦除预览（红色覆盖）和光标圆。
        patch: (y0, y1, x0, x1, new_circle) — 本次新增圆的脏区；
               None 表示全图重绘（加载 / _apply_stroke 后调用）。
        """
        scale = self._get_scale()
        r_img = max(1.0, self._brush_r / scale)
        sides = [
            (self._ovl_arr_b, self._ovl_b, self._cur_b,
             self._bg_b, self._cvs_b, self._fig_b, self._ax_b),
            (self._ovl_arr_s, self._ovl_s, self._cur_s,
             self._bg_s, self._cvs_s, self._fig_s, self._ax_s),
        ]
        for ovl_arr, ovl, cur, bg, cvs, fig, ax in sides:
            if ovl_arr is None or bg is None:
                continue
            if patch is not None:
                # 增量更新：只涂新圆区域，erase_mask 只增不减无需清零
                y0, y1, x0, x1, new_circle = patch
                tile = ovl_arr[y0:y1, x0:x1]
                tile[new_circle, 0] = 220
                tile[new_circle, 1] = 30
                tile[new_circle, 2] = 30
                tile[new_circle, 3] = 140
            else:
                # 全图重绘（加载图像 / _apply_stroke 后调用）
                # ovl_arr 是降采样的，需要把 erase_mask 下采样后再写入
                ovl_arr[:] = 0
                if self._erase_mask is not None and self._erase_mask.any():
                    ds = self._OVL_DS
                    mask_ds = self._erase_mask[::ds, ::ds]
                    oh, ow = ovl_arr.shape[:2]
                    mask_ds = mask_ds[:oh, :ow]
                    ovl_arr[mask_ds, 0] = 220
                    ovl_arr[mask_ds, 1] = 30
                    ovl_arr[mask_ds, 2] = 30
                    ovl_arr[mask_ds, 3] = 140
            ovl.set_data(ovl_arr)
            cur.set_center((cx, cy))
            cur.set_radius(r_img)
            cur.set_visible(True)
            cvs.restore_region(bg)
            ax.draw_artist(ovl)
            ax.draw_artist(cur)
            cvs.blit(fig.bbox)

    def _blit_cursors_only(self, cx, cy):
        """仅绘制光标圆（不绘制时的悬停反馈）。"""
        scale = self._get_scale()
        r_img = max(1.0, self._brush_r / scale)
        for cur, bg, cvs, fig, ax in [
            (self._cur_b, self._bg_b, self._cvs_b, self._fig_b, self._ax_b),
            (self._cur_s, self._bg_s, self._cvs_s, self._fig_s, self._ax_s),
        ]:
            if cur is None or bg is None:
                continue
            cur.set_center((cx, cy))
            cur.set_radius(r_img)
            cur.set_visible(True)
            cvs.restore_region(bg)
            ax.draw_artist(cur)
            cvs.blit(fig.bbox)

    # ------------------------------------------------------------------
    # 笔画应用（松开鼠标后立即执行）
    # ------------------------------------------------------------------
    def _apply_stroke(self):
        """将 erase_mask 应用到工作副本，更新底图，清除覆盖层，重建 blit 缓存。"""
        if self._erase_mask is None or not self._erase_mask.any():
            # 没有实际擦除：只重建缓存（清除覆盖层）
            self._rebuild_blit_cache()
            return
        self._bin_work[self._erase_mask]  = 0.0
        self._skel_work[self._erase_mask] = 0.0
        self._erase_mask[:] = False
        # 更新底图数据
        if self._base_b is not None:
            self._base_b.set_data(self._bin_work)
        if self._base_s is not None:
            self._base_s.set_data(self._skel_work)
        # 清除覆盖层
        if self._ovl_arr_b is not None:
            self._ovl_arr_b[:] = 0
        if self._ovl_arr_s is not None:
            self._ovl_arr_s[:] = 0
        # 全量重绘后重建 blit 缓存（底图已更新，需要重绘）
        self._cvs_b.draw()
        self._bg_b = self._cvs_b.copy_from_bbox(self._fig_b.bbox)
        self._cvs_s.draw()
        self._bg_s = self._cvs_s.copy_from_bbox(self._fig_s.bbox)
        self._undo_btn.setEnabled(True)
        self._status_lbl.setText(tr('er_status_erased'))

    def _rebuild_blit_cache(self):
        """全量重绘后重建 blit 缓存（无数据改变）。"""
        if self._ovl_arr_b is not None:
            self._ovl_arr_b[:] = 0
        if self._ovl_arr_s is not None:
            self._ovl_arr_s[:] = 0
        for cvs, fig, attr in [
            (self._cvs_b, self._fig_b, 'b'),
            (self._cvs_s, self._fig_s, 's'),
        ]:
            cvs.draw()
            if attr == 'b':
                self._bg_b = cvs.copy_from_bbox(fig.bbox)
            else:
                self._bg_s = cvs.copy_from_bbox(fig.bbox)

    # ------------------------------------------------------------------
    # 撤销
    # ------------------------------------------------------------------
    def _push_history(self):
        if self._bin_work is None:
            return
        self._history.append((self._bin_work.copy(), self._skel_work.copy()))
        if len(self._history) > self._max_history:
            self._history.pop(0)

    def _undo(self):
        if not self._history:
            return
        self._bin_work, self._skel_work = self._history.pop()
        if self._erase_mask is not None:
            self._erase_mask[:] = False
        # 更新底图
        if self._base_b is not None:
            self._base_b.set_data(self._bin_work)
        if self._base_s is not None:
            self._base_s.set_data(self._skel_work)
        self._cvs_b.draw()
        self._bg_b = self._cvs_b.copy_from_bbox(self._fig_b.bbox)
        self._cvs_s.draw()
        self._bg_s = self._cvs_s.copy_from_bbox(self._fig_s.bbox)
        self._undo_btn.setEnabled(bool(self._history))
        steps = len(self._history)
        stem = os.path.splitext(os.path.basename(self._bin_path))[0] if self._bin_path else ''
        remaining = f'，还可撤销 {steps} 步' if steps else ''
        self._log(f"已撤销上一步: {stem}{remaining}")
        self._status_lbl.setText(
            tr('er_status_ready') if steps == 0
            else f'已撤销（还可再撤销 {steps} 步）')

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------
    def _save(self):
        if self._bin_work is None or self._skel_work is None:
            return
        from PIL import Image as _PilImage
        try:
            def _pil_save(path, arr_float, dpi):
                uint8 = (np.clip(arr_float, 0, 1) * 255).astype(np.uint8)
                img = _PilImage.fromarray(uint8, mode='L')
                ext = os.path.splitext(path)[1].lower()
                from calibration import image_scale
                from PIL.PngImagePlugin import PngInfo
                _, source = image_scale(path)
                options = {'dpi':dpi} if dpi is not None else {}
                if ext == '.png':
                    info = PngInfo()
                    info.add_text('Scale_Source', source)
                    options['pnginfo'] = info
                if ext in ('.jpg', '.jpeg'):
                    img.save(path, 'JPEG', quality=95, **options)
                else:
                    img.save(path, **options)

            _pil_save(self._bin_path,  self._bin_work,  self._bin_dpi)
            _pil_save(self._skel_path, self._skel_work, self._skel_dpi)
            self._history.clear()
            self._undo_btn.setEnabled(False)
            stem = os.path.splitext(os.path.basename(self._bin_path))[0]
            self._status_lbl.setText(tr('er_status_saved', path=stem))
            self._log(f"已保存: {os.path.basename(self._bin_path)}"
                      f"  |  {os.path.basename(self._skel_path)}")
        except Exception as e:
            self._log(f"保存失败: {e}")
            QMessageBox.critical(self, tr('msg_error'), str(e))

    # ------------------------------------------------------------------
    # 笔刷
    # ------------------------------------------------------------------
    def _on_brush_changed(self, val):
        self._brush_r = val
        self._brush_px_lbl.setText(f'{val} px')

    # ------------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------------
    def _log(self, msg):
        self.log_message.emit(f"[擦除] {msg}")

    # ------------------------------------------------------------------
    # 语言切换
    # ------------------------------------------------------------------
    def retranslate(self):
        self._input_grp.setTitle(tr('er_input_group'))
        self._btn_bin.setText(tr('pp_browse'))
        self._btn_skel.setText(tr('pp_browse'))
        self._sel_lbl.setText(tr('er_select_sample'))
        self._refresh_btn.setText(tr('er_refresh_btn'))
        self._brush_lbl_w.setText(tr('er_brush_lbl'))
        self._undo_btn.setText(tr('er_undo_btn'))
        self._save_btn.setText(tr('er_save_btn'))
        if not self._er_binary_dir:
            self._lbl_bin.setText(tr('er_no_dir'))
        if not self._er_skel_dir:
            self._lbl_skel.setText(tr('er_no_dir'))


class AnalysisResultViewer(QWidget):
    """
    分析结果查看器（3面板）:
      左  — 二值化图
      中  — 骨架 + 拓扑散点（可缩放查看）
      右  — 该张图的量化指标数值

    sample_navigated(stem) 信号在点击 Prev/Next 导航时发射，
    供主窗口同步更新样本下拉框。

    show_pair()   : 分析开始前显示图像（正在分析提示）
    show_result() : 分析完成后更新拓扑标记 + 指标面板
    """
    sample_navigated = pyqtSignal(str)   # 导航切换时发射当前 stem

    # 右侧指标面板显示的指标（key: label）
    _METRIC_LABELS = [
        ('Topology_Status',       'Topology status'),
        ('Root_Model',            'Root model'),
        ('Scale_Source',          'Scale source'),
        ('Crown_Annotation',      'Crown source'),
        ('Stem_Repair_Status',    'Stem pore repair'),
        ('Stem_Repair_Holes',     'Filled stem pores'),
        ('Stem_Repair_Pixels',    'Inferred tissue (px)'),
        ('MF_Quality',            'MF fit quality'),
        ('DPI',                   'DPI'),
        ('Root_Length_px',        'Root Length (px)'),
        ('Projected_Path_Length_px', 'Projected Length (px)'),
        ('Num_Bases',             'Root bases'),
        ('Root_Length_cm',        'Root Length (cm)'),
        ('Root_Surface_Area_cm2', 'Surface Area (cm²)'),
        ('Avg_Root_Diameter_mm',  'Avg Diameter (mm)'),
        ('Root_Volume_cm3',       'Root Volume (cm³)'),
        ('Num_Tips',              'Tips'),
        ('Num_Forks',             'Forks'),
        ('Num_Crossings',         'Crossings'),
        ('Num_Reconstructed_Root_Paths', 'Traced root paths'),
        ('Num_Bundle_Separations','Bundle separations'),
        ('Num_Uncertain_Junctions','Uncertain junctions'),
        ('Cycle_Rank',            'Unresolved cycles'),
        ('Num_Components',        'Components'),
        ('Diameter_Measured_Length_Fraction','Measured width (%)'),
        ('Diameter_Unresolved_Length_Fraction','Unknown width (%)'),
        ('Path_Inferred_Length_Fraction','Inferred path (%)'),
        ('Avg_Branch_Angle_deg',  'Branch Angle (°)'),
        ('Tip_Density_per_cm',    'Tip Density (/cm)'),
        ('Branch_Density_per_cm', 'Branch Density (/cm)'),
        ('Avg_Link_Length_cm',    'Avg Link Length (cm)'),
        ('Fractal_Dimension',     'Fractal Dimension'),
        ('Fractal_Abundance',     'Fractal Abundance'),
        ('MF_D0_Capacity',        'MF D0 Capacity'),
        ('MF_D1_Information',     'MF D1 Information'),
        ('MF_D2_Correlation',     'MF D2 Correlation'),
        ('MF_Delta_alpha',        'MF Δα (width)'),
        ('MF_Delta_f',            'MF Δf (symmetry)'),
        ('Topological_Index',     'Topological Index'),
        ('TI_Altitude',           'TI Altitude'),
        ('TI_Magnitude',          'TI Magnitude'),
        ('Strahler_Max_Order',    'Strahler Max Order'),
        ('Strahler_Bifurcation_Ratio', 'Strahler Rb'),
        ('Strahler_Length_Ratio', 'Strahler Rl'),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.fig = Figure(figsize=(14, 7.5), dpi=90)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)

        # ── 可视化控制栏（单行，合并所有叠加选项）──────────────
        ctrl_bar = QWidget()
        ctrl_bar.setFixedHeight(32)
        ctrl_layout = QHBoxLayout(ctrl_bar)
        ctrl_layout.setContentsMargins(10, 2, 10, 2)
        ctrl_layout.setSpacing(4)

        # Tips
        self._chk_tips = QCheckBox()
        self._chk_tips.setChecked(True)
        self._lbl_tips = QLabel(tr('viz_tips'))
        self._lbl_tips.setStyleSheet("font-weight: bold;")
        ctrl_layout.addWidget(self._chk_tips)
        ctrl_layout.addWidget(self._lbl_tips)
        ctrl_layout.addSpacing(6)

        # Forks
        self._chk_forks = QCheckBox()
        self._chk_forks.setChecked(True)
        self._lbl_forks = QLabel(tr('viz_forks'))
        self._lbl_forks.setStyleSheet("font-weight: bold;")
        ctrl_layout.addWidget(self._chk_forks)
        ctrl_layout.addWidget(self._lbl_forks)
        ctrl_layout.addSpacing(6)

        # Crossings
        self._chk_cross = QCheckBox()
        self._chk_cross.setChecked(True)
        self._lbl_crossings = QLabel(tr('viz_crossings'))
        self._lbl_crossings.setStyleSheet("font-weight: bold;")
        ctrl_layout.addWidget(self._chk_cross)
        ctrl_layout.addWidget(self._lbl_crossings)
        ctrl_layout.addSpacing(10)

        # Strahler 级序
        self._chk_strahler = QCheckBox()
        self._chk_strahler.setChecked(False)
        self._lbl_strahler = QLabel(tr('viz_strahler'))
        self._lbl_strahler.setStyleSheet("font-weight: bold;")
        ctrl_layout.addWidget(self._chk_strahler)
        ctrl_layout.addWidget(self._lbl_strahler)
        ctrl_layout.addSpacing(6)

        # 分支角向量
        self._chk_angles = QCheckBox()
        self._chk_angles.setChecked(False)
        self._lbl_angles = QLabel(tr('viz_angles'))
        self._lbl_angles.setStyleSheet("font-weight: bold;")
        ctrl_layout.addWidget(self._chk_angles)
        ctrl_layout.addWidget(self._lbl_angles)
        ctrl_layout.addSpacing(6)

        # 根直径热力图
        self._chk_diameter = QCheckBox()
        self._chk_diameter.setChecked(False)
        self._lbl_diameter = QLabel(tr('viz_diameter'))
        self._lbl_diameter.setStyleSheet("font-weight: bold;")
        ctrl_layout.addWidget(self._chk_diameter)
        ctrl_layout.addWidget(self._lbl_diameter)
        ctrl_layout.addSpacing(6)

        # 盒计数格网
        self._chk_boxgrid = QCheckBox()
        self._chk_boxgrid.setChecked(False)
        self._lbl_boxgrid = QLabel(tr('viz_boxgrid'))
        self._lbl_boxgrid.setStyleSheet("font-weight: bold;")
        ctrl_layout.addWidget(self._chk_boxgrid)
        ctrl_layout.addWidget(self._lbl_boxgrid)

        ctrl_layout.addSpacing(14)
        self._lbl_marker_size = QLabel(tr('viz_marker_size'))
        ctrl_layout.addWidget(self._lbl_marker_size)
        self._marker_slider = QSlider(Qt.Horizontal)
        self._marker_slider.setRange(4, 100)
        self._marker_slider.setValue(20)
        self._marker_slider.setFixedWidth(90)
        self._marker_size_lbl = QLabel("20")
        self._marker_size_lbl.setMinimumWidth(24)
        ctrl_layout.addWidget(self._marker_slider)
        ctrl_layout.addWidget(self._marker_size_lbl)
        ctrl_layout.addStretch()

        # 连接信号
        self._chk_tips.toggled.connect(self._redraw_cached)
        self._chk_forks.toggled.connect(self._redraw_cached)
        self._chk_cross.toggled.connect(self._redraw_cached)
        self._chk_strahler.toggled.connect(self._redraw_cached)
        self._chk_angles.toggled.connect(self._redraw_cached)
        self._chk_diameter.toggled.connect(self._redraw_cached)
        self._chk_boxgrid.toggled.connect(self._redraw_cached)
        self._marker_slider.valueChanged.connect(self._on_marker_changed)

        layout.addWidget(ctrl_bar)
        layout.addWidget(self.canvas, 1)

        # ── 导航栏（左右切换样本） ─────────────────────────────
        nav_bar = QWidget()
        nav_bar.setFixedHeight(36)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(8, 2, 8, 2)
        nav_layout.setSpacing(6)

        self._btn_prev = QPushButton("◀  Prev")
        self._btn_prev.setMinimumWidth(80)
        self._btn_prev.setEnabled(False)
        self._btn_prev.clicked.connect(self._go_prev)

        self._nav_label = QLabel("—")
        self._nav_label.setAlignment(Qt.AlignCenter)
        font = self._nav_label.font()
        font.setBold(True)
        self._nav_label.setFont(font)

        self._btn_next = QPushButton("Next  ▶")
        self._btn_next.setMinimumWidth(80)
        self._btn_next.setEnabled(False)
        self._btn_next.clicked.connect(self._go_next)

        nav_layout.addStretch()
        nav_layout.addWidget(self._btn_prev)
        nav_layout.addWidget(self._nav_label)
        nav_layout.addWidget(self._btn_next)
        nav_layout.addStretch()
        layout.addWidget(nav_bar)

        # 样本缓存
        self._samples = []   # list of (binary_path, skel_path, result_dict)
        self._cur = 0
        # 渲染缓存（避免切换 checkbox 时重复读图）
        self._render_cache = None
        # DPI（由 MainWindow 在启动分析时设置）
        self._dpi = 300

        self._init_axes()

    def _on_marker_changed(self, val):
        self._marker_size_lbl.setText(str(val))
        self._redraw_cached()

    def _redraw_cached(self):
        """用缓存数据重绘（checkbox / 滑块变化时调用，不重新读文件）。"""
        if self._render_cache is None:
            return
        self._draw_result(**self._render_cache)

    def _init_axes(self):
        self.fig.clear()
        # 左2/5 = binary, 中2/5 = topology, 右1/5 = metrics
        gs = self.fig.add_gridspec(1, 3, width_ratios=[2, 2, 1.2], wspace=0.08)
        self._ax_bin  = self.fig.add_subplot(gs[0])
        self._ax_topo = self.fig.add_subplot(gs[1])
        self._ax_met  = self.fig.add_subplot(gs[2])
        self._ax_bin.set_title('Binary', fontsize=9, pad=4)
        self._ax_topo.set_title('Skeleton + Topology', fontsize=9, pad=4)
        self._ax_met.set_title('Metrics', fontsize=9, pad=4)
        for ax in (self._ax_bin, self._ax_topo, self._ax_met):
            ax.axis('off')
        self.fig.tight_layout(pad=1.2)
        self.canvas.draw()

    # ------------------------------------------------------------------
    def show_pair(self, binary_path, skeleton_path):
        """分析开始前：仅加载图像，中面板显示"Analyzing..."提示"""
        try:
            from skimage import io as skio
            img_bin  = skio.imread(binary_path,  as_gray=True)
            img_skel = skio.imread(skeleton_path, as_gray=True)
            fname = os.path.basename(binary_path)

            self.fig.clear()
            gs = self.fig.add_gridspec(1, 3, width_ratios=[2, 2, 1.2], wspace=0.08)
            ax_b = self.fig.add_subplot(gs[0])
            ax_t = self.fig.add_subplot(gs[1])
            ax_m = self.fig.add_subplot(gs[2])

            ax_b.imshow(img_bin,  cmap='gray'); ax_b.axis('off')
            ax_b.set_title(f'Binary  |  {fname}', fontsize=8, pad=4)

            ax_t.imshow(img_skel, cmap='gray'); ax_t.axis('off')
            ax_t.set_title('Skeleton  |  Analyzing...', fontsize=8, pad=4)
            ax_t.text(0.5, 0.5, 'Analyzing…', ha='center', va='center',
                      transform=ax_t.transAxes, fontsize=13,
                      color='steelblue', fontweight='bold', alpha=0.7)

            ax_m.axis('off')
            ax_m.set_title('Metrics', fontsize=9, pad=4)
            ax_m.text(0.5, 0.5, 'Pending...', ha='center', va='center',
                      transform=ax_m.transAxes, color='gray', fontsize=9)

            self.fig.tight_layout(pad=1.2)
            self.canvas.draw()
        except Exception:
            self._init_axes()
            self.canvas.draw()

    # ------------------------------------------------------------------
    def show_result(self, binary_path, skeleton_path, result: dict):
        """分析完成后：加载图像并绘制拓扑散点。

        坐标直接来自 analyze_root_image 的 result dict（_tip_coords 等），
        不再独立重复计算 skan_analyze，确保散点数量与数据表完全一致。
        """
        try:
            from skimage import io as skio
            img_bin  = skio.imread(binary_path,  as_gray=True)
            img_skel = skio.imread(skeleton_path, as_gray=True)
            fname = os.path.basename(binary_path)

            def _to_xy(coords):
                if not coords:
                    return np.array([]), np.array([])
                arr = np.array(coords)
                return arr[:, 1], arr[:, 0]   # (xs, ys)

            # 直接用分析引擎传来的坐标（与 CSV 数值同源，绝对一致）
            tip_pts   = _to_xy(result.get('_tip_coords', []))
            fork_pts  = _to_xy(result.get('_fork_coords', []))
            cross_pts = _to_xy(result.get('_crossing_coords', []))

            # 缓存，供 checkbox / 滑块变化时快速重绘
            self._render_cache = dict(
                img_bin=img_bin, img_skel=img_skel, fname=fname,
                result=result,
                tip_pts=tip_pts, fork_pts=fork_pts, cross_pts=cross_pts,
                angle_viz=result.get('_angle_viz', []),
                strahler_edge_viz=result.get('_strahler_edge_viz', []),
                binary_arr=result.get('_binary_img', None),
            )
            self._draw_result(**self._render_cache)

        except Exception as e:
            self._init_axes()
            self._ax_bin.text(0.5, 0.5, f'Display error:\n{e}',
                              ha='center', va='center',
                              transform=self._ax_bin.transAxes,
                              color='red', fontsize=8)
            self.canvas.draw()

    def _draw_result(self, img_bin, img_skel, fname, result,
                     tip_pts, fork_pts, cross_pts,
                     angle_viz=None, strahler_edge_viz=None, binary_arr=None):
        """用已有数据绘制三栏视图（checkbox / 滑块变化时直接调用）。"""
        marker_s = self._marker_slider.value()

        self.fig.clear()
        gs = self.fig.add_gridspec(1, 3, width_ratios=[2, 2, 1.2], wspace=0.08)
        ax_b = self.fig.add_subplot(gs[0])
        ax_t = self.fig.add_subplot(gs[1])
        ax_m = self.fig.add_subplot(gs[2])

        # ── 左：二值化图 ──────────────────────────────────────
        ax_b.imshow(img_bin, cmap='gray')
        ax_b.set_title(f'Binary  |  {fname}', fontsize=8, pad=4)
        ax_b.axis('off')

        # ── 中：骨架 + 可选拓扑散点（聚类质心）──────────────
        ax_t.imshow(img_skel, cmap='gray', alpha=0.85)
        ax_t.axis('off')

        topo_ok = False
        if tip_pts is not None:
            def _scatter(pts, hex_color, key, label):
                """pts = (xs_array, ys_array)，均为质心坐标。"""
                if pts is None:
                    return
                xs, ys = pts
                if len(xs) == 0:
                    return
                n = result.get(key, len(xs))
                ax_t.scatter(xs, ys, c=hex_color, s=marker_s,
                             linewidths=0.3, edgecolors='white',
                             alpha=0.95, label=f'{label}: {n}', zorder=3)

            bases = np.asarray(result.get('_base_coords', []))
            if bases.size:
                _scatter((bases[:,1], bases[:,0]), '#ffcc00', 'Num_Bases', 'Base')
            if self._chk_tips.isChecked():
                _scatter(tip_pts,  '#00cccc', 'Num_Tips',      'Tips')
            if self._chk_forks.isChecked():
                _scatter(fork_pts, '#ff4444', 'Num_Forks',     'Forks')
            if self._chk_cross.isChecked():
                _scatter(cross_pts,'#1e90ff', 'Num_Crossings', 'Crossings')

            handles, labels = ax_t.get_legend_handles_labels()
            if handles:
                ax_t.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5,-0.025),
                            ncol=2, fontsize=7, framealpha=0.7, markerscale=1.5)
            topo_ok = True

        # ── Strahler 级序染色（在骨架图上按级序画线段）──────────
        _STRAHLER_COLORS = {
            1: '#4A90D9', 2: '#27AE60', 3: '#F5A623',
            4: '#E74C3C', 5: '#8E44AD', 6: '#2C3E50', 7: '#00CED1',
        }
        if self._chk_strahler.isChecked() and strahler_edge_viz:
            # coords[:,0]=row(y), coords[:,1]=col(x)，折线绘制真实弯曲路径
            for coords, order in strahler_edge_viz:
                color = _STRAHLER_COLORS.get(order, '#888888')
                ax_t.plot(coords[:, 1], coords[:, 0], '-', color=color,
                          linewidth=1.2, alpha=0.85, zorder=2)
            # 图例
            from matplotlib.lines import Line2D
            orders_present = sorted({e[1] for e in strahler_edge_viz})
            legend_lines = [Line2D([0], [0], color=_STRAHLER_COLORS.get(o, '#888'),
                                   linewidth=2, label=f'Order {o}')
                            for o in orders_present]
            ax_t.legend(handles=legend_lines, loc='lower right',
                        fontsize=6, framealpha=0.7, ncol=2)

        # ── 分支角方向向量（在骨架图分叉处画方向箭头）──────────
        if self._chk_angles.isChecked() and angle_viz:
            arrow_len = max(15, marker_s // 2)
            sample_step = max(1, len(angle_viz) // 400)  # 最多显示400个
            for item in angle_viz[::sample_step]:
                r, c = item['rc']
                for d in item['dirs']:
                    dr, dc = d[0], d[1]
                    ax_t.annotate('',
                        xy=(c + dc * arrow_len, r + dr * arrow_len),
                        xytext=(c, r),
                        arrowprops=dict(arrowstyle='->', color='#FFD700',
                                        lw=0.9, alpha=0.75),
                        zorder=4)

        # ── 根直径热力图（在二值图上叠加距离变换色图）──────────
        if self._chk_diameter.isChecked() and binary_arr is not None:
            try:
                from scipy import ndimage as _ndi
                dist = _ndi.distance_transform_edt(binary_arr)
                ax_b.imshow(dist, cmap='hot', alpha=0.55,
                            vmin=0, vmax=float(dist.max()) or 1)
            except Exception:
                pass

        # ── 盒计数格网（在二值图上叠加 32px 网格线）────────────
        if self._chk_boxgrid.isChecked():
            h, w = img_bin.shape
            box_px = 32
            for r_line in range(0, h, box_px):
                ax_b.axhline(r_line, color='#00ccff', linewidth=0.25, alpha=0.5)
            for c_line in range(0, w, box_px):
                ax_b.axvline(c_line, color='#00ccff', linewidth=0.25, alpha=0.5)

        shown = [n for chk, n in [
            (self._chk_tips,     'Tips'),
            (self._chk_forks,    'Forks'),
            (self._chk_cross,    'Crossings'),
            (self._chk_strahler, 'Strahler'),
            (self._chk_angles,   'Angles'),
        ] if chk.isChecked()]
        title_topo = ('Skeleton + Topology  [' + '  '.join(shown) + ']'
                      if topo_ok and shown else 'Skeleton')
        ax_t.set_title(title_topo, fontsize=8, pad=4)

        # ── 右：量化指标数值 ──────────────────────────────────
        ax_m.axis('off')
        ax_m.set_title('Metrics', fontsize=9, pad=4)

        lines = []
        for key, label in self._METRIC_LABELS:
            if result.get('Scale_Source') in ('unknown','uncalibrated_clipboard'):
                pixel_fields = {
                    'Root_Surface_Area_cm2':('Root_Surface_Area_px2','Surface Area (px2)'),
                    'Avg_Root_Diameter_mm':('Avg_Root_Diameter_px','Avg Diameter (px)'),
                    'Root_Volume_cm3':('Root_Volume_px3','Root Volume (px3)'),
                    'Tip_Density_per_cm':('Tip_Density_per_px','Tip Density (/px)'),
                    'Branch_Density_per_cm':('Branch_Density_per_px','Branch Density (/px)'),
                    'Avg_Link_Length_cm':('Avg_Link_Length_px','Avg Link Length (px)'),
                }
                if key in ('Root_Length_cm','DPI'):
                    continue
                key,label = pixel_fields.get(key,(key,label))
            val = result.get(key)
            if val is None:
                continue
            try:
                fval = float(val)
                if key in ('Diameter_Measured_Length_Fraction',
                           'Diameter_Unresolved_Length_Fraction','Path_Inferred_Length_Fraction'):
                    fval *= 100
                if not np.isfinite(fval):
                    vstr = 'N/A'
                elif key.startswith('Num_') or key in ('Cycle_Rank',
                            'Strahler_Max_Order', 'TI_Altitude', 'TI_Magnitude'):
                    vstr = f'{int(round(fval))}'
                else:
                    vstr = f'{fval:.3f}'
            except (TypeError, ValueError):
                vstr = str(val)
                vstr = {'finite_scale_unstable':'Check scales', 'fit_consistent':'Consistent',
                        'manual_rectangle':'Manual crown', 'inferred_local_crown':'Inferred crown',
                        'shared_crown':'Shared crown', 'general':'General',
                        'model_assumed':'Model assumed', 'explicit_shared_crown_model':'Shared crown model',
                        'invalid_crown':'Invalid crown', 'unresolved':'Needs review'}.get(vstr,vstr)
            lines.append(f'{label:<25s}{vstr:>10s}')

        ax_m.text(0.02, 0.98, '\n'.join(lines),
                  transform=ax_m.transAxes,
                  va='top', ha='left',
                  fontsize=min(7, self.fig.get_figheight()*72*.85/max(len(lines)*1.2,1)), family='monospace',
                  bbox=dict(boxstyle='round,pad=0.4',
                            facecolor='#f0f4ff', alpha=0.85,
                            edgecolor='#aac'))

        self.fig.tight_layout(pad=1.2)
        self.canvas.draw()

    # ------------------------------------------------------------------
    # 样本导航接口
    # ------------------------------------------------------------------
    def clear_samples(self):
        """新一轮分析开始前清空缓存"""
        self._samples = []
        self._cur = 0
        self._render_cache = None
        self._update_nav()
        self._init_axes()

    def add_sample(self, binary_path, skeleton_path, result: dict):
        """每完成一个样本就调用：缓存并跳到最新"""
        self._samples.append((binary_path, skeleton_path, result))
        self._cur = len(self._samples) - 1
        self._show_current()

    def _show_current(self):
        if not self._samples:
            return
        bp, sp, res = self._samples[self._cur]
        self.show_result(bp, sp, res)
        self._update_nav()

    def show_by_stem(self, stem: str) -> bool:
        """用 stem（文件名无后缀）在已缓存结果中查找并显示，返回是否找到。
        批量分析完成后，下拉切换样本时调用此方法直接显示结果（含散点）。
        """
        for i, (bp, sp, res) in enumerate(self._samples):
            cached_stem = os.path.splitext(os.path.basename(bp))[0]
            if cached_stem == stem:
                self._cur = i
                self._show_current()
                return True
        return False

    def _update_nav(self):
        n = len(self._samples)
        if n == 0:
            self._nav_label.setText("—")
        else:
            sid = self._samples[self._cur][2].get('Sample_ID', str(self._cur + 1))
            self._nav_label.setText(f"  {self._cur + 1} / {n}   |   {sid}  ")
        self._btn_prev.setEnabled(n > 1 and self._cur > 0)
        self._btn_next.setEnabled(n > 1 and self._cur < n - 1)

    def _go_prev(self):
        if self._cur > 0:
            self._cur -= 1
            self._show_current()
            self._emit_navigated()

    def _go_next(self):
        if self._cur < len(self._samples) - 1:
            self._cur += 1
            self._show_current()
            self._emit_navigated()

    def _emit_navigated(self):
        """发射当前样本 stem，供主窗口同步样本下拉框。"""
        if self._samples:
            bp = self._samples[self._cur][0]
            stem = os.path.splitext(os.path.basename(bp))[0]
            self.sample_navigated.emit(stem)

    def retranslate(self):
        """切换语言时更新控制栏所有标签文字。"""
        self._lbl_tips.setText(tr('viz_tips'))
        self._lbl_forks.setText(tr('viz_forks'))
        self._lbl_crossings.setText(tr('viz_crossings'))
        self._lbl_strahler.setText(tr('viz_strahler'))
        self._lbl_angles.setText(tr('viz_angles'))
        self._lbl_diameter.setText(tr('viz_diameter'))
        self._lbl_boxgrid.setText(tr('viz_boxgrid'))
        self._lbl_marker_size.setText(tr('viz_marker_size'))


# ============================================================================
# 数据可视化面板
# ============================================================================

class ChartPanel(QWidget):
    """数据图表面板"""
    log_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # 控制栏
        ctrl = QHBoxLayout()
        self._metric_lbl = QLabel(tr('chart_metric_lbl'))
        ctrl.addWidget(self._metric_lbl)
        self.metric_combo = QComboBox()
        self.metric_combo.setMinimumWidth(200)
        ctrl.addWidget(self.metric_combo)

        self._type_lbl = QLabel(tr('chart_type_lbl'))
        ctrl.addWidget(self._type_lbl)
        self.chart_combo = QComboBox()
        self.chart_combo.addItems(tr('chart_types'))
        ctrl.addWidget(self.chart_combo)

        self._group_lbl = QLabel(tr('chart_group_lbl'))
        ctrl.addWidget(self._group_lbl)
        self.group_combo = QComboBox()
        self.group_combo.addItems(tr('chart_groups'))
        ctrl.addWidget(self.group_combo)

        self.plot_btn = QPushButton(tr('chart_plot_btn'))
        self.plot_btn.setMinimumWidth(78)
        self.plot_btn.clicked.connect(self.plot_chart)
        ctrl.addWidget(self.plot_btn)

        self.save_btn = QPushButton(tr('chart_save_btn'))
        self.save_btn.setMinimumWidth(90)
        self.save_btn.clicked.connect(self.save_chart)
        ctrl.addWidget(self.save_btn)

        ctrl.addStretch()
        layout.addLayout(ctrl)

        # 图表区域
        self.fig = Figure(figsize=(8, 5), dpi=100)
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.df = None

    def set_data(self, df):
        """设置数据，规范化元信息列后更新指标下拉框"""
        # 深复制，避免修改外部 df
        self.df = df.copy()

        # 将 Year/Variety/Treatment 统一为干净字符串
        # （从 CSV 加载时 Year 可能是 int64；分析结果中可能含 NaN/''/0）
        for col in ('Year', 'Variety', 'Treatment', 'Replicate'):
            if col in self.df.columns:
                self.df[col] = (
                    self.df[col]
                    .fillna('')
                    .astype(str)
                    .str.strip()
                    .replace({'nan': '', '0': ''})
                )

        self.metric_combo.clear()
        # 只添加数值列，排除元信息列
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        skip = {'Sample_ID', 'Year', 'Replicate'}
        numeric_cols = [c for c in numeric_cols if c not in skip]
        self.metric_combo.addItems(numeric_cols)

    # 科学配色方案（色盲友好，对比度高）
    _PALETTE = ['#4C72B0', '#DD8452', '#55A868', '#C44E52', '#8172B3',
                '#937860', '#DA8BC3', '#8C8C8C', '#CCB974', '#64B5CD',
                '#E07B39', '#7BC8F6', '#76B041', '#D64E91', '#A0522D']

    def _get_colors(self, n):
        p = self._PALETTE
        return [p[i % len(p)] for i in range(n)]

    def plot_chart(self):
        metric = self.metric_combo.currentText()
        if not metric or self.df is None:
            return
        group_idx = self.group_combo.currentIndex()
        GROUP_COL_MAP = {0: 'Treatment', 1: 'Variety', 2: 'Year'}
        chart_type = self.chart_combo.currentIndex()
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        try:
            if metric not in self.df.columns:
                ax.text(0.5, 0.5, tr('chart_col_not_found', col=metric),
                        ha='center', va='center', transform=ax.transAxes)
                self.canvas.draw()
                return

            def _draw_groups(gnames, gdata, xlabel):
                pairs = [(n, d) for n, d in zip(gnames, gdata) if len(d) > 0]
                if not pairs:
                    ax.text(0.5, 0.5, tr('chart_no_data'),
                            ha='center', va='center', transform=ax.transAxes)
                    return
                ns, ds = zip(*pairs)
                colors = self._get_colors(len(ns))
                rot = 45 if max(len(str(n)) for n in ns) > 6 or len(ns) > 6 else 0
                ha_a = 'right' if rot else 'center'
                if chart_type == 0:
                    bp = ax.boxplot(ds, labels=ns, patch_artist=True,
                                    widths=0.6, medianprops={'color': '#333', 'linewidth': 1.5})
                    for patch, color in zip(bp['boxes'], colors):
                        patch.set_facecolor(color); patch.set_alpha(0.75)
                    ax.set_xticklabels(ns, rotation=rot, ha=ha_a)
                    ax.set_xlabel(xlabel)
                elif chart_type == 1:
                    means = [float(np.mean(d)) for d in ds]
                    stds  = [float(np.std(d))  for d in ds]
                    x = list(range(len(ns)))
                    ax.bar(x, means, yerr=stds, capsize=4, edgecolor='#333',
                           linewidth=0.8, alpha=0.85, color=colors, width=0.65)
                    ax.set_xticks(x); ax.set_xticklabels(ns, rotation=rot, ha=ha_a)
                    ax.set_xlabel(xlabel)
                elif chart_type == 2:
                    for i, (name, d) in enumerate(zip(ns, ds)):
                        jitter = np.random.normal(0, 0.08, len(d))
                        ax.scatter(i + jitter, d, alpha=0.7, label=name, s=35,
                                   color=colors[i], edgecolors='white', linewidths=0.4, zorder=3)
                    ax.set_xticks(range(len(ns)))
                    ax.set_xticklabels(ns, rotation=rot, ha=ha_a)
                    ax.legend(fontsize=8, loc='best', framealpha=0.8)
                    ax.set_xlabel(xlabel)
                elif chart_type == 3:
                    parts = ax.violinplot(ds, showmeans=True, showmedians=True)
                    for i, pc in enumerate(parts.get('bodies', [])):
                        pc.set_facecolor(colors[i % len(colors)]); pc.set_alpha(0.7)
                    ax.set_xticks(range(1, len(ns) + 1))
                    ax.set_xticklabels(ns, rotation=rot, ha=ha_a)
                    ax.set_xlabel(xlabel)
                elif chart_type == 4:
                    for i, (name, d) in enumerate(zip(ns, ds)):
                        ax.hist(d, bins='auto', alpha=0.6, label=name,
                                edgecolor='#333', linewidth=0.6, color=colors[i])
                    ax.legend(fontsize=8, loc='best', framealpha=0.8)
                    ax.set_xlabel(metric); ax.set_ylabel(tr('chart_frequency'))
                ax.grid(axis='y', alpha=0.3, linestyle='--'); ax.set_axisbelow(True)

            if group_idx == 4:
                data = self.df[metric].dropna().values
                c0 = self._PALETTE[0]
                if chart_type == 0:
                    bp = ax.boxplot(data, labels=[metric], patch_artist=True)
                    bp['boxes'][0].set_facecolor(c0); bp['boxes'][0].set_alpha(0.75)
                elif chart_type == 1:
                    cs = self._get_colors(len(data))
                    ax.bar(range(len(data)), data, color=cs, alpha=0.85,
                           edgecolor='#333', linewidth=0.5)
                    ax.set_xlabel(tr('chart_sample'))
                elif chart_type == 2:
                    ax.scatter(range(len(data)), data, alpha=0.7, color=c0,
                               edgecolors='white', linewidths=0.4)
                    ax.set_xlabel(tr('chart_sample_idx'))
                elif chart_type == 3:
                    parts = ax.violinplot(data, showmeans=True, showmedians=True)
                    for pc in parts.get('bodies', []):
                        pc.set_facecolor(c0); pc.set_alpha(0.7)
                elif chart_type == 4:
                    ax.hist(data, bins='auto', edgecolor='#333', alpha=0.75,
                            color=c0, linewidth=0.6)
                    ax.set_xlabel(metric); ax.set_ylabel(tr('chart_frequency'))
                ax.grid(axis='y', alpha=0.3, linestyle='--'); ax.set_axisbelow(True)
            elif group_idx == 3:
                missing = [c for c in ('Variety', 'Treatment', 'Year')
                           if c not in self.df.columns]
                if missing:
                    ax.text(0.5, 0.5, tr('chart_missing_cols', cols=', '.join(missing)),
                            ha='center', va='center', transform=ax.transAxes)
                else:
                    plot_df = self.df[[metric, 'Variety', 'Treatment', 'Year']].copy()
                    plot_df = plot_df[
                        (plot_df['Variety'].str.len() > 0) |
                        (plot_df['Treatment'].str.len() > 0) |
                        (plot_df['Year'].str.len() > 0)
                    ].copy()
                    plot_df['_grp'] = (
                        plot_df['Variety'].where(plot_df['Variety'] != '', 'N/A')
                        + '-' + plot_df['Treatment'].where(plot_df['Treatment'] != '', 'N/A')
                        + '\n(' + plot_df['Year'].where(plot_df['Year'] != '', '?') + ')')
                    grp = plot_df.groupby('_grp')[metric]
                    gnames = sorted(grp.groups.keys())
                    gdata  = [grp.get_group(g).dropna().values for g in gnames]
                    _draw_groups(gnames, gdata, tr('chart_multi_xlabel'))
            else:
                col = GROUP_COL_MAP.get(group_idx, '')
                if col not in self.df.columns:
                    ax.text(0.5, 0.5, tr('chart_col_not_found', col=col),
                            ha='center', va='center', transform=ax.transAxes)
                else:
                    col_series = self.df[col]
                    valid_mask = col_series.str.len() > 0 if col_series.dtype == object else col_series.notna()
                    plot_df = self.df[valid_mask].copy()
                    if plot_df.empty:
                        ax.text(0.5, 0.5, tr('chart_no_valid_data', col=col),
                                ha='center', va='center', transform=ax.transAxes)
                    else:
                        grp = plot_df.groupby(col)[metric]
                        gnames = sorted([str(k) for k in grp.groups.keys()])
                        gdata  = [grp.get_group(
                                      next(k for k in grp.groups if str(k) == gn)
                                  ).dropna().values for gn in gnames]
                        _draw_groups(gnames, gdata, col)

            ax.set_ylabel(metric)
            group_display = self.group_combo.currentText()
            if group_idx == 4:
                ax.set_title(tr('chart_title_nogroup', metric=metric), fontsize=10)
            else:
                ax.set_title(tr('chart_title_grouped', metric=metric, group=group_display), fontsize=10)
            self.fig.tight_layout()
        except Exception as e:
            ax.clear()
            ax.text(0.5, 0.5, tr('chart_plot_error', err=str(e)),
                    ha='center', va='center', transform=ax.transAxes, fontsize=9, color='red')
            self.canvas.draw()
            return

        self.canvas.draw()

        # ── 写操作日志：说明图表类型、统计方法、图元含义 ─────────────────
        _type_keys = ['chart_log_boxplot', 'chart_log_bar', 'chart_log_scatter',
                      'chart_log_violin', 'chart_log_hist']
        type_desc = tr(_type_keys[chart_type])
        group_display = self.group_combo.currentText()
        self.log_message.emit(
            tr('chart_log_plotted',
               metric=metric,
               ctype=self.chart_combo.currentText(),
               group=group_display)
        )
        self.log_message.emit(f"  {type_desc}")


    def save_chart(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr('dlg_save_chart'), "chart.png",
            "PNG (*.png);;SVG (*.svg);;PDF (*.pdf);;TIFF (*.tiff)")
        if path:
            self.fig.savefig(path, dpi=300, bbox_inches='tight')
            QMessageBox.information(self, tr('msg_save_ok'), tr('dlg_save_chart_ok', path=path))


# ============================================================================
# 关于对话框
# ============================================================================

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于本软件")
        self.setFixedSize(560, 470)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(0)

        # ── matplotlib 封面图 ──────────────────────────────────────────
        fig = Figure(figsize=(5.6, 3.3), dpi=100)
        fig.patch.set_facecolor('#1a3a5c')
        canvas = FigureCanvas(fig)
        canvas.setFixedHeight(330)
        layout.addWidget(canvas)

        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 5.7)
        ax.axis('off')
        ax.set_facecolor('#1a3a5c')

        # 字体属性：优先 CJK，退回 DejaVu Sans（保证不显示方块）
        _fp_cjk  = {'fontfamily': _CJK_FONT} if _CJK_FONT else {}

        # --- 背景装饰：模拟根系网络 ---
        import matplotlib.patheffects as pe
        rng = np.random.default_rng(42)
        for _ in range(60):
            x0 = rng.uniform(0, 10)
            y0 = rng.uniform(0, 5.7)
            length = rng.uniform(0.3, 1.4)
            angle = rng.uniform(0, 2 * np.pi)
            x1 = x0 + length * np.cos(angle)
            y1 = y0 + length * np.sin(angle)
            alpha = rng.uniform(0.08, 0.22)
            lw = rng.uniform(0.4, 1.2)
            ax.plot([x0, x1], [y0, y1], color='#4a9fd4', alpha=alpha, lw=lw)

        # 顶部绿色色带
        ax.axhspan(5.0, 5.7, color='#2e7d32', alpha=0.85)

        # ── 机构 Logo（xjn.png）插入顶部色带左侧 ─────────────────────
        _logo_path = _resource_path('assets/xjn.png')
        if os.path.exists(_logo_path):
            try:
                from matplotlib.offsetbox import AnnotationBbox, OffsetImage
                _logo_arr = plt.imread(_logo_path)
                _oi = OffsetImage(_logo_arr, zoom=0.18)
                _oi.image.axes = ax
                _ab = AnnotationBbox(
                    _oi, (1.35, 5.35),
                    xycoords='data', frameon=False,
                    box_alignment=(0.5, 0.5),
                    pad=0)
                ax.add_artist(_ab)
            except Exception:
                pass

        ax.text(6.2, 5.35,
                'Xinjiang Academy of Agricultural Reclamation Sciences',
                ha='center', va='center', fontsize=7.5,
                color='#c8e6c9', fontweight='bold')

        # 主标题
        main_title = '根系构型参数量化分析系统' if _CJK_FONT else \
                     'Root Architecture\nQuantification System'
        ax.text(5, 3.85, main_title,
                ha='center', va='center', fontsize=17 if _CJK_FONT else 14,
                color='white', fontweight='bold',
                path_effects=[pe.withStroke(linewidth=3, foreground='#0d2137')],
                **_fp_cjk)

        # 副标题（英文）
        ax.text(5, 3.05,
                'Root Architecture Quantification System',
                ha='center', va='center', fontsize=9.5,
                color='#90caf9', style='italic')

        # 分隔线
        ax.plot([1.0, 9.0], [2.62, 2.62], color='#4a9fd4', lw=0.8, alpha=0.6)

        # 版权信息
        copyright_cn = '版权所有  \u00a9  王国栋（新疆农垦科学院）' if _CJK_FONT else \
                       'Copyright \u00a9  Wang Guodong (XJAARS)'
        ax.text(5, 2.18, copyright_cn,
                ha='center', va='center', fontsize=8.5,
                color='#bbdefb', fontweight='bold', **_fp_cjk)

        # 开发者信息（中英双行，中文部分依赖 CJK 字体）
        dev1_text = '作者：唐清芸\n石河子大学农学院、新疆农垦科学院' if _CJK_FONT else 'Author: Tang Qingyun\nCollege of Agriculture, Shihezi University; XJAARS'
        dev2_text = '软件版权人：王国栋\n新疆农垦科学院' if _CJK_FONT else 'Copyright: Wang Guodong\nXJAARS'
        ax.text(2.6, 1.55, dev1_text,
                ha='center', va='center', fontsize=7,
                color='#e3f2fd', linespacing=1.6, **_fp_cjk)
        ax.text(7.4, 1.55, dev2_text,
                ha='center', va='center', fontsize=7,
                color='#e3f2fd', linespacing=1.6, **_fp_cjk)

        # 竖线分隔两位开发者
        ax.plot([5, 5], [1.05, 2.02], color='#4a9fd4', lw=0.7, alpha=0.5)

        # 版本号
        ax.text(5, 0.55,
                f'Version {APP_VERSION}    |    2026',
                ha='center', va='center', fontsize=8,
                color='#78909c')

        # 底部装饰带
        ax.axhspan(0, 0.08, color='#2e7d32', alpha=0.5)

        fig.tight_layout(pad=0)
        canvas.draw()

        # ── 软件简介信息行 ─────────────────────────────────────────────
        from PyQt5.QtWidgets import QLabel as _QLabel
        info_lbl = _QLabel(
            '<span style="color:#555; font-size:11px;">'
            '基于图像的根系构型参数全流程自动化量化分析系统 &nbsp;|&nbsp; '
            f'v{APP_VERSION} &nbsp;|&nbsp; 新疆农垦科学院'
            '</span>'
        )
        info_lbl.setAlignment(Qt.AlignCenter)
        info_lbl.setContentsMargins(0, 6, 0, 2)
        layout.addWidget(info_lbl)

        # ── 关闭按钮 ──────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 2, 16, 0)
        btn_row.addStretch()
        close_btn = QPushButton(tr('about_close'))
        close_btn.setMinimumSize(100, 32)
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


# ============================================================================
# 主窗口
# ============================================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._lang = 'zh'
        self._theme = 'light'
        self._tr_refs = []  # list of (callable, key)
        self._tr_form_refs = []  # list of (QLabel, key) for FormLayout labels

        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        self.df = None
        self.csv_path = None
        self.worker = None

        self._init_menubar()
        self._init_ui()
        self._init_statusbar()
        self.setWindowTitle(tr('win_title'))
        # 窗口图标
        _ico_path = _resource_path('assets/icon.ico')
        if os.path.exists(_ico_path):
            self.setWindowIcon(QIcon(_ico_path))

    # ----------------------------------------------------------------
    # i18n helpers
    # ----------------------------------------------------------------
    def _t(self, widget, key, setter='setText'):
        """Register widget for language update, return widget."""
        self._tr_refs.append((getattr(widget, setter), key))
        return widget

    def set_language(self, lang):
        """Switch UI language."""
        _LANG[0] = lang
        self._lang = lang
        # Rebuild menubar
        self.menuBar().clear()
        self._init_menubar()
        # Update all registered widgets
        self.retranslate_ui()

    def retranslate_ui(self):
        """Apply current language to all registered widgets."""
        self.setWindowTitle(tr('win_title'))
        for setter, key in self._tr_refs:
            setter(tr(key))
        # Tabs（5个功能标签页；日志已移至底部固定面板）
        tab_keys = ['tab_preprocess', 'tab_erase', 'tab_analysis', 'tab_data', 'tab_chart']
        for i, k in enumerate(tab_keys):
            self.main_tabs.setTabText(i, tr(k))
        # 日志面板标题
        if hasattr(self, '_log_title_lbl'):
            self._log_title_lbl.setText(tr('log_panel_title'))
        # ChartPanel
        self.chart_panel.retranslate()
        # EraseTab
        if hasattr(self, 'erase_tab'):
            self.erase_tab.retranslate()
        # AnalysisResultViewer 控制栏标签
        if hasattr(self, 'an_viewer'):
            self.an_viewer.retranslate()
        # Status bar
        self.statusbar.showMessage(tr('status_ready'))

    def apply_theme(self, mode):
        """Apply 'light' or 'dark' theme and refresh menubar checkmarks."""
        self._theme = mode
        app = QApplication.instance()
        app.setStyleSheet(DARK_QSS if mode == 'dark' else LIGHT_QSS)
        # 重建菜单栏：确保主题勾选状态立即同步（与语言切换保持一致）
        self.menuBar().clear()
        self._init_menubar()

    # ----------------------------------------------------------------
    # 菜单栏
    # ----------------------------------------------------------------
    def _init_menubar(self):
        menubar = self.menuBar()

        # == File ==
        file_menu = menubar.addMenu(tr('menu_file'))
        a = QAction(tr('menu_open_csv'), self); a.setShortcut("Ctrl+O"); a.triggered.connect(self.open_csv)
        file_menu.addAction(a)
        a = QAction(tr('menu_save_csv'), self); a.setShortcut("Ctrl+S"); a.triggered.connect(self.save_csv_as)
        file_menu.addAction(a)
        file_menu.addSeparator()
        a = QAction(tr('menu_export_excel'), self); a.triggered.connect(self.export_excel)
        file_menu.addAction(a)
        file_menu.addSeparator()
        a = QAction(tr('menu_exit'), self); a.setShortcut("Ctrl+Q"); a.triggered.connect(self.close)
        file_menu.addAction(a)

        # == Tools ==
        tools_menu = menubar.addMenu(tr('menu_tools'))
        a = QAction(tr('menu_preprocess_action'), self); a.setShortcut("Ctrl+P")
        a.triggered.connect(self.switch_to_preprocess); tools_menu.addAction(a)
        a = QAction(tr('menu_analysis_action'), self); a.setShortcut("Ctrl+A")
        a.triggered.connect(self.switch_to_analysis); tools_menu.addAction(a)
        tools_menu.addSeparator()
        a = QAction(tr('menu_view_image'), self); a.triggered.connect(self.open_image_viewer)
        tools_menu.addAction(a)

        # == View ==
        view_menu = menubar.addMenu(tr('menu_view'))
        a = QAction(tr('menu_data_table'), self)
        a.triggered.connect(lambda: self.main_tabs.setCurrentIndex(3)); view_menu.addAction(a)
        a = QAction(tr('menu_chart_view'), self)
        a.triggered.connect(lambda: self.main_tabs.setCurrentIndex(4)); view_menu.addAction(a)
        a = QAction(tr('menu_stats'), self); a.triggered.connect(self.show_statistics)
        view_menu.addAction(a)
        view_menu.addSeparator()

        # Language submenu — QActionGroup 确保互斥单选
        from PyQt5.QtWidgets import QActionGroup
        lang_menu = view_menu.addMenu(tr('menu_lang'))
        lang_grp = QActionGroup(self)
        lang_grp.setExclusive(True)
        a_zh = QAction(tr('menu_lang_zh'), lang_grp, checkable=True)
        a_en = QAction(tr('menu_lang_en'), lang_grp, checkable=True)
        a_zh.setChecked(_LANG[0] == 'zh')
        a_en.setChecked(_LANG[0] == 'en')
        a_zh.triggered.connect(lambda checked: self.set_language('zh') if checked else None)
        a_en.triggered.connect(lambda checked: self.set_language('en') if checked else None)
        lang_menu.addAction(a_zh)
        lang_menu.addAction(a_en)

        # Theme submenu — QActionGroup 确保互斥单选
        theme_menu = view_menu.addMenu(tr('menu_theme'))
        theme_grp = QActionGroup(self)
        theme_grp.setExclusive(True)
        a_light = QAction(tr('menu_theme_light'), theme_grp, checkable=True)
        a_dark  = QAction(tr('menu_theme_dark'),  theme_grp, checkable=True)
        a_light.setChecked(self._theme == 'light')
        a_dark.setChecked(self._theme == 'dark')
        a_light.triggered.connect(lambda checked: self.apply_theme('light') if checked else None)
        a_dark.triggered.connect(lambda checked: self.apply_theme('dark')  if checked else None)
        theme_menu.addAction(a_light)
        theme_menu.addAction(a_dark)

        # == About ==
        about_menu = menubar.addMenu(tr('menu_about'))
        a = QAction(tr('menu_about_app'), self); a.triggered.connect(self.show_about)
        about_menu.addAction(a)
        a = QAction(tr('menu_help'), self); a.setShortcut("F1"); a.triggered.connect(self.show_help)
        about_menu.addAction(a)

    # ----------------------------------------------------------------
    # 主界面
    # ----------------------------------------------------------------
    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(4)

        # 垂直分割器：上方功能标签页 + 下方固定日志面板
        self._vsplit = QSplitter(Qt.Vertical)

        self.main_tabs = QTabWidget()
        # 禁用滚动箭头；Expanding=True 让 4 个 Tab 均分整个标签栏宽度
        self.main_tabs.tabBar().setUsesScrollButtons(False)
        self.main_tabs.tabBar().setExpanding(True)
        self._vsplit.addWidget(self.main_tabs)

        # 日志面板（固定在底部）
        self._log_panel = self._create_log_panel()
        self._vsplit.addWidget(self._log_panel)

        # 初始高度比例：功能区 80%，日志区 20%
        self._vsplit.setSizes([650, 140])
        self._vsplit.setStretchFactor(0, 1)
        self._vsplit.setStretchFactor(1, 0)

        main_layout.addWidget(self._vsplit)

        self.preprocess_tab = self._create_preprocess_tab()
        self.main_tabs.addTab(self.preprocess_tab, tr('tab_preprocess'))   # 0

        self.erase_tab = EraseTab()
        self.erase_tab.log_message.connect(self.log)
        self.main_tabs.addTab(self.erase_tab, tr('tab_erase'))             # 1

        self.analysis_tab = self._create_analysis_tab()
        self.main_tabs.addTab(self.analysis_tab, tr('tab_analysis'))        # 2

        self.data_tab = self._create_data_tab()
        self.main_tabs.addTab(self.data_tab, tr('tab_data'))                # 3

        self.chart_panel = ChartPanel()
        self.chart_panel.log_message.connect(self.log)
        self.main_tabs.addTab(self.chart_panel, tr('tab_chart'))            # 4

    # ---- 预处理 Tab ----
    def _create_preprocess_tab(self):
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # ── 顶部: 目录选择行 ────────────────────────────────────────────
        dir_group = self._t(QGroupBox(tr('pp_dir_group')), 'pp_dir_group', 'setTitle')
        dir_layout = QHBoxLayout(dir_group)

        self._pp_input_lbl_s = self._t(QLabel(tr('pp_input_dir')), 'pp_input_dir')
        dir_layout.addWidget(self._pp_input_lbl_s)
        self.pp_input_label = QLabel("(未选择)")
        self.pp_input_label.setStyleSheet("font-style: italic; opacity: 0.7;")
        dir_layout.addWidget(self.pp_input_label, 1)
        btn_input = self._t(QPushButton(tr('pp_browse')), 'pp_browse')
        btn_input.setMinimumWidth(82)
        btn_input.clicked.connect(self.pp_select_input)
        dir_layout.addWidget(btn_input)

        dir_layout.addSpacing(16)
        self._pp_output_lbl_s = self._t(QLabel(tr('pp_output_dir')), 'pp_output_dir')
        dir_layout.addWidget(self._pp_output_lbl_s)
        self.pp_output_label = QLabel("(未选择)")
        self.pp_output_label.setStyleSheet("font-style: italic; opacity: 0.7;")
        dir_layout.addWidget(self.pp_output_label, 1)
        btn_output = self._t(QPushButton(tr('pp_browse')), 'pp_browse')
        btn_output.setMinimumWidth(82)
        btn_output.clicked.connect(self.pp_select_output)
        dir_layout.addWidget(btn_output)

        main_layout.addWidget(dir_group)

        # ── 中部: 左参数 + 右三联图 ────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # -- 左侧参数面板（滚动容器，避免窗口小时内容挤压）--
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setMinimumWidth(300)
        left_scroll.setMaximumWidth(380)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(6)
        left_layout.setContentsMargins(2, 2, 4, 2)

        # 图像选择下拉
        sel_group = self._t(QGroupBox(tr('pp_preview_group')), 'pp_preview_group', 'setTitle')
        sel_layout = QVBoxLayout(sel_group)

        sel_row = QHBoxLayout()
        self._pp_sel_lbl = self._t(QLabel(tr('pp_select_img')), 'pp_select_img')
        sel_row.addWidget(self._pp_sel_lbl)
        self.pp_img_combo = QComboBox()
        self.pp_img_combo.setToolTip("从输入目录加载图像后，下拉选择要预览的单张图像")
        self.pp_img_combo.currentIndexChanged.connect(self.pp_on_img_selected)
        sel_row.addWidget(self.pp_img_combo, 1)
        sel_layout.addLayout(sel_row)

        self.pp_preview_btn = self._t(QPushButton(tr('pp_preview_btn')), 'pp_preview_btn')
        self.pp_preview_btn.setEnabled(False)
        self.pp_preview_btn.clicked.connect(self.pp_preview_single)
        sel_layout.addWidget(self.pp_preview_btn)

        self.pp_preview_status = QLabel(tr('pp_preview_hint'))
        self.pp_preview_status.setWordWrap(True)
        self.pp_preview_status.setStyleSheet("font-size: 9pt; opacity: 0.7;")
        sel_layout.addWidget(self.pp_preview_status)

        left_layout.addWidget(sel_group)

        # 参数
        param_group = self._t(QGroupBox(tr('pp_param_group')), 'pp_param_group', 'setTitle')
        param_form = QFormLayout(param_group)
        param_form.setLabelAlignment(Qt.AlignRight)
        param_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        param_form.setHorizontalSpacing(8)
        param_form.setVerticalSpacing(6)

        self.pp_method = QComboBox()
        self.pp_method.addItems([
            'multiscale  (推荐)',
            'texture',
            'otsu',
            'line_art  (黑线模拟图)',
            'adaptive',
            'intensity  (亮度滞后分割)',
        ])
        self.pp_method.setToolTip(tr('tt_method'))
        param_form.addRow(tr('pp_method_lbl'), self.pp_method)
        self._t(param_form.labelForField(self.pp_method), 'pp_method_lbl')
        param_form.labelForField(self.pp_method).setToolTip(tr('tt_method'))

        self.pp_stem_repair = QCheckBox('修复粗根基内部伪孔 / Repair stem pores')
        self.pp_stem_repair.setToolTip(
            '仅在拍摄暗斑造成粗根基内部伪孔时启用；保留外部空隙和侧根。'
            '请重新预处理原图，并检查结果。默认关闭。')
        param_form.addRow(self.pp_stem_repair)
        self.pp_stem_direction = QComboBox()
        for label, direction in [('上 / Top', 'top'), ('下 / Bottom', 'bottom'),
                                 ('左 / Left', 'left'), ('右 / Right', 'right')]:
            self.pp_stem_direction.addItem(label, direction)
        self.pp_stem_direction.setEnabled(False)
        self.pp_stem_repair.toggled.connect(self.pp_stem_direction.setEnabled)
        param_form.addRow('根基位置 / Stem side', self.pp_stem_direction)

        self.pp_window = QSpinBox()
        self.pp_window.setRange(5, 151); self.pp_window.setSingleStep(2); self.pp_window.setValue(25)
        self.pp_window.setToolTip(tr('tt_window'))
        param_form.addRow(tr('pp_window_lbl'), self.pp_window)
        self._t(param_form.labelForField(self.pp_window), 'pp_window_lbl')
        param_form.labelForField(self.pp_window).setToolTip(tr('tt_window'))

        self.pp_min_size = QSpinBox()
        self.pp_min_size.setRange(10, 50000); self.pp_min_size.setValue(500)
        self.pp_min_size.setToolTip(tr('tt_min_size'))
        param_form.addRow(tr('pp_min_size_lbl'), self.pp_min_size)
        self._t(param_form.labelForField(self.pp_min_size), 'pp_min_size_lbl')
        param_form.labelForField(self.pp_min_size).setToolTip(tr('tt_min_size'))

        self.pp_hole_size = QSpinBox()
        self.pp_hole_size.setRange(0, 5000); self.pp_hole_size.setValue(200)
        self.pp_hole_size.setToolTip(tr('tt_hole_size'))
        param_form.addRow(tr('pp_hole_size_lbl'), self.pp_hole_size)
        self._t(param_form.labelForField(self.pp_hole_size), 'pp_hole_size_lbl')
        param_form.labelForField(self.pp_hole_size).setToolTip(tr('tt_hole_size'))

        self.pp_close_radius = QSpinBox()
        self.pp_close_radius.setRange(0, 20); self.pp_close_radius.setValue(3)
        self.pp_close_radius.setToolTip(tr('tt_close_radius'))
        param_form.addRow(tr('pp_close_radius_lbl'), self.pp_close_radius)
        self._t(param_form.labelForField(self.pp_close_radius), 'pp_close_radius_lbl')
        param_form.labelForField(self.pp_close_radius).setToolTip(tr('tt_close_radius'))

        self.pp_bright_thresh = QDoubleSpinBox()
        self.pp_bright_thresh.setRange(0.5, 1.0); self.pp_bright_thresh.setSingleStep(0.01)
        self.pp_bright_thresh.setDecimals(2); self.pp_bright_thresh.setValue(0.92)
        self.pp_bright_thresh.setToolTip(tr('tt_bright_thresh'))
        param_form.addRow(tr('pp_bright_thresh_lbl'), self.pp_bright_thresh)
        self._t(param_form.labelForField(self.pp_bright_thresh), 'pp_bright_thresh_lbl')
        param_form.labelForField(self.pp_bright_thresh).setToolTip(tr('tt_bright_thresh'))

        self.pp_border_margin = QSpinBox()
        self.pp_border_margin.setRange(0, 200); self.pp_border_margin.setValue(20)
        self.pp_border_margin.setToolTip(tr('tt_border_margin'))
        param_form.addRow(tr('pp_border_margin_lbl'), self.pp_border_margin)
        self._t(param_form.labelForField(self.pp_border_margin), 'pp_border_margin_lbl')
        param_form.labelForField(self.pp_border_margin).setToolTip(tr('tt_border_margin'))

        self.pp_isolation = QSpinBox()
        self.pp_isolation.setRange(0, 2000); self.pp_isolation.setValue(150)
        self.pp_isolation.setToolTip(tr('tt_isolation'))
        param_form.addRow(tr('pp_isolation_lbl'), self.pp_isolation)
        self._t(param_form.labelForField(self.pp_isolation), 'pp_isolation_lbl')
        param_form.labelForField(self.pp_isolation).setToolTip(tr('tt_isolation'))

        left_layout.addWidget(param_group)

        # 进度和批量按钮
        prog_group = self._t(QGroupBox(tr('pp_batch_group')), 'pp_batch_group', 'setTitle')
        prog_layout = QVBoxLayout(prog_group)

        self.pp_progress = QProgressBar()
        self.pp_progress.setValue(0)
        prog_layout.addWidget(self.pp_progress)

        self.pp_status_label = QLabel(tr('pp_ready'))
        self.pp_status_label.setWordWrap(True)
        prog_layout.addWidget(self.pp_status_label)

        pp_workers_row = QHBoxLayout()
        pp_workers_row.addWidget(self._t(QLabel(tr('pp_workers_lbl')), 'pp_workers_lbl'))
        self.pp_workers = QSpinBox()
        self.pp_workers.setRange(1, 32)
        self.pp_workers.setValue(min(max(1, (os.cpu_count() or 4)), 8))
        self.pp_workers.setToolTip(tr('tt_workers'))
        pp_workers_row.addWidget(self.pp_workers)
        pp_workers_row.addStretch()
        prog_layout.addLayout(pp_workers_row)

        self.pp_run_btn = self._t(QPushButton(tr('pp_run_btn')), 'pp_run_btn')
        self.pp_run_btn.setObjectName('primary')
        self.pp_run_btn.setMinimumHeight(36)
        self.pp_run_btn.clicked.connect(self.run_preprocess)
        prog_layout.addWidget(self.pp_run_btn)

        left_layout.addWidget(prog_group)
        left_layout.addStretch()

        left_scroll.setWidget(left)

        # -- 右侧: 三联图 --
        self.pp_triple_viewer = TripleImageViewer()

        splitter.addWidget(left_scroll)
        splitter.addWidget(self.pp_triple_viewer)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, 1)

        # 内部存储
        self._pp_input_dirs = []
        self._pp_output_dir = ''
        self._pp_raw_files = []  # 所有找到的原始图像路径
        self._pp_preview_worker = None

        return widget

    # ---- 分析 Tab ----
    def _create_analysis_tab(self):
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # ── 顶部: 输入设置 ────────────────────────────────────────────
        dir_group = self._t(QGroupBox(tr('an_dir_group')), 'an_dir_group', 'setTitle')
        dir_vbox = QVBoxLayout(dir_group)
        dir_vbox.setSpacing(4)

        # 辅助：一行「标签 + 路径显示 + 浏览按钮」
        def _path_row(parent_layout, lbl_key, slot, default_text=None):
            row_w = QWidget()
            row_h = QHBoxLayout(row_w)
            row_h.setContentsMargins(0, 0, 0, 0)
            lbl = self._t(QLabel(tr(lbl_key)), lbl_key)
            lbl.setMinimumWidth(130)
            lbl.setMaximumWidth(165)
            path_lbl = QLabel(default_text or tr('an_not_selected'))
            path_lbl.setStyleSheet(
                "" if default_text else "font-style: italic; opacity: 0.7;")
            path_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            btn = self._t(QPushButton(tr('pp_browse')), 'pp_browse')
            btn.setMinimumWidth(82)
            btn.clicked.connect(slot)
            row_h.addWidget(lbl)
            row_h.addWidget(path_lbl, 1)
            row_h.addWidget(btn)
            parent_layout.addWidget(row_w)
            return row_w, path_lbl

        # ── 三行目录选择 ──
        _, self.an_binary_label   = _path_row(dir_vbox, 'an_binary_dir',     self.an_select_binary)
        _, self.an_skeleton_label = _path_row(dir_vbox, 'an_skel_dir',       self.an_select_skeleton)
        _, self.an_output_label   = _path_row(dir_vbox, 'an_output_dir_lbl', self.an_select_output,
                                              default_text='./results')

        # ── 样本下拉选择 ──
        sel_row = QHBoxLayout()
        sel_lbl = self._t(QLabel(tr('an_select_sample')), 'an_select_sample')
        sel_lbl.setMinimumWidth(130)
        sel_lbl.setMaximumWidth(165)
        self.an_sample_combo = QComboBox()
        self.an_sample_combo.setToolTip("选择二值化目录后自动填充，可下拉选择单个样本")
        self.an_sample_combo.currentIndexChanged.connect(self._an_on_sample_changed)
        sel_row.addWidget(sel_lbl)
        sel_row.addWidget(self.an_sample_combo, 1)
        refresh_btn = self._t(QPushButton(tr('an_refresh_btn')), 'an_refresh_btn')
        refresh_btn.setMinimumWidth(78)
        refresh_btn.clicked.connect(self._an_scan_samples)
        sel_row.addWidget(refresh_btn)
        dir_vbox.addLayout(sel_row)

        main_layout.addWidget(dir_group)

        # ── 中部: 左参数 + 右预览 ────────────────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        # 左侧参数面板（滚动容器）
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setMinimumWidth(280)
        left_scroll.setMaximumWidth(360)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(6)
        left_layout.setContentsMargins(2, 2, 4, 2)

        an_param = self._t(QGroupBox(tr('an_param_group')), 'an_param_group', 'setTitle')
        an_form = QFormLayout(an_param)
        an_form.setLabelAlignment(Qt.AlignRight)
        an_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        an_form.setHorizontalSpacing(8)
        an_form.setVerticalSpacing(6)

        self.an_dpi = QSpinBox()
        self.an_dpi.setRange(0, 10000)
        self.an_dpi.setSpecialValueText("自动 / 无记录用像素")
        self.an_dpi.setValue(0)
        self.an_dpi.setToolTip("0：读取文件尺度；缺失时仅输出像素。非零：显式覆盖 DPI，导出标为 user_supplied。")
        an_form.addRow("DPI（可覆盖）", self.an_dpi)
        self.an_root_direction = QComboBox()
        for label,value in [("根基部在上", "top"),("根基部在下", "bottom"),("根基部在左", "left"),("根基部在右", "right"),("散根 / 不定向", "none")]:
            self.an_root_direction.addItem(label, value)
        an_form.addRow("根系方向", self.an_root_direction)

        self.an_root_model = QComboBox()
        self.an_root_model.addItem("一般根系 / General", "general")
        self.an_root_model.addItem("共同根基、无侧分枝 / Shared crown", "shared_crown")
        self.an_root_model.setToolTip(
            "共同根基模型仅用于已知各根独立、无侧分枝且共享根基的样本。"
            "共享段长度属于模型推断；不能用此选项抹去真实侧根。")
        an_form.addRow("根系模型", self.an_root_model)
        self.an_crossing_context = QCheckBox("交叉短段上下文 / Crossing context")
        self.an_crossing_context.setChecked(True)
        self.an_crossing_context.setToolTip(
            "利用交叉附近短连接段判断贴合关系；关闭时仍保留局部交叉识别。"
            "复杂真实根系可比较开关结果，并保留所用参数。")
        an_form.addRow(self.an_crossing_context)

        self.an_csv_name = QComboBox()
        self.an_csv_name.setEditable(True)
        self.an_csv_name.addItem("root_architecture_metrics.csv")
        self.an_csv_name.setToolTip(tr('tt_csv_name'))
        an_form.addRow(tr('an_csv_lbl'), self.an_csv_name)
        self._t(an_form.labelForField(self.an_csv_name), 'an_csv_lbl')
        an_form.labelForField(self.an_csv_name).setToolTip(tr('tt_csv_name'))

        left_layout.addWidget(an_param)

        prog_group = self._t(QGroupBox(tr('an_run_group')), 'an_run_group', 'setTitle')
        prog_layout = QVBoxLayout(prog_group)

        self.an_progress = QProgressBar()
        self.an_progress.setValue(0)
        prog_layout.addWidget(self.an_progress)

        self.an_status_label = QLabel(tr('an_ready'))
        self.an_status_label.setWordWrap(True)
        prog_layout.addWidget(self.an_status_label)

        self.an_run_single_btn = self._t(QPushButton(tr('an_run_single_btn')), 'an_run_single_btn')
        self.an_run_single_btn.setMinimumHeight(34)
        self.an_run_single_btn.setEnabled(False)
        self.an_run_single_btn.clicked.connect(lambda: self.run_analysis(batch=False))
        prog_layout.addWidget(self.an_run_single_btn)

        an_workers_row = QHBoxLayout()
        an_workers_row.addWidget(self._t(QLabel(tr('an_workers_lbl')), 'an_workers_lbl'))
        self.an_workers = QSpinBox()
        self.an_workers.setRange(1, 32)
        self.an_workers.setValue(min(max(1, (os.cpu_count() or 4)), 8))
        self.an_workers.setToolTip(tr('tt_workers'))
        an_workers_row.addWidget(self.an_workers)
        an_workers_row.addStretch()
        prog_layout.addLayout(an_workers_row)

        self.an_run_batch_btn = self._t(QPushButton(tr('an_run_batch_btn')), 'an_run_batch_btn')
        self.an_run_batch_btn.setObjectName('primary')
        self.an_run_batch_btn.setMinimumHeight(34)
        self.an_run_batch_btn.setEnabled(False)
        self.an_run_batch_btn.clicked.connect(lambda: self.run_analysis(batch=True))
        prog_layout.addWidget(self.an_run_batch_btn)

        left_layout.addWidget(prog_group)
        left_layout.addStretch()

        left_scroll.setWidget(left)

        # 右侧: 分析结果预览（Binary | Skeleton+拓扑叠加）
        self.an_viewer = AnalysisResultViewer()
        # 点击 Prev/Next 时同步更新上方样本下拉框
        self.an_viewer.sample_navigated.connect(self._an_sync_combo_to_viewer)

        splitter.addWidget(left_scroll)
        splitter.addWidget(self.an_viewer)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, 1)

        # 内部存储
        self._an_binary_dir  = ''
        self._an_skeleton_dir = ''
        self._an_output_dir   = './results'

        return widget

    # ---- 数据表 Tab ----
    def _create_data_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)

        # 顶部信息栏
        top = QFrame()
        top.setFrameShape(QFrame.StyledPanel)
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(6, 4, 6, 4)
        self.data_info_label = self._t(
            QLabel(tr('data_no_data')), 'data_no_data')
        top_layout.addWidget(self.data_info_label, 1)
        self.data_stats_btn = self._t(QPushButton(tr('data_stats_btn')), 'data_stats_btn')
        self.data_stats_btn.setMinimumWidth(105)
        self.data_stats_btn.clicked.connect(self.show_statistics)
        top_layout.addWidget(self.data_stats_btn)
        layout.addWidget(top)

        # 表格
        self.data_table = QTableWidget()
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.data_table.horizontalHeader().setStretchLastSection(False)
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        layout.addWidget(self.data_table)

        return widget

    # ---- 日志底部固定面板 ----
    def _create_log_panel(self):
        """创建固定在界面底部的运行日志面板。"""
        widget = QWidget()
        widget.setMinimumHeight(80)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(3)

        # 标题栏：标签 + 清除按钮
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._log_title_lbl = QLabel(tr('log_panel_title'))
        self._log_title_lbl.setStyleSheet(
            "font-weight: bold; font-size: 13px; padding-left: 4px;")
        header.addWidget(self._log_title_lbl)
        header.addStretch()
        self._log_clear_btn = self._t(
            QPushButton(tr('log_clear_btn')), 'log_clear_btn')
        self._log_clear_btn.setMinimumSize(90, 24)
        self._log_clear_btn.clicked.connect(lambda: self.log_text.clear())
        header.addWidget(self._log_clear_btn)
        layout.addLayout(header)

        # 日志文本框
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.WidgetWidth)
        mono = QFont("Consolas", 9)
        if not mono.exactMatch():
            mono = QFont("Courier New", 9)
        self.log_text.setFont(mono)
        # 减小内边距避免文字被遮挡
        self.log_text.setStyleSheet("padding: 2px 4px;")
        layout.addWidget(self.log_text, 1)

        return widget

    # ----------------------------------------------------------------
    # 状态栏
    # ----------------------------------------------------------------
    def _init_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage(tr('status_ready') + f" | Xinjiang Academy of Agricultural Reclamation Sciences v{APP_VERSION}")

    # ----------------------------------------------------------------
    # 日志
    # ----------------------------------------------------------------
    def log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_text.append(f"[{ts}] {msg}")

    # ----------------------------------------------------------------
    # 文件菜单操作
    # ----------------------------------------------------------------
    def open_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr('dlg_open_csv'), "", "CSV (*.csv);;*")
        if path:
            try:
                self.df = pd.read_csv(path, encoding='utf-8-sig')
                self.csv_path = path
                self._update_data_table()
                self.chart_panel.set_data(self.df)
                self.main_tabs.setCurrentIndex(3)
                self.statusbar.showMessage(f"{path}  ({len(self.df)} rows)")
                self.log(f"已加载 CSV: {path}  ({len(self.df)} 行)")
            except Exception as e:
                QMessageBox.critical(self, tr('msg_error'), f"Cannot load CSV:\n{e}")

    def save_csv_as(self):
        if self.df is None:
            QMessageBox.warning(self, tr('msg_warn'), tr('msg_no_data'))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, tr('dlg_save_csv'), "root_architecture_metrics.csv", "CSV (*.csv)")
        if path:
            self.df.to_csv(path, index=False, encoding='utf-8-sig')
            QMessageBox.information(self, tr('msg_save_ok'), tr('msg_saved_to', path=path))

    def export_excel(self):
        if self.df is None:
            QMessageBox.warning(self, tr('msg_warn'), tr('msg_no_data'))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, tr('dlg_save_excel'), "root_architecture_metrics.xlsx", "Excel (*.xlsx)")
        if path:
            try:
                self.df.to_excel(path, index=False, engine='openpyxl')
                QMessageBox.information(self, tr('msg_save_ok'), tr('msg_export_ok', path=path))
            except ImportError:
                QMessageBox.warning(self, tr('msg_warn'),
                    "openpyxl is required.\nRun: pip install openpyxl")
            except Exception as e:
                QMessageBox.critical(self, tr('msg_error'), f"Export failed:\n{e}")

    # ----------------------------------------------------------------
    # 预处理操作
    # ----------------------------------------------------------------
    def _pp_get_method(self):
        """从下拉框解析方法名"""
        return self.pp_method.currentText().split()[0].lower()

    def pp_select_input(self):
        d = QFileDialog.getExistingDirectory(self, tr('pp_input_dir'))
        if not d:
            return
        self._pp_input_dirs = [d]
        self.pp_input_label.setText(d)

        # 填充图像下拉列表
        raw_files = preprocess.find_raw_images([d])
        self._pp_raw_files = raw_files
        self.pp_img_combo.blockSignals(True)
        self.pp_img_combo.clear()
        for f in raw_files:
            stem = os.path.splitext(os.path.basename(f))[0]
            self.pp_img_combo.addItem(stem, f)
        self.pp_img_combo.blockSignals(False)

        n = len(raw_files)
        if n > 0:
            self.pp_preview_btn.setEnabled(True)
            self.pp_preview_status.setText(f"{n} images found. Select one and click Preview.")
            self.pp_on_img_selected(0)
        else:
            self.pp_preview_btn.setEnabled(False)
            self.pp_preview_status.setText("No image files found.")

    def pp_select_output(self):
        d = QFileDialog.getExistingDirectory(self, tr('pp_output_dir'))
        if d:
            self._pp_output_dir = d
            self.pp_output_label.setText(d)

    def pp_on_img_selected(self, index):
        """下拉切换图像：仅显示原图，等待用户点击预览"""
        if index < 0 or index >= len(self._pp_raw_files):
            return
        raw_path = self._pp_raw_files[index]
        # 仅显示原图（binary/skeleton 位置留空）
        self.pp_triple_viewer.show_files(raw_path, None, None)
        self.pp_preview_status.setText(
            f"[{index+1}/{len(self._pp_raw_files)}] {os.path.basename(raw_path)}\n"
            "点击【预览当前图像】查看分割效果"
        )

    def pp_preview_single(self):
        """用当前参数处理所选图像，实时显示 raw/binary/skeleton"""
        idx = self.pp_img_combo.currentIndex()
        if idx < 0 or idx >= len(self._pp_raw_files):
            return

        # 如果没有设置输出目录，用系统临时目录（预览不写磁盘）
        out_dir = self._pp_output_dir or os.path.join(
            os.path.dirname(self._pp_raw_files[0]), '_preview_tmp')

        self.pp_preview_btn.setEnabled(False)
        self.pp_preview_btn.setText(tr('msg_previewing'))
        self.pp_preview_status.setText(tr('msg_previewing'))

        self._pp_preview_worker = SinglePreprocessWorker(
            img_path=self._pp_raw_files[idx],
            output_dir=out_dir,
            method=self._pp_get_method(),
            window_size=self.pp_window.value(),
            min_size=self.pp_min_size.value(),
            hole_size=self.pp_hole_size.value(),
            close_radius=self.pp_close_radius.value(),
            bright_thresh=self.pp_bright_thresh.value(),
            border_margin=self.pp_border_margin.value(),
            isolation_distance=self.pp_isolation.value(),
            repair_proximal_stem=self.pp_stem_repair.isChecked(),
            stem_direction=self.pp_stem_direction.currentData(),
        )
        self._pp_preview_worker.finished.connect(self._pp_on_preview_done)
        self._pp_preview_worker.error.connect(self._pp_on_preview_error)
        self._pp_preview_worker.start()

    def _pp_on_preview_done(self, raw, binary, skeleton, filepath):
        fname = os.path.basename(filepath)
        self.pp_triple_viewer.show_arrays(raw, binary, skeleton, fname)
        self.pp_preview_btn.setEnabled(True)
        self.pp_preview_btn.setText(tr('pp_preview_btn'))
        idx = self.pp_img_combo.currentIndex()
        self.pp_preview_status.setText(tr('msg_preview_ok', f=fname))

    def _pp_on_preview_error(self, err_msg):
        self.pp_preview_btn.setEnabled(True)
        self.pp_preview_btn.setText(tr('pp_preview_btn'))
        self.pp_preview_status.setText("Preview failed.")
        self.log(f"预览失败: {err_msg}")
        QMessageBox.critical(self, tr('msg_error'), err_msg)

    def run_preprocess(self):
        """批量处理所有图像"""
        if not self._pp_input_dirs:
            QMessageBox.warning(self, tr('msg_warn'), tr('msg_no_input'))
            return
        if not self._pp_output_dir:
            QMessageBox.warning(self, tr('msg_warn'), tr('msg_no_output'))
            return

        method = self._pp_get_method()
        self.pp_run_btn.setEnabled(False)
        self.pp_progress.setValue(0)
        n_files = len(self._pp_raw_files)
        self.pp_status_label.setText(f"正在启动，准备处理 {n_files} 张图像…")
        self.log("─" * 48)
        self.log("批量预处理开始")
        self.log(f"输入目录: {self._pp_input_dirs}")
        self.log(f"输出目录: {self._pp_output_dir}")
        self.log(f"方法: {method}  窗口: {self.pp_window.value()}  "
                 f"最小面积: {self.pp_min_size.value()}  "
                 f"孔洞: {self.pp_hole_size.value()}  "
                 f"闭运算: {self.pp_close_radius.value()}")

        self.pp_triple_viewer.clear_samples()   # 清空上次批量缓存

        self.worker = PreprocessWorker(
            input_dirs=self._pp_input_dirs,
            output_dir=self._pp_output_dir,
            method=method,
            window_size=self.pp_window.value(),
            min_size=self.pp_min_size.value(),
            hole_size=self.pp_hole_size.value(),
            close_radius=self.pp_close_radius.value(),
            bright_thresh=self.pp_bright_thresh.value(),
            border_margin=self.pp_border_margin.value(),
            isolation_distance=self.pp_isolation.value(),
            num_workers=self.pp_workers.value(),
            repair_proximal_stem=self.pp_stem_repair.isChecked(),
            stem_direction=self.pp_stem_direction.currentData(),
        )
        self.worker.progress.connect(self._pp_on_progress)
        self.worker.sample_done.connect(self._pp_on_sample_done)
        self.worker.finished.connect(self._pp_on_finished)
        self.worker.error.connect(self._pp_on_error)
        self.worker.log.connect(self.log)
        self.worker.start()

    def _pp_on_progress(self, current, total, fname):
        self.pp_progress.setMaximum(total)
        self.pp_progress.setValue(current)
        self.pp_status_label.setText(f"[{current}/{total}] {fname}")

    def _pp_on_sample_done(self, raw_path, bin_path, skel_path, fname):
        """一张处理完毕：缓存并实时显示（文件已确认写入磁盘）"""
        self.pp_triple_viewer.add_file_sample(raw_path, bin_path, skel_path, fname)

    def _pp_on_finished(self, success, failed):
        self.pp_run_btn.setEnabled(True)
        total = len(self._pp_raw_files)
        self.pp_status_label.setText(tr('msg_batch_done', ok=success, fail=len(failed)))
        self.log(f"批量处理完成: 成功 {success} 张，失败 {len(failed)} 张")
        for fname, err in failed:
            self.log(f"  [{fname}] 错误: {err}")
        msg = f"Batch complete!\nSuccess: {success}/{total}"
        if failed:
            msg += f"\nFailed: {len(failed)} (see log)"
        QMessageBox.information(self, tr('msg_info'), msg)

    def _pp_on_error(self, err_msg):
        self.pp_run_btn.setEnabled(True)
        self.pp_status_label.setText("Error")
        self.log(f"预处理错误: {err_msg}")
        QMessageBox.critical(self, tr('msg_error'), err_msg)

    # ----------------------------------------------------------------
    # 分析操作
    # ----------------------------------------------------------------
    def an_select_binary(self):
        d = QFileDialog.getExistingDirectory(self, tr('an_binary_dir'))
        if d:
            self._an_binary_dir = d
            self.an_binary_label.setText(d)
            self.an_binary_label.setStyleSheet("")
            self._an_scan_samples()

    def an_select_skeleton(self):
        d = QFileDialog.getExistingDirectory(self, tr('an_skel_dir'))
        if d:
            self._an_skeleton_dir = d
            self.an_skeleton_label.setText(d)
            self.an_skeleton_label.setStyleSheet("")

    def an_select_output(self):
        d = QFileDialog.getExistingDirectory(self, tr('an_output_dir_lbl'))
        if d:
            self._an_output_dir = d
            self.an_output_label.setText(d)

    def _an_scan_samples(self):
        """扫描二值化目录，刷新样本下拉列表。"""
        import glob as _glob
        self.an_sample_combo.blockSignals(True)
        self.an_sample_combo.clear()
        binary_dir = self._an_binary_dir
        if os.path.isdir(binary_dir):
            img_exts = ('*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff', '*.bmp')
            files = sorted(set(
                f for ext in img_exts
                for f in (_glob.glob(os.path.join(binary_dir, ext)) +
                          _glob.glob(os.path.join(binary_dir, ext.upper())))
            ))
            for f in files:
                stem = os.path.splitext(os.path.basename(f))[0]
                self.an_sample_combo.addItem(stem)
        self.an_sample_combo.blockSignals(False)
        n = self.an_sample_combo.count()
        self.an_run_single_btn.setEnabled(n > 0)
        self.an_run_batch_btn.setEnabled(n > 0)
        if n > 0:
            self._an_on_sample_changed(0)

    def _an_sync_combo_to_viewer(self, stem: str):
        """Prev/Next 导航后，将样本下拉框同步到 viewer 当前样本。
        blockSignals 防止触发 _an_on_sample_changed 形成循环。
        """
        for i in range(self.an_sample_combo.count()):
            if self.an_sample_combo.itemText(i) == stem:
                self.an_sample_combo.blockSignals(True)
                self.an_sample_combo.setCurrentIndex(i)
                self.an_sample_combo.blockSignals(False)
                break

    def _an_on_sample_changed(self, index):
        """下拉切换样本时，显示对应样本的分析结果或预览图像。

        优先级：
          1. 已有缓存分析结果 → 直接显示结果（含 Tips/Forks/Crossings 散点）
          2. 无缓存 → 显示原始图像预览（分析前或单样本未分析时）
        """
        if index < 0 or index >= self.an_sample_combo.count():
            return
        stem = self.an_sample_combo.itemText(index)

        # ── 优先：从已完成的批量分析结果缓存中查找并显示 ──────────
        if self.an_viewer.show_by_stem(stem):
            return

        # ── 回退：无缓存，显示原始图像预览（分析前状态）──────────
        img_exts = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp')

        def _find(directory, stem):
            for ext in img_exts:
                p = os.path.join(directory, stem + ext)
                if os.path.exists(p):
                    return p
            return None

        bin_p  = _find(self._an_binary_dir,   stem) if self._an_binary_dir   else None
        skel_p = _find(self._an_skeleton_dir, stem) if self._an_skeleton_dir else None
        if bin_p and skel_p:
            self.an_viewer.show_pair(bin_p, skel_p)

    def run_analysis(self, batch=True):
        if not self._an_binary_dir:
            QMessageBox.warning(self, tr('msg_warn'), tr('msg_no_binary'))
            return
        if not self._an_skeleton_dir:
            QMessageBox.warning(self, tr('msg_warn'), tr('msg_no_skel'))
            return

        import glob as _glob
        binary_dir = self._an_binary_dir
        skel_dir   = self._an_skeleton_dir
        img_exts   = ('*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff', '*.bmp')

        def _find_file(directory, stem):
            for ext in img_exts:
                matches = _glob.glob(os.path.join(directory, stem + ext[1:]))
                if matches:
                    return matches[0]
            return None

        # 收集要处理的样本：单个或全部
        if batch:
            stems = [self.an_sample_combo.itemText(i)
                     for i in range(self.an_sample_combo.count())]
        else:
            stem = self.an_sample_combo.currentText()
            stems = [stem] if stem else []

        pairs_override = []
        for stem in stems:
            bp = _find_file(binary_dir, stem)
            sp = _find_file(skel_dir,   stem)
            if bp and sp:
                # 从文件名中提取年份（新格式 Year-... / 旧格式 Year_...）
                _year = ''
                _hyp_first = stem.split('-')[0]
                _und_first = stem.split('_')[0]
                if len(_hyp_first) == 4 and _hyp_first.isdigit():
                    _year = _hyp_first   # 新格式: 2023-DH-P1-1
                elif len(_und_first) == 4 and _und_first.isdigit():
                    _year = _und_first   # 旧格式: 2023_DH-P1-1
                pairs_override.append({
                    'year': _year,
                    'sample_id': stem,
                    'binary_path': bp,
                    'skeleton_path': sp,
                })

        if not pairs_override:
            QMessageBox.warning(self, tr('msg_warn'), tr('msg_no_samples'))
            return

        self.an_run_single_btn.setEnabled(False)
        self.an_run_batch_btn.setEnabled(False)
        self.an_progress.setValue(0)
        n_pairs = len(pairs_override)
        self.an_status_label.setText(f"正在启动，准备分析 {n_pairs} 个样本…")
        self.an_viewer._dpi = root_analysis.DEFAULT_DPI   # 备用，实际由文件元数据决定
        self.an_viewer.clear_samples()
        self.log("─" * 48)
        self.log("根系构型分析开始")
        self.log(f"DPI={self.an_dpi.value() or '自动；缺失时输出像素'}  |  样本数: {n_pairs}")
        self.log(f"Root_Model={self.an_root_model.currentData()}  |  "
                 f"Crossing_Context={self.an_crossing_context.isChecked()}")
        self.log(f"二值化目录: {binary_dir}  |  骨架目录: {skel_dir}")

        csv_name = self.an_csv_name.currentText().strip()
        if not csv_name:
            csv_name = 'root_architecture_metrics.csv'

        self.worker = AnalysisWorker(
            binary_dirs=[binary_dir],
            skeleton_dirs=[skel_dir],
            output_dir=self._an_output_dir,
            dpi=self.an_dpi.value() or None,
            output_name=csv_name,
            pairs_override=pairs_override,
            num_workers=self.an_workers.value(),
            root_direction=self.an_root_direction.currentData(),
            root_model=self.an_root_model.currentData(),
            crossing_context=self.an_crossing_context.isChecked(),
        )
        self.worker.progress.connect(self._an_on_progress)
        self.worker.finished.connect(self._an_on_finished)
        self.worker.error.connect(self._an_on_error)
        self.worker.log.connect(self.log)
        self.worker.image_ready.connect(self.an_viewer.show_pair)
        self.worker.result_ready.connect(self.an_viewer.add_sample)
        self.worker.start()

    def _an_on_progress(self, current, total, sid):
        self.an_progress.setMaximum(total)
        self.an_progress.setValue(current)
        self.an_status_label.setText(f"{sid} ({current}/{total})")

    def _an_on_finished(self, df, csv_path):
        self.an_run_single_btn.setEnabled(True)
        self.an_run_batch_btn.setEnabled(True)
        self.an_status_label.setText(f"Done: {len(df)} samples")
        self.df = df
        self.csv_path = csv_path
        self._update_data_table()
        self.chart_panel.set_data(df)
        self.log(f"分析完成: 共 {len(df)} 个样本 → {csv_path}")
        self.statusbar.showMessage(f"{tr('msg_done')} | {len(df)} samples | {csv_path}")
        QMessageBox.information(self, tr('msg_info'),
            tr('msg_analysis_done', n=len(df), path=csv_path))
        self.main_tabs.setCurrentIndex(3)

    def _an_on_error(self, err_msg):
        self.an_run_single_btn.setEnabled(True)
        self.an_run_batch_btn.setEnabled(True)
        self.an_status_label.setText("Error")
        self.log(f"分析错误: {err_msg}")
        QMessageBox.critical(self, tr('msg_error'), err_msg)

    # ----------------------------------------------------------------
    # 数据表操作
    # ----------------------------------------------------------------
    def _update_data_table(self):
        if self.df is None:
            return

        df = self.df
        self.data_table.clear()
        self.data_table.setRowCount(len(df))
        self.data_table.setColumnCount(len(df.columns))
        self.data_table.setHorizontalHeaderLabels(list(df.columns))

        for i in range(len(df)):
            for j, col in enumerate(df.columns):
                val = df.iloc[i, j]
                if pd.isna(val):
                    text = ''
                elif isinstance(val, float):
                    text = f'{val:.4f}'
                else:
                    text = str(val)
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.data_table.setItem(i, j, item)

        self.data_table.resizeColumnsToContents()
        self.data_info_label.setText(
            f"{len(df)} rows × {len(df.columns)} cols"
            + (f"  |  {self.csv_path}" if self.csv_path else ""))

    def show_statistics(self):
        if self.df is None:
            QMessageBox.warning(self, tr('msg_warn'), tr('msg_no_data'))
            return

        desc = self.df.describe().round(4)
        dialog = QDialog(self)
        dialog.setWindowTitle(tr('dlg_stats_title'))
        dialog.resize(900, 500)
        layout = QVBoxLayout(dialog)

        table = QTableWidget()
        table.setRowCount(len(desc))
        table.setColumnCount(len(desc.columns))
        table.setHorizontalHeaderLabels(list(desc.columns))
        table.setVerticalHeaderLabels(list(desc.index))

        for i in range(len(desc)):
            for j in range(len(desc.columns)):
                val = desc.iloc[i, j]
                text = f'{val:.4f}' if not pd.isna(val) else ''
                table.setItem(i, j, QTableWidgetItem(text))

        table.resizeColumnsToContents()
        layout.addWidget(table)

        save_btn = QPushButton(tr('dlg_stats_export'))
        def save_stats():
            path, _ = QFileDialog.getSaveFileName(dialog, tr('dlg_stats_export'), "statistics.csv", "CSV (*.csv)")
            if path:
                desc.to_csv(path, encoding='utf-8-sig')
                QMessageBox.information(dialog, tr('msg_save_ok'), tr('msg_saved_to', path=path))
        save_btn.clicked.connect(save_stats)
        layout.addWidget(save_btn)

        dialog.exec_()

    # ----------------------------------------------------------------
    # 工具操作
    # ----------------------------------------------------------------
    def switch_to_preprocess(self):
        self.main_tabs.setCurrentIndex(0)

    def switch_to_analysis(self):
        self.main_tabs.setCurrentIndex(2)

    def open_image_viewer(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, tr('dlg_open_img'), "",
            tr('dlg_img_filter'))
        if paths:
            if len(paths) >= 2:
                self.an_viewer.show_pair(paths[0], paths[1])
            else:
                self.an_viewer.show_pair(paths[0], paths[0])
            self.main_tabs.setCurrentIndex(2)

    # ----------------------------------------------------------------
    # 关于
    # ----------------------------------------------------------------
    def show_about(self):
        dialog = AboutDialog(self)
        dialog.exec_()

    def show_help(self):
        """显示使用说明对话框（可滚动，中英双语，内容与当前软件版本同步）。"""
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton

        # ── 中英双语帮助内容（学术风格，简洁无图标）──────────────────
        help_zh = """
<style>
  body { font-family: "Microsoft YaHei", "SimSun", Arial, sans-serif;
         font-size: 13px; color: #1a1a1a; line-height: 1.6; }
  h2   { font-size: 15px; font-weight: bold; color: #1a1a1a;
         border-bottom: 1px solid #888; padding-bottom: 3px; margin-bottom: 10px; }
  h3   { font-size: 13px; font-weight: bold; color: #1a1a1a;
         margin-top: 14px; margin-bottom: 4px; }
  p    { margin: 4px 0; }
  li   { margin: 2px 0; }
  code { font-family: Consolas, monospace; background: #f4f4f4;
         padding: 0 4px; border-radius: 2px; }
  table{ border-collapse: collapse; width: 100%; font-size: 12px; }
  th   { background: #f0f0f0; border: 1px solid #ccc; padding: 4px 8px;
         text-align: left; font-weight: bold; }
  td   { border: 1px solid #ddd; padding: 4px 8px; vertical-align: top; }
  .note{ border-left: 3px solid #555; padding: 4px 10px;
         background: #fafafa; margin: 6px 0; font-style: italic; color: #444; }
</style>

<h2>根系构型参数量化分析系统 — 使用说明 v@@VERSION@@</h2>

<h3>1. 操作流程</h3>
<p>本系统包含五个功能模块，推荐按以下顺序操作：</p>
<table>
  <tr><th width="28%">模块</th><th>操作说明</th></tr>
  <tr><td>图像预处理</td>
      <td>选择原始扫描图像目录及输出目录，调整分割参数，单张预览确认效果后批量处理全部图像</td></tr>
  <tr><td>图像擦除（可选）</td>
      <td>选择 binary/ 和 skeleton/ 目录，从下拉列表选择样本，左键拖动擦除噪声像素，保存修改</td></tr>
  <tr><td>根系构型分析</td>
      <td>选择二值化和骨架图像目录，点击刷新加载样本列表，分析当前样本或批量分析全部样本</td></tr>
  <tr><td>结果数据表</td>
      <td>浏览全部量化指标，点击"描述性统计"查看各指标统计摘要</td></tr>
  <tr><td>图表可视化</td>
      <td>选择指标、图表类型（箱线图/柱状图/散点图/小提琴图/直方图）及分组方式，绘图并保存</td></tr>
</table>

<h3>2. 文件命名规范</h3>
<p>所有图像文件名须遵循格式：<code>Year-Variety-Treatment-Replicate</code></p>
<p>示例：<code>2025-DH-P0-1.png</code>（年份-品种-处理-生物学重复）</p>
<p>命名规范是图表分组（按处理/品种/年份）和元信息自动解析的必要前提。</p>

<h3>3. 尺度与方向（@@VERSION@@）</h3>
<p>DPI=0 时读取元数据；缺失时只输出像素量。非零值显式覆盖元数据，标记 user_supplied。文件名中的 600 不是校准记录。</p>
<p>选择根基部方向，默认在上。黑线模拟图使用 line_art 预处理。黄色为根基部，不计根尖；交叉按连续路径恢复。unresolved 表示需复核，TI/Strahler 不输出确定值。</p>
<p>人工根冠区域保存在 .png.review.json 中并随结果注明；多重分形 Check scales 表示有限尺度拟合需检查。</p>

<h3>4. 量化指标与质量诊断</h3>
<table>
  <tr><th width="30%">类别</th><th>指标</th></tr>
  <tr><td>分形参数</td><td>分形维数 (FD)、分形丰度 (FA)</td></tr>
  <tr><td>多重分形谱</td><td>容量维 D(0)、信息维 D(1)、关联维 D(2)、奇异谱宽 Δα、对称性 Δf</td></tr>
  <tr><td>形态参数</td><td>根长、根表面积、平均直径、根体积、根尖数、分支数、交叉数、平均分支角</td></tr>
  <tr><td>密度与结构</td><td>根尖密度、分枝密度、平均链接长度</td></tr>
  <tr><td>拓扑指数</td><td>拓扑指数 TI、拓扑高度 Altitude、拓扑量级 Magnitude</td></tr>
  <tr><td>Strahler 级序</td><td>最大级序、分叉比 R<sub>b</sub>、长度比 R<sub>l</sub></td></tr>
</table>

<h3>5. 数据导出</h3>
<p><b>量化结果：</b>文件 → 导出 Excel（UTF-8 编码 CSV，可直接在 Excel 中打开）</p>
<p><b>图表：</b>图表可视化 → 保存图表（支持 PNG、SVG、PDF、TIFF，300 DPI）</p>

<h3>6. 快捷键</h3>
<table>
  <tr><th width="30%">快捷键</th><th>功能</th></tr>
  <tr><td>F1</td><td>打开本帮助页面</td></tr>
  <tr><td>Ctrl+Z</td><td>图像擦除模块：撤销上一步操作</td></tr>
  <tr><td>Ctrl+O</td><td>打开 CSV 结果文件</td></tr>
  <tr><td>Ctrl+S</td><td>另存当前结果为 CSV</td></tr>
  <tr><td>Ctrl+Q</td><td>退出程序</td></tr>
</table>
"""
        help_en = """
<style>
  body { font-family: Arial, sans-serif; font-size: 13px;
         color: #1a1a1a; line-height: 1.6; }
  h2   { font-size: 15px; font-weight: bold; color: #1a1a1a;
         border-bottom: 1px solid #888; padding-bottom: 3px; margin-bottom: 10px; }
  h3   { font-size: 13px; font-weight: bold; color: #1a1a1a;
         margin-top: 14px; margin-bottom: 4px; }
  p    { margin: 4px 0; }
  li   { margin: 2px 0; }
  code { font-family: Consolas, monospace; background: #f4f4f4;
         padding: 0 4px; border-radius: 2px; }
  table{ border-collapse: collapse; width: 100%; font-size: 12px; }
  th   { background: #f0f0f0; border: 1px solid #ccc; padding: 4px 8px;
         text-align: left; font-weight: bold; }
  td   { border: 1px solid #ddd; padding: 4px 8px; vertical-align: top; }
  .note{ border-left: 3px solid #555; padding: 4px 10px;
         background: #fafafa; margin: 6px 0; font-style: italic; color: #444; }
</style>

<h2>Root Architecture Quantification System — User Manual v@@VERSION@@</h2>

<h3>1. Workflow</h3>
<p>The system contains five functional modules. The recommended workflow is:</p>
<table>
  <tr><th width="28%">Module</th><th>Description</th></tr>
  <tr><td>Image Preprocessing</td>
      <td>Select raw image directory and output directory, adjust segmentation parameters,
          preview a single image, then batch process all images.</td></tr>
  <tr><td>Image Erasing (optional)</td>
      <td>Select binary/ and skeleton/ directories, choose a sample from the dropdown,
          left-drag to erase noise pixels, then save changes.</td></tr>
  <tr><td>Root Architecture Analysis</td>
      <td>Select binary and skeleton directories, click Refresh to load the sample list,
          then analyze the current sample or batch-analyze all samples.</td></tr>
  <tr><td>Results Table</td>
      <td>Browse all quantification metrics. Click "Descriptive Statistics" for a
          statistical summary of all indicators.</td></tr>
  <tr><td>Chart Visualization</td>
      <td>Select a metric, chart type (Boxplot / Bar / Scatter / Violin / Histogram),
          and grouping variable, then plot and save the chart.</td></tr>
</table>

<h3>2. File Naming Convention</h3>
<p>All image filenames must follow the format: <code>Year-Variety-Treatment-Replicate</code></p>
<p>Example: <code>2025-DH-P0-1.png</code> (year-variety-treatment-replicate)</p>
<p>This naming convention is required for chart grouping and automatic metadata parsing.</p>

<h3>3. Scale and root direction (@@VERSION@@)</h3>
<p>DPI=0 reads metadata; missing calibration keeps measurements in pixels. An explicit DPI overrides metadata and is labelled user_supplied. Filenames do not establish calibration.</p>
<p>Select the crown direction (top by default). Use line_art for black-line drawings. The yellow base is excluded from tips. Crossings reconnect continuous paths. Unresolved graphs do not receive TI or Strahler values.</p>
<p>Manual crown rectangles are recorded in .png.review.json sidecars. Check scales indicates uncertain finite-scale multifractal fits.</p>

<h3>4. Quantification metrics and quality diagnostics</h3>
<table>
  <tr><th width="30%">Category</th><th>Metrics</th></tr>
  <tr><td>Fractal</td><td>Fractal Dimension (FD), Fractal Abundance (FA)</td></tr>
  <tr><td>Multifractal spectrum</td>
      <td>Capacity D(0), Information D(1), Correlation D(2), Spectrum width Δα, Symmetry Δf</td></tr>
  <tr><td>Morphology</td>
      <td>Root Length, Surface Area, Avg Diameter, Volume, Num Tips, Num Forks,
          Num Crossings, Avg Branch Angle</td></tr>
  <tr><td>Density &amp; structure</td>
      <td>Tip Density, Branch Density, Avg Link Length</td></tr>
  <tr><td>Topology</td>
      <td>Topological Index TI, Altitude, Magnitude</td></tr>
  <tr><td>Strahler Order</td>
      <td>Max Order, Bifurcation Ratio R<sub>b</sub>, Length Ratio R<sub>l</sub></td></tr>
</table>

<h3>5. Data Export</h3>
<p><b>Quantification results:</b> File → Export Excel (UTF-8 CSV, opens directly in Excel)</p>
<p><b>Charts:</b> Chart Visualization → Save Chart (PNG, SVG, PDF, or TIFF at 300 DPI)</p>

<h3>6. Keyboard Shortcuts</h3>
<table>
  <tr><th width="30%">Shortcut</th><th>Action</th></tr>
  <tr><td>F1</td><td>Open this help page</td></tr>
  <tr><td>Ctrl+Z</td><td>Image Erasing: undo last operation</td></tr>
  <tr><td>Ctrl+O</td><td>Open CSV results file</td></tr>
  <tr><td>Ctrl+S</td><td>Save current results as CSV</td></tr>
  <tr><td>Ctrl+Q</td><td>Quit the application</td></tr>
</table>
"""
        # ── 对话框 ────────────────────────────────────────────────────
        dlg = QDialog(self)
        dlg.setWindowTitle(tr('help_title'))
        dlg.resize(680, 620)
        dlg.setMinimumSize(500, 400)

        vbox = QVBoxLayout(dlg)
        vbox.setContentsMargins(10, 10, 10, 8)
        vbox.setSpacing(6)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setStyleSheet('border: 1px solid #ddd; border-radius: 4px; padding: 6px;')
        browser.setHtml((help_zh if _LANG[0] == 'zh' else help_en).replace('@@VERSION@@', APP_VERSION))
        vbox.addWidget(browser, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton(tr('about_close'))
        close_btn.setMinimumSize(100, 32)
        close_btn.setDefault(True)
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(close_btn)
        vbox.addLayout(btn_row)

        dlg.exec_()


# ============================================================================
# 入口
# ============================================================================

def main():
    """直接运行 root_gui.py 时的入口（不含启动画面）。
    编译版本请使用 launcher.py 作为入口，splash 在 launcher 中实现。
    """
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    font = QFont()
    font.setPointSize(10)
    app.setFont(font)
    app.setStyleSheet(LIGHT_QSS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())



if __name__ == '__main__':
    main()

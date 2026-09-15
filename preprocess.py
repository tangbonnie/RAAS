#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根系图像预处理脚本：原始图 → 二值化图 + 骨架图
Root Image Preprocessing: Raw → Binary + Skeleton

支持多种分割方法:
  1. multiscale — 多尺度分块自适应法 (推荐，适合粗细不均根系)
                  双尺度纹理特征融合 + 分块局部 Otsu + 软投票，
                  能同时保留粗主根和细侧根，对光照不均匀的扫描图像
                  鲁棒性更好。
  2. texture  — 单尺度纹理法 (传统方法)
  3. otsu     — Otsu 全局阈值 (适合前景/背景对比明显的图像)
  4. adaptive — 自适应阈值 (适合光照渐变的图像)

Usage:
    python preprocess.py -i ./2025-raw -o ./2025-processed
    python preprocess.py -i ./raw -o ./output --method otsu
    python preprocess.py -h

Software author: 唐清芸（石河子大学农学院；新疆农垦科学院）
Copyright: 王国栋（新疆农垦科学院）
"""

import os
import sys
import glob
import argparse
import warnings
import numpy as np
from skimage import io, filters, morphology, color, util
from skimage.morphology import disk, remove_small_objects, remove_small_holes
from scipy import ndimage



# ============================================================================
# 边框检测与移除
# ============================================================================

def detect_scanner_border(gray, dark_thresh=0.25, bright_thresh=0.92,
                           dilate_iter=10):
    """
    检测并移除扫描仪边框（同时处理黑色暗边和拍摄曝光亮边）。

    策略1 — 暗边: 找灰度 < dark_thresh 且与图像四边连通的暗色区域
    策略2 — 亮边: 找灰度 > bright_thresh 且与图像四边连通的过亮区域
                  （常见于相机拍摄时四周的曝光残留 / 白色背景过渡带）
    两类遮罩合并后膨胀，作为最终边框遮罩。

    Parameters
    ----------
    gray : ndarray (float, 0-1)
        灰度图像
    dark_thresh : float
        暗边阈值（默认 0.25）
    bright_thresh : float
        亮边阈值（默认 0.92），调低可移除更多亮边，调高则更保守
    dilate_iter : int
        遮罩膨胀迭代次数

    Returns
    -------
    border_mask : ndarray (bool)
        True = 边框区域（应排除）
    """
    h, w = gray.shape
    combined_mask = np.zeros((h, w), dtype=bool)

    for pixel_mask in (gray < dark_thresh, gray > bright_thresh):
        if not np.any(pixel_mask):
            continue
        labeled, _ = ndimage.label(pixel_mask)
        edge_labels = set()
        edge_labels.update(labeled[0, :].tolist())
        edge_labels.update(labeled[-1, :].tolist())
        edge_labels.update(labeled[:, 0].tolist())
        edge_labels.update(labeled[:, -1].tolist())
        edge_labels.discard(0)
        if edge_labels:
            combined_mask |= np.isin(labeled, list(edge_labels))

    if not np.any(combined_mask):
        return combined_mask

    # 膨胀以覆盖边框过渡区
    return ndimage.binary_dilation(combined_mask, iterations=dilate_iter)


# ============================================================================
# 分割方法
# ============================================================================

def segment_texture(gray, window_size=25, border_mask=None):
    """
    局部纹理法分割 (推荐用于扫描仪根系图像)。

    原理: 根系区域的局部灰度标准差远高于均匀背景。
    通过计算每个像素邻域的灰度方差，提取高纹理区域作为根系。

    同时结合局部对比度（像素比局部均值暗的程度），提高对粗根的
    召回率。

    Parameters
    ----------
    gray : ndarray (float, 0-1)
        灰度图像
    window_size : int
        纹理计算窗口大小（像素）。越大越能捕获粗根，但可能引入背景噪声。
        推荐: 小根系 15-25, 大根系 25-51
    border_mask : ndarray (bool) or None
        边框遮罩

    Returns
    -------
    binary : ndarray (bool)
        True = 根系前景
    """
    w = window_size

    # 局部均值和方差 (快速均匀滤波)
    local_mean = ndimage.uniform_filter(gray, size=w)
    local_sq = ndimage.uniform_filter(gray ** 2, size=w)
    local_var = np.clip(local_sq - local_mean ** 2, 0, None)
    local_std = np.sqrt(local_var)

    # 局部对比度: 像素比局部均值暗的程度
    intensity_diff = np.clip(local_mean - gray, 0, None)

    # 组合特征: 纹理(0.6) + 对比度(0.4)
    feature = local_std * 0.6 + intensity_diff * 0.4
    fmax = feature.max()
    if fmax > 0:
        feature = feature / fmax

    # Otsu 阈值
    valid = feature[feature > 0.005]
    if len(valid) == 0:
        return np.zeros_like(gray, dtype=bool)
    thresh = filters.threshold_otsu(valid)
    binary = feature > thresh

    # 移除边框
    if border_mask is not None:
        binary[border_mask] = False

    return binary


def segment_otsu(gray, border_mask=None, foreground='auto'):
    """
    Otsu 全局阈值二值化。

    适合前景/背景灰度分离明显的图像（如黑色背景上的白色根系）。

    Parameters
    ----------
    gray : ndarray (float, 0-1)
    border_mask : ndarray (bool) or None
    foreground : {'auto', 'dark', 'light'}, default 'auto'
        前景极性指定:
          'auto'  - 自动判定 (边缘均值 vs 中心均值; 边缘亮 → 根系暗).
                    对于纯背景 + 稀疏前景 (如铜丝模体、合成图像)
                    可能因边缘/中心差异过小而误判, 建议此类图像显式
                    传 'dark' 或 'light'.
          'dark'  - 强制: 前景 = gray < thresh (亮背景, 暗根系/暗物体).
          'light' - 强制: 前景 = gray > thresh (暗背景, 亮根系).

    Returns
    -------
    binary : ndarray (bool)
    """
    # 排除边框区域计算阈值
    if border_mask is not None:
        vals = gray[~border_mask]
    else:
        vals = gray.ravel()

    # 白背景图像 border_mask 可能覆盖几乎全部像素，vals 过少会使 threshold_otsu 崩溃
    if len(vals) < 10:
        vals = gray.ravel()

    thresh = filters.threshold_otsu(vals)

    if foreground == 'dark':
        binary = gray < thresh
    elif foreground == 'light':
        binary = gray > thresh
    else:
        # 'auto' — 判断前景方向: 边缘亮 → 根系暗; 边缘暗 → 根系亮
        h, w = gray.shape
        margin = max(h, w) // 20
        edge_mean = np.mean([
            gray[:margin, :].mean(),
            gray[-margin:, :].mean(),
            gray[:, :margin].mean(),
            gray[:, -margin:].mean()
        ])
        center_mean = gray[h//4:3*h//4, w//4:3*w//4].mean()

        if edge_mean > center_mean:
            # 背景亮, 根系暗
            binary = gray < thresh
        else:
            # 背景暗, 根系亮
            binary = gray > thresh

    if border_mask is not None:
        binary[border_mask] = False

    return binary


def segment_adaptive(gray, block_size=51, offset=10, border_mask=None,
                     foreground='auto'):
    """
    自适应 (局部) 阈值二值化。

    Parameters
    ----------
    gray : ndarray (float, 0-1)
    block_size : int
        局部窗口大小（奇数）
    offset : int
        阈值偏移量
    border_mask : ndarray (bool) or None
    foreground : {'auto', 'dark', 'light'}, default 'auto'
        见 segment_otsu 的同名参数说明.

    Returns
    -------
    binary : ndarray (bool)
    """
    img_uint8 = util.img_as_ubyte(gray)
    thresh = filters.threshold_local(img_uint8, block_size=block_size, offset=offset)

    if foreground == 'dark':
        binary = img_uint8 < thresh
    elif foreground == 'light':
        binary = img_uint8 > thresh
    else:
        # 自动检测前景方向
        h, w = gray.shape
        margin = max(h, w) // 20
        edge_mean = np.mean([
            gray[:margin, :].mean(), gray[-margin:, :].mean(),
            gray[:, :margin].mean(), gray[:, -margin:].mean()
        ])
        center_mean = gray[h//4:3*h//4, w//4:3*w//4].mean()

        if edge_mean > center_mean:
            binary = img_uint8 < thresh
        else:
            binary = img_uint8 > thresh

    if border_mask is not None:
        binary[border_mask] = False

    return binary


# ============================================================================
# 后处理与骨架化
# ============================================================================

def postprocess_binary(binary, min_size=500, hole_size=200, close_radius=3):
    """
    二值化后处理: 闭运算 → 去小对象 → 填小孔。

    Parameters
    ----------
    binary : ndarray (bool)
    min_size : int
        移除面积小于此值的小连通域 (像素数)
    hole_size : int
        填充面积小于此值的孔洞
    close_radius : int
        闭运算结构元素半径 (连接断裂根段, 0=不执行)

    Returns
    -------
    cleaned : ndarray (bool)
    """
    if close_radius > 0:
        cleaned = morphology.binary_closing(binary, footprint=disk(close_radius))
    else:
        cleaned = binary.copy()

    cleaned = remove_small_objects(cleaned, min_size=min_size)
    cleaned = remove_small_holes(cleaned, area_threshold=hole_size)

    return cleaned


def compute_skeleton(binary):
    """骨架化 (形态学细化为单像素宽的中轴线)"""
    return morphology.skeletonize(binary)


# ============================================================================
# 多尺度分块自适应分割
# ============================================================================

def segment_multiscale(gray, window_size=25, tile_size=None,
                        tile_overlap_ratio=0.25, border_mask=None):
    """
    多尺度分块自适应分割 —— 专为粗细不均根系设计。

    相比单尺度纹理法的改进:
    ┌──────────────────────────────────────────────────────────────────┐
    │ 1. 双尺度特征融合                                                 │
    │    细窗口 (window_size // 3) → 检测细侧根（纹理响应弱但确实存在）  │
    │    粗窗口 (window_size)      → 检测主根 / 粗根                   │
    │    取逐像素最大值，相当于 OR：两个尺度任意一个检测到即保留         │
    │                                                                  │
    │ 2. 分块局部 Otsu                                                  │
    │    图像切成重叠小块（默认边长=图像短边 1/5, 最小 256 px）         │
    │    每块内独立计算 Otsu 阈值                                       │
    │    → 适应扫描仪各区域的亮度/对比度差异                            │
    │    → 根密集区和稀疏区分别自适应，不互相拉偏                       │
    │                                                                  │
    │ 3. 软投票融合（消除拼接缝）                                       │
    │    重叠区多块投票：≥40% 的覆盖块判为前景 → 当前像素为根系         │
    └──────────────────────────────────────────────────────────────────┘

    Parameters
    ----------
    gray : ndarray (float, 0-1)
        灰度图像
    window_size : int
        粗尺度纹理窗口（主根 / 粗根），建议 20-51。
        细尺度自动设为 max(5, window_size // 3)。
    tile_size : int or None
        分块边长（像素）。None = 自动（图像短边的 1/5，最小 256）
    tile_overlap_ratio : float
        相邻块重叠比例，0.25 表示重叠 25%
    border_mask : ndarray (bool) or None

    Returns
    -------
    binary : ndarray (bool)
    """
    h, w = gray.shape

    # ── 1. 双尺度纹理特征 ──────────────────────────────────────────
    fine_win   = max(5, window_size // 3)
    coarse_win = window_size

    def _texture_feat(g, win):
        lm  = ndimage.uniform_filter(g, size=win)
        lsq = ndimage.uniform_filter(g ** 2, size=win)
        lv  = np.clip(lsq - lm ** 2, 0, None)
        ls  = np.sqrt(lv)
        di  = np.clip(lm - g, 0, None)
        f   = ls * 0.6 + di * 0.4
        mx  = f.max()
        return (f / mx) if mx > 1e-10 else f

    feature = np.maximum(
        _texture_feat(gray, fine_win),
        _texture_feat(gray, coarse_win),
    )

    if border_mask is not None:
        feature[border_mask] = 0.0

    # ── 2. 自动 tile 尺寸 ──────────────────────────────────────────
    if tile_size is None:
        tile_size = max(256, min(h, w) // 5)
    tile_size = min(tile_size, h, w)
    overlap   = max(32, int(tile_size * tile_overlap_ratio))
    step      = max(1, tile_size - overlap)

    def _starts(length, size, step):
        pts = list(range(0, length - size, step))
        pts.append(length - size)        # 最后一块贴紧右/下边界
        return sorted(set(max(0, p) for p in pts))

    y_starts = _starts(h, tile_size, step)
    x_starts = _starts(w, tile_size, step)

    # ── 3. 分块 Otsu + 软投票 ──────────────────────────────────────
    vote_sum = np.zeros((h, w), dtype=np.float32)
    vote_cnt = np.zeros((h, w), dtype=np.float32)

    for y0 in y_starts:
        y1 = y0 + tile_size
        for x0 in x_starts:
            x1 = x0 + tile_size

            tile_feat = feature[y0:y1, x0:x1]
            valid = tile_feat[tile_feat > 0.005].ravel()

            vote_cnt[y0:y1, x0:x1] += 1.0
            if len(valid) < 200:
                # 近乎全背景的块：不投票为前景
                continue

            # 局部 Otsu，略低于默认阈值以保留细根
            thresh = filters.threshold_otsu(valid) * 0.88
            vote_sum[y0:y1, x0:x1] += (tile_feat > thresh).astype(np.float32)

    # ≥ 40% 覆盖块投票为前景 → 判为根系
    with np.errstate(invalid='ignore', divide='ignore'):
        ratio = np.where(vote_cnt > 0, vote_sum / vote_cnt, 0.0)
    binary = ratio >= 0.40

    if border_mask is not None:
        binary[border_mask] = False

    return binary


# ============================================================================
# 边缘噪声移除
# ============================================================================

def remove_border_objects(binary, border_margin=20, size_ratio_threshold=0.10):
    """
    移除与图像边缘相连的噪声连通域（大尺寸组件受保护）。

    原理: 扫描根系图像中，根系始终放置在画面中央，不接触四周边框。
    因此，落在边缘带内的小连通域均视为边框噪声。

    重要: 为防止根系密集时大连通域触碰边缘被误删，增加了尺寸保护：
    只有面积 < size_ratio_threshold × 总前景面积 的组件才会被删除，
    大组件（主根系）即使触碰边缘也会被保留。

    Parameters
    ----------
    binary : ndarray (bool)
    border_margin : int
        边缘检测宽度（像素），默认 20
    size_ratio_threshold : float
        组件面积超过 (size_ratio_threshold × 总前景面积) 则不删除，默认 0.10

    Returns
    -------
    cleaned : ndarray (bool)
    """
    if not np.any(binary):
        return binary

    margin = max(0, int(border_margin))
    h, w = binary.shape
    total_fg = int(binary.sum())
    if total_fg == 0:
        return binary

    max_removable = total_fg * size_ratio_threshold

    labeled, n = ndimage.label(binary)
    if n == 0:
        return binary

    # 构建边缘带掩膜
    edge_mask = np.zeros((h, w), dtype=bool)
    if margin == 0:
        edge_mask[0, :] = True; edge_mask[-1, :] = True
        edge_mask[:, 0] = True; edge_mask[:, -1] = True
    else:
        edge_mask[:margin, :]  = True; edge_mask[-margin:, :] = True
        edge_mask[:, :margin]  = True; edge_mask[:, -margin:] = True

    border_labels = set(labeled[edge_mask].ravel())
    border_labels.discard(0)
    if not border_labels:
        return binary

    # 计算各组件面积，只删除小组件
    sizes = np.bincount(labeled.ravel())
    to_remove = [l for l in border_labels if sizes[l] <= max_removable]

    if not to_remove:
        return binary

    cleaned = binary.copy()
    cleaned[np.isin(labeled, to_remove)] = False
    return cleaned


def remove_isolated_noise(binary, main_size_fraction=0.02, isolation_distance=150):
    """
    用距离变换剔除远离主根系的散点噪声。

    算法:
    ┌──────────────────────────────────────────────────────────────────┐
    │ 1. 对所有连通域按面积排序                                         │
    │ 2. 大组件（面积 ≥ max_size × main_size_fraction）= 主根区域       │
    │ 3. 计算全图每个像素到「主根区域」最近前景像素的欧氏距离           │
    │    （scipy.ndimage.distance_transform_edt，高效）                 │
    │ 4. 小组件中，若其最近距离 > isolation_distance，则为孤立噪声删除  │
    └──────────────────────────────────────────────────────────────────┘

    Parameters
    ----------
    binary : ndarray (bool)
    main_size_fraction : float
        面积 ≥ (最大组件面积 × main_size_fraction) 的组件视为主根，
        默认 0.02（即最大组件面积的 2%）
    isolation_distance : int
        小组件距最近主根像素超过此距离（像素）则视为孤立噪声删除，
        默认 150 px（300 DPI ≈ 1.27 cm）

    Returns
    -------
    cleaned : ndarray (bool)
    """
    if not np.any(binary):
        return binary

    labeled, n = ndimage.label(binary)
    if n == 0:
        return binary

    sizes = np.bincount(labeled.ravel())  # index 0 = background
    comp_sizes = sizes[1:]                # sizes of labels 1..n
    if len(comp_sizes) == 0:
        return binary

    max_size = comp_sizes.max()
    main_threshold = max_size * main_size_fraction

    # 主根组件标签集合
    main_labels = set(np.where(comp_sizes >= main_threshold)[0] + 1)
    small_labels = set(range(1, n + 1)) - main_labels

    if not small_labels:
        return binary

    # 距离变换：每个像素到最近主根像素的距离
    main_mask = np.isin(labeled, list(main_labels))
    dist = ndimage.distance_transform_edt(~main_mask)

    cleaned = binary.copy()
    for lbl in small_labels:
        comp = labeled == lbl
        # 若组件内所有像素都远离主根，则删除
        if dist[comp].min() > isolation_distance:
            cleaned[comp] = False

    return cleaned


# ============================================================================
# 批处理
# ============================================================================

def find_raw_images(input_dirs,
                    extensions=('*.tif', '*.tiff', '*.jpg', '*.jpeg', '*.png', '*.bmp')):
    """查找输入目录中的所有图像文件。"""
    all_files = []
    for d in input_dirs:
        for ext in extensions:
            all_files.extend(glob.glob(os.path.join(d, ext)))
            all_files.extend(glob.glob(os.path.join(d, ext.upper())))

    raw_files = list(all_files)

    return sorted(set(raw_files))


def process_single_image(img_path, output_dir, method='multiscale',
                          window_size=25, block_size=51, offset=10,
                          min_size=500, hole_size=200, close_radius=3,
                          bright_thresh=0.92, border_margin=20,
                          isolation_distance=150, foreground='auto',
                          dpi=None, intensity_low_ratio=0.8,
                          pixel_hole_area=0, pixel_hole_connectivity=8):
    """
    处理单张图像: 分割 → 后处理 → 骨架化 → 保存。

    Returns
    -------
    binary_path, skeleton_path : str
    """
    basename = os.path.splitext(os.path.basename(img_path))[0]
    for suffix in ['-rgb', '_rgb', '-raw', '_raw', '-original', '_original']:
        if basename.lower().endswith(suffix):
            basename = basename[:len(basename) - len(suffix)]
            break

    binary_dir = os.path.join(output_dir, 'binary')
    skeleton_dir = os.path.join(output_dir, 'skeleton')
    os.makedirs(binary_dir, exist_ok=True)
    os.makedirs(skeleton_dir, exist_ok=True)

    # 加载并转灰度，同时用 PIL 读取原始 DPI 元数据以便输出时写回.
    # 调用者可通过显式 dpi= 覆盖 (对无 DPI 元数据的 JPEG / 合成图
    # 如 WinRHIZO simulation 数据集, 必须显式传入才能正确换算 px↔cm).
    from PIL import Image as _PilImage
    from calibration import image_scale
    from PIL.PngImagePlugin import PngInfo
    source_dpi, source_kind = image_scale(img_path, override=dpi)
    scale_info = PngInfo()
    scale_info.add_text('Scale_Source', source_kind)
    save_scale = {'pnginfo': scale_info}
    if source_dpi is not None:
        save_scale['dpi'] = (source_dpi, source_dpi)

    img = io.imread(img_path)
    if img.ndim == 3:
        gray = color.rgb2gray(img)   # rgb2gray 已处理 uint8/uint16，输出 float64 [0,1]
    else:
        # 灰度图：uint8 ÷255，uint16 ÷65535，其他整数除以类型最大值
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

    if method in ('line_art','intensity'):
        if method=='line_art':
            binary = gray < (128 / 255)
        else:
            from root_segmentation import segment_root_intensity
            binary,segmentation_info=segment_root_intensity(gray,foreground=foreground,
                                                           low_ratio=intensity_low_ratio)
            import json
            scale_info.add_text('Segmentation',json.dumps(segmentation_info))
        if pixel_hole_area>0:
            from root_crown import repair_microholes
            binary,hole_info=repair_microholes(binary,max_area=pixel_hole_area,
                                                background_connectivity=pixel_hole_connectivity)
            import json
            scale_info.add_text('Pixel_Hole_Repair',json.dumps({k:v for k,v in hole_info.items() if k!='repairs'}))
        skeleton = compute_skeleton(binary)
        binary_path = os.path.join(binary_dir, f'{basename}.png')
        skeleton_path = os.path.join(skeleton_dir, f'{basename}.png')
        _PilImage.fromarray(binary.astype(np.uint8)*255).save(binary_path, 'PNG', **save_scale)
        _PilImage.fromarray(skeleton.astype(np.uint8)*255).save(skeleton_path, 'PNG', **save_scale)
        return binary_path, skeleton_path

    # 检测边框（暗边 + 拍摄曝光亮边）
    border_mask = detect_scanner_border(gray, bright_thresh=bright_thresh)

    # 分割
    if method == 'multiscale':
        # multiscale/texture 基于纹理特征, 内部已假设"暗前景/亮背景",
        # 对 foreground 参数不敏感, 忽略之.
        binary = segment_multiscale(gray, window_size=window_size,
                                     border_mask=border_mask)
    elif method == 'texture':
        binary = segment_texture(gray, window_size=window_size,
                                  border_mask=border_mask)
    elif method == 'otsu':
        binary = segment_otsu(gray, border_mask=border_mask,
                              foreground=foreground)
    elif method == 'adaptive':
        binary = segment_adaptive(gray, block_size=block_size,
                                   offset=offset, border_mask=border_mask,
                                   foreground=foreground)
    else:
        raise ValueError(f"Unknown method: {method}")

    # 后处理
    binary = postprocess_binary(binary, min_size=min_size,
                                 hole_size=hole_size, close_radius=close_radius)

    # 移除边缘噪声（小组件触碰边缘 → 删除；大组件受保护）
    binary = remove_border_objects(binary, border_margin=border_margin)

    # 剔除远离主根系的散点噪声
    binary = remove_isolated_noise(binary, isolation_distance=isolation_distance)

    # 骨架化
    skeleton = compute_skeleton(binary)

    # 保存 (白色前景, 黑色背景)，用 PIL 写回原始 DPI 元数据
    binary_path   = os.path.join(binary_dir,   f'{basename}.png')
    skeleton_path = os.path.join(skeleton_dir, f'{basename}.png')
    _PilImage.fromarray(binary.astype(np.uint8) * 255,   mode='L').save(
        binary_path,   'PNG', **save_scale)
    _PilImage.fromarray(skeleton.astype(np.uint8) * 255, mode='L').save(
        skeleton_path, 'PNG', **save_scale)

    return binary_path, skeleton_path


# ============================================================================
# 命令行入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='根系图像预处理: 原始图 → 二值化 + 骨架 (Root Image Preprocessing)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
分割方法说明:
  multiscale  多尺度分块自适应法 (默认，推荐)。
              双尺度纹理 + 分块 Otsu + 软投票，粗细根均能保留。
  texture     单尺度纹理法。
  otsu        Otsu 全局阈值。适合前景/背景对比明显的图像。
  adaptive    自适应阈值。适合光照不均匀的图像。

使用示例:
  # 多尺度法 (推荐，粗细根均保留)
  python preprocess.py -i ./2025-raw -o ./2025-processed

  # 调整粗尺度窗口 (主根很粗时用大窗口)
  python preprocess.py -i ./raw -o ./output --window_size 51

  # 传统纹理法
  python preprocess.py -i ./raw -o ./output --method texture

  # 处理多个目录
  python preprocess.py -i ./2024-raw ./2025-raw -o ./processed

输出目录结构:
  <output_dir>/
  ├── binary/       # 二值化图像 (与样本同名, .png)
  └── skeleton/     # 骨架图像   (与样本同名, .png)

与分析脚本衔接:
  python root_analysis.py -b ./output/binary -s ./output/skeleton -o ./results
        """
    )
    parser.add_argument('-i', '--input_dirs', type=str, nargs='+', required=True,
                        help='原始图像目录 (可指定多个)')
    parser.add_argument('-o', '--output_dir', type=str, default='./processed',
                        help='输出目录 (默认: ./processed)')
    parser.add_argument('--method', type=str, default='multiscale',
                        choices=['multiscale', 'texture', 'otsu', 'adaptive', 'line_art', 'intensity'],
                        help='分割方法 (默认: multiscale)')
    parser.add_argument('--window_size', type=int, default=25,
                        help='纹理法窗口大小 (默认: 25, 仅 texture 方法; 粗根用 30-51)')
    parser.add_argument('--block_size', type=int, default=51,
                        help='自适应阈值窗口大小，须为奇数 (默认: 51, 仅 adaptive)')
    parser.add_argument('--offset', type=int, default=10,
                        help='自适应阈值偏移量 (默认: 10, 仅 adaptive)')
    parser.add_argument('--min_size', type=int, default=500,
                        help='去噪: 最小连通域面积 (默认: 500 像素)')
    parser.add_argument('--hole_size', type=int, default=200,
                        help='填孔: 最大孔洞面积 (默认: 200 像素)')
    parser.add_argument('--close_radius', type=int, default=3,
                        help='闭运算半径，连接断裂根段 (默认: 3, 0=不执行)')
    parser.add_argument('--border_margin', type=int, default=20,
                        help='边缘噪声移除宽度，像素 (默认: 20)')
    parser.add_argument('--isolation_distance', type=int, default=150,
                        help='散点噪声剔除距离，像素 (默认: 150，小组件距主根超过此距离则删除)')
    parser.add_argument('--foreground', choices=['auto', 'dark', 'light'],
                        default='auto',
                        help='前景极性 (仅 otsu/adaptive 有效): '
                             'auto=自动(默认,边缘vs中心比较), '
                             'dark=亮背景+暗根系, light=暗背景+亮根系. '
                             '对于稀疏前景 (铜丝模体、合成图像) 强烈建议显式指定.')

    args = parser.parse_args()

    for d in args.input_dirs:
        if not os.path.isdir(d):
            print(f"  错误: 目录不存在: {d}")
            sys.exit(1)

    print("=" * 70)
    print("  根系图像预处理")
    print("  Root Image Preprocessing")
    print("=" * 70)
    print(f"  输入目录:   {args.input_dirs}")
    print(f"  输出目录:   {args.output_dir}")
    print(f"  分割方法:   {args.method}")
    if args.method == 'texture':
        print(f"  纹理窗口:   {args.window_size} px")
    print(f"  最小面积:   {args.min_size} px")
    print(f"  闭运算半径: {args.close_radius} px")
    print("=" * 70)

    raw_files = find_raw_images(args.input_dirs)
    print(f"\n  找到 {len(raw_files)} 张原始图像")

    if len(raw_files) == 0:
        print("  错误: 未找到任何图像文件。")
        sys.exit(1)

    success = 0
    failed = []
    for i, fpath in enumerate(raw_files):
        fname = os.path.basename(fpath)
        print(f"  [{i+1}/{len(raw_files)}] {fname} ...", end=" ", flush=True)
        try:
            process_single_image(
                fpath, args.output_dir,
                method=args.method,
                window_size=args.window_size,
                block_size=args.block_size,
                offset=args.offset,
                min_size=args.min_size,
                hole_size=args.hole_size,
                close_radius=args.close_radius,
                border_margin=args.border_margin,
                isolation_distance=args.isolation_distance,
                foreground=args.foreground,
            )
            print("OK")
            success += 1
        except Exception as e:
            print(f"FAILED: {e}")
            failed.append((fname, str(e)))

    print("\n" + "=" * 70)
    print(f"  预处理完成: {success}/{len(raw_files)} 成功")
    if failed:
        print(f"  失败 {len(failed)} 张:")
        for fname, err in failed:
            print(f"    {fname}: {err}")
    print(f"\n  二值化图像: {os.path.join(args.output_dir, 'binary/')}")
    print(f"  骨架图像:   {os.path.join(args.output_dir, 'skeleton/')}")
    print(f"\n  下一步运行量化分析:")
    print(f"  python root_analysis.py "
          f"-b {os.path.join(args.output_dir, 'binary')} "
          f"-s {os.path.join(args.output_dir, 'skeleton')} -o ./results")
    print("=" * 70)


def _preprocess_worker_task(args):
    """
    顶层函数供 ProcessPoolExecutor 调用（必须可被 pickle 序列化）。
    每个子进程拥有独立的 Python 解释器和 GIL，实现真正的 CPU 并行。

    为兼容旧调用方 (12 元组), 若 args 长度为 12 则 foreground 默认 'auto'.
    """
    dpi = args[13] if len(args)==14 else None
    args = args[:13] if len(args)==14 else args
    if len(args) == 13:
        (fpath, output_dir, method, window_size, block_size, offset,
         min_size, hole_size, close_radius, bright_thresh,
         border_margin, isolation_distance, foreground) = args
    else:
        (fpath, output_dir, method, window_size, block_size, offset,
         min_size, hole_size, close_radius, bright_thresh,
         border_margin, isolation_distance) = args
        foreground = 'auto'
    process_single_image(
        fpath, output_dir,
        method=method,
        window_size=window_size,
        block_size=block_size,
        offset=offset,
        min_size=min_size,
        hole_size=hole_size,
        close_radius=close_radius,
        bright_thresh=bright_thresh,
        border_margin=border_margin,
        isolation_distance=isolation_distance,
        foreground=foreground, dpi=dpi,
    )
    return fpath


if __name__ == '__main__':
    main()

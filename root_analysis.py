#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Root architecture measurements from binary masks and skeletons.

Whole-root mode assumes the crown is at the top unless root_direction/base_rc
is supplied. Endpoints, forks and crossings are different biological concepts.
All rooted metrics use the same path-preserving resolved graph. Cyclic or
fragmented results are flagged and rooted indices are undefined.

Local normal-section widths are integrated along each path: surface=sum(pi*d*dl),
volume=sum(pi*d*d/4*dl), mean diameter=sum(d*dl)/sum(dl). Overlap paths are
inferred from continuity, not recovered ground truth. Measurements without
scale metadata or an explicit DPI remain in pixel units; cm/mm fields are NaN.
Strahler ratios count maximal connected same-order branches, not graph links.
See docs/TECHNICAL_METHODS.md for assumptions and validation scope.
"""

import os
import sys
import glob
import argparse
import warnings
import numpy as np
import pandas as pd
from scipy.stats import linregress
from skimage import io


# ============================================================================
# 配置参数
# ============================================================================

# 默认扫描分辨率 (DPI)，用于像素到物理单位的转换
# 常见根系扫描仪 (如 EPSON) 扫描分辨率为 300-600 DPI
DEFAULT_DPI = 300
# ============================================================================
# 工具函数
# ============================================================================

def _normalize_gray(img):
    """将任意灰度图像归一化到 float64 [0,1]。
    支持 uint8 (÷255), uint16 (÷65535), uint32 (÷4294967295),
    float32/64 (直接使用), bool (×1.0)。
    """
    if img.dtype == bool:
        return img.astype(np.float64)
    if img.dtype == np.uint8:
        return img.astype(np.float64) / 255.0
    if img.dtype == np.uint16:
        return img.astype(np.float64) / 65535.0
    if img.dtype == np.uint32:
        return img.astype(np.float64) / 4294967295.0
    if np.issubdtype(img.dtype, np.floating):
        arr = img.astype(np.float64)
        if arr.max() > 1.0:   # 安全兜底（理论上 float 应在 [0,1]）
            arr = arr / arr.max()
        return arr
    # 其他整数类型：除以该类型最大值
    info = np.iinfo(img.dtype)
    return img.astype(np.float64) / info.max


def load_binary_image(path):
    """加载二值化图像，返回布尔数组 (True=根系前景)。
    支持 JPEG/PNG/TIFF（8位、16位）、BMP 等常见格式。
    """
    img = io.imread(path, as_gray=True)
    img = _normalize_gray(img)
    # 自适应前景判断：白色像素占比 < 50% → 白色为前景
    if np.mean(img > 0.5) < 0.5:
        binary = img > 0.5
    else:
        binary = img < 0.5
    return binary.astype(bool)


def load_skeleton_image(path):
    """加载骨架图像，返回布尔数组 (True=骨架前景)。
    支持 JPEG/PNG/TIFF（8位、16位）、BMP 等常见格式。
    直接返回 PNG 骨架，不做 re-skeletonize（PNG 骨架已是单像素宽）。
    """
    img = io.imread(path, as_gray=True)
    img = _normalize_gray(img)
    if np.mean(img > 0.5) < 0.5:
        skeleton = img > 0.5
    else:
        skeleton = img < 0.5
    return skeleton.astype(bool)


def pixels_to_cm(pixels, dpi):
    """像素数转换为厘米"""
    return pixels * 2.54 / dpi


def pixel_area_to_cm2(pixel_count, dpi):
    """像素面积转换为平方厘米"""
    return pixel_count * (2.54 / dpi) ** 2


# ============================================================================
# 分形参数计算
# ============================================================================

def compute_fractal_dimension(binary_image, min_box=2, max_box_ratio=0.25, num_sizes=20):
    """
    盒计数法 (Box-counting) 计算分形维数、分形丰度和拟合优度。

    盒尺寸从 min_box 自适应地延伸至图像短边的 25%（最小 128 px），以 num_sizes 个
    对数均匀采样点构成。这样在 300 DPI 扫描图中盒尺寸可覆盖约 0.17–52 mm，完整
    捕获根系从细根到整体构型的多尺度分形自相似区间，与 ImageJ Fractal Box Count
    插件在全尺度使用时的范围一致，并显著扩展了原固定序列（上限 84 px = 7.1 mm）
    对粗尺度处理效应的检测能力。

    Parameters
    ----------
    binary_image : ndarray (bool)
        二值化图像
    min_box : int
        最小盒子边长（像素），默认 2
    max_box_ratio : float
        最大盒子边长占图像短边的比例，默认 0.25
    num_sizes : int
        盒子尺寸采样数，默认 20

    Returns
    -------
    FD : float
        分形维数 (Fractal Dimension)
    FA : float
        分形丰度 (Fractal Abundance)，log₁₀ 坐标下的截距
    FD_R2 : float
        log-log 线性回归的决定系数 R²，用于评估分形自相似性的拟合质量
    """
    # 获取前景像素坐标
    pixels = np.argwhere(binary_image)
    if len(pixels) == 0:
        return np.nan, np.nan, np.nan

    # 自适应盒尺寸：从 min_box 到图像短边的 25%（至少 128 px）
    # 确保在 300 DPI 时上限 ≥ 128 px（约 10.8 mm），实际 A4 图像上限 ~600 px（约 50 mm）
    h, w = binary_image.shape
    max_box = max(int(min(h, w) * max_box_ratio), 128)
    max_box = min(max_box, min(h, w) // 2)   # 上限不超过图像短边的一半

    box_sizes = np.unique(
        np.round(
            np.logspace(np.log10(min_box), np.log10(max_box), num=num_sizes)
        ).astype(int)
    )
    box_sizes = box_sizes[box_sizes >= min_box]

    if len(box_sizes) < 4:
        return np.nan, np.nan, np.nan

    min_coords = pixels.min(axis=0)

    counts = []
    valid_sizes = []
    for box_size in box_sizes:
        # 将像素坐标映射到网格
        grid_coords = (pixels - min_coords) // box_size
        # 统计非空网格数
        n_boxes = len(np.unique(grid_coords, axis=0))
        if n_boxes >= 2:             # 排除退化点（只有单个网格）
            counts.append(n_boxes)
            valid_sizes.append(box_size)

    if len(valid_sizes) < 4:
        return np.nan, np.nan, np.nan

    counts = np.array(counts, dtype=float)
    valid_sizes = np.array(valid_sizes, dtype=float)

    # 线性回归: log(N) = FD * log(1/ε) + log(FA)
    log_inv_eps = np.log(1.0 / valid_sizes)
    log_N = np.log(counts)

    slope, intercept, r_value, p_value, std_err = linregress(log_inv_eps, log_N)

    FD = slope                          # 分形维数
    FA = intercept / np.log(10)         # 分形丰度 = log₁₀ 坐标下的截距，与 WinRHIZO 惯例一致
    FD_R2 = r_value ** 2               # 决定系数，≥0.99 表示良好的分形自相似性

    return FD, FA, FD_R2


def compute_multifractal_spectrum(binary_image, q_range=(-10, 10), q_num=41,
                                  min_box=2, max_box_ratio=0.25, num_sizes=15):
    """
    多重分形分析 (Multifractal Analysis)。

    计算广义维数谱 D(q) 和奇异谱 f(α)。

    Parameters
    ----------
    binary_image : ndarray (bool)
        二值化图像
    q_range : tuple
        q 值范围 (q_min, q_max)
    q_num : int
        q 值采样数
    min_box : int
        最小盒子尺寸
    max_box_ratio : float
        最大盒子尺寸占图像短边的比例
    num_sizes : int
        盒子尺寸采样数

    Returns
    -------
    mf_results : dict
        包含:
        - D0: 容量维数 (Capacity Dimension, q=0)
        - D1: 信息维数 (Information Dimension, q=1)
        - D2: 关联维数 (Correlation Dimension, q=2)
        - Delta_alpha: 奇异谱宽 α_max - α_min
        - Delta_f: 奇异谱对称性 f(α_min) - f(α_max)
        - alpha_0: q=0 对应的 α 值（最可能奇异指数）
        - f_alpha_0: q=0 对应的 f(α) 值
        - q_values, Dq, alpha, f_alpha: 完整谱数据
    """
    pixels = np.argwhere(binary_image)
    if len(pixels) == 0:
        return {
            'D0': np.nan, 'D1': np.nan, 'D2': np.nan,
            'Delta_alpha': np.nan, 'Delta_f': np.nan,
            'alpha_0': np.nan, 'f_alpha_0': np.nan,
        }

    min_coords = pixels.min(axis=0)
    max_coords = pixels.max(axis=0)
    sizes = max_coords - min_coords + 1

    max_box = max(int(min(sizes) * max_box_ratio), min_box + 1)
    box_sizes = np.logspace(np.log10(min_box), np.log10(max_box),
                            num=num_sizes)
    box_sizes = np.rint(box_sizes).astype(int)
    box_sizes = np.unique(box_sizes)
    box_sizes = box_sizes[box_sizes >= min_box]

    if len(box_sizes) < 3:
        return {
            'D0': np.nan, 'D1': np.nan, 'D2': np.nan,
            'Delta_alpha': np.nan, 'Delta_f': np.nan,
            'alpha_0': np.nan, 'f_alpha_0': np.nan,
        }

    # 对每个盒子尺寸，计算每个网格中的像素概率
    N_total = len(pixels)
    q_values = np.linspace(q_range[0], q_range[1], q_num)

    # 预计算: 每个盒子尺寸下各网格的概率分布
    log_eps = np.log(box_sizes.astype(float))

    # 配分函数 χ(q, ε) 对每个 q 和 ε
    # chi[q_idx, eps_idx] = sum_i mu_i^q
    chi = np.zeros((len(q_values), len(box_sizes)))
    alpha_fit = np.zeros_like(chi)
    from scipy.special import logsumexp

    for j, box_size in enumerate(box_sizes):
        # 将像素映射到网格
        grid_coords = (pixels - min_coords) // box_size
        # 统计每个网格中的像素数
        # 使用 np.unique 沿第 0 轴直接对 (row, col) 元组去重，避免手工一维
        # 哈希（如 row*M+col）在 box_size=1 或极端尺寸下可能的碰撞/溢出风险，
        # 与盒计数 FD (compute_fractal_dimension) 中的计数方式保持一致。
        _, counts = np.unique(grid_coords, axis=0, return_counts=True)
        mu = counts / N_total  # 概率分布

        log_mu = np.log(mu)
        for i, q in enumerate(q_values):
            log_partition = logsumexp(q * log_mu)
            weights = np.exp(q * log_mu - log_partition)
            # Analytic derivative of log partition with respect to q.
            # Regression is linear, so its derivative is the slope below.
            alpha_fit[i,j] = np.dot(weights, log_mu)
            chi[i,j] = np.dot(mu,log_mu) if abs(q-1)<1e-10 else log_partition

    # 对每个 q，用线性回归计算 τ(q)
    # τ(q) = lim log(χ(q,ε)) / log(ε)
    tau = np.zeros(len(q_values))
    Dq = np.zeros(len(q_values))
    fit_r2 = np.zeros(len(q_values))

    for i, q in enumerate(q_values):
        if abs(q - 1.0) < 1e-10:
            # q=1: χ(1, ε)=Σμ_i=1, hence τ(1)=0.
            # The entropy slope estimates D(1)=τ'(1), not τ(1).
            y = chi[i, :]  # 已是 Σ μ_i ln(μ_i)
            slope, _, r, _, _ = linregress(log_eps, y)
            fit_r2[i] = r*r
            tau[i] = 0.0
            Dq[i] = slope
        else:
            y = chi[i, :]
            slope, _, r, _, _ = linregress(log_eps, y)
            fit_r2[i] = r*r
            tau[i] = slope
            Dq[i] = slope / (q - 1)

    # Legendre 变换: α(q) = dτ/dq, f(α) = q·α - τ(q)
    # Differentiate the partition function analytically before scale regression.
    alpha = np.array([linregress(log_eps,y).slope for y in alpha_fit])
    f_alpha = q_values * alpha - tau

    # 提取关键指标
    # D(0), D(1), D(2)
    idx_0 = np.argmin(np.abs(q_values - 0.0))
    idx_1 = np.argmin(np.abs(q_values - 1.0))
    idx_2 = np.argmin(np.abs(q_values - 2.0))

    D0 = Dq[idx_0]
    D1 = Dq[idx_1]
    D2 = Dq[idx_2]

    # 奇异谱宽: Δα = α_max - α_min
    # 过滤掉 f(α) < 0 的部分（非物理区域）
    valid = f_alpha >= -0.5  # 允许小幅度负值（数值误差）
    if np.sum(valid) > 2:
        alpha_valid = alpha[valid]
        f_valid = f_alpha[valid]
        Delta_alpha = np.max(alpha_valid) - np.min(alpha_valid)

        # Δf: 对称性
        idx_alpha_min = np.argmin(alpha_valid)
        idx_alpha_max = np.argmax(alpha_valid)
        Delta_f = f_valid[idx_alpha_min] - f_valid[idx_alpha_max]
    else:
        Delta_alpha = np.nan
        Delta_f = np.nan

    alpha_0 = alpha[idx_0]
    f_alpha_0 = f_alpha[idx_0]

    quality = 'finite_scale_unstable' if not np.all(np.isfinite(fit_r2)) or D0+0.01 < D1 or D1+0.01 < D2 or np.min(fit_r2)<.95 else 'fit_consistent'
    if quality != 'fit_consistent':
        Delta_alpha = Delta_f = alpha_0 = f_alpha_0 = np.nan
    mf_results = {
        'min_R2': float(np.min(fit_r2)),
        'quality': quality,
        'D0': round(D0, 4),
        'D1': round(D1, 4),
        'D2': round(D2, 4),
        'Delta_alpha': round(Delta_alpha, 4) if not np.isnan(Delta_alpha) else np.nan,
        'Delta_f': round(Delta_f, 4) if not np.isnan(Delta_f) else np.nan,
        'alpha_0': round(alpha_0, 4),
        'f_alpha_0': round(f_alpha_0, 4),
    }

    return mf_results


# ============================================================================
# 图论拓扑检测（骨架 → 节点-边图 → Tips / Forks / Crossings）
# ============================================================================

def skan_analyze(skeleton, dpi=300, min_spur_mm=0., cross_merge_mm=None,
                 binary=None, base_rc=None, root_direction='top', crown_box=None,
                 root_model='general', crossing_context=True):
    """Analyze whole roots with an explicit orientation (default: crown at top).

    Pixel endpoints exclude the crown. Crossings reconnect continuous arms;
    all structural metrics use that same resolved graph. Use direction='none'
    for unrooted fragments; rooted indices then remain undefined.
    """
    from root_topology import analyze_topology
    return analyze_topology(skeleton, dpi=dpi, binary=binary, base_rc=base_rc,
                            root_direction=root_direction,
                            min_spur_mm=min_spur_mm, cross_merge_mm=cross_merge_mm,
                            crown_box=crown_box, root_model=root_model,
                            crossing_context=crossing_context)


def analyze_root_image(binary_path, skeleton_path, dpi=None, sample_id="",
                       step_log=None, root_direction="top", base_rc=None, crown_box=None,
                       root_model='general', crossing_context=True):
    """
    对一对（二值化 + 骨架）图像进行完整的根系构型分析。

    数据来源规则：
      - 二值化图像 (binary_path, PNG)：用于分形维数、多重分形谱、
        根面积、根直径、根体积计算。
      - 骨架图像 (skeleton_path, PNG，无损，包含人工修正)：用于所有
        形态拓扑指标（根长、根尖数、分支数、交叉数、分支角、TI、
        Strahler 等）。不从二值图重建骨架，直接读取 PNG 文件确保
        人工修正的连接关系作为输入；图转换前仍做单像素细化。

    显式 dpi 参数优先于元数据；两者均缺失时只输出像素量，不猜测物理尺度。

    Parameters
    ----------
    binary_path : str
        二值化图像路径
    skeleton_path : str
        骨架图像路径
    dpi : int
        显式 DPI 覆盖；不提供且元数据缺失时仅输出像素量
    sample_id : str
        样本标识符
    step_log : callable or None
        可选回调函数 step_log(msg: str)，在每个计算步骤完成后调用，
        供 GUI 实时显示进度（不传则静默）。

    Returns
    -------
    result : dict
        包含所有量化参数的字典
    """
    def _log(msg):
        if step_log:
            step_log(msg)

    import json
    from pathlib import Path
    review_path = Path(str(binary_path) + '.review.json')
    review_error = ''
    review = {}
    if crown_box is None and review_path.exists():
        try:
            review = json.loads(review_path.read_text(encoding='utf-8'))
            if not isinstance(review, dict):
                raise ValueError('Review annotation must be a JSON object')
        except (ValueError, OSError) as exc:
            review_error = f'Invalid review annotation: {exc}'
            crown_box = [np.nan]*4
    if crown_box is None:
        crown_box = review.get('crown_box')
    from calibration import image_scale
    physical_dpi, scale_source = image_scale(binary_path, override=dpi)
    dpi = physical_dpi or DEFAULT_DPI  # only internal unit conversion fallback
    _log(f"  [{sample_id}] Scale: {scale_source}, DPI={physical_dpi}")

    # 加载二值化图像
    binary_img = load_binary_image(binary_path)
    # This records explicit preprocessing; never rebuild an imported/manual
    # skeleton here. Both saved inputs already represent the repaired mask.
    from PIL import Image as _Image
    with _Image.open(binary_path) as _im:
        stem_metadata = _im.info.get('Stem_Repair')
    try:
        stem_info = json.loads(stem_metadata) if stem_metadata else {}
        if not isinstance(stem_info, dict):
            raise ValueError('expected object')
        stem_holes = int(stem_info.get('filled_holes', 0))
        stem_pixels = int(stem_info.get('added_pixels', 0))
    except (ValueError, TypeError):
        stem_info = {'status': 'invalid_metadata'}
        stem_holes = stem_pixels = 0

    # 骨架：直接加载 PNG 骨架文件（无损格式，包含人工修正和软件优化结果）
    # load_skeleton_image 仅执行二值化阈值判断，不调用 skeletonize/thinning，
    # 因此能忠实保留人工修正和外部软件输出的骨架拓扑；
    # 若输入骨架非单像素宽，需在上游（预处理/optimize_images）完成细化。
    skeleton_img = load_skeleton_image(skeleton_path)

    # ---- 基础像素统计 ----
    root_area_px = np.sum(binary_img)  # 二值化前景像素数
    skeleton_length_px = np.sum(skeleton_img)  # 骨架像素数

    # ---- 分形参数 ----
    _log(f"  [{sample_id}] 计算分形维数...")
    FD, FA, FD_R2 = compute_fractal_dimension(binary_img)

    # ---- 多重分形谱 ----
    _log(f"  [{sample_id}] 计算多重分形谱...")
    mf = compute_multifractal_spectrum(binary_img)

    # ---- skan 骨架拓扑分析（Tips/Forks/Crossings + 根长 + 角度 + Strahler）----
    _log(f"  [{sample_id}] 分析骨架拓扑（skan 图论方法）...")
    sa = skan_analyze(skeleton_img, dpi=dpi, binary=binary_img,
                      root_direction=root_direction, base_rc=base_rc, crown_box=crown_box,
                      root_model=root_model, crossing_context=crossing_context)
    if review_error:
        sa['topology_error'] = review_error
    num_tips_val = sa['num_tips']
    num_forks_val = sa['num_forks']
    num_crossings_val = sa['num_crossings']
    num_junctions_val = sa['num_junctions']

    # ---- 形态特征参数 ----
    # 根长：skan 已含 √2 步长加权，比像素计数更准确
    root_length_cm = sa['root_length_cm']

    from root_topology import measure_paths
    morphology_px = measure_paths(sa['_resolved_edges'], binary_img)
    cm_per_px = 2.54 / dpi
    avg_diameter_mm = morphology_px['diameter_px'] * cm_per_px * 10
    root_surface_area_cm2 = morphology_px['surface_px2'] * cm_per_px**2
    root_volume_cm3 = morphology_px['volume_px3'] * cm_per_px**3

    # 分支角度
    avg_branch_angle = sa['avg_branch_angle']

    # 密度
    tip_density = num_tips_val / root_length_cm if root_length_cm > 0 else 0.0
    branch_density = num_forks_val / root_length_cm if root_length_cm > 0 else 0.0

    # 平均链接长度
    avg_link_length = sa['avg_link_length_cm']

    # ---- 拓扑指数（直接取自 skan 图，与 Num_Tips / Strahler 同源）----
    # skan 图已在 _skan_strahler 中完成 BFS 计算，无需额外降采样或重骨架化。
    TI       = sa['strahler'].get('_TI', np.nan)
    altitude = sa['strahler'].get('_TI_altitude', 0)
    magnitude = sa['strahler'].get('_TI_magnitude', 0)

    # ---- Strahler（skan 图论后序遍历）----
    strahler = sa['strahler']
    _log(f"  [{sample_id}] 汇总结果...")

    # 组装结果
    result = {
        'Sample_ID': sample_id,
        'DPI': physical_dpi if physical_dpi is not None else np.nan,
        'Scale_Source': scale_source,
        'Root_Direction': root_direction,
        'Root_Model': root_model,
        'Crossing_Context': bool(crossing_context),
        'Root_Reconstruction_Status': sa['reconstruction']['status'],
        'Root_Reconstruction_Reason': sa['reconstruction'].get('reason',''),
        'Num_Reconstructed_Root_Paths': sa['num_root_paths'],
        'Num_Bundle_Separations': len(sa['bundle_separation_coords']),
        'Projected_Path_Length_px': sa['projected_length_px'],
        'Overlap_Added_Length_px': sa['reconstruction'].get('overlap_added_length_px',0.),
        'Path_Inferred_Length_Fraction': morphology_px['path_inferred_length_fraction'],
        'Crown_Annotation': sa['crown_source'],
        '_crown_box': sa['crown_box'],
        'Topology_Status': sa['topology_status'],
        'Stem_Repair_Status': stem_info.get('status', 'disabled'),
        'Stem_Repair_Holes': stem_holes,
        'Stem_Repair_Pixels': stem_pixels,
        'Stem_Repair_ROI': json.dumps(stem_info.get('roi_rc')),
        'Stem_Repair_Assumption': stem_info.get('assumption', ''),
        'Topology_Error': sa.get('topology_error',''),
        'Cycle_Rank': sa['cycle_rank'],
        'Num_Uncertain_Junctions': sa.get('num_uncertain_junctions',0),
        'Num_Fragment_Endpoints': len(sa.get('fragment_tip_coords',[])),
        'Num_Boundary_Endpoints': len(sa.get('boundary_tip_coords',[])),
        'Num_Possible_Crop_Endpoints': len(sa.get('possible_crop_tip_coords',[])),
        'Diameter_Measured_Length_Fraction': morphology_px['diameter_measured_fraction'],
        'Diameter_Unresolved_Length_Fraction': morphology_px['diameter_unresolved_fraction'],
        'Num_Bases': len(sa['base_coords']),
        'Root_Length_px': sa['root_length_px'],
        'Avg_Link_Length_px': sa['root_length_px']/len(sa['edges']) if sa['edges'] else 0.,
        'Tip_Density_per_px': sa['num_tips']/sa['root_length_px'] if sa['root_length_px'] else 0.,
        'Branch_Density_per_px': sa['num_forks']/sa['root_length_px'] if sa['root_length_px'] else 0.,
        'Raster_Pruned_Spurs': sa['raster_pruned'],
        'Avg_Root_Diameter_px': morphology_px['diameter_px'],
        'Root_Surface_Area_px2': morphology_px['surface_px2'],
        'Root_Volume_px3': morphology_px['volume_px3'],                          # 实际使用的 DPI（自动检测）
        # 分形参数
        'Fractal_Dimension': round(FD, 4) if not np.isnan(FD) else np.nan,
        'Fractal_Abundance': round(FA, 4) if not np.isnan(FA) else np.nan,
        'FD_R2': round(FD_R2, 6) if not np.isnan(FD_R2) else np.nan,
        # 多重分形谱
        'MF_D0_Capacity': mf['D0'],
        'MF_D1_Information': mf['D1'],
        'MF_D2_Correlation': mf['D2'],
        'MF_Delta_alpha': mf['Delta_alpha'],
        'MF_Delta_f': mf['Delta_f'],
        'MF_Quality': mf.get('quality','insufficient_scales'),
        'MF_Min_R2': mf.get('min_R2',np.nan),
        'MF_alpha_0': mf['alpha_0'],
        'MF_f_alpha_0': mf['f_alpha_0'],
        # 形态特征参数
        'Root_Length_cm': round(root_length_cm, 4),
        'Root_Surface_Area_cm2': round(root_surface_area_cm2, 4),
        'Avg_Root_Diameter_mm': round(avg_diameter_mm, 4),
        'Root_Volume_cm3': round(root_volume_cm3, 4),
        'Num_Tips': num_tips_val,
        'Num_Forks': num_forks_val,
        'Num_Crossings': num_crossings_val,
        'Num_Junctions': num_junctions_val,
        'Avg_Branch_Angle_deg': round(avg_branch_angle, 2) if not np.isnan(avg_branch_angle) else np.nan,
        'Tip_Density_per_cm': round(tip_density, 4),
        'Branch_Density_per_cm': round(branch_density, 4),
        'Avg_Link_Length_cm': round(avg_link_length, 4),
        # 拓扑指数
        'Topological_Index': round(TI, 4) if not np.isnan(TI) else np.nan,
        'TI_Altitude': altitude,
        'TI_Magnitude': magnitude,
        # Strahler 分支级序
        'Strahler_Max_Order': strahler['Strahler_Max_Order'],
        'Strahler_Bifurcation_Ratio': strahler['Strahler_Bifurcation_Ratio'],
        'Strahler_Length_Ratio': strahler['Strahler_Length_Ratio'],
        # 连通性诊断（论文质量控制表使用）
        # - Num_Components: 骨架全图的连通分量数（>1 表示有断裂或噪声碎片）
        # - Largest_Component_Node_Fraction: 最大分量节点占全图节点的比例；
        #   TI/Strahler 要求全图单连通且无环；此字段仅为碎片诊断
        'Num_Components': strahler.get('Num_Components', np.nan),
        'Largest_Component_Node_Fraction': strahler.get(
            'Largest_Component_Node_Fraction', np.nan),
        # 坐标（不写入 CSV，供 GUI show_result 直接使用，避免重复计算）
        '_base_coords': sa['base_coords'],
        '_tip_coords': sa['tip_coords'],
        '_fork_coords': sa['fork_coords'],
        '_crossing_coords': sa['crossing_coords'],
        # 可视化验证数据
        '_angle_viz': sa.get('_angle_viz', []),
        '_strahler_edge_viz': sa.get('_strahler_edge_viz', []),
        '_binary_img': binary_img,          # 供直径/盒计数叠加层使用
    }

    # 添加各级序的段数和平均长度 (展开为列)
    for od in strahler['Strahler_Orders']:
        order = od['order']
        result[f'Strahler_Order{order}_Count'] = od['count']
        result[f'Strahler_Order{order}_AvgLen_cm'] = od['avg_length_cm']
        result[f'Strahler_Order{order}_AvgLen_px'] = od['avg_length_px']

    if physical_dpi is None:
        # Never silently turn a default DPI into measured centimetres.
        for key in result:
            if key.endswith(('_cm', '_cm2', '_cm3', '_mm')) or 'Length_cm' in key:
                result[key] = np.nan
    return result


# ============================================================================
# 文件匹配与批处理
# ============================================================================

def find_image_pairs(binary_dirs, skeleton_dirs):
    """
    自动查找二值化-骨架图像对。

    Parameters
    ----------
    binary_dirs : list of str
        二值化图像目录列表
    skeleton_dirs : list of str
        骨架图像目录列表（顺序须与 binary_dirs 一一对应）

    Returns
    -------
    pairs : list of dict
        每个元素包含 'year', 'sample_id', 'binary_path', 'skeleton_path'
    """
    pairs = []

    for binary_dir, skeleton_dir in zip(binary_dirs, skeleton_dirs):
        # 自动推断年份标签（从目录名中提取，如 "2024-binary" -> "2024"）
        bin_name = os.path.basename(os.path.normpath(binary_dir))
        year = ''
        for part in bin_name.split('-'):
            if part.isdigit() and len(part) == 4:
                year = part
                break
        if not year:
            year = bin_name  # 如果无法提取年份，使用目录名

        # 查找所有图像文件（兼容大写/小写扩展名，如 .TIF .JPG）
        img_exts = ('*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff', '*.bmp')
        binary_files = sorted(set(
            f for ext in img_exts
            for f in (glob.glob(os.path.join(binary_dir, ext)) +
                      glob.glob(os.path.join(binary_dir, ext.upper())))
        ))
        skeleton_files = sorted(set(
            f for ext in img_exts
            for f in (glob.glob(os.path.join(skeleton_dir, ext)) +
                      glob.glob(os.path.join(skeleton_dir, ext.upper())))
        ))

        # 建立骨架文件名映射：stem → 路径
        skel_map = {}
        for sp in skeleton_files:
            stem = os.path.splitext(os.path.basename(sp))[0]
            skel_map[stem] = sp

        for bp in binary_files:
            stem = os.path.splitext(os.path.basename(bp))[0]
            if stem in skel_map:
                # 若文件名本身已含4位年份前缀（新格式 Year-Variety-Treatment-Rep），
                # 直接用 stem 作为 sample_id，否则拼接目录年份（旧格式兼容）
                stem_year_prefix = stem.split('-')[0]
                if len(stem_year_prefix) == 4 and stem_year_prefix.isdigit():
                    sid = stem            # 新格式: 2023-DH-P1-1
                    yr  = stem_year_prefix
                else:
                    sid = f"{year}_{stem}" if year else stem  # 旧格式兼容
                    yr  = year
                pairs.append({
                    'year': yr,
                    'sample_id': sid,
                    'binary_path': bp,
                    'skeleton_path': skel_map[stem],
                })

    return pairs


def main():
    parser = argparse.ArgumentParser(
        description='根系构型参数量化分析 (Maize Root Architecture Quantification)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 分析单组数据 (一个二值化目录 + 一个骨架目录)
  python root_analysis.py -b ./2024-binary -s ./2024-skeleton -o ./results

  # 分析多组数据 (多个目录对，按顺序一一对应)
  python root_analysis.py -b ./2024-binary ./2025-binary -s ./2024-skeleton ./2025-skeleton -o ./results

  # 指定扫描分辨率
  python root_analysis.py -b ./2024-binary -s ./2024-skeleton --dpi 600

目录命名建议:
  二值化图像文件名应包含 "-binary" 或 "_binary"，如: DH-P0-1-binary.jpg
  骨架图像文件名应包含 "-skeleton" 或 "_skeleton"，如: DH-P0-1-skeleton.jpg
        """
    )
    parser.add_argument('-b', '--binary_dirs', type=str, nargs='+', required=True,
                        help='二值化图像所在目录 (可指定多个，用空格分隔)')
    parser.add_argument('-s', '--skeleton_dirs', type=str, nargs='+', required=True,
                        help='骨架图像所在目录 (可指定多个，须与 -b 一一对应)')
    parser.add_argument('-o', '--output_dir', type=str, default='./results',
                        help='输出目录 (默认: ./results)')
    parser.add_argument('--dpi', type=int, default=None,
                        help='显式覆盖 DPI；默认读取元数据，缺失时只输出像素量')
    parser.add_argument('--root-direction', choices=['top','bottom','left','right','none'], default='top')
    parser.add_argument('--root-model', choices=['general','shared_crown'], default='general',
                        help='shared_crown explicitly assumes independent unbranched roots from a common base')
    parser.add_argument('--no-crossing-context', action='store_true',
                        help='disable contextual contraction of short crossing segments')
    parser.add_argument('--output_name', type=str, default='root_architecture_metrics.csv',
                        help='输出 CSV 文件名 (默认: root_architecture_metrics.csv)')

    args = parser.parse_args()

    # 校验输入目录数量匹配
    if len(args.binary_dirs) != len(args.skeleton_dirs):
        print("  错误: -b 和 -s 指定的目录数量必须一致！")
        print(f"  二值化目录数: {len(args.binary_dirs)}, 骨架目录数: {len(args.skeleton_dirs)}")
        sys.exit(1)

    # 校验目录存在
    for d in args.binary_dirs + args.skeleton_dirs:
        if not os.path.isdir(d):
            print(f"  错误: 目录不存在: {d}")
            sys.exit(1)

    dpi = args.dpi
    os.makedirs(args.output_dir, exist_ok=True)
    output_csv = os.path.join(args.output_dir, args.output_name)

    print("=" * 70)
    print("  根系构型参数量化分析")
    print("  Maize Root Architecture Quantification")
    print("=" * 70)
    print(f"  二值化目录: {args.binary_dirs}")
    print(f"  骨架目录:   {args.skeleton_dirs}")
    print(f"  输出目录:   {args.output_dir}")
    print(f"  扫描分辨率: {dpi} DPI")
    print(f"  输出文件:   {output_csv}")
    print("=" * 70)

    # 查找所有图像对
    pairs = find_image_pairs(args.binary_dirs, args.skeleton_dirs)
    print(f"\n  找到 {len(pairs)} 对图像:")
    for p in pairs:
        print(f"    {p['sample_id']}")

    if len(pairs) == 0:
        print("\n  错误: 未找到任何图像对，请检查目录结构。")
        sys.exit(1)

    # 逐一分析
    results = []
    for i, pair in enumerate(pairs):
        print(f"\n  [{i + 1}/{len(pairs)}]", end="")
        result = analyze_root_image(
            binary_path=pair['binary_path'],
            skeleton_path=pair['skeleton_path'],
            dpi=dpi,
            sample_id=pair['sample_id'],
            root_direction=args.root_direction, root_model=args.root_model,
            crossing_context=not args.no_crossing_context
        )
        # 添加额外元信息
        result['Year'] = pair['year']
        # 解析品种和处理
        sid = pair['sample_id']
        # 从 sample_id 提取品种 (Variety) 和处理 (Treatment)
        # 新格式: 2023-DH-P1-1 → Year=2023, Variety=DH, Treatment=P1, Replicate=1
        # 旧格式: 2024_DH-P0-1 → Variety=DH, Treatment=P0, Replicate=1
        # 旧格式: 2025_DHP0-1  → Variety=DH, Treatment=P0, Replicate=1
        hyp_parts = sid.split('-')
        if len(hyp_parts) >= 4 and len(hyp_parts[0]) == 4 and hyp_parts[0].isdigit():
            # 新格式: Year-Variety-Treatment-Replicate（已由 find_image_pairs 设置 year）
            result['Variety']   = hyp_parts[1]
            result['Treatment'] = hyp_parts[2]
            result['Replicate'] = '-'.join(hyp_parts[3:])
        else:
            parts = sid.split('_', 1)
            if len(parts) == 2:
                name = parts[1]
                if name.startswith('DH-') or name.startswith('XY-'):
                    sub_parts = name.split('-')
                    result['Variety'] = sub_parts[0]
                    result['Treatment'] = sub_parts[1] if len(sub_parts) > 1 else ''
                    result['Replicate'] = sub_parts[2] if len(sub_parts) > 2 else ''
                elif name.startswith('DHP') or name.startswith('XYP'):
                    if name.startswith('DHP'):
                        result['Variety'] = 'DH'
                        rest = name[3:]
                    elif name.startswith('XYP'):
                        result['Variety'] = 'XY'
                        rest = name[3:]
                    else:
                        result['Variety'] = ''
                        rest = name
                    rest_parts = rest.split('-')
                    result['Treatment'] = 'P' + rest_parts[0] if len(rest_parts) > 0 else ''
                    result['Replicate'] = rest_parts[1] if len(rest_parts) > 1 else ''
                else:
                    result['Variety'] = name
                    result['Treatment'] = ''
                    result['Replicate'] = ''
            else:
                result['Variety'] = ''
                result['Treatment'] = ''
                result['Replicate'] = ''

        results.append(result)

    # 构建 DataFrame
    df = pd.DataFrame(results)

    # 调整列顺序：元信息在前，指标在后
    meta_cols = ['Sample_ID', 'Year', 'Variety', 'Treatment', 'Replicate', 'DPI', 'Scale_Source', 'Topology_Status', 'Root_Direction', 'Crown_Annotation', 'Cycle_Rank', 'Num_Bases', 'Root_Length_px', 'Avg_Root_Diameter_px', 'Root_Surface_Area_px2', 'Root_Volume_px3']
    metric_cols = [
        # 分形参数
        'Fractal_Dimension', 'Fractal_Abundance', 'FD_R2',
        # 多重分形谱
        'MF_D0_Capacity', 'MF_D1_Information', 'MF_D2_Correlation',
        'MF_Delta_alpha', 'MF_Delta_f', 'MF_alpha_0', 'MF_f_alpha_0',
        # 形态特征
        'Root_Length_cm', 'Root_Surface_Area_cm2', 'Avg_Root_Diameter_mm',
        'Root_Volume_cm3', 'Num_Tips', 'Num_Forks', 'Num_Crossings', 'Num_Junctions',
        'Avg_Branch_Angle_deg', 'Tip_Density_per_cm', 'Branch_Density_per_cm',
        'Avg_Link_Length_cm',
        # 拓扑指数
        'Topological_Index', 'TI_Altitude', 'TI_Magnitude',
        # Strahler 分支级序
        'Strahler_Max_Order', 'Strahler_Bifurcation_Ratio', 'Strahler_Length_Ratio',
        # 连通性诊断（质量控制列）
        'Num_Components', 'Largest_Component_Node_Fraction',
    ]
    # Strahler 各级序列（动态列名）
    strahler_detail_cols = sorted(
        [c for c in df.columns if c.startswith('Strahler_Order')],
        key=lambda x: (int(x.split('Order')[1].split('_')[0]),  # 按级序排
                        x.split('_')[-1])  # Count 在 AvgLen 前
    )
    col_order = meta_cols + metric_cols + strahler_detail_cols
    # 确保所有列都在
    col_order = [c for c in col_order if c in df.columns]
    col_order += [c for c in df.columns if c not in col_order and not c.startswith('_')]
    df = df[col_order]

    # 保存 CSV
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print("\n" + "=" * 70)
    print(f"  分析完成！结果已保存至: {output_csv}")
    print(f"  共分析 {len(df)} 个样本")
    print("=" * 70)

    # 打印摘要统计
    print("\n  ===== 描述性统计摘要 =====")
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    summary = df[numeric_cols].describe().round(4)
    print(summary.to_string())

    return df


def _analysis_worker_task(args):
    """
    顶层函数供 ProcessPoolExecutor 调用（必须可被 pickle 序列化）。
    每个子进程拥有独立的 Python 解释器和 GIL，实现真正的 CPU 并行。
    """
    binary_path, skeleton_path, dpi, sample_id = args[:4]
    root_direction = args[4] if len(args)>4 else "top"
    base_rc = args[5] if len(args)>5 else None
    crown_box = args[6] if len(args)>6 else None
    root_model = args[7] if len(args)>7 else 'general'
    crossing_context = args[8] if len(args)>8 else True
    return analyze_root_image(
        binary_path=binary_path,
        skeleton_path=skeleton_path,
        dpi=dpi,
        sample_id=sample_id,
        step_log=None,
        root_direction=root_direction,
        base_rc=base_rc, crown_box=crown_box, root_model=root_model,
        crossing_context=crossing_context,
    )


if __name__ == '__main__':
    main()

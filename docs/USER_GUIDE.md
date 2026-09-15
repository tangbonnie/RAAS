# 根系构型参数量化分析系统使用指南

**V1.0.0｜无激活码发行版｜更新日期：2026-09-15**

正式作者：唐清芸（石河子大学农学院、新疆农垦科学院）  
软件版权人：王国栋（新疆农垦科学院）

本指南介绍安装、GUI、命令行、Python API、数据准备和结果解释。[技术方案与数学公式](TECHNICAL_METHODS.md) 介绍实际实现和论文方法学；[数据集说明](../datasets/README.md) 介绍随项目整理的数据。

源码仓库：[tangbonnie/RAAS](https://github.com/tangbonnie/RAAS)。本项目源码、原创文档、数据集和第三方依赖的条款各自适用，参阅 [源码许可证](../LICENSE)、[文档许可证](../LICENSE-DOCS.md) 及 [第三方声明](THIRD_PARTY_NOTICES.md)。无激活码表示软件无需激活，不改变这些权利归属。

## 1. 选择运行方式

| 方式 | Windows | macOS | 用途 |
|---|---|---|---|
| 便携 EXE | 完整解压后运行 `RootArchitecture.exe` | Windows EXE 不能原生运行 | 不安装 Python，进行 GUI 分析 |
| Python GUI | `python root_gui.py` | `python root_gui.py` | 源码运行，同一 PyQt5 界面 |
| 带启动画面的 GUI | `python launcher.py` | `python launcher.py` | 先显示启动画面，再加载分析模块 |
| Python 命令行 | `preprocess.py`、`root_analysis.py` | 相同入口 | 批量处理及参数记录 |
| Python API | 可用 | 依赖安装成功后可用 | 精细控制微孔修复、根冠标注、四图复现等 |

本发行版已经移除程序激活流程，不要求输入密钥、激活码或连接授权服务。科学计算在本机完成。

**验证环境边界：** 本次实际运行和编译使用 Windows x64、Python 3.13.12。macOS 下的源码安装与启动步骤依据同一代码提供，尚未完成 macOS 实机测试；没有提供已验证的 `.app`、`.dmg` 或 macOS 命令行二进制。Python 3.12 是可尝试的源码安装版本，不能将安装指引写成该版本和所有平台均已实测。

## 2. Windows 安装和启动

### 2.1 使用便携 EXE

1. 完整解压 Windows 发行包到可读写目录，例如 `D:\RootArchitecture`。
2. 确认 `RootArchitecture.exe` 和 `_internal` 目录在同一级。只复制 EXE 会缺少运行库和界面资源。
3. 双击 `RootArchitecture.exe`。第一次加载科学计算库和启动子进程可能需要较长时间，查看启动画面和操作日志。
4. 选择原图、预处理输出和分析输出目录。建议把分析数据存放在独立工作目录，便于保留原始图像和不同参数的结果。

本次在开发项目中的交付位置为 `dist/RootArchitecture_NoKey_V1.0.0/RootArchitecture/RootArchitecture.exe`；拿到便携包后以解压位置为准。该 EXE 启动的是 GUI，没有把 `preprocess.py` 和 `root_analysis.py` 的选项封装成 EXE 的通用命令行入口。需要 CLI 时请使用源码环境。

### 2.2 从源码运行

先安装匹配机器架构的 Python，进入包含 `root_gui.py` 的仓库根目录。PowerShell 示例以已安装 Python 3.12 为例：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe root_gui.py
```

若安装的是 3.13，可把第一行换为 `py -3.13 -m venv .venv`。后续命令直接使用虚拟环境的解释器，不需要修改 PowerShell 的执行策略。

`requirements.txt` 给出依赖版本范围；`requirements-lock.txt` 记录当前 Windows 验证环境的固定版本。若要复现该环境，可在对应 Python 版本的独立虚拟环境中安装锁定文件；不要直接把 Windows 的锁定环境等同于已经验证的 macOS 环境。

## 3. macOS 源码 GUI 和命令行

使用已安装的 Python 3.12，在“终端”切换到仓库根目录：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python root_gui.py
```

带启动画面的方式是 `python launcher.py`。结束时关闭窗口；退出虚拟环境可运行 `deactivate`。以后再次使用时只需进入项目目录并执行 `source .venv/bin/activate`，无需重复安装。

Apple Silicon 机器应使用与所装依赖一致的 ARM64 Python，Intel Mac 使用相应的 x86_64 环境。若 `PyQt5` 或科学计算依赖无法找到匹配的安装包，先检查 `python --version`、解释器架构和 `python -m pip --version`，不要混用另一套 Python 的 `pip`。程序要求有可用的图形桌面来显示 GUI；纯命令行处理本身不要求打开主窗口。

macOS 与 Windows 的核心 CLI 命令相同。本文其余示例写作 `python ...`；Windows 未启用环境时，可替换为 `.venv\Scripts\python.exe ...`。

## 4. 输入图像与目录

### 4.1 数据要求

- 支持 PNG、JPG/JPEG、TIF/TIFF、BMP 等入口识别的图像格式。分析针对二维图像，不是三维根系重建。
- 保持原生分辨率，保存未修改的原图。二值图和骨架建议使用无损 PNG；JPEG 压缩可能造成细线断裂、微孔和伪连接。
- 原图既可以是亮底暗根，也可以是暗底亮根，但分割方法和前景极性必须匹配。
- 原图目录采用平铺文件。命令行查找不会递归遍历所有子目录；多个目录应分别传入。
- 同一次处理的样本名要唯一。预处理会去掉文件名末尾的 `-rgb`、`_rgb`、`-raw`、`_raw`、`-original`、`_original`，再生成同名二值图和骨架，注意避免去掉后重名。
- 从论文图、剪贴板、网页或重新缩放图像得到的图片通常不能凭文件名或屏幕显示推断真实物理尺度。

### 4.2 推荐工作目录

```text
work/
├── original/                # 保留原图
├── processed/
│   ├── binary/sample_01.png
│   └── skeleton/sample_01.png
└── results/                 # CSV、Excel 和导出图
```

**配对按文件名主干相等进行。** `binary/sample_01.png` 应对应 `skeleton/sample_01.png`；不是分别命名成 `sample_01-binary.png` 与 `sample_01-skeleton.png`。两张图必须尺寸相同、像素位置对应，骨架要属于该二值图。

项目的数据入口包括：

| 目录 | 内容 |
|---|---|
| `datasets/copper_wire/original/` | 82 张铜丝模拟根系原图，保留原文件名 |
| `datasets/four_examples/original/` | `input_1.png` 至 `input_4.png`，用于四图复核 |
| `datasets/real_roots_2024/jpeg/` | 24 张整理后的真实根系 JPEG |
| `datasets/four_examples/analysis_parameters.json` | 四图各自的预处理和分析参数 |
| `datasets/manifest.csv` | 尺寸、相对路径、哈希与尺度记录 |

82 张铜丝图不需要每次全部运行。调试时先选代表性的简单、局部重叠和密集样本，确认设置后再批处理。数据集不包含这批样本完整的实物长度、真实根尖或分叉标注；哈希和原图清单是可追溯记录，不是量化真值。

## 5. GUI 完整流程

Windows EXE、Windows Python GUI 和 macOS Python GUI 使用相同操作逻辑。

### 5.1 图像预处理

1. 打开“图像预处理”，选择“原始图像目录”和“输出目录”。
2. 从“选择图像”中选一张代表图，设置分割方法后点击“预览当前图像”。预览用于检查，批量处理才保存对应输出文件。
3. 对照原图检查二值掩膜是否漏掉细根、把背景或边框作为根、把相邻根粘连，随后检查骨架是否保持真实连接。
4. 确认参数后点击“批量处理全部图像”。结果写入输出目录的 `binary` 和 `skeleton` 子目录。
5. 遇到失败样本查看日志中的文件名与原因，不要只凭“完成”提示认为所有样本均成功。

| 方法 | 对应图像和作用 | 使用注意 |
|---|---|---|
| `line_art` | 白底黑色线条、铜丝模拟图；固定灰度阈值 128/255 | 固定暗前景，不采用一般去噪、填孔和闭运算 |
| `intensity` | 亮度对比明确的根系图；高低阈值连接保留较弱细根 | GUI 使用自动极性、低阈值比例 0.8；一般形态学后处理参数不用于此分支 |
| `otsu` | 根与背景亮度差明显、照明较均匀 | 全局阈值，需核对前景极性 |
| `adaptive` | 亮度随位置变化 | 局部阈值；窗口和偏移量需结合图像 |
| `texture` | 单尺度纹理区分 | 根较粗或纹理明显时检查效果，弱细线可能不适配 |
| `multiscale` | 融合多尺度纹理信息 | 界面默认选项；“推荐”不表示适用于所有样本 |

普通后处理中的“最小连通域”和“填孔阈值”实际是**像素面积 px²**。调大最小连通域可能删除真实短细根；调大填孔或闭运算半径可能把独立根粘连。它们会改变待测对象，不是越大越准确。边缘噪声与远距离散点剔除同样需要逐图检查。

GUI 中可设置的参数是常用子集。指定 `foreground`、亮度低阈值比例或 `pixel_hole_area` 等精细参数，使用 CLI 中已经暴露的选项或 Python API，见第 7、8 节。尤其是四图记录中的微孔设置，不能仅靠 GUI 普通“填孔阈值”替代。

### 5.2 可选的图像擦除

1. 切换“图像擦除”，选择对应的二值图和骨架目录，再选择样本。
2. 调整笔刷，左键拖动擦除噪声；操作同步作用于二值图和骨架。
3. 保存前可使用 `Ctrl+Z` 撤销上一笔。
4. “保存修改”会覆盖所选处理文件，并清空本次撤销历史。先保留原始预处理副本，记录人工修改了哪些区域。
5. 修改后重新运行分析，使表格与当前图像一致。

该模块是像素擦除工具，**不提供任意画根、自动补回隐藏根、手工把某个结点重新标成分叉或交叉的完整标注流程**。分析读取保存的骨架，不会从二值图重新生成骨架来覆盖人工修正。若在其他图像软件编辑，须保持二值/骨架尺寸、坐标和单像素结构一致。

### 5.3 根系构型分析

1. 选择二值化目录、骨架目录和结果输出目录。
2. 确认样本下拉框可以找到对应文件，必要时刷新。
3. 设置 DPI、根系方向、根系模型和交叉短段上下文。
4. 先点“分析当前样本”，核对三栏结果；随后按需使用“批量分析全部样本”。
5. 通过 Prev/Next 或样本下拉框核查每个样本。

**DPI：** 界面默认 0 表示自动读取尺度；没有可靠记录就显示像素。输入有效的非零 DPI 表示使用者确认的覆盖值，并在结果中标为 `user_supplied`。接受的显式范围为 10–10000；不要把默认或猜测分辨率作为扫描记录。

**根系方向：** `top`、`bottom`、`left`、`right` 指根基所在方向。选择“散根 / 不定向”对应 `none`，适合没有可确定单一根基的图像；此时不能期待获得有根树所需的级序和拓扑指数。

**根系模型：**

- `general`：默认的一般根系模型，允许真实分枝，按图结构识别分叉与交叉候选。
- `shared_crown`：显式假设各条根独立、无侧分枝，并从共同根基发出。程序沿各可见末端回到根基，贴合后分开的部位可解释为束内分离。只有样本构造或观测支持该假设时才选用。共享长度按模型重建，结果标为 `model_assumed`；不能用于一般真实侧根图来降低分叉计数。
- 模型重建要求存在合适的已定向、连通、无未消解环的图；失败原因见 `Root_Reconstruction_Status` 和 `Root_Reconstruction_Reason`。选择该模型不保证重建一定成功。

**交叉短段上下文：** 默认为开启。开启时用局部短连接段的上下文辅助判断相交关系；关闭时仍保留基础局部交叉判断。它不是“关闭所有交叉识别”。复杂样本可比较两种设置，记录最终选择，不能按指标是否符合预期倒推选项。

GUI 的“并行线程数”控件决定同时分析的进程数。高分辨率图像较耗内存；初次试验可设 1，机器资源允许后再增加。单样本保留详细步骤日志，多样本采用进程池。

### 5.4 三栏结果与导出

- **左栏 Binary：** 实际输入二值图。
- **中栏 Skeleton + Topology：** 实际输入骨架，以及分析入口返回的识别坐标。黄色是根基、青色是 Tips、红色是 Forks、蓝色是 Crossings。
- **右栏 Metrics：** 几何、拓扑、分形、多重分形及质量字段。没有标尺时使用像素列，无法有效计算的项目显示 `N/A`。

可开关根尖、分叉、交叉、级序和角度图层，并调整标记大小。工具栏提供缩放、平移、恢复视图和图片保存；保存当前分析图即可得到包含二值图、骨架识别点和指标的三栏结果图。调整图层不重新计算指标，也不修改检测坐标。

“根直径热力图”显示的是二值掩膜的距离变换，主要帮助检查局部粗细；不能把其色值直接视为最终法向测宽结果。“盒计数格网”显示 32 px 检查网格，不代表分形拟合只用了这个尺度。

结果表可从“文件”菜单保存 CSV 或导出 Excel。图表可视化支持按数值指标绘图、按分组比较并导出图像。分组标签从样本文件名解析，推荐 `年份-品种-处理-重复`，例如 `2024-DH-P0-1`；自动解析出的标签需核对。打开历史 CSV 可以查看数据，但 CSV 不包含完整识别坐标和图像缓存；恢复叠加图需要原二值图、骨架及重新分析。

## 6. 物理尺度与单位

程序优先采用显式 DPI，其次读取有效图像元数据。没有尺度来源时，输出 `Scale_Source=unknown`，物理列为空。文件名含 `600` 不会自动建立 600 DPI 标定；元数据中有 DPI 也仍需与实验记录相符。编辑器重采样、截图或导出可能使原分辨率记录失效。

各向同性图像、DPI 为 $d$ 时，像素边长为：

$$
s=\frac{2.54}{d}\quad\mathrm{cm/px}.
$$

因此路径长度乘 $s$，面积乘 $s^2$，体积乘 $s^3$；以毫米表示的直径乘 $10s$。这是单位换算，不会提高图像识别准确性。软件检查水平与垂直尺度的一致性，不提供一般各向异性像素或透视畸变标定流程。

有已知实物标尺时，先在原分辨率下建立真实像素—长度关系，再换算等效 DPI；标尺本身应从根系分析区域排除。图像中没有有效标尺且实物记录缺失时，只报告像素量。

## 7. 命令行模式

### 7.1 最小示例

在仓库根目录创建 `input`，放入少量白底黑线图。运行：

```bash
python preprocess.py -i input -o processed --method line_art
python root_analysis.py -b processed/binary -s processed/skeleton -o results --root-direction top
```

全目录示例（会处理目录内全部 82 张，调试阶段可先复制代表图到 `input`）：

```bash
python preprocess.py -i datasets/copper_wire/original -o processed/copper --method line_art
python root_analysis.py -b processed/copper/binary -s processed/copper/skeleton -o results/copper
```

暗背景亮根的强度分割：

```bash
python preprocess.py -i input -o processed/light --method intensity --foreground light
python root_analysis.py -b processed/light/binary -s processed/light/skeleton -o results/light --no-crossing-context
```

其中关闭上下文只是参数示例，实际选择需基于该批图像核查。若已由扫描记录确认 600 DPI，可在分析命令末尾添加 `--dpi 600`；未知尺度时不要添加。

多个平铺目录按顺序配对：

```bash
python root_analysis.py -b processed/group_a/binary processed/group_b/binary -s processed/group_a/skeleton processed/group_b/skeleton -o results --output_name all_samples.csv
```

### 7.2 预处理 CLI 参数

以 `python preprocess.py --help` 为当前入口的最终清单；下划线和连字符请按表中拼写。

| 参数 | 默认值 | 含义 |
|---|---|---|
| `-i` / `--input_dirs` | 必填 | 一个或多个原图目录 |
| `-o` / `--output_dir` | `./processed` | 输出根目录 |
| `--method` | `multiscale` | `multiscale/texture/otsu/adaptive/line_art/intensity` |
| `--foreground` | `auto` | `auto/dark/light`；用于 Otsu、自适应和 intensity；line_art 固定暗前景 |
| `--window_size` | 25 | 纹理窗口，像素 |
| `--block_size` | 51 | 自适应阈值窗口，须为奇数 |
| `--offset` | 10 | 自适应阈值偏移量 |
| `--min_size` | 500 | 一般后处理删除的小连通域面积阈值，px² |
| `--hole_size` | 200 | 一般后处理的填孔面积阈值，px² |
| `--close_radius` | 3 | 一般闭运算圆盘半径，0 表示跳过 |
| `--border_margin` | 20 | 边缘噪声检查宽度，px |
| `--isolation_distance` | 150 | 一般孤立噪声距离阈值，px |

`line_art`、`intensity` 分支直接骨架化，不执行上表中的一般去噪、填孔、闭运算、边缘和孤立噪声流程。API 提供的微孔修复是另一个显式步骤。当前预处理 CLI 未暴露 `dpi`、`bright_thresh`、`intensity_low_ratio`、`pixel_hole_area` 和 `pixel_hole_connectivity`，需使用 Python API；不要向 CLI 传入不存在的选项。

### 7.3 分析 CLI 参数

| 参数 | 默认值 | 含义 |
|---|---|---|
| `-b` / `--binary_dirs` | 必填 | 二值图目录，可多个 |
| `-s` / `--skeleton_dirs` | 必填 | 骨架目录，与 `-b` 数量和顺序一致 |
| `-o` / `--output_dir` | `./results` | CSV 输出目录 |
| `--dpi` | 未指定 | 可信 DPI 的显式覆盖；未知时不填 |
| `--root-direction` | `top` | `top/bottom/left/right/none` |
| `--root-model` | `general` | `general/shared_crown` |
| `--no-crossing-context` | 未指定，即上下文开启 | 关闭交叉短段上下文 |
| `--output_name` | `root_architecture_metrics.csv` | CSV 文件名 |

CLI 分析按样本顺序执行；GUI 的并行数不是 CLI 参数。程序返回的 CSV 包含可导出的质量字段，级序明细列随结果变化，不应按固定列数读取。

## 8. Python API 与四图精确参数复现

### 8.1 单张图

在仓库根目录的 Python 脚本中：

```python
from preprocess import process_single_image
from root_analysis import analyze_root_image

binary, skeleton = process_single_image(
    "datasets/four_examples/original/input_1.png",
    "processed/example_1",
    method="line_art",
    foreground="dark",
    pixel_hole_area=16,
    pixel_hole_connectivity=4,
    dpi=None,
)
result = analyze_root_image(
    binary, skeleton,
    sample_id="input_1",
    dpi=None,
    root_direction="top",
    root_model="shared_crown",
    crossing_context=False,
)
for field in ("Num_Tips", "Num_Forks", "Num_Crossings",
              "Root_Length_px", "Scale_Source", "Topology_Status"):
    print(field, result[field])
```

这一组参数是已记录的示例设置，不是通用默认参数。`pixel_hole_connectivity=4` 可能合并斜向一个像素的间隙，需要视作显式图像处理假设；不能称为无损修复。普通长缝和较大空隙有保护条件，详见技术方案。

### 8.2 四图参数和正确用法

| 输入 | 方法 | 微孔最大面积 / 背景连通性 | 模型 | 交叉短段上下文 |
|---|---|---|---|---|
| `input_1.png` 共同根基铜丝 | `line_art` | 16 px² / 4 | `shared_crown` | 关闭 |
| `input_2.png` 重叠铜丝 | `line_art` | 16 px² / 4 | `general` | 开启 |
| `input_3.png` 密集铜丝 | `line_art` | 16 px² / 4 | `general` | 开启 |
| `input_4.png` 真实根系 | `intensity`，亮前景，低阈值比 0.8 | 不修复微孔 | `general` | 关闭 |

四图均为未知物理尺度。若在 GUI 复核这些参数的结果，先用 API 完成预处理，再在 GUI 选择其二值/骨架目录与对应模型和上下文选项。不能把四张不同类型图一起按同一种分割方式、同一种模型批处理后称为同一复现实验。

仓库已经提供 [四图复现脚本](../scripts/reproduce_four_examples.py)，它读取上述参数 JSON 并校验输入哈希，无需手工复制参数：

```bash
python scripts/reproduce_four_examples.py --images 1
python scripts/reproduce_four_examples.py --images 2 3 4
```

不指定 `--images` 时计算全部四张，真实图耗时较长。`--output-dir` 可以指定输出目录，默认 `results/four_examples`；`--no-figures` 只计算数据、不导入 Qt 绘图组件。例如：

```bash
python scripts/reproduce_four_examples.py --images 1 --no-figures --output-dir results/first_example
```

输出包含 `processed_N` 下的二值/骨架、`figure_N.png`、`metrics_N.json`、`points_N.csv`、`metrics.csv` 及 `provenance.json`，记录输入、参数、源码/依赖信息和本次运行情况；`--no-figures` 时不生成图片。每次的合并 CSV 和运行记录只包含本次所选图，不累计之前分次运行的样本；需要一张四图汇总表时一次运行全部四张。

每张图通过 `analyze_root_image` 运行，再将返回的结果传给软件实际的 `AnalysisResultViewer`。没有按期待的计数另行补点；PNG 是软件绘图组件导出的结果，不是人工绘制的示意图。

### 8.3 人工根冠与显式根基

API 支持 `base_rc=(row, column)` 指定根基附近的图节点，或 `crown_box=[row_min, column_min, row_max, column_max]` 指定人工确认的根冠区域。坐标按**原图像素、左上角为原点、行在前列在后**，不是常见的 `(x,y)` 顺序。

也可在二值图旁保存同名标注文件，例如：

```text
processed/binary/sample_01.png
processed/binary/sample_01.png.review.json
```

其中 JSON 格式示例为：

```json
{"crown_box": [10, 120, 90, 230]}
```

这些数字仅演示格式，必须换成当前图像人工核查的真实区域。矩形内需包含合适的连通图节点。读取失败、坐标反转或区域无效时标记 `invalid_crown` 并记录原因；不要扩大矩形来强行隐藏错误分叉。当前侧车文件读取的是 `crown_box`，显式 `base_rc` 使用 API 参数；GUI 没有绘制这类标注的专门工具。人工根冠标注与 `shared_crown` 模型也是两个不同操作，必须分别记录。

## 9. 如何读取指标与质量字段

### 9.1 常用字段

| 字段 | 解释 |
|---|---|
| `Num_Bases` | 算法确定的根基数量，根基不计入 Tips |
| `Num_Tips` | 可见骨架末端总数，包含疑似裁切、边界或碎片端点；复杂图中是候选根尖 |
| `Num_Forks` | 分叉/连接点候选数，不是整条侧根的数量，也不是图边数 |
| `Num_Crossings` | 根据几何与图结构条件识别的交叉候选数；可能漏判或误判 |
| `Num_Junctions` | 连接相关汇总计数，须结合分叉和交叉解释 |
| `Root_Length_px` / `Root_Length_cm` | 最终用于量化的路径总长；重建模型可能包含推断段 |
| `Projected_Path_Length_px` | 观测图的路径长度，用于区别模型重复分配的共享段 |
| `Avg_Root_Diameter_px` / `Avg_Root_Diameter_mm` | 路径长度加权的直径估计，不是各根简单算术平均 |
| `Root_Surface_Area_*` / `Root_Volume_*` | 依据局部直径与路径、圆柱近似计算；不是三维实测值 |
| `Avg_Link_Length_*` | 图中连接段平均长度，不等同于每条完整侧根的平均长度 |
| `Tip_Density_*` / `Branch_Density_*` | 端点或分叉计数除以路径长度 |
| `Topological_Index`、`TI_*`、`Strahler_*` | 依赖有效根基及树状关系的层级指标 |
| `Fractal_Dimension`、`Fractal_Abundance` | 二值投影在有限尺度上的盒计数拟合指标 |
| `MF_*` | 二值投影的多重分形量与拟合诊断 |

字段末尾 `px`、`px2`、`px3` 为像素单位，`cm`、`cm2`、`cm3`、`mm` 为物理单位。指标的严格定义、拟合区间和公式见 [技术方案](TECHNICAL_METHODS.md)。

### 9.2 必须随数据保存的质量信息

| 字段 / 状态 | 正确解释 |
|---|---|
| `Scale_Source=metadata` | 采用图像元数据中的尺度，仍需实验记录支持 |
| `Scale_Source=user_supplied` | 使用者显式提供 DPI |
| `Scale_Source=unknown` | 无可信尺度，厘米、毫米等列不应当作测量值 |
| `Topology_Status=ok` | 当前结构满足算法的一致性条件；不是人工准确率证明 |
| `Topology_Status=model_assumed` | 结果依赖显式共同根基模型 |
| `Topology_Status=unresolved` | 交叉、环或连接关系未解决；相关层级指标未定义 |
| `Topology_Status=invalid_crown` | 根冠标注无效，查看 `Topology_Error` |
| `Cycle_Rank` | 未消解环的数量诊断；大于 0 提醒图不是简单树 |
| `Num_Components` | 连通分量数；大于 1 可能涉及散根、断裂或背景碎片 |
| `Num_Uncertain_Junctions` | 仍有歧义的连接点数，是候选连接点的诊断子集 |
| `Num_Fragment_Endpoints` / `Num_Boundary_Endpoints` / `Num_Possible_Crop_Endpoints` | 端点诊断，不要与 `Num_Tips` 再相加 |
| `Diameter_Measured_Length_Fraction` | 可以直接可靠测宽的路径覆盖比例 |
| `Diameter_Unresolved_Length_Fraction` | 无法可靠确定直径的路径比例 |
| `Path_Inferred_Length_Fraction` | 推断路径长度占总路径长度的比例 |
| `Crown_Annotation` | 根冠来自人工矩形、局部推断，或没有标注 |
| `MF_Quality`、`MF_Min_R2`、`FD_R2` | 有限尺度拟合质量，需结合有效尺度和数据图审查 |

CSV 中比例字段采用 0–1；GUI 指标栏明确标 `%` 的对应项显示为百分数。未直接测得与完全无法确定并非同一类：一部分直径可从同一根的可测段估计。详细分类见技术说明。

**N/A 与 0 不同。** 0 表示实际返回的零值；N/A 表示没有定义或前提不足。例如，含未解决连接关系时不能把不可计算的 Strahler 级序、TI 或角度改写为 0。Excel 和 CSV 中的空值也应保留。

疑似裁切端点已经并入可见端点显示，软件保留诊断字段便于追溯。第四张真实图中的端点包含大量可能的碎片或断裂端，不能直接解释成已确认的完整根尖。

## 10. 常见问题

| 现象 | 检查和处理 |
|---|---|
| 找不到 Python / 模块 | 确认使用虚拟环境解释器；用同一个 `python -m pip` 安装依赖 |
| EXE 缺 DLL、Qt 插件或无法启动 | 检查是否完整解压，`_internal` 是否同级；查看发行自检报告和系统提示 |
| macOS 安装 PyQt5 失败 | 核对 Python 版本和架构、依赖安装包匹配情况；此平台未实机验证 |
| 找不到样本对 | 两目录同名主干、平铺放置、扩展名可识别；刷新样本列表 |
| 根全黑或背景全白 | 检查前景极性和方法；line_art 固定用于白底黑线 |
| 细根断裂、末端大量增加 | 先检查分割和 JPEG 损伤；不要直接靠删除端点让计数接近期望 |
| 相邻根粘连、分叉过多 | 检查闭运算和填孔；先减小会改变连接关系的处理，再复核原图 |
| 根基被当根尖 | 核对根基方向及是否为散根模式；必要时通过人工标注/API 提供根基信息 |
| 共同根基仍有分叉 | 检查所选模型是否适用于该样本，以及是否满足可重建图条件 |
| cm/mm 列空白 | 查看 `Scale_Source`，未知尺度保留像素量；不要随意补 300 或 600 DPI |
| TI、角度或 Strahler 为 N/A | 检查根基、连通块、环和拓扑状态；无需强行补值 |
| 很慢或内存占用大 | 先单张、并行数设 1；密集真实图远多于简单线图的图节点和交会，耗时不同 |
| 历史 CSV 的数值与当前图不符 | 核对版本、处理参数及人工修改记录，并重新分析当前二值/骨架文件 |

复杂真实图像中的遮挡无法仅靠单幅二维投影唯一恢复。分割、结构解释和几何测量是不同阶段；单像素骨架是计算工具，不会自动消除交叉、贴合或根冠歧义。

## 11. 回归检查与 Windows 编译

在源码环境中执行：

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python build_exe.py
```

编译脚本使用当前 Python 环境和 `RootArchitecture.spec`。Windows 默认输出为 `dist/RootArchitecture/RootArchitecture.exe`；编译目录、日志和验证文件在 `build`。可用 `--output-dir` 和 `--work-dir` 指定其他位置，例如：

```powershell
python build_exe.py --output-dir ../dist/RootArchitecture_NoKey_V1.0.0 --work-dir ../build/no_key_release
```

目标应用目录已存在时，脚本停止并要求选择新输出目录，不会静默覆盖既有发行版。构建过程检查分析计算、并行工作进程和正常 GUI 启动，并核查可执行归档未包含已移除的激活模块。最终交付保留整个应用目录；数据集属于独立源码/数据包，不要求复制进 `_internal`。

当前编译脚本专门生成 Windows 便携 EXE，不生成 macOS 安装包，也不生成 Inno Setup 安装器。macOS 用源码 GUI 或 CLI。不要把旧版本的打包选项（例如 `--pyonly`）用于本脚本。

## 12. 给论文作者的可复现记录

用于 CEA 稿件时，保存以下实际记录，并与技术方案对照：

1. 使用的软件版本、源码归档或提交标识、依赖版本与运行平台。
2. 原图来源、原生尺寸、文件哈希、裁切或缩放记录；实物标尺/扫描 DPI 的原始记录。
3. 每组样本的分割方式、前景极性、去噪/填孔/闭运算和微孔处理参数。
4. 原图、最终二值图、最终骨架、人工擦除和根冠标注记录。
5. 根系方向、一般/共同根基模型、交叉上下文开关及其使用依据。
6. 完整指标和质量字段，不能只保留看起来正确的计数或只导出图中一部分指标。
7. 人工标注/实物真值的来源、独立验证样本、定位和计数误差、长度与直径误差、失败案例。

已有铜丝和真实图示例可以展示处理流程及限制，但缺少实物记录的样本不能用于宣称绝对长度、表面积、体积的实测准确率。回归测试通过只能证明测试覆盖的代码行为，不能替代真实样本的独立准确性评估。

本指南内的数学公式使用 GitHub 支持的 LaTeX 数学语法；完整推导在 [TECHNICAL_METHODS.md](TECHNICAL_METHODS.md)。阅读时应使用支持数学渲染的 Markdown 查看器或项目提供的渲染版文档，不要以纯文本编辑器显示的反斜杠判断公式错误。

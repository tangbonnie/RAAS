# RAAS V1.0.0 使用指南

本指南说明 Windows EXE、Windows/macOS 源码 GUI、命令行和四张示例的运行方法。正式作者为唐清芸（石河子大学农学院、新疆农垦科学院），软件版权人为王国栋（新疆农垦科学院）。软件无需密钥或激活码。

## 1. 安装与启动

### Windows EXE

1. 从 [GitHub Releases](https://github.com/tangbonnie/RAAS/releases) 下载最新 Windows 便携包。
2. 将整个压缩包解压到可写目录，双击 `RootArchitecture.exe`。
3. 保留 `_internal` 文件夹及全部运行文件，不要单独移动 EXE。
4. 无需安装 Python。EXE 提供 GUI；命令行使用源码发行版。

不要将结果保存到只读目录。遇到启动失败，可先确认完整解压，查看日志和依赖是否齐全；从源码运行便于取得详细错误信息。

### Windows Python GUI

安装 Python 3.12 或 3.13。以下 PowerShell 示例使用 Python 3.12：

```powershell
git clone https://github.com/tangbonnie/RAAS.git
cd RAAS
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe root_gui.py
```

也可使用 `launcher.py` 启动 GUI。后续命令中的 `python` 应换成此虚拟环境的解释器，或先启用环境。

### macOS Python GUI

安装与 Apple Silicon 或 Intel 架构对应的 Python 3.12：

```bash
git clone https://github.com/tangbonnie/RAAS.git
cd RAAS
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python root_gui.py
```

Windows EXE 不能原生运行于 macOS；本次发行没有 macOS 应用包，尚未进行 macOS 实机验证。安装失败时先检查 Python 版本、CPU 架构和报错依赖，避免混用不同架构的解释器与二进制包。

## 2. 图像准备

- 一张输入图中使用一致的根/背景极性；白底黑线铜丝和黑底白根应分别处理。
- 保留原图，预处理和人工擦除在独立输出目录进行。
- 检查细根是否可见、图像是否失焦、粗根基是否出现孔状拍摄伪影。
- 二值图和骨架必须尺寸相同、样本名称相同、坐标一致。骨架为单像素线。
- DPI 只能来自可信采集记录或实物标尺；截图、文件名中的数字不构成可靠标定。

仓库仅随附 [四张测试图像](../datasets/README.md)，均未提供可信物理尺度和完整实物真值。不要将它们当成具有标准答案的准确率数据集。

## 3. GUI 操作

### 3.1 预处理

1. 打开图像预处理页，选择原图目录和输出目录。
2. 选择一张代表图及分割方法，先预览当前图像。
3. 对照原图检查二值图：细根是否丢失，背景是否混入，相邻根是否粘连。
4. 检查骨架连通关系，确认后批量处理。
5. 输出写入 `binary/` 和 `skeleton/`，失败样本及原因见处理日志。

| 方法 | 常见用途 | 注意 |
|---|---|---|
| `line_art` | 白底黑线、铜丝模拟图 | 固定暗前景阈值 128/255 |
| `intensity` | 黑底亮根等亮度对比明显图像 | 用强弱阈值连通保留较弱细根；检查噪声 |
| `otsu` | 照明较均匀的亮度分割 | 检查前景极性 |
| `adaptive` | 背景亮度不均匀 | 窗口和偏移需逐图核对 |
| `texture` / `multiscale` | 纹理差异明显的图像 | 不保证适合弱细根 |

普通去小连通域和填孔阈值是像素面积；增大参数可能删除短根或把相邻根粘在一起。`line_art`、`intensity` 不使用一般形态学后处理流程，专门的微孔与粗根基修复是另外的显式选项。

### 3.2 粗根基伪孔修复（默认关闭）

粗根基因拍摄亮度或纹理形成内部封闭暗孔时，骨架可能沿孔边生成多条线，产生虚假的分叉、交叉和末端候选。可在预处理页勾选“修复粗根基内部伪孔 / Repair stem pores”，并设置“根基位置 / Stem side”。

- 方向 `top/bottom/left/right` 表示根基位于图像上/下/左/右。
- 修复局限于指定方向粗根基区域内符合条件的封闭伪孔；不对整张根系无差别填孔。
- 修复二值图后重新生成骨架，再使用这组新二值图和新骨架进行分析。
- 开启后比较原图、二值图和识别点，确认被填区域属于粗根基内部拍摄伪影。
- 真实孔隙与拍摄伪孔仅凭单图可能无法区分。保留修复前结果，记录是否开启，不能为了降低分叉计数随意启用。
- 此功能不恢复遮挡根，不自动修补所有断根，也不代替交叉识别。

启用后，`stem_repair/` 保存增加像素的掩膜与 JSON 记录，二值图和骨架 PNG 的 `Stem_Repair` 元数据保持一致。结果表的 `Stem_Repair_Status`、`Stem_Repair_Holes`、`Stem_Repair_Pixels`、`Stem_Repair_ROI` 和 `Stem_Repair_Assumption` 记录是否实际修复、填孔数量、推断像素及区域。修复后的长度、宽度及面积等指标均以这张修补掩膜为条件；填入像素不是原照片直接观测到的组织。

### 3.3 人工擦除

图像擦除页用于在二值图和骨架上同步擦除噪声。保存会覆盖当前处理文件，先保留副本；擦除后重新分析。此页不是完整的根系拓扑人工标注工具。

### 3.4 分析

1. 选择配对的二值图目录、骨架目录和结果目录。
2. 设置 DPI、根基方向、模型和交叉上下文。
3. 先分析当前样本，核对三栏结果，再批量运行。
4. 高分辨率样本先用较少并行进程，确认内存允许后增加。

**DPI：** GUI 的 0 表示自动读取尺度。无可信记录时保持 0，输出像素单位；有效非零值表示使用者明确指定的 DPI。

**根基方向：** `top/bottom/left/right` 指根基所在方向；`none` 适用于无明确单一根基的散根图。无有根树前提时，部分级序/拓扑指标不可用。

**模型：** 默认 `general` 允许真实分枝。`shared_crown` 仅用于已知各根独立、没有侧分枝并从共同根基发出的构型；贴合段长度按模型推断。它与粗根基伪孔修复是两个不同设置，不能互相替代。

**交叉短段上下文：** 用短连接段周围结构辅助局部交叉判断。关闭并不等于关闭全部交叉检测；选择应依据图像核查，不依据想得到的计数。

### 3.5 结果图与导出

- 左栏：本次分析使用的二值图。
- 中栏：骨架与软件返回的识别点。黄色为根基，青色为可见端点，红色为分叉候选，蓝色为交叉候选。
- 右栏：几何、拓扑、分形指标与质量字段；无法有效计算时显示 `N/A`。

可以缩放、平移、切换识别点图层并保存当前图像。图层显示设置不改变算法返回的数量。结果表可保存 CSV 或 Excel；仅有历史 CSV 时不含完整图像和点位缓存，恢复叠加图应保留原二值图、骨架和处理参数。

## 4. 命令行模式

以下命令在启用相应 Python 环境的 Windows 和 macOS 中通用。先准备只含同一图像类型的 `input/`。

### 白底黑线

```bash
python preprocess.py -i input -o processed --method line_art
python root_analysis.py -b processed/binary -s processed/skeleton -o results --root-direction top
```

### 黑底亮根及可选粗根基修复

```bash
python preprocess.py -i input -o processed --method intensity --foreground light --repair-proximal-stem --stem-direction top
python root_analysis.py -b processed/binary -s processed/skeleton -o results --root-direction top --no-crossing-context
```

不需要粗根基修复时去掉 `--repair-proximal-stem`。上下文开关应按样本选择；上述关闭设置用于演示，与四图真实根系示例的设置一致。

| 常用选项 | 作用 |
|---|---|
| 预处理 `-i`、`-o` | 原图目录、处理输出目录 |
| `--method` | 分割方法 |
| `--foreground auto/dark/light` | 前景极性；`line_art` 固定暗前景 |
| `--repair-proximal-stem` | 开启粗根基封闭伪孔修复，默认关闭 |
| `--stem-direction top/bottom/left/right` | 粗根基所在方向 |
| 分析 `-b`、`-s`、`-o` | 二值图、骨架、结果目录 |
| `--root-direction top/bottom/left/right/none` | 分析根基方向 |
| `--root-model general/shared_crown` | 一般模型或已知无侧枝的共同根基模型 |
| `--no-crossing-context` | 关闭交叉短段上下文 |
| `--dpi` | 用户确认的 DPI 覆盖值；未知时不填 |

完整参数以运行 `python preprocess.py --help` 和 `python root_analysis.py --help` 的结果为准。预处理目录中 `binary` 和 `skeleton` 必须相互对应；不要混用不同参数生成的图。

## 5. 四张测试图复现

| 输入 | 内容 | 分割 | 模型 |
|---|---|---|---|
| `input_1.png` | 贴合、共同根基铜丝 | `line_art` | `shared_crown` |
| `input_2.png` | 重叠铜丝 | `line_art` | `general` |
| `input_3.png` | 密集铜丝 | `line_art` | `general` |
| `input_4.png` | 黑底白色真实根系 | `intensity` | `general` |

示例在 `datasets/four_examples/original/`。确切参数、修复开关、输入尺寸及 SHA-256 以 [analysis_parameters.json](../datasets/four_examples/analysis_parameters.json) 为准；复现脚本读取该文件，不需要把四张不同类型图用同一种方法批量处理。

```bash
python scripts/reproduce_four_examples.py --images 1
python scripts/reproduce_four_examples.py --images 2 3 4
python scripts/reproduce_four_examples.py
```

最后一条运行全部四张，真实根系较耗时。仅计算数据可加 `--no-figures`，输出目录可用 `--output-dir` 修改。

默认 `results/four_examples/` 包含处理后的二值图与骨架、软件三栏图 `figure_N.png`、单图指标 JSON、点位 CSV、合并指标 CSV 和运行来源记录。每次合并表只包含本次所选图；需要四图同表时一次运行全部四张。绘图来自真实 `AnalysisResultViewer` 组件，不是根据预期数量人工补点。

## 6. 结果解释与尺度

| 字段 | 含义和限制 |
|---|---|
| `Num_Tips` | 扣除根基后的可见骨架端点，包含疑似裁切、碎片和边界端点；不是全部已确认的生物学根尖 |
| `Num_Forks` | 分叉/连接候选，不等于侧根根数 |
| `Num_Crossings` | 根据局部几何及图结构识别的交叉候选 |
| `Root_Length_px` | 用于测量的路径总长；共享根基模型可能含推断段 |
| `Projected_Path_Length_px` | 可见投影图路径长度 |
| `Avg_Root_Diameter_px` | 路径长度加权的直径估计 |
| `Root_Surface_Area_*`、`Root_Volume_*` | 基于局部宽度和路径、圆柱近似的估计，不是三维实测值 |
| `Scale_Source` | 标尺来源；`unknown` 时不能解释为厘米 |
| `Topology_Status` | 结构质量状态；`ok` 不代表测量无误差 |
| 未消解环、未确定连接、测宽覆盖率 | 检查拓扑和几何估计能否解释的必要信息 |

物理尺度必须来自可信 DPI 或实物标尺。像素边长为 `2.54 / DPI` 厘米，长度、面积、体积按相应的一、二、三次方换算。文件名中含数字 `600` 不会自动建立 600 DPI 标定。四张测试图以像素报告，不能补造实物真值。

密集重叠、断裂和拍摄伪影仍可能影响分割与拓扑。无法定义或前提不足的指标显示 `N/A`，不能用 0 替换。共享根基推断、粗根基修复和人工修改都应随结果记录。

## 7. 测试、编译和常见问题

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python build_exe.py
```

最后一条仅在 Windows 使用，输出整个 `dist/RootArchitecture/` 便携目录。合成几何测试验证实现，不代表真实样本具有相同精度。历史外部铜丝图片已从公开仓库移除，缺失数据时其专门测试报告跳过；实际通过数和跳过数应分别记录。

- **指标为空或 N/A：** 先检查尺度和质量字段，不要填入任意 DPI 或把空值替换成 0。
- **粗根基上大量红蓝点：** 先核对二值图是否存在拍摄伪孔，符合条件时启用可选修复并重新预处理、分析。
- **细根缺失：** 先调整分割方法和阈值；骨架算法无法恢复二值图里已经丢失的根。
- **明显交叉仍识别成分叉：** 二维遮挡本身可能无法唯一辨别，检查局部图和质量信息，不能保证全自动还原。
- **EXE 找不到运行库：** 重新完整解压便携包，保留 `_internal`。

本仓库仅公开软件代码、运行资源、四张测试图和必要 MD；论文技术方案与排版文档不在本次上传范围内。许可见 [LICENSE.md](../LICENSE.md)、[LICENSE-DOCS.md](../LICENSE-DOCS.md) 和 [第三方声明](THIRD_PARTY_NOTICES.md)。

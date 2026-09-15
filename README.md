# Root Architecture — 根系构型参数量化分析系统

**V1.0.0 · 无激活码发行版 · Python / Windows GUI / macOS 源码运行 / 命令行**

项目仓库：[tangbonnie/RAAS](https://github.com/tangbonnie/RAAS)。

本软件从二维根系图像生成二值掩膜和单像素骨架，再计算根长、直径、表面积与体积估计、可见端点、分叉与交叉候选、分支角、拓扑指数、Strahler 级序、分形和多重分形指标。图形界面同时显示二值图、骨架识别点和指标表，并支持批处理与 CSV、Excel、图片导出。

- **正式作者：** 唐清芸（石河子大学农学院、新疆农垦科学院）
- **软件版权人：** 王国栋（新疆农垦科学院）
- **版本：** V1.0.0；源码许可证见 [LICENSE](LICENSE)，文档许可证见 [LICENSE-DOCS.md](LICENSE-DOCS.md)，引用信息见 [CITATION.cff](CITATION.cff)。数据的来源和权利状态单独见 [数据集说明](datasets/README.md)。依赖保持各自许可证，见 [第三方声明](docs/THIRD_PARTY_NOTICES.md)；本项目 MIT 许可证不替代 PyQt5、Qt 等依赖的条款。

## 从这里开始

| 需要 | 文档 / 入口 |
|---|---|
| Windows EXE、Windows/macOS GUI、命令行、参数与结果解释 | [详细使用指南](docs/USER_GUIDE.md) |
| 用于 CEA 论文的方法、实现细节、数学公式和适用条件 | [技术方案与公式](docs/TECHNICAL_METHODS.md) |
| 直接离线阅读排版后的公式 | [技术方案 HTML](docs/TECHNICAL_METHODS.html) · [使用指南 HTML](docs/USER_GUIDE.html) |
| 数据目录、原图尺寸、文件哈希、未纳入的大文件 | [数据集说明](datasets/README.md) · [数据清单](datasets/manifest.csv) |
| 运行图形界面 | `python root_gui.py` 或 `python launcher.py` |
| 自动化分析 | `python preprocess.py --help` 和 `python root_analysis.py --help` |

## 安装与启动

先进入包含本 README 的项目目录。当前实际验证环境为 **Windows x64、Python 3.13.12**。其他系统可按以下方式从源码安装；**本次没有在 macOS 上实机验证，也没有生成 macOS 应用包**。

仓库发布后，可用 Git 获取源码，或在 GitHub 选择 Code → Download ZIP 后解压：

```bash
git clone https://github.com/tangbonnie/RAAS.git
cd RAAS
```

### Windows 源码运行

安装 Python 3.12 或 3.13 后，在 PowerShell 中运行；下面以已安装的 3.12 为例：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe root_gui.py
```

已取得 Windows 便携发行包时，完整解压后双击 `RootArchitecture.exe`。必须保留同目录的 `_internal`，不需要另装 Python，**不需要密钥或激活码**。EXE 是 GUI 入口；命令行批量处理使用下述 Python 脚本。

### macOS 源码运行

以已安装 Python 3.12 为例，在“终端”运行：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python root_gui.py
```

Apple Silicon 与 Intel Mac 的解释器、依赖须对应机器架构。Windows `.exe` 不能作为 macOS 原生程序运行。平台问题处理见使用指南。

## 命令行最短流程

以下命令在已经启用虚拟环境时适用于 Windows 和 macOS；也可以把 `python` 换为该环境解释器的完整路径。先把少量代表性原图放入 `input` 目录。

```bash
python preprocess.py -i input -o processed --method line_art
python root_analysis.py -b processed/binary -s processed/skeleton -o results --root-direction top
```

`line_art` 适用于白底黑线模拟图；真实图像要先比较分割方法及预览。`processed/binary` 和 `processed/skeleton` 的样本文件名必须相同。未提供可信物理尺度时结果使用 px、px²、px³，物理单位列留空；只有确认真实扫描分辨率后才使用 `--dpi 600` 等覆盖值。

## 准确性和结果边界

- 一般模型 `general` 是默认选项。`shared_crown` 仅适用于**已知各根独立、没有侧分枝、从共同根基发出**的样本；其共享段属于模型推断，不能用于消除真实侧根。
- `Num_Tips` 为扣除根基后的可见骨架端点计数，包含疑似裁切端点；端点不等于逐一人工确认的生物学根尖。
- 分割误差、遮挡、断裂与密集重叠会影响所有后续指标。`Topology_Status=ok` 仅表示结构一致性检查通过，不代表测量误差为零。
- `unresolved`、`model_assumed`、未消解环及测宽覆盖率均需随结果报告。没有定义或可信前提不足的指标显示 `N/A`，不要替换成 0。
- 仓库中的四张示例用于检查流程和识别点，不具有完整实物测量真值。复杂真实根系尚未达到全自动精准量化，不能把当前输出直接当作论文验证真值。

## 项目结构

```text
.
├── root_gui.py / launcher.py       # 图形界面与启动器
├── preprocess.py                  # 分割、后处理与骨架化
├── root_segmentation.py           # 亮度滞后分割
├── root_analysis.py               # 统一分析入口、CLI 与结果表
├── root_topology.py               # 图结构、交叉处理、测量与拓扑指标
├── root_crown.py                   # 根冠、微孔处理与共同根基模型
├── calibration.py                 # 尺度来源与单位换算
├── assets/                        # 程序图标和界面资源
├── tests/                         # 算法与发行回归检查
├── datasets/                      # 图像及来源、参数、哈希清单
├── docs/                          # 使用指南和技术方案
├── requirements.txt               # 依赖范围
├── requirements-lock.txt          # 当前 Windows 验证环境的固定版本
└── build_exe.py / RootArchitecture.spec
```

本目录用于上传源码、运行所需资源、文档与数据集；不包含本地虚拟环境、历史分析结果、密钥或旧发行包。Windows 编译产物单独交付，并适合放在 GitHub Releases 中，而不纳入源码历史。

## 验证与编译

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python build_exe.py
```

编译 Windows EXE 请在 Windows 上执行；输出为 `dist/RootArchitecture/RootArchitecture.exe`，发布时保留整个 `RootArchitecture` 目录。回归检查验证限定行为，不等同于对全部生物样本完成准确性验证。

本次 Windows 发布检查：127 项回归测试通过；冻结 EXE 的图像分析、未知尺度、并行子进程、GUI 渲染、资源和无需激活的普通启动均通过。公式渲染器逐项检查了技术方案的 50 个独立公式与 129 个行内公式；HTML 及字体随项目提供，可离线阅读。完整记录见 [发布验证](docs/RELEASE_VALIDATION.md)。

四图按记录参数复现：`python scripts/reproduce_four_examples.py --images 1` 先计算图①；去掉 `--images 1` 计算全部四张。默认输出软件三栏结果图、点位、指标及运行记录至 `results/four_examples`；`--no-figures` 仅导出数据。

论文写作请引用软件版本、数据来源、分割参数、尺度来源、根系模型、交叉参数和质控结果，方法与公式以 [技术方案](docs/TECHNICAL_METHODS.md) 为准。

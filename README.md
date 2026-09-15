# RAAS — 根系构型参数量化分析系统

**V1.0.0 · 无激活码 · Windows EXE / Windows 与 macOS 源码 GUI / 命令行**

RAAS 将二维根系图像分割为二值图和单像素骨架，计算根长、直径、表面积与体积估计、可见端点、分叉与交叉候选、分支角、拓扑及分形指标。软件三栏结果同时显示二值图、骨架识别点和指标表，支持批处理与结果导出。

- **正式作者：** 唐清芸（石河子大学农学院、新疆农垦科学院）
- **软件版权人：** 王国栋（新疆农垦科学院）
- **下载 Windows 便携包：** [GitHub Releases](https://github.com/tangbonnie/RAAS/releases)
- **操作说明：** [使用指南](docs/USER_GUIDE.md)
- **测试图像：** [三张铜丝与一张真实根系](datasets/README.md)

## Windows EXE

从 Releases 下载最新 Windows 便携包并完整解压，双击 `RootArchitecture.exe`。保留同目录的 `_internal` 及其全部文件。无需安装 Python，无需密钥或激活码。EXE 是 Windows 图形界面入口；命令行分析使用源码脚本。

## Windows 源码 GUI

安装 Python 3.12 或 3.13，在项目根目录运行：

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe root_gui.py
```

## macOS 源码 GUI

安装与机器架构对应的 Python 3.12 后运行：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python root_gui.py
```

macOS 使用 Python 源码入口，不能原生运行 Windows EXE。本项目尚未完成 macOS 实机验证。

## 命令行

以下命令在已启用 Python 环境的 Windows 和 macOS 中通用。`input` 目录应只放同一处理类型的图像。

```bash
python preprocess.py -i input -o processed --method line_art
python root_analysis.py -b processed/binary -s processed/skeleton -o results --root-direction top
```

白底黑线铜丝采用 `line_art`。黑底亮根可用 `intensity --foreground light`，先检查二值图是否保留细根。

### 可选：粗根基伪孔修复

拍摄造成粗根基内部出现封闭暗孔时，可在 GUI 预处理中勾选“修复粗根基内部伪孔 / Repair stem pores”，或运行：

```bash
python preprocess.py -i input -o processed --method intensity --foreground light --repair-proximal-stem --stem-direction top
python root_analysis.py -b processed/binary -s processed/skeleton -o results --root-direction top
```

该功能**默认关闭**，仅在指定方向的粗根基区域内修复满足条件的封闭伪孔，再生成骨架。`top` 表示根基在上方；其他方向按实际摆放选择。启用后核对修复区域与原图，真实空隙不应被当成拍摄伪孔。它不能恢复被遮挡的根，也不能解决所有断裂和交叉问题。

## 四张示例

仓库仅保留 `datasets/four_examples/original/input_1.png` 至 `input_4.png`。逐图处理设置和输入哈希在 `datasets/four_examples/analysis_parameters.json`。

```bash
python scripts/reproduce_four_examples.py --images 1
python scripts/reproduce_four_examples.py --images 2 3 4
```

不指定 `--images` 会运行全部四张。实际软件组件生成的结果图、指标、点位和运行记录位于 `results/four_examples`。每次合并表只包含本次所选图像。

## 解释结果

- 无可靠 DPI 或标尺时，使用 px、px²、px³；不要为得到厘米指标填写猜测的 DPI。
- `Num_Tips` 是扣除根基后的可见骨架端点，包含疑似裁切端点；它不是逐个人工确认的生物学根尖。
- `general` 为默认模型。`shared_crown` 只用于已知各根独立、没有侧分枝并共用根基的样本；共享段属于模型推断。
- 图中密集重叠、拍摄伪影和分割错误仍可能影响指标。检查 `Topology_Status`、未消解环、测宽覆盖率和 `N/A`；四张示例没有完整实物真值。

## 测试与编译

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python build_exe.py
```

Windows EXE 必须在 Windows 上编译，产物为 `dist/RootArchitecture/`。历史外部铜丝数据未随精简仓库发布；依赖该数据的可选测试缺失时应报告跳过，不能计为通过。其余合成几何和接口回归仍应执行。发布检查见 [验证记录](docs/RELEASE_VALIDATION.md)。

## 目录与许可

源码位于根目录，`assets/` 为运行资源，`tests/` 为测试代码，`datasets/` 仅含四张示例与参数，`docs/` 为操作与许可 MD。编译产物放在 Releases；开发环境、分析结果和论文技术文档不进入仓库。

[源码许可](LICENSE.md) · [原创文档许可](LICENSE-DOCS.md) · [第三方许可文本](docs/THIRD_PARTY_NOTICES.md)。源码许可不自动覆盖图像数据及第三方依赖。

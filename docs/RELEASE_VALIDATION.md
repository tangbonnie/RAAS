# V1.0.0 无激活码发行检查

验证日期：2026-09-15。平台：Windows x64，Python 3.13.12。这是软件发行检查，不是所有根系图像的生物学精度验证。

## 已执行

- 在整理后的独立源码目录运行完整测试：**127 passed in 22.13 s**。
- 实际编译 Windows PyInstaller 便携应用，检查冻结归档中不存在 `license_manager`。
- 冻结 EXE：已知合成图的 3 端点 / 2 分叉 / 1 交叉、缺少尺度时物理量为空、两个 spawn 子进程分析、三栏结果绘制及机构图标均通过。
- 普通启动路径创建主窗口，默认一般根系模型，未经过任何激活检查；不是仅验证绕过启动流程的计算入口。
- 发布目录的四图复现脚本实际运行图①：16 可见端点 / 0 分叉 / 0 交叉，输出真实软件三栏图与点位表，未知尺度未被改写为物理单位。
- 数据集 110 个图像文件（82 铜丝、4 核查图、24 真实根系 JPEG）逐文件 SHA-256 核对；图像总计 44,278,948 字节，没有字节重复或超过 GitHub 普通文件限制的大图。
- 技术方案采用 GitHub `$...$` 和 `$$...$$` 语法；离线 HTML 由 KaTeX 对全部表达式严格解析后生成，统计见 `FORMULA_RENDER_CHECK.json`。HTML 附带 CSS、字体与 KaTeX 许可证，不需要在线加载公式资源。

## 复现

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python scripts/reproduce_four_examples.py --images 1 --output-dir results/example1
python build_exe.py
```

构建日志在 `build/no-key-时间戳/`，成功后的 `dist/release-manifest.json` 记录 EXE、源码 SHA-256 和冻结运行检查。若 OneDrive 阻止目录移动，当前构建器保留暂存副本并复制交付，不删除暂存目录。`--verify-existing` 可重新检查源码哈希一致的已构建目录。

可选：修改 Markdown 后重新渲染离线 HTML（仅文档构建需要 Node.js）：

```bash
npm install --prefix scripts/docs_renderer
node scripts/render_docs.cjs
```

## 未验证范围

- 本次没有在 macOS 或另一台干净 Windows 机器运行；使用手册的 macOS 部分为源码安装与操作说明。
- 没有 Windows 数字签名或 macOS 签名、公证；未生成 macOS `.app`。
- 没有可靠实物真值证明密集重叠图的所有端点、连接和根径正确；四图旧结果与方法假设见技术方案。
- 当前附件缺乏可信尺度，不能将像素数当作厘米；真实根系 JPEG 中的 DPI 元数据也需由成像记录确认。
- 本次仅检查代表性图像和已有回归用例，没有重新运行所有历史大数据基准。

# 第三方组件与许可说明（Third-Party Notices）

本项目源码通过命令行调用外部可执行文件，未将第三方二进制链接进 Python 代码。
Release 包中随附了以下二进制，分发时请保留本说明。

---

## 1. FFmpeg / FFprobe

- 版本：N-128433-gdb8537d8cc（BtbN `FFmpeg-Builds` 的 `win64-gpl` 静态构建）
- 来源：https://github.com/BtbN/FFmpeg-Builds
- 许可：FFmpeg 本体为 LGPL v2.1+；本项目使用的构建启用了 GPL 组件（libx264、libx265 等），
  因此该二进制整体按 **GPL** 分发（具体版本以 FFmpeg 源码与构建配置为准）。
- 使用方式：作为**独立可执行文件**被 `subprocess` / `QProcess` 调用，未链接进应用本体。
- 合规提示：
  - 若对外分发本 Release，请同时提供 FFmpeg 的许可证文本与对应源码获取方式；
  - 商业闭源分发建议改用 LGPL 构建或取得合规评估，或让用户自行安装 ffmpeg。
- 参考：
  - FFmpeg 法律信息：https://ffmpeg.org/legal.html
  - FFmpeg 源码：https://ffmpeg.org/download.html
  - BtbN 构建说明：https://github.com/BtbN/FFmpeg-Builds#license

## 2. PySide6 / Qt

- 来源：https://pypi.org/project/PySide6-Essentials/
- 许可：LGPLv3 / GPLv3 / Qt 商业许可 三选一（https://www.qt.io/licensing/）。
- 使用方式：以 LGPLv3 方式使用动态库；未修改 Qt 源码。

## 3. Python 依赖

| 组件 | 用途 | 许可 |
| --- | --- | --- |
| PySide6-Essentials | GUI | LGPLv3 / GPLv3 |
| pytest | 测试 | MIT |
| PyInstaller | 打包 | GPLv2+（含例外条款，允许打包专有程序） |

依赖的完整许可证文本可在各自发行包或官网获取。

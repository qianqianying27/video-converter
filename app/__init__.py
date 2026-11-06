"""视频格式转换器 —— PySide6 桌面客户端。

模块划分：
- env        外部工具（ffmpeg/ffprobe）定位与子进程封装
- media_info 视频元信息探测
- thumbnail  缩略图抽取（多时间点回退）
- presets    转码预设与命令行构建
- progress   ffmpeg -progress 输出解析
- converter  单个转换任务（QProcess，异步、可取消）
- queue      转换队列（顺序执行、状态机）
- settings   QSettings 封装
- ui         主窗口
"""

__version__ = "1.0.0"

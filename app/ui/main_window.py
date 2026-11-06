"""主窗口：视频列表 / 信息与缩略图 / 转换设置 / 队列。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..env import ToolNotFoundError, resolve_tools
from ..media_info import VideoInfo, human_duration, human_size
from ..presets import PRESETS, get_preset, parse_height
from ..queue import CANCELLED, FAILED, RUNNING, SUCCESS, ConversionQueue
from ..settings import AppSettings
from .workers import MediaLoadWorker

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v",
    ".ts", ".mts", ".mpg", ".mpeg", ".3gp", ".ogv", ".rmvb",
}
RESOLUTIONS = ["保持原分辨率", "1080p", "720p", "480p", "360p"]

PLACEHOLDER_BG = QColor("#22262e")
PLACEHOLDER_FG = QColor("#8b93a3")


def placeholder_pixmap(width: int = 480, height: int = 270, text: str = "无预览") -> QPixmap:
    pm = QPixmap(width, height)
    pm.fill(PLACEHOLDER_BG)
    painter = QPainter(pm)
    painter.setPen(PLACEHOLDER_FG)
    font = painter.font()
    font.setPointSize(max(10, width // 36))
    painter.setFont(font)
    painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, text)
    painter.end()
    return pm


class ScalableLabel(QLabel):
    """保持宽高比自适应缩放显示的图片标签。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(220)

    def set_source(self, pixmap: QPixmap | None) -> None:
        self._source = pixmap
        self._apply()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt 接口
        super().resizeEvent(event)
        self._apply()

    def _apply(self) -> None:
        if self._source is None:
            self.setText("选择视频查看缩略图")
            return
        scaled = self._source.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)


class VideoList(QListWidget):
    filesDropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setIconSize(QSize(128, 72))
        self.setSpacing(2)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.filesDropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


class MainWindow(QMainWindow):
    def __init__(
        self,
        ffmpeg: Path,
        ffprobe: Path,
        settings: AppSettings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ffmpeg = ffmpeg
        self._ffprobe = ffprobe
        self._settings = settings

        self._infos: dict[Path, VideoInfo] = {}
        self._thumbs: dict[Path, Path] = {}
        self._items: dict[Path, QListWidgetItem] = {}
        self._workers: dict[Path, MediaLoadWorker] = {}
        self._progress_bars: dict[int, QProgressBar] = {}

        self._pool = QThreadPool.globalInstance()
        self._queue = ConversionQueue(ffmpeg, self)

        self._build_ui()
        self._connect_signals()
        self._restore_settings()
        self._queue.set_ffmpeg(ffmpeg)

    # ================= UI 构建 =================

    def _build_ui(self) -> None:
        self.setWindowTitle("视频格式转换器")
        self.resize(1180, 860)
        self.setMinimumSize(980, 720)

        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")
        add_action = QAction("添加视频…", self)
        add_action.setShortcut("Ctrl+O")
        add_action.triggered.connect(self._choose_files)
        file_menu.addAction(add_action)

        remove_action = QAction("移除选中", self)
        remove_action.setShortcut("Delete")
        remove_action.triggered.connect(self._remove_selected)
        file_menu.addAction(remove_action)
        file_menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        settings_menu = menubar.addMenu("设置")
        locate_action = QAction("指定 ffmpeg 位置…", self)
        locate_action.triggered.connect(self._locate_ffmpeg)
        settings_menu.addAction(locate_action)

        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(8)

        # ---- 顶部按钮 ----
        top = QHBoxLayout()
        self.add_btn = QPushButton("添加视频…")
        self.add_btn.clicked.connect(self._choose_files)
        self.remove_btn = QPushButton("移除选中")
        self.remove_btn.clicked.connect(self._remove_selected)
        top.addWidget(self.add_btn)
        top.addWidget(self.remove_btn)
        top.addStretch(1)
        self.open_dir_btn = QPushButton("打开输出目录")
        self.open_dir_btn.clicked.connect(self._open_output_dir)
        top.addWidget(self.open_dir_btn)
        root.addLayout(top)

        # ---- 中部：列表 + 详情 ----
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.video_list = VideoList()
        self.video_list.setObjectName("videoList")
        splitter.addWidget(self.video_list)

        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(8)

        self.preview = ScalableLabel()
        self.preview.setObjectName("preview")
        self.preview.set_source(placeholder_pixmap())
        detail_layout.addWidget(self.preview, 3)

        info_group = QGroupBox("视频信息")
        self._info_form = QFormLayout(info_group)
        self._info_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._meta_labels: dict[str, QLabel] = {}
        for key in ("文件名", "大小", "时长", "分辨率", "帧率", "视频编码",
                    "像素格式", "旋转", "音频编码", "音频参数", "容器"):
            label = QLabel("—")
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._meta_labels[key] = label
            self._info_form.addRow(f"{key}：", label)
        detail_layout.addWidget(info_group, 2)

        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([440, 620])
        root.addWidget(splitter, 5)

        # ---- 转换设置 ----
        settings_group = QGroupBox("转换设置")
        grid = QVBoxLayout(settings_group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("目标格式："))
        self.preset_combo = QComboBox()
        for preset in PRESETS:
            self.preset_combo.addItem(preset.label, preset.key)
            self.preset_combo.setItemData(
                self.preset_combo.count() - 1, preset.note, Qt.ItemDataRole.ToolTipRole
            )
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        row1.addWidget(self.preset_combo, 2)

        row1.addSpacing(12)
        row1.addWidget(QLabel("分辨率："))
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(RESOLUTIONS)
        row1.addWidget(self.resolution_combo)

        row1.addSpacing(12)
        row1.addWidget(QLabel("CRF："))
        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        self.crf_spin.setValue(23)
        self.crf_spin.setToolTip("数值越小画质越好、体积越大；对 H.264 / VP9 生效")
        row1.addWidget(self.crf_spin)
        row1.addStretch(1)
        grid.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("输出目录："))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("默认：视频文件夹")
        row2.addWidget(self.output_edit, 1)
        browse_btn = QPushButton("浏览…")
        browse_btn.clicked.connect(self._choose_output_dir)
        row2.addWidget(browse_btn)
        grid.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addStretch(1)
        self.cancel_btn = QPushButton("取消当前")
        self.cancel_btn.clicked.connect(self._cancel_current)
        row3.addWidget(self.cancel_btn)
        self.convert_btn = QPushButton("开始转换")
        self.convert_btn.setObjectName("primary")
        self.convert_btn.setMinimumWidth(140)
        self.convert_btn.clicked.connect(self._start_conversion)
        row3.addWidget(self.convert_btn)
        grid.addLayout(row3)
        root.addWidget(settings_group)

        # ---- 队列 ----
        queue_group = QGroupBox("转换队列")
        queue_layout = QVBoxLayout(queue_group)

        self.queue_table = QTableWidget(0, 5)
        self.queue_table.setHorizontalHeaderLabels(["文件", "格式", "状态", "进度", "说明"])
        self.queue_table.verticalHeader().setVisible(False)
        self.queue_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.queue_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.queue_table.setColumnWidth(3, 150)
        queue_layout.addWidget(self.queue_table)

        queue_btns = QHBoxLayout()
        cancel_selected = QPushButton("取消选中任务")
        cancel_selected.clicked.connect(self._cancel_selected_queue_row)
        clear_done = QPushButton("清空已完成")
        clear_done.clicked.connect(self._clear_finished)
        queue_btns.addStretch(1)
        queue_btns.addWidget(cancel_selected)
        queue_btns.addWidget(clear_done)
        queue_layout.addLayout(queue_btns)
        root.addWidget(queue_group, 3)

        self.statusBar().showMessage(f"ffmpeg：{self._ffmpeg}")

    def _connect_signals(self) -> None:
        self.video_list.itemSelectionChanged.connect(self._refresh_details)
        self.video_list.filesDropped.connect(self._add_files)
        self._queue.job_added.connect(self._on_job_added)
        self._queue.job_changed.connect(self._on_job_changed)
        self._queue.busy_changed.connect(self._on_busy_changed)
        self._queue.all_finished.connect(self._on_all_finished)

    # ================= 设置持久化 =================

    def _restore_settings(self) -> None:
        geometry = self._settings.get("geometry")
        if isinstance(geometry, QByteArray) and not geometry.isEmpty():
            self.restoreGeometry(geometry)

        preset_key = str(self._settings.get("preset") or "mp4")
        index = self.preset_combo.findData(preset_key)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)
        self.resolution_combo.setCurrentText(str(self._settings.get("resolution") or RESOLUTIONS[0]))
        try:
            self.crf_spin.setValue(int(self._settings.get("crf") or 23))
        except (TypeError, ValueError):
            pass

        out_dir = str(self._settings.get("output_dir") or "")
        if not out_dir:
            out_dir = str(self._default_output_dir())
            self._settings.set("output_dir", out_dir)
        self.output_edit.setText(out_dir)

    def _save_settings(self) -> None:
        self._settings.set("geometry", self.saveGeometry())
        self._settings.set("output_dir", self.output_edit.text().strip())
        self._settings.set("preset", self.preset_combo.currentData())
        self._settings.set("resolution", self.resolution_combo.currentText())
        self._settings.set("crf", self.crf_spin.value())
        self._settings.sync()

    def _default_output_dir(self) -> Path:
        videos = Path.home() / "Videos"
        return videos if videos.exists() else Path.home()

    # ================= 文件操作 =================

    def _choose_files(self) -> None:
        last_dir = str(self._settings.get("last_input_dir") or Path.home())
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "添加视频",
            last_dir,
            "视频文件 (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv *.m4v *.ts *.mts *.mpg *.3gp);;所有文件 (*.*)",
        )
        if files:
            self._settings.set("last_input_dir", str(Path(files[0]).parent))
            self._add_files(files)

    def _add_files(self, paths: list[str]) -> None:
        added = 0
        for raw in paths:
            path = Path(raw)
            try:
                path = path.resolve()
            except OSError:
                continue
            if path.suffix.lower() not in VIDEO_EXTENSIONS or not path.is_file():
                continue
            if path in self._items:
                continue

            item = QListWidgetItem(QIcon(placeholder_pixmap(128, 72, "加载中")), f"{path.name}\n加载中…")
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setSizeHint(QSize(0, 84))
            item.setToolTip(str(path))
            self.video_list.addItem(item)
            self._items[path] = item

            worker = MediaLoadWorker(path, self._ffmpeg, self._ffprobe)
            worker.setAutoDelete(False)
            worker.signals.done.connect(self._on_media_loaded)
            self._workers[path] = worker
            self._pool.start(worker)
            added += 1

        if added:
            self.statusBar().showMessage(f"正在读取 {added} 个文件…", 3000)

    def _on_media_loaded(self, result: dict) -> None:
        path: Path = result["path"]
        self._workers.pop(path, None)  # QRunnable 由线程池回收，这里只释放引用

        item = self._items.get(path)
        if item is None:  # 已被移除
            return

        info: VideoInfo | None = result.get("info")
        if info is None:
            item.setText(f"{path.name}\n无法读取")
            item.setToolTip(result.get("error") or "无法读取该文件")
            return

        self._infos[path] = info
        item.setText(
            f"{path.name}\n{info.resolution} · {human_duration(info.duration)} · {human_size(info.size_bytes)}"
        )
        thumb = result.get("thumb")
        if thumb:
            self._thumbs[path] = Path(thumb)
            item.setIcon(QIcon(str(thumb)))
        else:
            item.setToolTip(result.get("thumb_error") or "缩略图生成失败")

        if self.video_list.currentItem() is None:
            self.video_list.setCurrentItem(item)
        else:
            self._refresh_details()
        if not self._workers:
            self.statusBar().showMessage(f"已加载 {len(self._items)} 个视频", 4000)

    def _remove_selected(self) -> None:
        for item in list(self.video_list.selectedItems()):
            path = Path(item.data(Qt.ItemDataRole.UserRole))
            worker = self._workers.pop(path, None)
            if worker is not None:
                worker.signals.done.disconnect()
            row = self.video_list.row(item)
            self.video_list.takeItem(row)
            self._items.pop(path, None)
            self._infos.pop(path, None)
            self._thumbs.pop(path, None)
        self._refresh_details()

    def _refresh_details(self) -> None:
        item = self.video_list.currentItem()
        path: Path | None = Path(item.data(Qt.ItemDataRole.UserRole)) if item else None
        info = self._infos.get(path) if path else None

        if info is None:
            for label in self._meta_labels.values():
                label.setText("—")
            self.preview.set_source(placeholder_pixmap())
            return

        thumb = self._thumbs.get(path) if path else None
        self.preview.set_source(
            QPixmap(str(thumb)).scaled(640, 360, Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation)
            if thumb and Path(thumb).exists() else placeholder_pixmap()
        )

        audio = (
            f"{info.audio_channels} 声道 · {info.audio_rate / 1000:.1f} kHz"
            if info.audio_codec else "无音轨"
        )
        values = {
            "文件名": info.path.name,
            "大小": human_size(info.size_bytes),
            "时长": human_duration(info.duration),
            "分辨率": info.resolution,
            "帧率": f"{info.fps:.2f} fps" if info.fps else "—",
            "视频编码": info.video_codec or "无视频流",
            "像素格式": info.pixel_format or "—",
            "旋转": f"{info.rotation}°" if info.rotation else "无",
            "音频编码": info.audio_codec or "无音轨",
            "音频参数": audio,
            "容器": info.container or "—",
        }
        for key, text in values.items():
            self._meta_labels[key].setText(text)

    # ================= 转换操作 =================

    def _choose_output_dir(self) -> None:
        current = self.output_edit.text().strip() or str(self._default_output_dir())
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录", current)
        if directory:
            self.output_edit.setText(directory)
            self._settings.set("output_dir", directory)

    def _on_preset_changed(self) -> None:
        preset = get_preset(self.preset_combo.currentData())
        editable = preset.kind in ("video",)
        self.crf_spin.setEnabled(editable)
        self.resolution_combo.setEnabled(editable or preset.kind == "gif")

    def _start_conversion(self) -> None:
        selected = self.video_list.selectedItems()
        paths = (
            [Path(i.data(Qt.ItemDataRole.UserRole)) for i in selected]
            if selected else list(self._items.keys())
        )
        paths = [p for p in paths if p in self._infos]
        if not paths:
            QMessageBox.information(self, "提示", "请先添加视频，并至少成功读取一个文件。")
            return

        out_dir = Path(self.output_edit.text().strip() or self._default_output_dir())
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "输出目录不可用", f"无法创建输出目录：\n{exc}")
            return

        preset = get_preset(self.preset_combo.currentData())
        height = parse_height(self.resolution_combo.currentText())
        if preset.kind in ("audio", "copy"):
            height = None
        crf = self.crf_spin.value()

        for path in paths:
            self._queue.add(
                path, preset, out_dir, self._infos[path].duration,
                crf=crf, height=height,
            )
        self.statusBar().showMessage(f"已加入 {len(paths)} 个任务，开始转换…", 5000)
        self._queue.start()

    def _cancel_current(self) -> None:
        self._queue.cancel_current()

    def _cancel_selected_queue_row(self) -> None:
        rows = sorted({idx.row() for idx in self.queue_table.selectedIndexes()})
        if rows:
            for row in rows:
                self._queue.cancel(row)
        else:
            self._queue.cancel_current()

    def _clear_finished(self) -> None:
        self._queue.clear_finished()
        self.queue_table.setRowCount(0)
        self._progress_bars.clear()
        for job in self._queue.jobs:
            self._append_queue_row(job)

    # ================= 队列表更新 =================

    def _on_job_added(self, index: int) -> None:
        job = self._queue.jobs[index]
        self._append_queue_row(job)

    def _append_queue_row(self, job) -> None:
        row = self.queue_table.rowCount()
        self.queue_table.insertRow(row)
        self.queue_table.setItem(row, 0, QTableWidgetItem(job.source.name))
        self.queue_table.setItem(row, 1, QTableWidgetItem(job.preset.label))
        status = QTableWidgetItem(job.state)
        self.queue_table.setItem(row, 2, status)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(True)
        self.queue_table.setCellWidget(row, 3, bar)
        self.queue_table.setItem(row, 4, QTableWidgetItem(""))
        self._progress_bars[job.index] = bar

    def _on_job_changed(self, index: int) -> None:
        if index >= self.queue_table.rowCount():
            return
        job = self._queue.jobs[index]
        row = index
        state_item = self.queue_table.item(row, 2)
        if state_item is not None:
            state_item.setText(job.state)
            color = {
                SUCCESS: QColor("#1f9d55"),
                FAILED: QColor("#d64545"),
                CANCELLED: QColor("#999999"),
                RUNNING: QColor("#2f6fed"),
            }.get(job.state)
            if color:
                state_item.setForeground(color)

        bar = self._progress_bars.get(index)
        if bar is not None:
            bar.setValue(int(job.progress))

        detail = ""
        if job.state == FAILED:
            detail = job.error
        elif job.state == SUCCESS:
            detail = str(job.output)
        elif job.detail:
            detail = job.detail
        if detail:
            self.queue_table.item(row, 4).setText(detail)

    def _on_busy_changed(self, busy: bool) -> None:
        self.convert_btn.setEnabled(True)
        self.convert_btn.setText("转换中…（可继续添加）" if busy else "开始转换")

    def _on_all_finished(self) -> None:
        self.statusBar().showMessage("全部任务已结束", 8000)
        if self._queue.jobs:
            out_dir = self._queue.jobs[-1].output.parent
            self._settings.set("output_dir", str(out_dir))

    # ================= 其他 =================

    def _open_output_dir(self) -> None:
        directory = Path(self.output_edit.text().strip() or self._default_output_dir())
        if not directory.exists():
            QMessageBox.information(self, "提示", "输出目录还不存在，转换后会自动创建。")
            return
        try:
            if sys.platform == "win32":
                os.startfile(str(directory))  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(directory)])
            else:
                subprocess.Popen(["xdg-open", str(directory)])
        except OSError as exc:
            QMessageBox.warning(self, "无法打开", str(exc))

    def _locate_ffmpeg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 ffmpeg 可执行文件", str(self._ffmpeg.parent),
            "ffmpeg (ffmpeg.exe ffmpeg);;所有文件 (*.*)",
        )
        if not path:
            return
        try:
            ffmpeg, ffprobe = resolve_tools(path)
        except ToolNotFoundError as exc:
            QMessageBox.warning(self, "不可用", str(exc))
            return
        self._ffmpeg, self._ffprobe = ffmpeg, ffprobe
        self._settings.ffmpeg_path = str(ffmpeg)
        self._queue.set_ffmpeg(ffmpeg)
        self.statusBar().showMessage(f"已切换 ffmpeg：{ffmpeg}", 5000)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "关于",
            "视频格式转换器 1.0.0\n\n"
            "PySide6 + ffmpeg CLI 实现的桌面视频转换工具。\n"
            "支持 MP4 / MKV / WebM / GIF / MP3，可调分辨率与画质。",
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._queue.busy:
            answer = QMessageBox.question(
                self,
                "确认退出",
                "还有任务正在转换，退出将中断当前任务。确定退出吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._queue.cancel_current()
        self._save_settings()
        super().closeEvent(event)

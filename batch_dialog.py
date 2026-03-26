"""
batch_dialog.py — Cửa sổ Batch TTS (Lồng Tiếng File TXT / SRT)
Văn Khải A.I Studio — PRO VERSION
"""

import os
import re
import threading
import platform
import subprocess

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox, QSplitter, QWidget, QFrame,
    QSpinBox, QDoubleSpinBox, QSlider, QLineEdit, QGroupBox,
    QProgressBar, QSizePolicy
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtGui import QFont

CREATE_NO_WINDOW = 0x08000000 if platform.system() == 'Windows' else 0


# ── Signals ──────────────────────────────────────────────
class BatchSignals(QObject):
    log      = pyqtSignal(str)
    progress = pyqtSignal(int, int)   # done, total
    done     = pyqtSignal(str)        # output path


# ── Dialog ───────────────────────────────────────────────
class BatchTTSDialog(QDialog):
    def __init__(self, parent=None, piper_exe="", model_path="", tts_speed=1.0):
        super().__init__(parent)
        self.setWindowTitle("📚 Batch TTS — Lồng Tiếng File TXT / SRT")
        self.resize(1100, 700)
        self.setMinimumSize(800, 500)

        # Kế thừa cấu hình TTS từ app chính
        self.piper_exe  = piper_exe
        self.model_path = model_path
        self.tts_speed  = tts_speed

        self.segments     = []   # list of str — các đoạn đã chia
        self.audio_chunks = []   # list of str — đường dẫn file wav từng đoạn
        self.is_running   = False
        self.output_dir   = os.path.join(os.getcwd(), "batch_tts_output")
        os.makedirs(self.output_dir, exist_ok=True)

        self.signals = BatchSignals()
        self.signals.log.connect(self._append_log)
        self.signals.progress.connect(self._update_progress)
        self.signals.done.connect(self._on_done)

        self._build_ui()

    # ─────────────────── UI ───────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        # ── Top toolbar ──
        toolbar = QHBoxLayout()

        btn_load = QPushButton("📂 Tải File TXT / SRT")
        btn_load.setStyleSheet("background-color:#17a2b8;color:white;font-weight:bold;padding:6px 12px;")
        btn_load.clicked.connect(self.load_file)

        btn_process = QPushButton("⚙ Xử Lý Văn Bản")
        btn_process.setStyleSheet("background-color:#ffc107;font-weight:bold;padding:6px 12px;")
        btn_process.clicked.connect(self.process_text)

        self.spin_maxlen = QSpinBox()
        self.spin_maxlen.setRange(20, 500)
        self.spin_maxlen.setValue(120)
        self.spin_maxlen.setSuffix(" ký tự/đoạn")
        self.spin_maxlen.setToolTip("Độ dài tối đa mỗi đoạn (ký tự)")

        toolbar.addWidget(btn_load)
        toolbar.addWidget(btn_process)
        toolbar.addWidget(QLabel("  Tối đa:"))
        toolbar.addWidget(self.spin_maxlen)
        toolbar.addStretch()

        self.lbl_file = QLabel("[Chưa tải file]")
        self.lbl_file.setStyleSheet("color:#555;font-style:italic;")
        toolbar.addWidget(self.lbl_file)
        root.addLayout(toolbar)

        # ── Splitter: text editor | segment table ──
        splitter = QSplitter(Qt.Horizontal)

        # Trái: nội dung thô
        left_w = QWidget()
        lv = QVBoxLayout(left_w)
        lv.setContentsMargins(0, 0, 4, 0)
        lv.addWidget(QLabel("📄 Nội dung văn bản (có thể chỉnh sửa):"))
        self.txt_content = QTextEdit()
        self.txt_content.setPlaceholderText("Tải file TXT hoặc SRT... nội dung sẽ hiện ở đây.")
        lv.addWidget(self.txt_content)

        # Phải: bảng đoạn
        right_w = QWidget()
        rv = QVBoxLayout(right_w)
        rv.setContentsMargins(4, 0, 0, 0)
        rv.addWidget(QLabel("📋 Danh sách đoạn (có thể sửa trực tiếp):"))
        self.seg_table = QTableWidget(0, 2)
        self.seg_table.setHorizontalHeaderLabels(["#", "Nội Dung Đoạn"])
        self.seg_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.seg_table.setColumnWidth(0, 40)
        rv.addWidget(self.seg_table)

        lbl_count = QLabel()
        self.lbl_count = lbl_count
        rv.addWidget(lbl_count)

        splitter.addWidget(left_w)
        splitter.addWidget(right_w)
        splitter.setSizes([480, 480])
        root.addWidget(splitter, stretch=1)

        # ── TTS Config ──
        grp_tts = QGroupBox("🎙 Cấu Hình TTS (Piper)")
        tts_h = QHBoxLayout()

        # Piper exe
        self.txt_exe = QLineEdit(self.piper_exe)
        self.txt_exe.setPlaceholderText("Đường dẫn piper.exe")
        btn_exe = QPushButton("📂")
        btn_exe.setFixedWidth(32)
        btn_exe.clicked.connect(self._browse_exe)

        # Model onnx
        self.txt_model = QLineEdit(self.model_path)
        self.txt_model.setPlaceholderText("Đường dẫn model .onnx")
        btn_model = QPushButton("📂")
        btn_model.setFixedWidth(32)
        btn_model.clicked.connect(self._browse_model)

        # Speed
        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.40, 2.00)
        self.spin_speed.setSingleStep(0.05)
        self.spin_speed.setDecimals(2)
        self.spin_speed.setValue(self.tts_speed)
        self.spin_speed.setSuffix("x")
        self.spin_speed.setFixedWidth(68)
        self.spin_speed.setToolTip("Tốc độ đọc: < 1.0 nhanh | 1.0 bình thường | > 1.0 chậm")

        tts_h.addWidget(QLabel("exe:"))
        tts_h.addWidget(self.txt_exe)
        tts_h.addWidget(btn_exe)
        tts_h.addSpacing(8)
        tts_h.addWidget(QLabel("model:"))
        tts_h.addWidget(self.txt_model)
        tts_h.addWidget(btn_model)
        tts_h.addSpacing(8)
        tts_h.addWidget(QLabel("Tốc độ:"))
        tts_h.addWidget(self.spin_speed)
        grp_tts.setLayout(tts_h)
        root.addWidget(grp_tts)

        # ── Action bar ──
        action_h = QHBoxLayout()

        self.btn_run = QPushButton("🎙 LỒNG TIẾNG")
        self.btn_run.setStyleSheet(
            "background-color:#28a745;color:white;font-weight:bold;font-size:14px;padding:10px 24px;"
        )
        self.btn_run.clicked.connect(self.start_tts)

        self.btn_stop = QPushButton("⏹ Dừng")
        self.btn_stop.setStyleSheet("background-color:#dc3545;color:white;font-weight:bold;padding:8px 16px;")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_tts)

        self.btn_play = QPushButton("▶ Nghe File Ghép")
        self.btn_play.setStyleSheet("background-color:#17a2b8;color:white;font-weight:bold;padding:8px 16px;")
        self.btn_play.clicked.connect(self.play_output)

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFormat("%v / %m đoạn")
        self.progress.setValue(0)

        action_h.addWidget(self.btn_run)
        action_h.addWidget(self.btn_stop)
        action_h.addWidget(self.btn_play)
        action_h.addWidget(self.progress, stretch=1)
        root.addLayout(action_h)

        # ── Log ──
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(90)
        self.log_box.setStyleSheet("background:#1e1e1e;color:#d4d4d4;font-family:monospace;font-size:11px;")
        root.addWidget(self.log_box)

    # ─────────────────── File loading ─────────────────────
    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file TXT hoặc SRT", "",
            "Text & SRT (*.txt *.srt);;All files (*)"
        )
        if not path:
            return

        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                raw = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))
            return

        if path.lower().endswith('.srt'):
            content = self._strip_srt(raw)
            self._log(f"[TẢI] SRT → đã bỏ timestamp, giữ lại nội dung phụ đề.")
        else:
            content = raw
            self._log(f"[TẢI] TXT → {len(content)} ký tự.")

        self.txt_content.setPlainText(content)
        self.lbl_file.setText(f"📄 {os.path.basename(path)}")

    @staticmethod
    def _strip_srt(raw: str) -> str:
        """Loại bỏ index, timestamp, thẻ HTML trong SRT → nội dung thuần."""
        lines = []
        for line in raw.splitlines():
            line = line.strip()
            # Bỏ dòng số thứ tự
            if re.match(r'^\d+$', line):
                continue
            # Bỏ dòng timestamp
            if re.match(r'\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->', line):
                continue
            # Bỏ dòng trống
            if not line:
                continue
            # Bỏ thẻ HTML như <i>, <b>, <font ...>
            line = re.sub(r'<[^>]+>', '', line)
            if line:
                lines.append(line)
        # Ghép các dòng thành văn bản liên tục, phân tách bằng khoảng trắng
        return ' '.join(lines)

    # ─────────────────── Text processing ──────────────────
    def process_text(self):
        text = self.txt_content.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Cảnh báo", "Chưa có nội dung văn bản!")
            return

        max_len = self.spin_maxlen.value()
        segs = self._split_text(text, max_len)
        self.segments = segs
        self._fill_table(segs)
        self._log(f"[XỬ LÝ] Đã chia thành {len(segs)} đoạn (max {max_len} ký tự/đoạn).")

    @staticmethod
    def _split_text(text: str, max_len: int) -> list:
        """Chia văn bản theo dấu câu, giữ mỗi đoạn ≤ max_len ký tự."""
        # Tách theo dấu câu kết thúc
        raw_parts = re.split(r'(?<=[.!?。！？…])\s+', text)
        segments = []
        buf = ""
        for part in raw_parts:
            part = part.strip()
            if not part:
                continue
            if len(buf) + len(part) + 1 <= max_len:
                buf = (buf + " " + part).strip() if buf else part
            else:
                if buf:
                    segments.append(buf)
                # Nếu part > max_len, cắt tiếp
                while len(part) > max_len:
                    segments.append(part[:max_len])
                    part = part[max_len:]
                buf = part
        if buf:
            segments.append(buf)
        return [s for s in segments if s.strip()]

    def _fill_table(self, segs: list):
        self.seg_table.setRowCount(len(segs))
        for i, s in enumerate(segs):
            self.seg_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.seg_table.setItem(i, 1, QTableWidgetItem(s))
        self.lbl_count.setText(f"Tổng: {len(segs)} đoạn")

    def _read_segments_from_table(self) -> list:
        """Đọc lại segments từ bảng (cho phép người dùng chỉnh sửa trước khi TTS)."""
        segs = []
        for r in range(self.seg_table.rowCount()):
            item = self.seg_table.item(r, 1)
            if item:
                t = item.text().strip()
                if t:
                    segs.append(t)
        return segs

    # ─────────────────── TTS ──────────────────────────────
    def _browse_exe(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn piper.exe", "", "Executable (*.exe);;All (*)")
        if p:
            self.txt_exe.setText(p)

    def _browse_model(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn model .onnx", "", "ONNX (*.onnx);;All (*)")
        if p:
            self.txt_model.setText(p)

    def start_tts(self):
        segs = self._read_segments_from_table()
        if not segs:
            QMessageBox.warning(self, "Cảnh báo",
                "Chưa có đoạn nào. Hãy tải file và nhấn ⚙ Xử Lý Văn Bản trước!")
            return

        piper = self.txt_exe.text().strip()
        model = self.txt_model.text().strip()
        if not piper or not os.path.exists(piper):
            QMessageBox.warning(self, "Cảnh báo", "Chưa chọn đường dẫn piper.exe!")
            return
        if not model or not os.path.exists(model):
            QMessageBox.warning(self, "Cảnh báo", "Chưa chọn đường dẫn model .onnx!")
            return

        self.is_running = True
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress.setMaximum(len(segs))
        self.progress.setValue(0)

        threading.Thread(
            target=self._worker_tts,
            args=(segs, piper, model, round(self.spin_speed.value(), 2)),
            daemon=True
        ).start()

    def stop_tts(self):
        self.is_running = False
        self._log("[DỪNG] Đã ra lệnh dừng lồng tiếng.")

    def _worker_tts(self, segs, piper, model, speed):
        import wave as _wave

        chunk_dir = os.path.join(self.output_dir, "_chunks")
        os.makedirs(chunk_dir, exist_ok=True)
        chunk_paths = []

        self._log(f"[TTS] Bắt đầu lồng tiếng {len(segs)} đoạn | tốc độ {speed}x")

        for i, text in enumerate(segs):
            if not self.is_running:
                break
            out_path = os.path.join(chunk_dir, f"chunk_{i:04d}.wav")
            ok = self._piper_run(text, piper, model, speed, out_path)
            if ok:
                chunk_paths.append(out_path)
                self._log(f"  [{i+1}/{len(segs)}] ✅ {text[:50]}{'...' if len(text)>50 else ''}")
            else:
                self._log(f"  [{i+1}/{len(segs)}] ⚠ Lỗi đoạn này, bỏ qua.")
            self.signals.progress.emit(i + 1, len(segs))

        if chunk_paths:
            output_path = os.path.join(self.output_dir, "batch_output.wav")
            self._log("[GHÉP] Đang ghép các đoạn...")
            try:
                # Ghép nối tiếp bằng wave module thuần (nhanh, không cần pydub)
                ref = None
                with _wave.open(output_path, 'wb') as out_wf:
                    for cp in chunk_paths:
                        try:
                            with _wave.open(cp, 'rb') as wf:
                                if ref is None:
                                    ref = (wf.getnchannels(), wf.getsampwidth(), wf.getframerate())
                                    out_wf.setnchannels(ref[0])
                                    out_wf.setsampwidth(ref[1])
                                    out_wf.setframerate(ref[2])
                                out_wf.writeframes(wf.readframes(wf.getnframes()))
                        except Exception as e:
                            self._log(f"  ⚠ Bỏ qua chunk lỗi: {e}")
                self._log(f"[XONG] ✅ File ghép: {output_path}")
                self.signals.done.emit(output_path)
            except Exception as e:
                self._log(f"[LỖI GHÉP] {e}")
        else:
            self._log("[CẢNH BÁO] Không có đoạn nào tạo audio thành công.")

        self.is_running = False
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _piper_run(self, text, piper, model, speed, out_path) -> bool:
        # Tiền xử lý văn bản tiếng Việt
        try:
            from vn_text_processor import process as vn_process
            text = vn_process(text)
        except ImportError:
            pass
        try:
            proc = subprocess.Popen(
                [piper, '--model', model,
                 '--length_scale', str(speed),
                 '--output_file', out_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW
            )
            _, stderr = proc.communicate(input=text.encode('utf-8'))
            if proc.returncode != 0:
                self._log(f"  [PIPER ERR] {stderr.decode('utf-8', errors='ignore')[:120]}")
                return False
            return True
        except Exception as e:
            self._log(f"  [LỖI PIPER] {e}")
            return False

    # ─────────────────── helpers ──────────────────────────
    def play_output(self):
        path = os.path.join(self.output_dir, "batch_output.wav")
        if not os.path.exists(path):
            QMessageBox.warning(self, "Cảnh báo", "Chưa có file ghép! Hãy chạy lồng tiếng trước.")
            return
        try:
            if platform.system() == 'Windows':
                os.startfile(path)
            elif platform.system() == 'Darwin':
                subprocess.call(['open', path])
            else:
                subprocess.call(['xdg-open', path])
        except Exception as e:
            self._log(f"[LỖI PHÁT] {e}")

    def _log(self, msg):
        self.signals.log.emit(msg)

    def _append_log(self, msg):
        self.log_box.append(msg)
        self.log_box.verticalScrollBar().setValue(self.log_box.verticalScrollBar().maximum())

    def _update_progress(self, done, total):
        self.progress.setMaximum(total)
        self.progress.setValue(done)

    def _on_done(self, path):
        QMessageBox.information(self, "Hoàn Tất", f"✅ Đã lồng tiếng xong!\nFile: {path}")

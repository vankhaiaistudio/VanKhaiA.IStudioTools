import sys
import time
import threading
import re
import random
import os
import json
import subprocess
import platform
from pathlib import Path

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QRadioButton,
                             QGroupBox, QTableWidget, QTableWidgetItem,
                             QHeaderView, QComboBox, QSpinBox, QDoubleSpinBox,
                             QCheckBox, QTextEdit, QSpacerItem, QSizePolicy,
                             QFrame, QButtonGroup, QFileDialog, QDialog,
                             QGridLayout, QMessageBox, QLineEdit, QSlider)
from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal
from PyQt5.QtGui import QFont

# selenium imports (used by main selenium-driven browser)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

CREATE_NO_WINDOW = 0x08000000 if platform.system() == 'Windows' else 0

# ==================== Worker signals ====================
class WorkerSignals(QObject):
    log         = pyqtSignal(str)
    log_inplace = pyqtSignal(str)   # cập nhật dòng cuối thay vì append
    update_table = pyqtSignal()
    analysis_done = pyqtSignal(str)

# ==================== Main App ====================
class AIStudioApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Văn Khải A.i Studio - PRO VERSION")
        self.resize(1300, 850)

        # Internal state
        self.srt_entries = []
        self.per_page = 50            
        self.current_page = 1
        self.driver = None
        self.translation_rule = ""
        self.is_translating = False
        self.is_generating_audio = False
        self.loaded_srt_path = None
        
        # Audio Settings
        self.config_path = "app_config.json"
        self.tts_model_path = ""
        self.piper_exe_path = ""
        self.tts_speed = 100
        self.audio_output_dir = os.path.join(os.getcwd(), "audio_output")
        if not os.path.exists(self.audio_output_dir):
            os.makedirs(self.audio_output_dir)

        # Load Config
        self.load_app_config()

        # Signals
        self.signals = WorkerSignals()
        self.signals.log.connect(self.append_log)
        self.signals.log_inplace.connect(self.update_last_log)
        self.signals.update_table.connect(self.refresh_table_from_thread)
        self.signals.analysis_done.connect(self._on_analysis_done)

        # Build UI
        self.initUI()

    def load_app_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.tts_model_path = config.get("tts_model_path", "")
                    self.piper_exe_path = config.get("piper_exe_path", "")
                    self.tts_speed = config.get("tts_speed", 100)
            except Exception:
                pass

    def save_app_config(self):
        config = {
            "tts_model_path": self.tts_model_path,
            "piper_exe_path": self.piper_exe_path,
            "tts_speed": self.slider_speed.value() if hasattr(self, 'slider_speed') else 100
        }
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            self.log("[HỆ THỐNG] Đã lưu cấu hình ứng dụng.")
            QMessageBox.information(self, "Thành công", "Đã lưu cấu hình giọng nói và đường dẫn phần mềm Piper thành công!")
        except Exception as e:
            self.log(f"[LỖI] Không thể lưu cấu hình: {e}")

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Top bar
        top_bar_layout = QHBoxLayout()
        title_label = QLabel("VĂN KHẢI A.I STUDIO")
        title_font = QFont("Arial", 14, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #004d99;")
        top_bar_layout.addWidget(title_label)

        # Browser group
        browser_group = QGroupBox("Trình Duyệt")
        browser_layout = QHBoxLayout()
        self.radio_chrome = QRadioButton("Chrome")
        self.radio_chrome.setChecked(True)
        self.btn_open_browser = QPushButton("🚀 MỞ")
        self.btn_open_browser.setStyleSheet("background-color: #6a0dad; color: white; font-weight: bold; padding: 5px;")
        self.btn_batch = QPushButton("📚 BATCH")
        self.btn_batch.setStyleSheet("background-color: #6a0dad; color: white; font-weight: bold; padding: 5px;")
        browser_layout.addWidget(self.radio_chrome)
        browser_layout.addWidget(self.btn_open_browser)
        browser_layout.addWidget(self.btn_batch)
        browser_group.setLayout(browser_layout)
        top_bar_layout.addWidget(browser_group)

        # --- Group 0: Dự án (inline top bar) ---
        group_project_top = QGroupBox("Dự Án")
        group_project_top.setStyleSheet("QGroupBox { font-weight: bold; color: #d9534f; }")
        hbox_proj_top = QHBoxLayout()
        hbox_proj_top.setContentsMargins(4, 2, 4, 2)
        self.btn_load_project = QPushButton("📥 Tải")
        self.btn_load_project.setStyleSheet("background-color: #ffc107; font-weight: bold; padding: 5px 8px;")
        self.btn_save_project = QPushButton("💾 Lưu")
        self.btn_save_project.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 5px 8px;")
        hbox_proj_top.addWidget(self.btn_load_project)
        hbox_proj_top.addWidget(self.btn_save_project)
        group_project_top.setLayout(hbox_proj_top)
        top_bar_layout.addWidget(group_project_top)

        # --- Group 1: File SRT (inline top bar) ---
        group_file_top = QGroupBox("File SRT")
        group_file_top.setStyleSheet("QGroupBox { font-weight: bold; color: #004d99; }")
        hbox_file_top = QHBoxLayout()
        hbox_file_top.setContentsMargins(4, 2, 4, 2)
        self.btn_load_srt = QPushButton("📂 Tải SRT")
        self.btn_save_srt = QPushButton("💾 Xuất SRT")
        hbox_file_top.addWidget(self.btn_load_srt)
        hbox_file_top.addWidget(self.btn_save_srt)
        group_file_top.setLayout(hbox_file_top)
        top_bar_layout.addWidget(group_file_top)

        # --- Group 1.5: Nối Gap (inline top bar) ---
        group_noigap_top = QGroupBox("Nối Gap Phụ Đề")
        group_noigap_top.setStyleSheet("QGroupBox { font-weight: bold; color: #e67e22; }")
        hbox_gap_top = QHBoxLayout()
        hbox_gap_top.setContentsMargins(4, 2, 4, 2)
        lbl_gap_top = QLabel("Gap:")
        self.spin_gap = QSpinBox()
        self.spin_gap.setRange(-500, 500)
        self.spin_gap.setValue(0)
        self.spin_gap.setSuffix(" ms")
        self.spin_gap.setFixedWidth(75)
        self.spin_gap.setToolTip("Giá trị dương = tạo khoảng cách, âm = cho chồng lên nhau")
        self.btn_xuat_noigap = QPushButton("⚡ Xuất & Tải Lại")
        self.btn_xuat_noigap.setStyleSheet(
            "background-color: #e67e22; color: white; font-weight: bold; padding: 5px 8px;"
        )
        self.btn_xuat_noigap.setToolTip("Xuất _noigap.srt rồi tự động tải lại vào app")
        hbox_gap_top.addWidget(lbl_gap_top)
        hbox_gap_top.addWidget(self.spin_gap)
        hbox_gap_top.addWidget(self.btn_xuat_noigap)
        group_noigap_top.setLayout(hbox_gap_top)
        top_bar_layout.addWidget(group_noigap_top)

        top_bar_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        # Right top buttons
        self.btn_huongdan = QPushButton("❓ HƯỚNG DẪN")
        self.btn_huongdan.setStyleSheet("background-color: #008080; color: white; font-weight: bold; padding: 5px;")
        self.lbl_server = QLabel("🟢 Server: ON")
        self.lbl_server.setStyleSheet("color: #228B22; font-weight: bold; font-size: 14px;")
        self.btn_log = QPushButton("⚙ LOG")
        self.btn_log.setStyleSheet("background-color: #dc143c; color: white; font-weight: bold; padding: 5px;")

        top_bar_layout.addWidget(self.btn_huongdan)
        top_bar_layout.addWidget(self.lbl_server)
        top_bar_layout.addWidget(self.btn_log)

        main_layout.addLayout(top_bar_layout)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        main_layout.addWidget(line)

        # Body layout
        body_layout = QHBoxLayout()

        # Left panel - table
        left_panel = QVBoxLayout()
        table_controls = QHBoxLayout()
        self.lbl_status = QLabel("[Chưa tải file]")
        self.lbl_status.setStyleSheet("color: #004d99;")
        
        self.btn_translate_selected = QPushButton("✍ Dịch dòng chọn")
        self.btn_translate_selected.setStyleSheet("background-color: #ffcc00; font-weight: bold; padding: 4px;")
        
        self.btn_translate_empty = QPushButton("⚡ Dịch bù dòng trống")
        self.btn_translate_empty.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 4px;")

        table_controls.addWidget(self.lbl_status)
        table_controls.addWidget(self.btn_translate_selected)
        table_controls.addWidget(self.btn_translate_empty)
        table_controls.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))

        self.btn_prev = QPushButton("<< Trước")
        self.combo_page = QComboBox()
        self.btn_next = QPushButton("Sau >>")
        table_controls.addWidget(self.btn_prev)
        table_controls.addWidget(self.combo_page)
        table_controls.addWidget(self.btn_next)
        left_panel.addLayout(table_controls)

        # Table: 6 columns
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['✔', '#', 'Time', 'Gốc', 'Dịch', 'Audio'])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 30)
        self.table.setColumnWidth(1, 40)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(5, 120)
        left_panel.addWidget(self.table)
        self.table.cellChanged.connect(self.on_cell_changed)

        body_layout.addLayout(left_panel, stretch=7)

        # Right panel - controls
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)

        # Group 2: Ngữ cảnh & Phân tích
        group_ngucanh = QGroupBox("2. Ngữ cảnh & Phân tích")
        vbox_ngucanh = QVBoxLayout()
        self.btn_phan_tich = QPushButton("🔍 Phân tích & Gợi ý dịch (Tạo BỘ LUẬT)")
        self.btn_loc_trung = QPushButton("CN Lọc dòng còn tiếng Trung")
        vbox_ngucanh.addWidget(self.btn_phan_tich)
        vbox_ngucanh.addWidget(self.btn_loc_trung)
        group_ngucanh.setLayout(vbox_ngucanh)
        right_panel.addWidget(group_ngucanh)

        # Group 3: Dịch Thuật
        group_dich = QGroupBox("3. Dịch Thuật")
        vbox_dich = QVBoxLayout()

        hbox_gui = QHBoxLayout()
        hbox_gui.addWidget(QLabel("Gửi:"))
        self.spin_dong = QSpinBox()
        self.spin_dong.setValue(20)  
        self.spin_dong.setRange(1, 1000)
        hbox_gui.addWidget(self.spin_dong)
        hbox_gui.addWidget(QLabel("dòng"))
        hbox_gui.addStretch()
        vbox_dich.addLayout(hbox_gui)

        grid_cb = QGridLayout()
        self.chk_bodaucau = QCheckBox("Bỏ dấu câu")
        self.chk_ngangon = QCheckBox("Dịch Ngắn Gọn")
        self.chk_longtieng = QCheckBox("Lồng tiếng")
        self.chk_themcham = QCheckBox("Thêm '...'")
        self.chk_fix1tu = QCheckBox("Nói câu 1 chữ")
        self.chk_send_context = QCheckBox("Gửi lại Context")
        grid_cb.addWidget(self.chk_bodaucau, 0, 0)
        grid_cb.addWidget(self.chk_ngangon, 0, 1)
        grid_cb.addWidget(self.chk_longtieng, 1, 0)
        grid_cb.addWidget(self.chk_themcham, 1, 1)
        grid_cb.addWidget(self.chk_fix1tu, 2, 0)
        grid_cb.addWidget(self.chk_send_context, 2, 1)
        vbox_dich.addLayout(grid_cb)

        hbox_tocdo = QHBoxLayout()
        hbox_tocdo.addWidget(QLabel("Tốc độ:"))
        self.combo_tocdo = QComboBox()
        self.combo_tocdo.addItems(["Bình thường (3-7s)", "Nhanh (1-3s)", "Rất nhanh", "An toàn/Anti Bot (10-20s)"])
        hbox_tocdo.addWidget(self.combo_tocdo)
        vbox_dich.addLayout(hbox_tocdo)

        self.btn_batdaudich = QPushButton("🚀 BẮT ĐẦU DỊCH")
        self.btn_batdaudich.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; font-size: 14px; padding: 10px;")
        self.btn_dung = QPushButton("⏹ Dừng Dịch / Dừng Audio")
        self.btn_dung.setStyleSheet("background-color: #dc3545; color: white; padding: 5px;")
        self.btn_dung.setEnabled(False)

        vbox_dich.addWidget(self.btn_batdaudich)
        vbox_dich.addWidget(self.btn_dung)
        group_dich.setLayout(vbox_dich)
        right_panel.addWidget(group_dich)

        # Group 4: Text-to-Speech (Piper) + Ghép Audio
        group_tts = QGroupBox("4. Cấu Hình Giọng Nói (Độc lập Windows)")
        vbox_tts = QVBoxLayout()
        
        # Piper EXE Path
        hbox_exe = QHBoxLayout()
        self.txt_piper_exe = QLineEdit()
        self.txt_piper_exe.setPlaceholderText("Đường dẫn file piper.exe (Vừa giải nén)")
        self.txt_piper_exe.setText(self.piper_exe_path)
        self.btn_browse_exe = QPushButton("📂 File .exe")
        hbox_exe.addWidget(self.txt_piper_exe)
        hbox_exe.addWidget(self.btn_browse_exe)
        vbox_tts.addLayout(hbox_exe)

        # Model ONNX Path
        hbox_model = QHBoxLayout()
        self.txt_model_path = QLineEdit()
        self.txt_model_path.setPlaceholderText("Đường dẫn Model .onnx (JSON để chung thư mục)")
        self.txt_model_path.setText(self.tts_model_path)
        self.btn_browse_model = QPushButton("📂 Model")
        hbox_model.addWidget(self.txt_model_path)
        hbox_model.addWidget(self.btn_browse_model)
        vbox_tts.addLayout(hbox_model)

        # Tốc độ đọc (length_scale Piper): < 1.0 = nhanh, 1.0 = bình thường, > 1.0 = chậm
        hbox_speed = QHBoxLayout()
        hbox_speed.addWidget(QLabel("🎚 Tốc độ đọc:"))

        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.40, 2.00)
        self.spin_speed.setSingleStep(0.05)
        self.spin_speed.setDecimals(2)
        self.spin_speed.setValue(1.00)
        self.spin_speed.setSuffix("x")
        self.spin_speed.setFixedWidth(72)
        self.spin_speed.setToolTip(
            "Tốc độ đọc (length_scale Piper):\n"
            "  < 1.00 → Đọc nhanh hơn (vd: 0.80)\n"
            "  = 1.00 → Bình thường\n"
            "  > 1.00 → Đọc chậm hơn (vd: 1.20)"
        )
        self.spin_speed.setStyleSheet("font-weight: bold; color: #004d99;")

        self.slider_speed = QSlider(Qt.Horizontal)
        self.slider_speed.setMinimum(40)    # 0.40
        self.slider_speed.setMaximum(200)   # 2.00
        self.slider_speed.setValue(100)     # 1.00
        self.slider_speed.setTickInterval(10)
        self.slider_speed.setTickPosition(QSlider.TicksBelow)

        # Đồng bộ 2 chiều: spinbox <-> slider
        self.slider_speed.valueChanged.connect(self._on_speed_slider_changed)
        self.spin_speed.valueChanged.connect(self._on_speed_spin_changed)

        hbox_speed.addWidget(self.spin_speed)
        hbox_speed.addWidget(self.slider_speed)

        # Nhãn mô tả nhanh/chậm
        hbox_speed_hint = QHBoxLayout()
        lbl_fast = QLabel("⚡ 0.40x (nhanh)")
        lbl_fast.setStyleSheet("color: gray; font-size: 10px;")
        lbl_normal = QLabel("1.00x")
        lbl_normal.setStyleSheet("color: gray; font-size: 10px;")
        lbl_normal.setAlignment(Qt.AlignCenter)
        lbl_slow = QLabel("2.00x (chậm) 🐢")
        lbl_slow.setStyleSheet("color: gray; font-size: 10px;")
        lbl_slow.setAlignment(Qt.AlignRight)
        hbox_speed_hint.addWidget(lbl_fast)
        hbox_speed_hint.addWidget(lbl_normal)
        hbox_speed_hint.addWidget(lbl_slow)

        vbox_tts.addLayout(hbox_speed)
        vbox_tts.addLayout(hbox_speed_hint)

        self.btn_save_config_btn = QPushButton("💾 Lưu Cấu Hình Mặc Định")
        vbox_tts.addWidget(self.btn_save_config_btn)

        hbox_batch_audio = QHBoxLayout()
        self.btn_batch_audio = QPushButton("🎧 TẠO AUDIO HÀNG LOẠT")
        self.btn_batch_audio.setStyleSheet("background-color: #6a0dad; color: white; font-weight: bold; font-size: 12px; padding: 8px;")
        self.btn_delete_all_audio = QPushButton("🗑 Xóa Tất Cả")
        self.btn_delete_all_audio.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 8px;")
        self.btn_delete_all_audio.setToolTip("Xóa toàn bộ file audio_*.wav trong thư mục audio_output")
        hbox_batch_audio.addWidget(self.btn_batch_audio)
        hbox_batch_audio.addWidget(self.btn_delete_all_audio)
        vbox_tts.addLayout(hbox_batch_audio)
        
        line_tts = QFrame()
        line_tts.setFrameShape(QFrame.HLine)
        vbox_tts.addWidget(line_tts)

        self.combo_merge_type = QComboBox()
        self.combo_merge_type.addItems(["Ghép Nối Tiếp Nhau", "Ghép Chuẩn Timeline (Theo Thời Gian SRT)"])
        vbox_tts.addWidget(self.combo_merge_type)

        hbox_merge = QHBoxLayout()
        self.btn_merge_audio = QPushButton("🎬 TẠO FILE GHÉP")
        self.btn_merge_audio.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold; padding: 6px;")
        self.btn_play_merged = QPushButton("▶ Nghe File Ghép")
        self.btn_play_merged.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 6px;")
        
        hbox_merge.addWidget(self.btn_merge_audio)
        hbox_merge.addWidget(self.btn_play_merged)
        vbox_tts.addLayout(hbox_merge)

        line_tts2 = QFrame()
        line_tts2.setFrameShape(QFrame.HLine)
        vbox_tts.addWidget(line_tts2)

        lbl_timeline_hint = QLabel("⏱ Xuất audio khớp đúng thời lượng SRT:\nAudio dài hơn → tăng tốc | Audio ngắn hơn → thêm lặng")
        lbl_timeline_hint.setStyleSheet("color: #666; font-size: 10px;")
        lbl_timeline_hint.setWordWrap(True)
        vbox_tts.addWidget(lbl_timeline_hint)

        hbox_tl = QHBoxLayout()
        self.btn_export_timeline = QPushButton("⏱ XUẤT CHUẨN TIMELINE")
        self.btn_export_timeline.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 6px;")
        self.btn_play_timeline = QPushButton("▶ Nghe")
        self.btn_play_timeline.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 6px;")
        hbox_tl.addWidget(self.btn_export_timeline)
        hbox_tl.addWidget(self.btn_play_timeline)
        vbox_tts.addLayout(hbox_tl)

        group_tts.setLayout(vbox_tts)
        right_panel.addWidget(group_tts)

        # Log box
        self.log_text = QTextEdit()
        self.log_text.setStyleSheet("background-color: black; color: white;")
        self.log_text.setReadOnly(True)
        right_panel.addWidget(self.log_text)

        body_layout.addLayout(right_panel, stretch=2)
        main_layout.addLayout(body_layout)

        # Status bar
        self.statusBar().showMessage("0%")
        self.statusBar().setStyleSheet("border-top: 1px solid #ccc;")

        # Connect controls
        self.btn_load_project.clicked.connect(self.load_project)
        self.btn_save_project.clicked.connect(self.save_project)
        self.btn_load_srt.clicked.connect(self.load_srt)
        self.btn_save_srt.clicked.connect(self.save_srt)
        self.btn_xuat_noigap.clicked.connect(self.save_srt_with_gap)
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next.clicked.connect(self.next_page)
        self.combo_page.currentIndexChanged.connect(self.on_page_combo_changed)
        self.btn_phan_tich.clicked.connect(self.show_analysis_dialog)
        self.btn_batdaudich.clicked.connect(self.start_translation_thread)
        self.btn_dung.clicked.connect(self.stop_all_processes)
        self.btn_open_browser.clicked.connect(self.start_browser_thread)
        self.btn_translate_selected.clicked.connect(self.translate_selected_now)
        self.btn_translate_empty.clicked.connect(self.start_empty_lines_translation)
        self.btn_loc_trung.clicked.connect(self.start_loc_trung_translation)
        self.btn_log.clicked.connect(lambda: QMessageBox.information(self, "Log", "Mở log (hiện có)"))
        self.btn_huongdan.clicked.connect(self.show_guide)
        self.btn_batch.clicked.connect(self.show_batch_dialog)
        
        # TTS Connections
        self.btn_browse_exe.clicked.connect(self.browse_piper_exe)
        self.btn_browse_model.clicked.connect(self.browse_tts_model)
        self.btn_save_config_btn.clicked.connect(self.save_tts_config)
        self.btn_batch_audio.clicked.connect(self.start_batch_audio_thread)
        self.btn_delete_all_audio.clicked.connect(self.delete_all_audio)
        self.btn_merge_audio.clicked.connect(self.start_merge_audio_thread)
        self.btn_play_merged.clicked.connect(self.play_merged_audio)
        self.btn_export_timeline.clicked.connect(self.start_export_timeline_audio_thread)
        self.btn_play_timeline.clicked.connect(self.play_timeline_audio)

        # Restore speed slider value from config
        self.slider_speed.setValue(self.tts_speed)
        self._update_speed_color(self.tts_speed / 100.0)

    # ----------------- UI helper -----------------
    def show_guide(self):
        try:
            from guide import show_guide as _show_guide
            _show_guide(self)
        except ImportError:
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy file 'guide.py'.\nVui lòng đặt guide.py cùng thư mục với appgui_4.py.")

    def show_batch_dialog(self):
        try:
            from batch_dialog import BatchTTSDialog
            piper  = self.txt_piper_exe.text().strip() if hasattr(self, 'txt_piper_exe') else self.piper_exe_path
            model  = self.txt_model_path.text().strip() if hasattr(self, 'txt_model_path') else self.tts_model_path
            speed  = round(self.spin_speed.value(), 2)  if hasattr(self, 'spin_speed')    else 1.0
            dlg = BatchTTSDialog(self, piper_exe=piper, model_path=model, tts_speed=speed)
            dlg.exec_()
        except ImportError:
            QMessageBox.warning(self, "Lỗi", "Không tìm thấy file 'batch_dialog.py'.\nVui lòng đặt batch_dialog.py cùng thư mục với appgui_4.py.")
    def append_log(self, text):
        self.log_text.append(text)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def update_last_log(self, text):
        """Thay thế dòng cuối cùng trong log thay vì thêm dòng mới."""
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.End)
        cursor.select(cursor.LineUnderCursor)
        if cursor.selectedText():
            cursor.removeSelectedText()
            cursor.insertText(text)
        else:
            cursor.insertText(text)
        self.log_text.setTextCursor(cursor)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def log(self, msg):
        self.signals.log.emit(msg)

    def log_inplace(self, msg):
        """Ghi đè lên dòng cuối — dùng cho đếm ngược, tiến độ liên tục."""
        self.signals.log_inplace.emit(msg)

    def refresh_table_from_thread(self):
        self.display_page(self.current_page)

    def _on_analysis_done(self, txt):
        pass

    def stop_all_processes(self):
        self.is_translating = False
        self.is_generating_audio = False
        self.btn_dung.setEnabled(False)
        self.log("[HỆ THỐNG] Đã ra lệnh DỪNG các tiến trình đang chạy.")

    # ----------------- PROJECT (SAVE/LOAD) -----------------
    def save_project(self):
        if not self.srt_entries:
            QMessageBox.warning(self, "Cảnh báo", "Không có dữ liệu để lưu dự án!")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Lưu Dự Án", "", "VK Project (*.vkproj);;JSON files (*.json)")
        if not path:
            return

        project_data = {
            "srt_entries": self.srt_entries,
            "loaded_srt_path": self.loaded_srt_path,
            "translation_rule": self.translation_rule,
            "tts_model_path": self.txt_model_path.text().strip(),
            "piper_exe_path": self.txt_piper_exe.text().strip(),
            "settings": {
                "spin_dong": self.spin_dong.value(),
                "combo_tocdo": self.combo_tocdo.currentIndex(),
                "chk_bodaucau": self.chk_bodaucau.isChecked(),
                "chk_ngangon": self.chk_ngangon.isChecked(),
                "chk_longtieng": self.chk_longtieng.isChecked(),
                "chk_themcham": self.chk_themcham.isChecked(),
                "chk_fix1tu": self.chk_fix1tu.isChecked(),
                "chk_send_context": self.chk_send_context.isChecked()
            }
        }

        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, ensure_ascii=False, indent=4)
            self.log(f"[DỰ ÁN] Đã lưu dự án thành công tại: {path}")
            QMessageBox.information(self, "Thành công", "Đã lưu toàn bộ tiến trình dự án!")
        except Exception as e:
            self.log(f"[LỖI] Không thể lưu dự án: {e}")
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu dự án: {e}")

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Mở Dự Án", "", "VK Project (*.vkproj);;JSON files (*.json);;All files (*)")
        if not path:
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)

            self.srt_entries = project_data.get("srt_entries", [])
            self.loaded_srt_path = project_data.get("loaded_srt_path", "")
            self.translation_rule = project_data.get("translation_rule", "")
            
            loaded_tts_model = project_data.get("tts_model_path", "")
            if loaded_tts_model:
                self.tts_model_path = loaded_tts_model
                self.txt_model_path.setText(self.tts_model_path)
                
            loaded_piper_exe = project_data.get("piper_exe_path", "")
            if loaded_piper_exe:
                self.piper_exe_path = loaded_piper_exe
                self.txt_piper_exe.setText(self.piper_exe_path)

            settings = project_data.get("settings", {})
            if settings:
                self.spin_dong.setValue(settings.get("spin_dong", 20))
                self.combo_tocdo.setCurrentIndex(settings.get("combo_tocdo", 0))
                self.chk_bodaucau.setChecked(settings.get("chk_bodaucau", False))
                self.chk_ngangon.setChecked(settings.get("chk_ngangon", False))
                self.chk_longtieng.setChecked(settings.get("chk_longtieng", False))
                self.chk_themcham.setChecked(settings.get("chk_themcham", False))
                self.chk_fix1tu.setChecked(settings.get("chk_fix1tu", False))
                self.chk_send_context.setChecked(settings.get("chk_send_context", False))

            self.current_page = 1
            self.update_page_combo()
            self.display_page(1)
            self.lbl_status.setText(f"[Đã tải dự án: {len(self.srt_entries)} dòng]")
            
            if self.translation_rule:
                self.chk_send_context.setChecked(True)

            self.log(f"[DỰ ÁN] Đã khôi phục dự án từ: {path}")
            QMessageBox.information(self, "Thành công", f"Đã tải dự án thành công!\nTổng cộng: {len(self.srt_entries)} dòng.")

        except Exception as e:
            self.log(f"[LỖI] Không thể mở dự án: {e}")
            QMessageBox.critical(self, "Lỗi", f"Không thể đọc file dự án: {e}")

    # ----------------- WINDOWS NATIVE PIPER.EXE -----------------
    def browse_piper_exe(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file piper.exe", "", "Executable (*.exe);;All files (*)")
        if path:
            self.txt_piper_exe.setText(path)
            self.piper_exe_path = path

    def browse_tts_model(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file Model ONNX", "", "ONNX files (*.onnx);;All files (*)")
        if path:
            self.txt_model_path.setText(path)
            self.tts_model_path = path

    def save_tts_config(self):
        self.tts_model_path = self.txt_model_path.text().strip()
        self.piper_exe_path = self.txt_piper_exe.text().strip()
        self.save_app_config()

    def _on_speed_slider_changed(self, value):
        """Slider kéo -> cập nhật SpinBox (chặn vòng lặp)."""
        speed = value / 100.0
        self.spin_speed.blockSignals(True)
        self.spin_speed.setValue(speed)
        self.spin_speed.blockSignals(False)
        self._update_speed_color(speed)

    def _on_speed_spin_changed(self, value):
        """SpinBox nhập -> cập nhật Slider (chặn vòng lặp)."""
        self.slider_speed.blockSignals(True)
        self.slider_speed.setValue(int(round(value * 100)))
        self.slider_speed.blockSignals(False)
        self._update_speed_color(value)

    def _update_speed_color(self, speed):
        """Đổi màu SpinBox theo ngưỡng tốc độ."""
        if speed < 0.80:
            color = "#e67e22"   # cam = rất nhanh
        elif speed < 1.00:
            color = "#28a745"   # xanh lá = nhanh vừa
        elif speed == 1.00:
            color = "#004d99"   # xanh dương = bình thường
        elif speed <= 1.30:
            color = "#17a2b8"   # cyan = hơi chậm
        else:
            color = "#dc3545"   # đỏ = rất chậm
        self.spin_speed.setStyleSheet(f"font-weight: bold; color: {color};")

    def generate_single_audio_subprocess(self, text, output_wav_path):
        if not self.piper_exe_path or not os.path.exists(self.piper_exe_path):
            self.log("[LỖI] Chưa trỏ đường dẫn tới file 'piper.exe'. Vui lòng chọn ở mục 4!")
            return False

        if not self.tts_model_path or not os.path.exists(self.tts_model_path):
            self.log("[LỖI] Không tìm thấy Model ONNX. Vui lòng kiểm tra lại đường dẫn!")
            return False

        # ── Tiền xử lý văn bản tiếng Việt (số, ngày, đơn vị...) ──
        try:
            from vn_text_processor import process as vn_process
            processed_text = vn_process(text)
            if processed_text != text:
                self.log(f"[TTS-PRE] {text[:40]}… → {processed_text[:60]}")
        except ImportError:
            processed_text = text   # Fallback nếu chưa có file
        
        try:
            length_scale = round(self.spin_speed.value(), 2)
            self.log_inplace(f"[AUDIO] 🎙 ID đang tạo... tốc độ {length_scale}x")
            # GỌI TRỰC TIẾP FILE EXE, ẨN CỬA SỔ CMD BẰNG CREATE_NO_WINDOW
            process = subprocess.Popen(
                [self.piper_exe_path, '--model', self.tts_model_path,
                 '--length_scale', str(length_scale),
                 '--output_file', output_wav_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW
            )
            stdout, stderr = process.communicate(input=processed_text.encode('utf-8'))
            if process.returncode != 0:
                self.log(f"[LỖI PIPER] {stderr.decode('utf-8', errors='ignore')}")
                return False
            return True
        except Exception as e:
            self.log(f"[LỖI TẠO AUDIO] {e}")
            return False

    def on_click_create_single_audio(self, global_idx):
        entry = self.srt_entries[global_idx]
        text = entry.get('translated', '').strip()
        if not text:
            QMessageBox.warning(self, "Cảnh báo", "Dòng này chưa có văn bản Dịch!")
            return
        
        row_id = entry.get('id', str(global_idx))
        output_path = os.path.join(self.audio_output_dir, f"audio_{row_id}.wav")

        self.log_inplace(f"[AUDIO] 🎙 Đang tạo ID {row_id}...")
        
        def worker():
            success = self.generate_single_audio_subprocess(text, output_path)
            if success:
                self.log(f"[AUDIO] ✅ Tạo xong ID: {row_id}")
                self.signals.update_table.emit()
                
        threading.Thread(target=worker, daemon=True).start()

    def start_batch_audio_thread(self):
        self.tts_model_path = self.txt_model_path.text().strip()
        self.piper_exe_path = self.txt_piper_exe.text().strip()

        if not self.piper_exe_path or not os.path.exists(self.piper_exe_path):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn đường dẫn tới file 'piper.exe' trước!")
            return

        if not self.tts_model_path or not os.path.exists(self.tts_model_path):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn model ONNX ở phần 4 trước khi chạy Hàng Loạt!")
            return
            
        if self.is_generating_audio:
            return
            
        self.is_generating_audio = True
        self.btn_dung.setEnabled(True)
        threading.Thread(target=self.run_batch_audio, daemon=True).start()

    def run_batch_audio(self):
        self.log("[HỆ THỐNG] Bắt đầu tạo Audio Hàng Loạt (Bằng Piper.exe độc lập)...")
        count = 0
        total = sum(1 for item in self.srt_entries if item.get('translated', '').strip())
        self.log(f"[TIẾN ĐỘ AUDIO] 🎙 Đã tạo 0/{total} file...")   # seed line

        for idx, entry in enumerate(self.srt_entries):
            if not self.is_generating_audio:
                break
                
            text = entry.get('translated', '').strip()
            if not text:
                continue 
            
            row_id = entry.get('id', str(idx))
            output_path = os.path.join(self.audio_output_dir, f"audio_{row_id}.wav")
            
            success = self.generate_single_audio_subprocess(text, output_path)
            if success:
                count += 1
                self.log_inplace(f"[TIẾN ĐỘ AUDIO] 🎙 Đã tạo {count}/{total} file... (ID {row_id})")
                if count % 5 == 0:
                    self.signals.update_table.emit()

        self.signals.update_table.emit()
        self.is_generating_audio = False
        self.btn_dung.setEnabled(False if not self.is_translating else True)
        self.log(f"[HỆ THỐNG] ✅ Hoàn tất tạo Audio! (Tổng: {count} file)")

    def delete_single_audio(self, path, row_id):
        if not os.path.exists(path):
            return
        try:
            os.remove(path)
            self.log(f"[AUDIO] 🗑 Đã xóa audio ID {row_id}")
            self.signals.update_table.emit()
        except Exception as e:
            self.log(f"[LỖI] Không thể xóa audio {row_id}: {e}")

    def delete_all_audio(self):
        files = [f for f in os.listdir(self.audio_output_dir)
                 if f.startswith('audio_') and f.endswith('.wav')]
        if not files:
            QMessageBox.information(self, "Thông báo", "Không có file audio nào để xóa.")
            return
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            f"Bạn có chắc muốn xóa {len(files)} file audio không?\n"
            f"(Chỉ xóa audio_*.wav, không xóa file ghép)",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        count = 0
        for f in files:
            try:
                os.remove(os.path.join(self.audio_output_dir, f))
                count += 1
            except Exception as e:
                self.log(f"[LỖI] Không xóa được {f}: {e}")
        self.log(f"[AUDIO] 🗑 Đã xóa {count}/{len(files)} file audio.")
        self.signals.update_table.emit()

    def play_audio(self, path):
        if not os.path.exists(path):
            self.log("[LỖI] File âm thanh không tồn tại.")
            return
        try:
            if platform.system() == 'Windows':
                os.startfile(path)
            elif platform.system() == 'Darwin':
                subprocess.call(['open', path])
            else:
                subprocess.call(['xdg-open', path])
        except Exception as e:
            self.log(f"[LỖI PHÁT AUDIO] {e}")

    # ----------- XUẤT AUDIO CHUẨN TIMELINE (Kéo/Giãn) -----------
    def start_export_timeline_audio_thread(self):
        if not self.srt_entries:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng tải SRT trước!")
            return
        if self.is_generating_audio:
            QMessageBox.warning(self, "Cảnh báo", "Hệ thống đang bận tạo audio. Vui lòng chờ!")
            return
        self.is_generating_audio = True
        self.btn_dung.setEnabled(True)
        threading.Thread(target=self.run_export_timeline_audio, daemon=True).start()

    def run_export_timeline_audio(self):
        """
        Xuất 1 file WAV duy nhất: mỗi clip audio được kéo/giãn khớp đúng duration_ms
        của dòng SRT, sau đó đặt vào đúng vị trí start_ms → KHÔNG đè giọng nhau.
        
        Logic:
          - audio dài hơn SRT duration  → tăng tốc (resample) cho vừa khít
          - audio ngắn hơn SRT duration → giữ nguyên + thêm im lặng phía sau
          - đặt vào buffer tại vị trí start_ms của SRT
        """
        import wave as _wave
        try:
            import numpy as np
            has_numpy = True
        except ImportError:
            has_numpy = False
            self.log("[CẢNH BÁO] Không có numpy — dùng audioop fallback (chỉ 16-bit).")

        output_path = os.path.join(self.audio_output_dir, "merged_nokede.wav")
        self.log("[NOKEDE] 🔍 Đang quét danh sách audio và tính toán buffer...")

        # ── Pass 1: Lấy thông số WAV chung + quét tổng độ dài cần thiết ──
        ref_n_ch = ref_sw = ref_rate = None
        segments = []   # list of (start_frame, adjusted_raw_bytes)

        for idx, entry in enumerate(self.srt_entries):
            if not self.is_generating_audio:
                break
            row_id   = entry.get('id', str(idx))
            src      = os.path.join(self.audio_output_dir, f"audio_{row_id}.wav")
            srt_ms   = entry.get('duration_ms', 0)
            start_ms = self.srt_time_to_ms(entry.get('time', ''))

            if not os.path.exists(src):
                continue

            try:
                with _wave.open(src, 'rb') as wf:
                    n_ch = wf.getnchannels()
                    sw   = wf.getsampwidth()
                    rate = wf.getframerate()
                    n_fr = wf.getnframes()
                    raw  = wf.readframes(n_fr)
            except Exception as e:
                self.log(f"[NOKEDE] ⚠ Bỏ qua ID {row_id}: {e}")
                continue

            # Lấy thông số tham chiếu từ file đầu tiên
            if ref_rate is None:
                ref_n_ch, ref_sw, ref_rate = n_ch, sw, rate
                self.log(f"[NOKEDE] Thông số WAV: {rate} Hz | {n_ch}ch | {sw*8}-bit")

            start_frame   = int(start_ms * rate / 1000)
            audio_ms      = n_fr * 1000 / rate
            target_frames = int(srt_ms * rate / 1000) if srt_ms > 0 else n_fr

            # ── Điều chỉnh độ dài clip ──
            if srt_ms > 0 and audio_ms > srt_ms + 50:   # dư > 50ms mới kéo
                # TĂNG TỐC (OLA) — giữ pitch, không gây biến dạng cao độ
                if has_numpy:
                    if sw == 2:   dtype = np.int16
                    elif sw == 1: dtype = np.uint8
                    else:         dtype = np.int32

                    # Tách thành từng channel rồi OLA từng channel
                    samples = np.frombuffer(raw, dtype=dtype).astype(np.float32)
                    if n_ch > 1:
                        ch_data = [samples[c::n_ch] for c in range(n_ch)]
                    else:
                        ch_data = [samples]

                    stretch_ratio = target_frames / n_fr   # < 1 = nén lại

                    def _wsola_stretch(mono, ratio, sr):
                        """
                        WSOLA time-stretch — giữ pitch, chỉ thay đổi tốc độ.
                        ratio < 1 = nén (nhanh hơn), ratio > 1 = giãn (chậm hơn).
                        """
                        win_size = int(sr * 0.025)   # 25ms window
                        hop_in   = int(sr * 0.010)   # 10ms hop input
                        hop_out  = max(1, int(hop_in * ratio))
                        search   = int(sr * 0.005)   # 5ms WSOLA search range
                        window   = np.hanning(win_size).astype(np.float32)
                        n_in     = len(mono)
                        out_len  = int(n_in * ratio) + win_size + search + 64
                        out_buf  = np.zeros(out_len, np.float32)
                        norm_buf = np.zeros(out_len, np.float32)
                        out_ptr  = 0
                        in_ptr   = 0
                        while in_ptr + win_size <= n_in and out_ptr + win_size <= out_len:
                            best_off, best_corr = 0, -np.inf
                            if out_ptr >= hop_out:
                                prev = out_buf[out_ptr - hop_out : out_ptr - hop_out + win_size]
                                for off in range(-search, search + 1):
                                    p = in_ptr + off
                                    if p < 0 or p + win_size > n_in:
                                        continue
                                    c = float(np.dot(prev, mono[p : p + win_size]))
                                    if c > best_corr:
                                        best_corr, best_off = c, off
                            actual = max(0, min(in_ptr + best_off, n_in - win_size))
                            chunk  = mono[actual : actual + win_size].copy() * window
                            out_buf [out_ptr : out_ptr + win_size] += chunk
                            norm_buf[out_ptr : out_ptr + win_size] += window
                            out_ptr += hop_out
                            in_ptr  += hop_in
                        norm_buf = np.maximum(norm_buf, 1e-8)
                        t = int(n_in * ratio)
                        return (out_buf / norm_buf)[:t]

                    stretched_chs = [_wsola_stretch(ch, stretch_ratio, rate) for ch in ch_data]
                    # Interleave channels back
                    out_f = np.empty(target_frames * n_ch, np.float32)
                    for c, ch in enumerate(stretched_chs):
                        ch_trimmed = ch[:target_frames]
                        out_f[c::n_ch] = ch_trimmed
                    # Clip và convert về dtype gốc
                    if dtype == np.int16:
                        np.clip(out_f, -32768, 32767, out=out_f)
                        clip_raw = out_f.astype(np.int16).tobytes()
                    elif dtype == np.uint8:
                        np.clip(out_f, 0, 255, out=out_f)
                        clip_raw = out_f.astype(np.uint8).tobytes()
                    else:
                        clip_raw = out_f.astype(np.int32).tobytes()
                else:
                    import audioop
                    ratio    = n_fr / target_frames
                    clip_raw, _ = audioop.ratecv(raw, sw, n_ch, rate,
                                                 int(rate / ratio), None)
                    target_frames = len(clip_raw) // (sw * n_ch)
            elif srt_ms > 0 and audio_ms < srt_ms - 50:  # thiếu > 50ms mới pad
                # THÊM IM LẶNG: giữ nguyên audio + silence phần còn lại
                silence = bytes((target_frames - n_fr) * n_ch * sw)
                clip_raw = raw + silence
            else:
                # Khớp đủ gần → dùng nguyên
                clip_raw = raw
                target_frames = n_fr

            segments.append((start_frame, target_frames, clip_raw))

        if not segments:
            self.log("[NOKEDE] ⚠ Không tìm thấy file audio nào để ghép.")
            self.is_generating_audio = False
            self.btn_dung.setEnabled(False if not self.is_translating else True)
            return

        # ── Pass 2: Cấp phát 1 buffer duy nhất và ghi từng clip ──
        total_frames = max(sf + tf for sf, tf, _ in segments)
        total_sec    = total_frames / ref_rate
        self.log(f"[NOKEDE] Tổng thời lượng: {total_sec:.1f}s | Đang mix {len(segments)} clip...")
        self.log(f"[NOKEDE] 🔀 Mix 0/{len(segments)} clip...")

        if has_numpy:
            if ref_sw == 2:   np_dtype, mix_dtype = np.int16, np.int32
            elif ref_sw == 1: np_dtype, mix_dtype = np.uint8, np.int16
            else:             np_dtype, mix_dtype = np.int32, np.int64

            mix_buf = np.zeros(total_frames * ref_n_ch, dtype=mix_dtype)

            for i, (start_frame, n_frames, clip_raw) in enumerate(segments):
                start_sample = start_frame * ref_n_ch
                seg_arr = np.frombuffer(clip_raw, dtype=np_dtype).astype(mix_dtype)
                end_s   = start_sample + len(seg_arr)
                if end_s <= len(mix_buf):
                    mix_buf[start_sample:end_s] += seg_arr
                else:
                    mix_buf[start_sample:] += seg_arr[:len(mix_buf) - start_sample]
                if (i + 1) % 100 == 0:
                    self.log_inplace(f"[NOKEDE] 🔀 Mix {i+1}/{len(segments)} clip...")

            # Clamp và chuyển về dtype gốc
            if ref_sw == 2:
                np.clip(mix_buf, -32768, 32767, out=mix_buf)
                out_data = mix_buf.astype(np.int16).tobytes()
            elif ref_sw == 1:
                np.clip(mix_buf, 0, 255, out=mix_buf)
                out_data = mix_buf.astype(np.uint8).tobytes()
            else:
                out_data = mix_buf.astype(np.int32).tobytes()
        else:
            # Fallback thuần Python — chỉ 16-bit PCM
            if ref_sw != 2:
                self.log("[LỖI] Cần numpy để xử lý WAV không phải 16-bit. Cài: pip install numpy")
                self.is_generating_audio = False
                self.btn_dung.setEnabled(False if not self.is_translating else True)
                return
            import array as _arr
            mix_buf = _arr.array('i', [0] * (total_frames * ref_n_ch))
            for start_frame, n_frames, clip_raw in segments:
                start_sample = start_frame * ref_n_ch
                seg_arr = _arr.array('h', clip_raw)
                for j, s in enumerate(seg_arr):
                    pos = start_sample + j
                    if pos < len(mix_buf):
                        mix_buf[pos] += s
            out_data = _arr.array('h', [max(-32768, min(32767, s)) for s in mix_buf]).tobytes()

        # ── Ghi file output duy nhất ──
        try:
            with _wave.open(output_path, 'wb') as wf:
                wf.setnchannels(ref_n_ch)
                wf.setsampwidth(ref_sw)
                wf.setframerate(ref_rate)
                wf.writeframes(out_data)
            self.log(
                f"[NOKEDE] ✅ Hoàn tất!\n"
                f"           📁 File: merged_nokede.wav  ({total_sec:.1f}s)\n"
                f"           🔊 Tổng: {len(segments)} clip được ghép"
            )
        except Exception as e:
            self.log(f"[LỖI NOKEDE] Không ghi được file: {e}")

        self.is_generating_audio = False
        self.btn_dung.setEnabled(False if not self.is_translating else True)

    def play_timeline_audio(self):
        path = os.path.join(self.audio_output_dir, "merged_nokede.wav")
        if os.path.exists(path):
            self.log(f"[AUDIO] Đang phát: {path}")
            self.play_audio(path)
        else:
            QMessageBox.warning(self, "Lỗi", "Chưa có file 'merged_nokede.wav'! Vui lòng bấm 'XUẤT CHUẨN TIMELINE' trước.")

    # ----------------- Audio Merging (Nối tiếp / Timeline) -----------------
    def srt_time_to_ms(self, time_str):
        try:
            start_str = time_str.split('-->')[0].strip()
            match = re.search(r'(\d+):(\d+):(\d+),(\d+)', start_str)
            if match:
                h, m, s, ms = map(int, match.groups())
                return (h * 3600 + m * 60 + s) * 1000 + ms
        except:
            pass
        return 0

    def start_merge_audio_thread(self):
        if self.is_generating_audio:
            QMessageBox.warning(self, "Cảnh báo", "Hệ thống đang bận tạo audio. Vui lòng chờ!")
            return
        threading.Thread(target=self.run_merge_audio, daemon=True).start()

    def run_merge_audio(self):
        import wave as _wave
        import array as _arr

        self.is_generating_audio = True
        self.log("[HỆ THỐNG] Bắt đầu gộp file audio...")
        mode = self.combo_merge_type.currentIndex()
        if mode == 0:
            output_path = os.path.join(self.audio_output_dir, "merged_noitieip.wav")
        else:
            output_path = os.path.join(self.audio_output_dir, "merged_timeline.wav")
        count = 0

        try:
            # ── Thu thập danh sách file hợp lệ ──
            file_list = []
            for idx, entry in enumerate(self.srt_entries):
                row_id = entry.get('id', str(idx))
                fp = os.path.join(self.audio_output_dir, f"audio_{row_id}.wav")
                if os.path.exists(fp):
                    file_list.append((fp, entry))

            if not file_list:
                self.log("[CẢNH BÁO] Không tìm thấy file audio lẻ nào để ghép.")
                self.is_generating_audio = False
                return

            # ── Đọc thông số WAV từ file đầu tiên ──
            with _wave.open(file_list[0][0], 'rb') as wf:
                n_channels = wf.getnchannels()
                sampwidth  = wf.getsampwidth()
                framerate  = wf.getframerate()

            self.log(f"[GHÉP AUDIO] {len(file_list)} file | {framerate} Hz | {n_channels}ch | {sampwidth*8}-bit")

            # ══════════════════════════════════════════════════════════
            # MODE 0: Nối tiếp — ghi thẳng raw PCM bytes, O(n), không copy
            # ══════════════════════════════════════════════════════════
            if mode == 0:
                with _wave.open(output_path, 'wb') as out_wf:
                    out_wf.setnchannels(n_channels)
                    out_wf.setsampwidth(sampwidth)
                    out_wf.setframerate(framerate)
                    for i, (fp, entry) in enumerate(file_list):
                        try:
                            with _wave.open(fp, 'rb') as wf:
                                out_wf.writeframes(wf.readframes(wf.getnframes()))
                            count += 1
                        except Exception as e:
                            self.log(f"[CẢNH BÁO] Bỏ qua file lỗi: {os.path.basename(fp)} — {e}")
                        if (i + 1) % 100 == 0:
                            self.log_inplace(f"[GHÉP] 📎 {i+1}/{len(file_list)} file...")
                self.log(f"[HỆ THỐNG] ✅ Đã ghép nối tiếp {count} file thành công!")

            # ══════════════════════════════════════════════════════════
            # MODE 1: Timeline — cấp phát 1 buffer duy nhất, ghi 1 lần
            # ══════════════════════════════════════════════════════════
            else:
                self.log("[GHÉP AUDIO] Đang quét timeline và chuẩn bị bộ đệm...")

                # Pass 1: tính tổng độ dài cần thiết
                segments = []
                max_end_frame = 0
                for fp, entry in file_list:
                    start_ms    = self.srt_time_to_ms(entry.get('time', ''))
                    start_frame = int(start_ms * framerate / 1000)
                    try:
                        with _wave.open(fp, 'rb') as wf:
                            n_frames = wf.getnframes()
                        end_frame = start_frame + n_frames
                        if end_frame > max_end_frame:
                            max_end_frame = end_frame
                        segments.append((fp, start_frame, n_frames))
                    except Exception as e:
                        self.log(f"[CẢNH BÁO] Bỏ qua: {os.path.basename(fp)} — {e}")

                total_samples = max_end_frame * n_channels
                total_sec     = max_end_frame / framerate
                self.log(f"[GHÉP AUDIO] Thời lượng: {total_sec:.1f}s | Đang mix {len(segments)} file...")
                self.log(f"[GHÉP] 📎 0/{len(segments)} file...")

                # Pass 2: mix vào buffer
                try:
                    import numpy as np
                    # numpy: vectorized, nhanh nhất
                    if sampwidth == 2:
                        np_dtype, mix_dtype = np.int16, np.int32
                    elif sampwidth == 1:
                        np_dtype, mix_dtype = np.uint8, np.int16
                    else:
                        np_dtype, mix_dtype = np.int32, np.int64

                    mix_buf = np.zeros(total_samples, dtype=mix_dtype)

                    for i, (fp, start_frame, n_frames) in enumerate(segments):
                        start_sample = start_frame * n_channels
                        try:
                            with _wave.open(fp, 'rb') as wf:
                                raw = wf.readframes(n_frames)
                            seg_arr = np.frombuffer(raw, dtype=np_dtype).astype(mix_dtype)
                            end_s   = start_sample + len(seg_arr)
                            if end_s <= total_samples:
                                mix_buf[start_sample:end_s] += seg_arr
                            else:
                                mix_buf[start_sample:] += seg_arr[:total_samples - start_sample]
                            count += 1
                        except Exception as e:
                            self.log(f"[CẢNH BÁO] Bỏ qua: {os.path.basename(fp)} — {e}")
                        if (i + 1) % 100 == 0:
                            self.log_inplace(f"[GHÉP] 📎 {i+1}/{len(segments)} file...")

                    # Clamp và chuyển về dtype gốc
                    if sampwidth == 2:
                        np.clip(mix_buf, -32768, 32767, out=mix_buf)
                        out_data = mix_buf.astype(np.int16).tobytes()
                    elif sampwidth == 1:
                        np.clip(mix_buf, 0, 255, out=mix_buf)
                        out_data = mix_buf.astype(np.uint8).tobytes()
                    else:
                        out_data = mix_buf.astype(np.int32).tobytes()

                except ImportError:
                    # Fallback: array module (chỉ hỗ trợ 16-bit PCM)
                    self.log("[GHÉP AUDIO] numpy không có — dùng array module (16-bit only)...")
                    if sampwidth != 2:
                        self.log("[LỖI] Cần numpy để ghép WAV không phải 16-bit. Cài: pip install numpy")
                        self.is_generating_audio = False
                        return

                    mix_buf = _arr.array('i', bytes(total_samples * 4))  # int32 pre-alloc
                    for i, (fp, start_frame, n_frames) in enumerate(segments):
                        start_sample = start_frame * n_channels
                        try:
                            with _wave.open(fp, 'rb') as wf:
                                raw = wf.readframes(n_frames)
                            seg_arr = _arr.array('h', raw)
                            for j, s in enumerate(seg_arr):
                                pos = start_sample + j
                                if pos < total_samples:
                                    mix_buf[pos] += s
                            count += 1
                        except Exception as e:
                            self.log(f"[CẢNH BÁO] Bỏ qua: {os.path.basename(fp)} — {e}")
                        if (i + 1) % 50 == 0:
                            self.log_inplace(f"[GHÉP] 📎 {i+1}/{len(segments)} file...")

                    out_arr  = _arr.array('h', [max(-32768, min(32767, s)) for s in mix_buf])
                    out_data = out_arr.tobytes()

                # Ghi output một lần duy nhất
                with _wave.open(output_path, 'wb') as out_wf:
                    out_wf.setnchannels(n_channels)
                    out_wf.setsampwidth(sampwidth)
                    out_wf.setframerate(framerate)
                    out_wf.writeframes(out_data)

                self.log(f"[HỆ THỐNG] ✅ Đã ghép chuẩn TIMELINE {count} file thành công!")

        except Exception as e:
            self.log(f"[LỖI GHÉP AUDIO] {e}")

        self.is_generating_audio = False

    def play_merged_audio(self):
        mode = self.combo_merge_type.currentIndex()
        fname = "merged_noitieip.wav" if mode == 0 else "merged_timeline.wav"
        path = os.path.join(self.audio_output_dir, fname)
        if os.path.exists(path):
            self.log(f"[AUDIO] Đang phát file tổng: {path}")
            self.play_audio(path)
        else:
            QMessageBox.warning(self, "Lỗi", f"Chưa có file '{fname}'! Vui lòng bấm 'TẠO FILE GHÉP' trước.")

    # ----------------- File load/save / SRT parsing -----------------
    def load_srt(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file SRT", "", "SRT files (*.srt);;All files (*)")
        if not path:
            return
        self._load_srt_from_path(path)

    def _load_srt_from_path(self, path):
        """Tải file SRT từ đường dẫn cụ thể vào bảng."""
        self.loaded_srt_path = path
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))
            return

        blocks = re.split(r'\n\s*\n', content.strip())
        self.srt_entries = []
        for block in blocks:
            lines = block.split('\n')
            if len(lines) >= 3 and lines[0].strip().isdigit():
                time_line = lines[1].strip()
                entry = {'id': lines[0].strip(), 'time': time_line,
                         'original': '\n'.join(lines[2:]).strip(), 'translated': '',
                         'duration_ms': self._calc_duration_ms(time_line)}
            elif len(lines) >= 2 and '-->' in lines[0]:
                time_line = lines[0].strip()
                entry = {'id': '', 'time': time_line,
                         'original': '\n'.join(lines[1:]).strip(), 'translated': '',
                         'duration_ms': self._calc_duration_ms(time_line)}
            else:
                time_line = lines[1].strip() if len(lines) > 1 else ''
                entry = {'id': (lines[0].strip() if lines else ''), 'time': time_line,
                         'original': '\n'.join(lines[2:]).strip() if len(lines) > 2 else '\n'.join(lines).strip(),
                         'translated': '', 'duration_ms': self._calc_duration_ms(time_line)}
            self.srt_entries.append(entry)

        self.current_page = 1
        self.update_page_combo()
        self.display_page(1)
        self.lbl_status.setText(f"[Đã tải {len(self.srt_entries)} dòng — {os.path.basename(path)}]")
        self.log(f"[HỆ THỐNG] Đã tải SRT: {len(self.srt_entries)} dòng từ '{os.path.basename(path)}'.")

    # ----------------- Nối Gap helpers -----------------
    def _calc_duration_ms(self, time_str):
        """Tính thời lượng (ms) từ chuỗi 'HH:MM:SS,mmm --> HH:MM:SS,mmm'."""
        try:
            parts = time_str.split('-->')
            if len(parts) == 2:
                return max(0, self._time_str_to_ms(parts[1].strip()) - self._time_str_to_ms(parts[0].strip()))
        except Exception:
            pass
        return 0

    def _time_str_to_ms(self, t):
        """Chuyển chuỗi HH:MM:SS,mmm sang milliseconds."""
        try:
            t = t.strip()
            h, m, s_ms = t.split(':')
            s, ms = s_ms.split(',')
            return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)
        except Exception:
            return 0

    def _ms_to_time_str(self, ms):
        """Chuyển milliseconds sang chuỗi HH:MM:SS,mmm."""
        ms = max(0, int(ms))
        h = ms // 3600000
        ms %= 3600000
        m = ms // 60000
        ms %= 60000
        s = ms // 1000
        ms %= 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def _apply_gap_to_entries(self, entries, gap_ms):
        """Trả về danh sách entries mới với thời gian kết thúc đã được điều chỉnh."""
        result = []
        for i, entry in enumerate(entries):
            new_entry = entry.copy()
            time_str = entry.get('time', '')
            if '-->' in time_str:
                parts = time_str.split('-->')
                start_str = parts[0].strip()
                start_ms = self._time_str_to_ms(start_str)
                if i < len(entries) - 1:
                    next_time = entries[i + 1].get('time', '')
                    if '-->' in next_time:
                        next_start_str = next_time.split('-->')[0].strip()
                        next_start_ms = self._time_str_to_ms(next_start_str)
                        new_end_ms = next_start_ms - gap_ms
                        if new_end_ms <= start_ms:
                            new_end_ms = start_ms + 1000
                        new_entry['time'] = f"{start_str} --> {self._ms_to_time_str(new_end_ms)}"
            result.append(new_entry)
        return result

    def save_srt_with_gap(self):
        """Xuất file SRT đã nối gap rồi tự động tải lại vào app."""
        if not self.srt_entries:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng tải file SRT trước!")
            return

        gap_ms = self.spin_gap.value()

        # Xây dựng tên file _noigap.srt
        if self.loaded_srt_path:
            base = self.loaded_srt_path
            if base.lower().endswith('.srt'):
                save_path = base[:-4] + '_noigap.srt'
            else:
                save_path = base + '_noigap.srt'
        else:
            save_path, _ = QFileDialog.getSaveFileName(
                self, "Lưu SRT Nối Gap", "output_noigap.srt", "SRT files (*.srt)"
            )
            if not save_path:
                return

        # Áp dụng gap
        adjusted = self._apply_gap_to_entries(self.srt_entries, gap_ms)

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                for item in adjusted:
                    entry_id = item.get('id', '')
                    entry_time = item.get('time', '')
                    entry_orig = item.get('original', '')
                    if entry_id:
                        f.write(f"{entry_id}\n")
                    f.write(f"{entry_time}\n{entry_orig}\n\n")

            self.log(f"[NỐI GAP] ✅ Đã xuất: '{os.path.basename(save_path)}' (gap={gap_ms} ms)")

            # Tự động tải lại file _noigap vào app
            self._load_srt_from_path(save_path)

            QMessageBox.information(
                self, "Thành công",
                f"✅ Đã xuất và tải lại file nối gap:\n{os.path.basename(save_path)}\n\n"
                f"File gốc vẫn được giữ nguyên.\n"
                f"Bây giờ bạn có thể tiến hành Phân tích & Dịch thuật."
            )
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def save_srt(self):
        if not self.srt_entries:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Lưu file SRT", "", "SRT files (*.srt)")
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                for item in self.srt_entries:
                    if item.get('translated', '').strip():
                        f.write(f"{item.get('id','')}\n{item.get('time','')}\n{item.get('translated','')}\n\n")
            self.log("[HỆ THỐNG] Đã lưu SRT thành công.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", str(e))

    def update_page_combo(self):
        total = max(1, (len(self.srt_entries) + self.per_page - 1) // self.per_page)
        self.combo_page.blockSignals(True)
        self.combo_page.clear()
        for i in range(1, total + 1):
            self.combo_page.addItem(str(i))
        self.combo_page.blockSignals(False)

    def display_page(self, page):
        if not self.srt_entries:
            self.table.setRowCount(0)
            return
        total = max(1, (len(self.srt_entries) + self.per_page - 1) // self.per_page)
        page = max(1, min(page, total))
        self.current_page = page
        start = (page - 1) * self.per_page
        end = min(start + self.per_page, len(self.srt_entries))
        page_entries = self.srt_entries[start:end]

        self.table.setRowCount(len(page_entries))
        for r, ent in enumerate(page_entries):
            global_idx = start + r
            row_id = ent.get('id', str(global_idx))

            item_chk = QTableWidgetItem()
            item_chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item_chk.setCheckState(Qt.Unchecked)
            self.table.setItem(r, 0, item_chk)

            self.table.setItem(r, 1, QTableWidgetItem(row_id))
            time_raw = ent.get('time', '')
            dur_ms   = self._calc_duration_ms(time_raw) if '-->' in time_raw else ent.get('duration_ms', 0)
            dur_s    = dur_ms / 1000.0
            if dur_ms > 0:
                time_display = f"{time_raw}  ⏱ {dur_s:.2f}s"
            else:
                time_display = time_raw
            time_item = QTableWidgetItem(time_display)
            time_item.setToolTip(f"Thời lượng phụ đề: {dur_s:.3f}s ({dur_ms} ms)")
            self.table.setItem(r, 2, time_item)
            self.table.setItem(r, 3, QTableWidgetItem(ent.get('original', '')))
            trans_item = QTableWidgetItem(ent.get('translated', ''))
            if ent.get('translated','').strip():
                trans_item.setBackground(Qt.darkGreen)
                trans_item.setForeground(Qt.white)
            self.table.setItem(r, 4, trans_item)

            audio_widget = QWidget()
            audio_layout = QHBoxLayout(audio_widget)
            audio_layout.setContentsMargins(2, 2, 2, 2)
            
            btn_create = QPushButton("Tạo")
            btn_play   = QPushButton("▶")
            btn_del    = QPushButton("🗑")
            btn_del.setFixedWidth(28)
            btn_del.setToolTip("Xóa file audio này")
            
            expected_audio_path = os.path.join(self.audio_output_dir, f"audio_{row_id}.wav")
            if os.path.exists(expected_audio_path):
                btn_play.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
                btn_play.setEnabled(True)
                btn_del.setStyleSheet("background-color: #dc3545; color: white;")
                btn_del.setEnabled(True)
            else:
                btn_play.setEnabled(False)
                btn_del.setEnabled(False)

            btn_create.clicked.connect(lambda checked, idx=global_idx: self.on_click_create_single_audio(idx))
            btn_play.clicked.connect(lambda checked, path=expected_audio_path: self.play_audio(path))
            btn_del.clicked.connect(lambda checked, path=expected_audio_path, rid=row_id: self.delete_single_audio(path, rid))

            audio_layout.addWidget(btn_create)
            audio_layout.addWidget(btn_play)
            audio_layout.addWidget(btn_del)
            self.table.setCellWidget(r, 5, audio_widget)

        self.statusBar().showMessage(f"Trang {self.current_page}/{total}")
        if self.combo_page.count() == total:
            self.combo_page.blockSignals(True)
            self.combo_page.setCurrentIndex(self.current_page - 1)
            self.combo_page.blockSignals(False)

    def on_page_combo_changed(self, idx):
        if idx >= 0:
            self.display_page(idx + 1)

    def next_page(self):
        total = max(1, (len(self.srt_entries) + self.per_page - 1) // self.per_page)
        if self.current_page < total:
            self.display_page(self.current_page + 1)

    def prev_page(self):
        if self.current_page > 1:
            self.display_page(self.current_page - 1)

    def on_cell_changed(self, row, column):
        if column not in [3, 4]:
            return

        self.table.blockSignals(True)
        try:
            item = self.table.item(row, column)
            if not item:
                return

            new_text = item.text()
            global_idx = (self.current_page - 1) * self.per_page + row

            if 0 <= global_idx < len(self.srt_entries):
                entry = self.srt_entries[global_idx]
                field_to_update = 'original' if column == 3 else 'translated'

                if entry.get(field_to_update, '') != new_text:
                    entry[field_to_update] = new_text
                    self.log(f"[HỆ THỐNG] Đã cập nhật dòng #{entry.get('id', global_idx + 1)}.")
                    
                    if field_to_update == 'original':
                        self._save_srt_in_place()

        finally:
            self.table.blockSignals(False)

    def _save_srt_in_place(self):
        if not self.loaded_srt_path or not self.srt_entries:
            return
        try:
            with open(self.loaded_srt_path, 'w', encoding='utf-8') as f:
                for item in self.srt_entries:
                    if item.get('id'):
                        f.write(f"{item['id']}\n")
                    f.write(f"{item.get('time', '')}\n")
                    f.write(f"{item.get('original', '')}\n\n")
            self.log(f"[HỆ THỐNG] Đã tự động lưu thay đổi vào file gốc: {os.path.basename(self.loaded_srt_path)}")
        except Exception as e:
            self.log(f"[LỖI] Không thể tự động lưu file SRT gốc: {e}")

    # ----------------- Translate selected now -----------------
    def translate_selected_now(self):
        rows = []
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.checkState() == Qt.Checked:
                global_idx = (self.current_page - 1) * self.per_page + r
                if 0 <= global_idx < len(self.srt_entries):
                    rows.append(global_idx)
        if not rows:
            self.lbl_status.setText("[Chưa chọn dòng nào]")
            return

        chunk = [self.srt_entries[i] for i in rows]
        data_string = "\n".join([f"[{item.get('id','')}] {item.get('original','')}" for item in chunk])

        opts = ""
        if self.chk_bodaucau.isChecked(): opts += "- Bỏ dấu câu.\n"
        if self.chk_ngangon.isChecked(): opts += "- Ngắn gọn.\n"
        if self.chk_longtieng.isChecked(): opts += "- Thêm [nam]/[nữ] lồng tiếng.\n"
        if self.chk_themcham.isChecked(): opts += "- Thêm dấu '...'\n"
        if self.chk_fix1tu.isChecked(): opts += "- XỬ LÝ CÂU 1 TỪ: Nếu dịch ra 1 chữ, BẮT BUỘC thêm từ đệm (đâu, thôi, rồi, ạ, hả, cơ, chứ, đây...) để thành 2-3 chữ.\n"

        prompt = f"""Dịch {len(chunk)} dòng sang TIẾNG VIỆT (BẮT BUỘC DỊCH TOÀN BỘ).
Áp dụng nghiêm ngặt BỘ LUẬT DỊCH:
{self.translation_rule}
YÊU CẦU: Giữ nguyên ID [số]. Trả về Code Block.
{opts}
DỮ LIỆU:
{data_string}"""

        if not self.wait_for_ready_state(timeout=180):
            self.lbl_status.setText('[Gemini chua san sang - dung de tranh huy]')
            self.log('[LOI] Gemini van dang tra loi, chua the gui prompt moi.')
            return

        self.log(f"[TIẾN ĐỘ] (Dòng chọn) Đang gửi {len(chunk)} dòng...")
        sent = self.send_to_gemini(prompt)
        if not sent:
            self.lbl_status.setText("[Không có driver Selenium — prompt đã được copy vào clipboard]")
            return

        response = self.get_gemini_response(timeout=120)
        if response:
            translated_dict = {}
            for line in response.split('\n'):
                match = re.search(r'\[(\d+)\]\s*(.*)', line.strip())
                if match:
                    translated_dict[match.group(1)] = match.group(2).strip()
            updated = 0
            for idx in rows:
                idval = self.srt_entries[idx].get('id','')
                if idval in translated_dict:
                    self.srt_entries[idx]['translated'] = translated_dict[idval]
                    updated += 1
            self.signals.update_table.emit()
            self.lbl_status.setText(f"[Đã cập nhật {updated} dòng]")
        else:
            self.lbl_status.setText("[Không nhận được phản hồi từ Gemini]")

    # ----------------- DỊCH BÙ DÒNG TRỐNG -----------------
    def start_empty_lines_translation(self):
        if not self.driver or not self.translation_rule:
            QMessageBox.information(self, "Thông báo", "Vui lòng mở trình duyệt (Selenium) và Lưu 'BỘ LUẬT DỊCH' trước khi bắt đầu.")
            return
        if self.is_translating:
            self.log("[HỆ THỐNG] Đang chạy tác vụ dịch khác. Vui lòng ấn Dừng trước khi thao tác.")
            return

        self.is_translating = True
        self.btn_dung.setEnabled(True)
        threading.Thread(target=self.run_empty_lines_translation, daemon=True).start()

    def run_empty_lines_translation(self):
        empty_indices = [i for i, item in enumerate(self.srt_entries) if not item.get('translated', '').strip()]

        if not empty_indices:
            self.log("[HỆ THỐNG] Tuyệt vời! Không tìm thấy dòng trống nào cần dịch lại.")
            self.is_translating = False
            self.btn_dung.setEnabled(False if not self.is_generating_audio else True)
            return

        chunk_size = max(1, self.spin_dong.value())
        speed = self.combo_tocdo.currentText()
        if "Nhanh" in speed: delay = (1, 3)
        elif "An toàn" in speed or "Anti Bot" in speed: delay = (10, 20)
        elif "Rất nhanh" in speed: delay = (0.5, 1.5)
        else: delay = (3, 7)

        self.log(f"[HỆ THỐNG] Đã quét thấy {len(empty_indices)} dòng trống. Bắt đầu tiến hành dịch bù...")

        for i in range(0, len(empty_indices), chunk_size):
            if not self.is_translating:
                break
            
            current_indices = empty_indices[i:i + chunk_size]
            chunk = [self.srt_entries[idx] for idx in current_indices]

            opts = ""
            if self.chk_bodaucau.isChecked(): opts += "- Bỏ dấu câu.\n"
            if self.chk_ngangon.isChecked(): opts += "- Ngắn gọn.\n"
            if self.chk_longtieng.isChecked(): opts += "- Thêm [nam]/[nữ] lồng tiếng.\n"
            if self.chk_themcham.isChecked(): opts += "- Thêm dấu '...'\n"
            if self.chk_fix1tu.isChecked(): opts += "- XỬ LÝ CÂU 1 TỪ: Nếu dịch ra 1 chữ, BẮT BUỘC thêm từ đệm (đâu, thôi, rồi, ạ, hả, cơ, chứ, đây...) để thành 2-3 chữ.\n"

            data_string = "\n".join([f"[{item.get('id','')}] {item.get('original','')}" for item in chunk])
            
            prompt = f"""Dịch {len(chunk)} dòng sang TIẾNG VIỆT (BẮT BUỘC DỊCH TOÀN BỘ).
Áp dụng nghiêm ngặt BỘ LUẬT DỊCH:
{self.translation_rule}
YÊU CẦU: Giữ nguyên ID [số]. Trả về Code Block.
{opts}
DỮ LIỆU:
{data_string}"""
            
            if not self.wait_for_ready_state(timeout=300):
                self.log("[LOI] Gemini chua san sang - dung he thong de tranh huy prompt.")
                self.is_translating = False
                break

            self.log(f"[TIẾN ĐỘ] Đang gửi chunk gồm {len(chunk)} dòng trống (bắt đầu từ ID {chunk[0].get('id','?')})...")
            self.send_to_gemini(prompt)

            response = self.get_gemini_response()
            
            if response:
                translated_dict = {}
                for line in response.split('\n'):
                    match = re.search(r'\[(\d+)\]\s*(.*)', line.strip())
                    if match:
                        translated_dict[match.group(1)] = match.group(2).strip()
                
                updated_count = 0
                for item in chunk:
                    if item.get('id','') in translated_dict:
                        item['translated'] = translated_dict[item['id']]
                        updated_count += 1
                self.signals.update_table.emit()
                
                delay_time = random.uniform(delay[0], delay[1])
                self.log(f"[TIẾN ĐỘ] ⏳ Chờ {int(delay_time)} giây...")
                for j in range(int(delay_time), 0, -1):
                    if not self.is_translating:
                        break
                    self.log_inplace(f"[TIẾN ĐỘ] ⏳ Chờ {j} giây...")
                    time.sleep(1)
            else:
                self.log(f"[LOI] Khong nhan duoc phan hoi. Dung de tranh gui chong.")
                self.wait_for_ready_state(timeout=300)
                self.is_translating = False
                break

        if self.is_translating:
            self.is_translating = False
            self.log("[HỆ THỐNG] ✅ Hoàn tất việc dịch bù các dòng trống!")
        
        self.btn_dung.setEnabled(False if not self.is_generating_audio else True)

    # ----------------- LỌC DÒNG CÒN TIẾNG TRUNG -----------------
    @staticmethod
    def has_chinese(text):
        for ch in text:
            cp = ord(ch)
            if (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or
                    0x20000 <= cp <= 0x2A6DF or 0xF900 <= cp <= 0xFAFF or
                    0x2F800 <= cp <= 0x2FA1F):
                return True
        return False

    def start_loc_trung_translation(self):
        if not self.driver or not self.translation_rule:
            QMessageBox.information(self, "Thông báo", "Vui lòng mở trình duyệt (Selenium) và Lưu 'BỘ LUẬT DỊCH' trước khi bắt đầu.")
            return
        if self.is_translating:
            self.log("[HỆ THỐNG] Đang chạy tác vụ dịch khác. Vui lòng ấn Dừng trước.")
            return
        self.is_translating = True
        self.btn_dung.setEnabled(True)
        threading.Thread(target=self.run_loc_trung_translation, daemon=True).start()

    def run_loc_trung_translation(self):
        chinese_indices = [
            i for i, item in enumerate(self.srt_entries)
            if item.get('translated', '').strip() and self.has_chinese(item.get('translated', ''))
        ]
        if not chinese_indices:
            self.log("[HỆ THỐNG] ✅ Không tìm thấy dòng nào còn sót tiếng Trung.")
            self.is_translating = False
            self.btn_dung.setEnabled(False if not self.is_generating_audio else True)
            return

        self.log(f"[LỌC TRUNG] 🔍 Tìm thấy {len(chinese_indices)} dòng còn sót tiếng Trung. Bắt đầu dịch lại...")
        chunk_size = max(1, self.spin_dong.value())
        speed = self.combo_tocdo.currentText()
        if "Nhanh" in speed:          delay = (1, 3)
        elif "An toàn" in speed or "Anti Bot" in speed: delay = (10, 20)
        elif "Rất nhanh" in speed:    delay = (0.5, 1.5)
        else:                          delay = (3, 7)

        for i in range(0, len(chinese_indices), chunk_size):
            if not self.is_translating:
                break
            current_indices = chinese_indices[i:i + chunk_size]
            chunk = [self.srt_entries[idx] for idx in current_indices]

            for item in chunk:
                self.log(f"[LỌC TRUNG] ⚠ ID {item.get('id','?')} | Lỗi: {item.get('translated','')}")

            opts = ""
            if self.chk_bodaucau.isChecked():  opts += "- Bỏ dấu câu.\n"
            if self.chk_ngangon.isChecked():   opts += "- Ngắn gọn.\n"
            if self.chk_longtieng.isChecked(): opts += "- Thêm [nam]/[nữ] lồng tiếng.\n"
            if self.chk_themcham.isChecked():  opts += "- Thêm dấu '...'\n"
            if self.chk_fix1tu.isChecked():    opts += "- XỬ LÝ CÂU 1 TỪ: Nếu dịch ra 1 chữ, BẮT BUỘC thêm từ đệm.\n"

            data_string = "\n".join([f"[{item.get('id','')}] {item.get('original','')}" for item in chunk])
            prompt = f"""Dịch {len(chunk)} dòng sang TIẾNG VIỆT (BẮT BUỘC DỊCH TOÀN BỘ).
Áp dụng nghiêm ngặt BỘ LUẬT DỊCH:
{self.translation_rule}
YÊU CẦU: Giữ nguyên ID [số]. Trả về Code Block.
QUAN TRỌNG: Kết quả TUYỆT ĐỐI KHÔNG được chứa ký tự tiếng Trung (Hán tự).
{opts}
DỮ LIỆU:
{data_string}"""

            if not self.wait_for_ready_state(timeout=300):
                self.log("[LỖI] Gemini chưa sẵn sàng - dừng.")
                self.is_translating = False
                break

            self.log(f"[LỌC TRUNG] Đang gửi {len(chunk)} dòng (ID {chunk[0].get('id','?')})...")
            self.send_to_gemini(prompt)
            response = self.get_gemini_response()

            if response:
                translated_dict = {}
                for line in response.split('\n'):
                    match = re.search(r'\[(\d+)\]\s*(.*)', line.strip())
                    if match:
                        translated_dict[match.group(1)] = match.group(2).strip()
                updated_count = 0
                for item in chunk:
                    if item.get('id', '') in translated_dict:
                        new_val = translated_dict[item['id']]
                        item['translated'] = new_val
                        updated_count += 1
                        if self.has_chinese(new_val):
                            self.log(f"[LỌC TRUNG] ⚠ ID {item.get('id','?')} vẫn còn tiếng Trung: {new_val}")
                self.signals.update_table.emit()
                self.log(f"[LỌC TRUNG] ✅ Dịch lại xong {updated_count}/{len(chunk)} dòng.")
                delay_time = random.uniform(delay[0], delay[1])
                self.log(f"[TIẾN ĐỘ] ⏳ Chờ {int(delay_time)} giây...")
                for j in range(int(delay_time), 0, -1):
                    if not self.is_translating: break
                    self.log_inplace(f"[TIẾN ĐỘ] ⏳ Chờ {j} giây...")
                    time.sleep(1)
            else:
                self.log("[LỖI] Không nhận được phản hồi. Dừng.")
                self.wait_for_ready_state(timeout=300)
                self.is_translating = False
                break

        if self.is_translating:
            self.is_translating = False
            self.log("[HỆ THỐNG] ✅ Hoàn tất lọc & dịch lại các dòng còn tiếng Trung!")
        self.btn_dung.setEnabled(False if not self.is_generating_audio else True)

    # ----------------- Browser initialisation and sending prompts -----------------
    def start_browser_thread(self):
        if self.driver:
            self.log("[TRÌNH DUYỆT] Đã có driver Selenium.")
            return
        threading.Thread(target=self.init_browser, daemon=True).start()

    def init_browser(self):
        self.log("[TRÌNH DUYỆT] Đang mở Chrome (Selenium)...")
        try:
            current_dir = Path().absolute()
            profile_path = str(current_dir / "ChromeProfile")
            options = webdriver.ChromeOptions()
            options.add_argument(f"--user-data-dir={profile_path}")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            self.driver = webdriver.Chrome(options=options)
            self.driver.get('https://gemini.google.com/app')
            self.log("[TRÌNH DUYỆT] Sẵn sàng!")
        except Exception as e:
            self.log(f"[LỖI] {e}")

    def send_to_gemini(self, prompt_text):
        if not self.driver:
            return False
        try:
            input_element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//rich-textarea//p'))
            )
            input_element.send_keys(Keys.CONTROL + "a")
            input_element.send_keys(Keys.BACKSPACE)
            self.driver.execute_script("arguments[0].textContent = arguments[1];", input_element, prompt_text)
            input_element.send_keys(Keys.SPACE)
            time.sleep(0.5)
            input_element.send_keys(Keys.ENTER)
            return True
        except Exception as e:
            self.log(f"[LỖI GỬI] {e}")
            return False

    def get_gemini_response(self, timeout=600):
        if not self.driver:
            return None

        start_time = time.time()
        last_text = ""
        stable_counter = 0
        stop_clear_cycles = 0

        mic_xpath = "//speech-dictation-mic-button//button"
        response_xpath = "//model-response//structured-content-container/div"
        stop_xpath = "//button[contains(@aria-label, 'Stop') or contains(@aria-label, 'D\u1eebng') or contains(@aria-label, 'stop generating')]"

        while time.time() - start_time < timeout:
            try:
                response_elements = self.driver.find_elements(By.XPATH, response_xpath)
                if not response_elements:
                    time.sleep(1)
                    continue
                current_text = response_elements[-1].get_attribute('innerText').strip()

                stop_buttons = self.driver.find_elements(By.XPATH, stop_xpath)
                if stop_buttons:
                    stop_clear_cycles = 0
                    stable_counter = 0
                    last_text = current_text
                    time.sleep(0.8)
                    continue
                else:
                    stop_clear_cycles += 1

                mic_buttons = self.driver.find_elements(By.XPATH, mic_xpath)

                if mic_buttons:
                    if current_text == last_text:
                        stable_counter += 1
                    else:
                        stable_counter = 0
                    last_text = current_text

                    if stable_counter >= 5 and stop_clear_cycles >= 4:
                        return current_text
                else:
                    stable_counter = 0
            except Exception:
                pass
            time.sleep(0.8)
        return None

    def wait_for_ready_state(self, timeout=300):
        if not self.driver:
            return False

        mic_xpath = "//speech-dictation-mic-button//button"
        stop_xpath = "//button[contains(@aria-label, 'Stop') or contains(@aria-label, 'D\u1eebng') or contains(@aria-label, 'stop generating')]"
        start = time.time()

        while time.time() - start < timeout:
            try:
                if self.driver.find_elements(By.XPATH, stop_xpath):
                    time.sleep(0.8)
                    continue

                mic_buttons = self.driver.find_elements(By.XPATH, mic_xpath)
                if mic_buttons:
                    btn = mic_buttons[-1]
                    disabled = btn.get_attribute("aria-disabled") == "true" or not btn.is_enabled()
                    if btn.is_displayed() and not disabled:
                        return True
            except Exception:
                pass
            time.sleep(0.8)
        return False

    # ----------------- Analysis dialog -----------------
    def show_analysis_dialog(self):
        if not self.driver or not self.srt_entries:
            QMessageBox.information(self, "Thông báo", "Vui lòng mở trình duyệt (Selenium) và tải SRT trước khi phân tích.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle('Phân Tích & Ngữ Cảnh')
        dlg.resize(800, 600)
        layout = QVBoxLayout(dlg)

        top = QHBoxLayout()
        chk_all = QCheckBox('Toàn bộ')
        spin = QSpinBox()
        spin.setRange(1, 10000)
        spin.setValue(100)
        top.addWidget(QLabel('Gửi phân tích:'))
        top.addWidget(chk_all)
        top.addWidget(spin)
        btn_send = QPushButton('➤ Phân Tích')
        top.addWidget(btn_send)
        layout.addLayout(top)

        preview = QTextEdit()
        preview.setStyleSheet('background-color: #2b2b2b; color: white;')
        layout.addWidget(preview)

        btn_save = QPushButton('💾 LƯU CẤU HÌNH DỊCH (BẮT BUỘC)')
        layout.addWidget(btn_save)

        def run_analysis():
            lines = len(self.srt_entries) if chk_all.isChecked() else spin.value()
            content = "\n".join([item['original'] for item in self.srt_entries[:lines]])
            prompt = f"""Dựa vào nội dung phim:
{content}
Hãy đóng vai chuyên gia ngôn ngữ, soạn thảo một 'BỘ LUẬT DỊCH THUẬT' chi tiết trong Code Block:
1. Xác định Thể loại & Thời đại (Cổ trang/Hiện đại/Học đường...).
2. Bảng Xưng hô (Bắt buộc dùng: ...).
3. Bảng Từ vựng BẮT BUỘC DÙNG (Ví dụ Cổ trang: 'Đa tạ', 'Huynh/Đệ').
4. Bảng Từ vựng CẤM TUYỆT ĐỐI (Ví dụ Cổ trang cấm: 'Ok', 'Bye', 'Anh/Em').
5. TIẾNG KHÁC NGOÀI TIẾNG TRUNG (TIẾNG ANH, ETC) THÌ BẮT BUỘC PHIÊN ÂM RA TIẾNG VIỆT ĐỌC ĐƯỢC. VÍ DỤ: 'I LOVE YOU' -> 'AI LỚP - DIU'.
6. DỊCH HAY, BÁM SÁT - NGHIÊM CẤM CHẾ TỪ LINH TINH.
7. Nếu có những từ '哈' thì dịch thành 'ha ha!', nhiều chữ thì tối đa 2 chữ 'ha ha!'.
8. Nếu có những từ '啊' thì dịch thành 'á á'.
9. Từ '哎' (Ai) bắt buộc phải dịch ra thành 'Ây da', 'Haizz', 'Ôi' hoặc từ cảm thán phù hợp.
10. CHỮ IN HOA: TUYỆT ĐỐI không sử dụng chữ in hoa trong bản dịch. Bất kể tên riêng, tên nhân vật, địa danh, danh từ hay bất kỳ từ nào cũng phải viết bằng chữ in thường. Ví dụ: 'việt nam', 'hà nội', 'nguyễn văn a' - không bao giờ viết 'Việt Nam', 'Hà Nội', 'Nguyễn Văn A'."""
            preview.setText("Đang gửi cho Gemini...")
            threading.Thread(target=self._worker_analysis, args=(prompt, preview), daemon=True).start()

        def on_analysis_done(txt):
            preview.setText(txt)

        self.signals.analysis_done.connect(on_analysis_done)

        def save_rule():
            self.translation_rule = preview.toPlainText().strip()
            confirm = f"HÃY GHI NHỚ BỘ LUẬT SAU ĐỂ DỊCH TOÀN BỘ PHIM:\n{self.translation_rule}\nTrả lời 'ĐÃ RÕ'."
            threading.Thread(target=self.send_to_gemini, args=(confirm,), daemon=True).start()
            QMessageBox.information(dlg, "Thành công", "Đã lưu Luật!")
            dlg.accept()

        btn_send.clicked.connect(run_analysis)
        btn_save.clicked.connect(save_rule)
        dlg.exec_()

    def _worker_analysis(self, prompt, preview_widget=None):
        self.send_to_gemini(prompt)
        time.sleep(2)
        res = self.get_gemini_response()
        self.signals.analysis_done.emit(res if res else "Lỗi.")

    # ----------------- Batch translation -----------------
    def start_translation_thread(self):
        if not self.driver or not self.translation_rule:
            QMessageBox.information(self, "Thông báo", "Vui lòng mở trình duyệt (Selenium) và Lưu 'BỘ LUẬT DỊCH' trước khi bắt đầu.")
            return
        if self.is_translating:
            self.log("[HỆ THỐNG] Đang chạy rồi.")
            return

        if self.chk_send_context.isChecked():
            confirm = f"HÃY GHI NHỚ BỘ LUẬT SAU ĐỂ DỊCH TOÀN BỘ PHIM:\n{self.translation_rule}\nTrả lời 'ĐÃ RÕ'."
            threading.Thread(target=self.send_to_gemini, args=(confirm,), daemon=True).start()
            time.sleep(1)

        self.is_translating = True
        self.btn_dung.setEnabled(True)
        threading.Thread(target=self.run_batch_translation, daemon=True).start()

    def run_batch_translation(self):
        chunk_size = max(1, self.spin_dong.value())
        speed = self.combo_tocdo.currentText()
        if "Nhanh" in speed: delay = (1, 3)
        elif "An toàn" in speed or "Anti Bot" in speed: delay = (10, 20)
        elif "Rất nhanh" in speed: delay = (0.5, 1.5)
        else: delay = (3, 7)

        for i in range(0, len(self.srt_entries), chunk_size):
            if not self.is_translating:
                break
            chunk = self.srt_entries[i:i + chunk_size]
            if all(item.get('translated','').strip() != '' for item in chunk):
                continue

            opts = ""
            if self.chk_bodaucau.isChecked(): opts += "- Bỏ dấu câu.\n"
            if self.chk_ngangon.isChecked(): opts += "- Ngắn gọn.\n"
            if self.chk_longtieng.isChecked(): opts += "- Thêm [nam]/[nữ] lồng tiếng.\n"
            if self.chk_themcham.isChecked(): opts += "- Thêm dấu '...'\n"
            if self.chk_fix1tu.isChecked(): opts += "- XỬ LÝ CÂU 1 TỪ: Nếu dịch ra 1 chữ, BẮT BUỘC thêm từ đệm (đâu, thôi, rồi, ạ, hả, cơ, chứ, đây...) để thành 2-3 chữ.\n"

            data_string = "\n".join([f"[{item.get('id','')}] {item.get('original','')}" for item in chunk])
            prompt = f"""Dịch {len(chunk)} dòng sang TIẾNG VIỆT (BẮT BUỘC DỊCH TOÀN BỘ).
Áp dụng nghiêm ngặt BỘ LUẬT DỊCH:
{self.translation_rule}
YÊU CẦU: Giữ nguyên ID [số]. Trả về Code Block.
{opts}
DỮ LIỆU:
{data_string}"""
            
            if not self.wait_for_ready_state(timeout=300):
                self.log("[LOI] Gemini chua san sang - dung batch de tranh huy prompt.")
                self.is_translating = False
                break

            self.log(f"[TIẾN ĐỘ] Đang gửi chunk {chunk[0].get('id','?')}...")
            self.send_to_gemini(prompt)

            response = self.get_gemini_response()
            
            if response:
                translated_dict = {}
                for line in response.split('\n'):
                    match = re.search(r'\[(\d+)\]\s*(.*)', line.strip())
                    if match:
                        translated_dict[match.group(1)] = match.group(2).strip()
                
                for item in chunk:
                    if item.get('id','') in translated_dict:
                        item['translated'] = translated_dict[item['id']]
                self.signals.update_table.emit()
                
                delay_time = random.uniform(delay[0], delay[1])
                self.log(f"[TIẾN ĐỘ] ⏳ Chờ {int(delay_time)} giây...")
                for j in range(int(delay_time), 0, -1):
                    if not self.is_translating:
                        break
                    self.log_inplace(f"[TIẾN ĐỘ] ⏳ Chờ {j} giây...")
                    time.sleep(1)
            else:
                self.log(f"[LOI] Khong nhan duoc phan hoi cho chunk {chunk[0].get('id','?')}. Dung de tranh gui chong.")
                self.wait_for_ready_state(timeout=300)
                self.is_translating = False
                break

        if self.is_translating:
            self.is_translating = False
            self.log("[HỆ THỐNG] ✅ Xong toàn bộ Dịch Thuật!")
            
        self.btn_dung.setEnabled(False if not self.is_generating_audio else True)

# --------------- Run application ---------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    ex = AIStudioApp()
    ex.show()
    sys.exit(app.exec_())
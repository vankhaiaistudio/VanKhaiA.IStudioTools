"""
guide.py — Cửa sổ Hướng Dẫn Sử Dụng
Văn Khải A.I Studio — PRO VERSION
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QTabWidget, QTextBrowser
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


def show_guide(parent=None):
    dlg = GuideDialog(parent)
    dlg.exec_()


class GuideDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("❓ Hướng Dẫn Sử Dụng — Văn Khải A.I Studio")
        self.resize(900, 680)
        self.setMinimumSize(700, 500)
        self._build_ui()

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(10, 10, 10, 10)

        # Header
        hdr = QLabel("📖  HƯỚNG DẪN SỬ DỤNG — VĂN KHẢI A.I STUDIO")
        hdr.setFont(QFont("Arial", 14, QFont.Bold))
        hdr.setStyleSheet("color: #004d99; padding: 6px 0;")
        hdr.setAlignment(Qt.AlignCenter)
        main.addWidget(hdr)

        line = QFrame(); line.setFrameShape(QFrame.HLine)
        main.addWidget(line)

        # Tab widget
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabBar::tab { padding: 6px 14px; font-weight: bold; }
            QTabBar::tab:selected { background: #004d99; color: white; border-radius: 4px 4px 0 0; }
        """)

        tabs.addTab(self._tab_tongquan(),    "🏠 Tổng Quan")
        tabs.addTab(self._tab_buoc1(),       "1️⃣  Bước 1 — Tải & Phân tích")
        tabs.addTab(self._tab_buoc2(),       "2️⃣  Bước 2 — Dịch Thuật")
        tabs.addTab(self._tab_buoc3(),       "3️⃣  Bước 3 — Tạo Audio")
        tabs.addTab(self._tab_ghep(),        "🎬 Ghép Audio")
        tabs.addTab(self._tab_batch(),       "📚 Batch TTS")
        tabs.addTab(self._tab_tips(),        "💡 Mẹo & Lỗi Thường Gặp")

        main.addWidget(tabs)

        # Close button
        btn_close = QPushButton("✖  Đóng")
        btn_close.setStyleSheet(
            "background-color: #dc3545; color: white; font-weight: bold;"
            "padding: 8px 30px; border-radius: 4px;"
        )
        btn_close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn_close)
        main.addLayout(row)

    # ─────────────────── helpers ───────────────────
    @staticmethod
    def _browser(html: str) -> QScrollArea:
        """Trả về QScrollArea chứa QTextBrowser với nội dung HTML."""
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setStyleSheet("font-size: 13px; line-height: 1.6;")
        tb.setHtml(html)
        return tb

    @staticmethod
    def _h(text, color="#004d99", size=13):
        return f'<h3 style="color:{color};margin-bottom:4px;font-size:{size}px">{text}</h3>'

    @staticmethod
    def _p(text):
        return f'<p style="margin:4px 0 8px 0">{text}</p>'

    @staticmethod
    def _ul(items):
        lis = "".join(f"<li>{i}</li>" for i in items)
        return f'<ul style="margin:4px 0 8px 16px">{lis}</ul>'

    @staticmethod
    def _note(text):
        return (f'<div style="background:#fff3cd;border-left:4px solid #ffc107;'
                f'padding:8px 12px;margin:8px 0;border-radius:0 4px 4px 0">'
                f'⚠️  {text}</div>')

    @staticmethod
    def _tip(text):
        return (f'<div style="background:#d4edda;border-left:4px solid #28a745;'
                f'padding:8px 12px;margin:8px 0;border-radius:0 4px 4px 0">'
                f'✅  {text}</div>')

    @staticmethod
    def _code(text):
        return (f'<div style="background:#2b2b2b;color:#f8f8f2;font-family:monospace;'
                f'padding:8px 12px;margin:6px 0;border-radius:4px;font-size:12px">'
                f'{text}</div>')

    # ─────────────────── tabs ───────────────────
    def _tab_tongquan(self):
        H, P, UL, NOTE, TIP = self._h, self._p, self._ul, self._note, self._tip
        html = f"""
        {H("Giới Thiệu")}
        {P("Văn Khải A.I Studio là công cụ hỗ trợ <b>dịch phụ đề phim Trung → Việt</b> và "
           "<b>tạo giọng đọc (TTS)</b> bằng AI, chạy hoàn toàn trên máy tính cục bộ.")}

        {H("Luồng Làm Việc Cơ Bản")}
        {UL([
            "① Tải file <b>.srt</b> (phụ đề gốc tiếng Trung)",
            "② Mở trình duyệt Chrome (Selenium) → đăng nhập Gemini",
            "③ Chạy <b>Phân tích</b> → Lưu Bộ Luật Dịch",
            "④ Nhấn <b>BẮT ĐẦU DỊCH</b> — AI dịch hàng loạt",
            "⑤ Xuất SRT đã dịch <i>hoặc</i> tạo Audio (Piper TTS)",
            "⑥ Ghép audio thành 1 file hoàn chỉnh",
        ])}

        {H("Các Khu Vực Chính Trên Giao Diện")}
        {UL([
            "<b>Thanh trên:</b> Dự Án | File SRT | Nối Gap | Trình Duyệt",
            "<b>Bảng trái:</b> Danh sách phụ đề (ID, Time, Gốc, Dịch, Audio)",
            "<b>Bảng phải:</b> Ngữ cảnh | Dịch Thuật | Cấu hình TTS | Log",
        ])}

        {NOTE("Cần <b>Google Chrome</b> và <b>ChromeDriver</b> tương thích phiên bản Chrome đang dùng.")}
        {TIP("Lưu Dự Án (.vkproj) thường xuyên để không mất tiến độ.")}
        """
        return self._browser(html)

    def _tab_buoc1(self):
        H, P, UL, NOTE, TIP, CODE = self._h, self._p, self._ul, self._note, self._tip, self._code
        html = f"""
        {H("1. Tải File SRT")}
        {P("Nhấn <b>📂 Tải SRT</b> → chọn file <code>.srt</code> tiếng Trung.")}
        {UL([
            "Bảng sẽ hiển thị: ID | Time (<code>00:00:00,666 --> 00:00:02,000  ⏱ 1.33s</code>) | Gốc | Dịch",
            "Cột <b>Time</b> tự tính thời lượng phụ đề từ time-in và time-out",
            "Cột <b>Dịch</b> ban đầu trống — sẽ được điền sau khi dịch",
        ])}

        {H("2. Nối Gap Phụ Đề (tuỳ chọn)")}
        {P("Dùng khi các dòng phụ đề bị cắt rời, không liền nhau:")}
        {UL([
            "Nhập giá trị <b>Gap (ms)</b>: dương = tạo khoảng cách, âm = cho chồng lên nhau",
            "Nhấn <b>⚡ Xuất & Tải Lại</b> → xuất file <code>_noigap.srt</code> rồi tự load lại",
        ])}

        {H("3. Mở Trình Duyệt Chrome")}
        {P("Nhấn <b>🚀 MỞ</b> trong nhóm <i>Trình Duyệt</i>.")}
        {UL([
            "Chrome sẽ mở với profile riêng (<code>ChromeProfile/</code>)",
            "Lần đầu: đăng nhập tài khoản Google → vào <code>gemini.google.com</code>",
            "Từ lần sau Chrome tự nhớ đăng nhập",
        ])}
        {NOTE("KHÔNG đóng cửa sổ Chrome trong khi đang dịch.")}

        {H("4. Phân Tích & Tạo Bộ Luật Dịch")}
        {P("Nhấn <b>🔍 Phân tích & Gợi ý dịch</b>:")}
        {UL([
            "Chọn số dòng mẫu hoặc tick <b>Toàn bộ</b>",
            "Nhấn <b>➤ Phân Tích</b> → AI phân tích thể loại, xưng hô, từ vựng",
            "<b>BẮT BUỘC</b> nhấn <b>💾 LƯU CẤU HÌNH DỊCH</b> trước khi thoát",
        ])}
        {TIP("Bộ luật càng chi tiết, bản dịch càng chuẩn và nhất quán.")}
        """
        return self._browser(html)

    def _tab_buoc2(self):
        H, P, UL, NOTE, TIP = self._h, self._p, self._ul, self._note, self._tip
        html = f"""
        {H("Các Nút Dịch")}
        {UL([
            "<b>🚀 BẮT ĐẦU DỊCH</b> — dịch toàn bộ file, bỏ qua dòng đã có bản dịch",
            "<b>✍ Dịch dòng chọn</b> — tick checkbox ✔ ở các dòng muốn dịch lại → nhấn nút",
            "<b>⚡ Dịch bù dòng trống</b> — chỉ dịch những dòng cột Dịch còn trống",
            "<b>CN Lọc dòng còn tiếng Trung</b> — phát hiện & dịch lại dòng có Hán tự sót",
        ])}

        {H("Cài Đặt Dịch")}
        {UL([
            "<b>Gửi X dòng</b>: số dòng mỗi lần gửi (khuyến nghị 15–25)",
            "<b>Bỏ dấu câu</b>: loại bỏ dấu chấm, phẩy trong bản dịch",
            "<b>Dịch Ngắn Gọn</b>: AI cô đọng câu ngắn hơn",
            "<b>Lồng tiếng</b>: thêm <code>[nam]</code>/<code>[nữ]</code> trước câu",
            "<b>Thêm '...'</b>: thêm dấu chấm lửng vào câu bỏ lửng",
            "<b>Nói câu 1 chữ</b>: thêm từ đệm tránh câu quá ngắn",
            "<b>Gửi lại Context</b>: gửi lại Bộ Luật Dịch mỗi khi bắt đầu",
        ])}

        {H("Tốc Độ Gửi")}
        {UL([
            "<b>Bình thường (3-7s)</b>: an toàn, dùng hàng ngày",
            "<b>Nhanh (1-3s)</b>: dùng khi Gemini đang ổn định",
            "<b>Rất nhanh</b>: dễ bị rate-limit",
            "<b>An toàn/Anti Bot (10-20s)</b>: dùng khi bị lỗi liên tục",
        ])}

        {NOTE("Nhấn <b>⏹ Dừng</b> để dừng giữa chừng — dữ liệu đã dịch được giữ nguyên.")}

        {H("Xuất File SRT")}
        {P("Nhấn <b>💾 Xuất SRT</b> → chọn nơi lưu → file <code>.srt</code> chỉ chứa bản dịch tiếng Việt.")}
        """
        return self._browser(html)

    def _tab_buoc3(self):
        H, P, UL, NOTE, TIP, CODE = self._h, self._p, self._ul, self._note, self._tip, self._code
        html = f"""
        {H("Yêu Cầu")}
        {UL([
            "Tải <b>Piper TTS</b> (Windows): <code>piper.exe</code> + model <code>.onnx</code> + file <code>.onnx.json</code>",
            "Đặt file <code>.onnx</code> và <code>.onnx.json</code> <b>cùng thư mục</b>",
        ])}

        {H("Cấu Hình (Mục 4)")}
        {UL([
            "Nhấn <b>📂 File .exe</b> → chọn <code>piper.exe</code>",
            "Nhấn <b>📂 Model</b> → chọn file <code>.onnx</code>",
            "Điều chỉnh <b>Tốc độ đọc</b>: < 1.0 = nhanh | 1.0 = bình thường | > 1.0 = chậm",
            "Nhấn <b>💾 Lưu Cấu Hình Mặc Định</b> để ghi nhớ",
        ])}

        {H("Tạo Audio")}
        {UL([
            "<b>Nút Tạo (từng dòng)</b>: tạo audio cho 1 dòng ngay trong bảng",
            "<b>🎧 TẠO AUDIO HÀNG LOẠT</b>: tạo toàn bộ dòng đã có bản dịch",
            "Audio lưu vào thư mục <code>audio_output/audio_[ID].wav</code>",
            "Nút <b>▶</b> màu xanh = file đã tồn tại → nhấn để nghe thử",
        ])}

        {TIP("Mỗi dòng phụ đề → 1 file <code>.wav</code> riêng. File cũ sẽ bị ghi đè khi tạo lại.")}
        {NOTE("Cột <b>Dịch</b> phải có nội dung thì mới tạo được audio.")}
        """
        return self._browser(html)

    def _tab_ghep(self):
        H, P, UL, NOTE, TIP = self._h, self._p, self._ul, self._note, self._tip
        html = f"""
        {H("3 Chế Độ Ghép Audio")}

        {H("① Ghép Nối Tiếp Nhau → merged_noitieip.wav", color="#28a745", size=12)}
        {P("Ghép tất cả file audio lại theo thứ tự ID, không có khoảng lặng giữa các đoạn.")}
        {UL([
            "Dùng khi: cần 1 file audio liên tục để nghe thử toàn bộ bản dịch",
            "Chọn <b>Ghép Nối Tiếp Nhau</b> → nhấn <b>🎬 TẠO FILE GHÉP</b>",
        ])}

        {H("② Ghép Chuẩn Timeline → merged_timeline.wav", color="#17a2b8", size=12)}
        {P("Đặt từng audio đúng vị trí <code>start_ms</code> của SRT. Giọng nói có thể đè lên nhau "
           "nếu audio dài hơn khoảng trống.")}
        {UL([
            "Dùng khi: cần sync sơ bộ với video gốc",
            "Chọn <b>Ghép Chuẩn Timeline</b> → nhấn <b>🎬 TẠO FILE GHÉP</b>",
        ])}

        {H("③ Xuất Chuẩn Timeline (Không Đè Giọng) → merged_nokede.wav", color="#2196F3", size=12)}
        {P("Tính năng nâng cao nhất:")}
        {UL([
            "<b>Audio dài hơn duration SRT</b> → tự động <b>tăng tốc</b> (resample) cho vừa khít",
            "<b>Audio ngắn hơn duration SRT</b> → giữ nguyên + <b>thêm im lặng</b> phần thiếu",
            "Sau đó đặt vào đúng vị trí <code>start_ms</code> — <b>không bao giờ đè lên nhau</b>",
            "Nhấn <b>⏱ XUẤT CHUẨN TIMELINE</b>",
        ])}

        {TIP("Cần cài <code>numpy</code> để dùng tính năng này: <code>pip install numpy</code>")}
        {NOTE("Chỉ hỗ trợ file WAV cùng sample rate. Nếu khác rate, file đầu tiên được dùng làm chuẩn.")}
        """
        return self._browser(html)

    def _tab_batch(self):
        H, P, UL, NOTE, TIP = self._h, self._p, self._ul, self._note, self._tip
        html = f"""
        {H("📚 Batch TTS — Lồng Tiếng File TXT / SRT")}
        {P("Nhấn nút <b>📚 BATCH</b> trên thanh Trình Duyệt để mở cửa sổ Batch TTS.")}

        {H("Hỗ Trợ 2 Loại File")}
        {UL([
            "<b>File TXT</b>: văn bản thuần tuý, mỗi dòng / đoạn là 1 nội dung đọc",
            "<b>File SRT</b>: tự động <b>bỏ toàn bộ timestamp & mốc thời gian</b>, "
            "chỉ giữ lại nội dung phụ đề → ghép thành văn bản liên tục",
        ])}

        {H("Quy Trình Sử Dụng")}
        {UL([
            "① Nhấn <b>📂 Tải File TXT / SRT</b> → nội dung hiển thị trong ô bên trái",
            "② Chỉnh sửa nội dung nếu cần trong ô hiển thị",
            "③ Nhấn <b>⚙ Xử Lý Văn Bản</b> → tự động chia đoạn theo câu/độ dài",
            "④ Xem danh sách đoạn đã chia ở bảng bên phải",
            "⑤ Chọn <b>Piper.exe</b> và <b>Model .onnx</b> (hoặc dùng cấu hình đã lưu)",
            "⑥ Nhấn <b>🎙 LỒNG TIẾNG</b> → Piper đọc từng đoạn → ghép lại 1 file",
            "⑦ Nhấn <b>▶ Nghe</b> để kiểm tra file ghép cuối cùng",
        ])}

        {H("Xử Lý Văn Bản")}
        {UL([
            "Tự chia theo <b>dấu câu</b> (. ! ?) hoặc <b>độ dài tối đa</b> mỗi đoạn",
            "Có thể chỉnh thủ công trong bảng trước khi lồng tiếng",
            "Đoạn trống sẽ tự động tạo khoảng lặng tương ứng",
        ])}

        {TIP("File SRT không cần dịch trước — Batch TTS đọc luôn nội dung trong file SRT gốc hoặc đã dịch.")}
        {NOTE("Cần cấu hình đường dẫn <b>piper.exe</b> và <b>model .onnx</b> trước khi lồng tiếng.")}
        """
        return self._browser(html)

    def _tab_tips(self):
        H, P, UL, NOTE, TIP, CODE = self._h, self._p, self._ul, self._note, self._tip, self._code
        html = f"""
        {H("💡 Mẹo Sử Dụng Hiệu Quả")}
        {UL([
            "Gửi <b>15–20 dòng</b> mỗi lần để tránh Gemini timeout",
            "Tick <b>Gửi lại Context</b> khi bắt đầu phiên dịch mới",
            "Dùng <b>Dịch bù dòng trống</b> sau khi dịch toàn bộ để bù những dòng bị bỏ sót",
            "Dùng <b>CN Lọc tiếng Trung</b> để tự động phát hiện & dịch lại dòng còn Hán tự",
            "Tốc độ <b>0.85–0.95x</b> thường cho giọng đọc tự nhiên nhất",
            "Lưu dự án <code>.vkproj</code> để giữ toàn bộ bản dịch + cấu hình",
        ])}

        {H("🔴 Lỗi Thường Gặp & Cách Xử Lý")}

        {H("Lỗi: Chrome không mở được", color="#dc3545", size=12)}
        {UL([
            "Kiểm tra ChromeDriver đúng phiên bản Chrome đang dùng",
            "Tải tại: <a href='https://chromedriver.chromium.org'>chromedriver.chromium.org</a>",
            "Đặt <code>chromedriver.exe</code> cùng thư mục với <code>appgui_4.py</code>",
        ])}

        {H("Lỗi: Gemini không phản hồi / timeout", color="#dc3545", size=12)}
        {UL([
            "Kiểm tra kết nối internet",
            "Tải lại trang Gemini thủ công trong cửa sổ Chrome đang mở",
            "Chuyển sang tốc độ <b>An toàn/Anti Bot</b>",
            "Giảm số dòng mỗi lần gửi xuống 10–15",
        ])}

        {H("Lỗi: Piper không tạo được audio", color="#dc3545", size=12)}
        {UL([
            "Kiểm tra đường dẫn <code>piper.exe</code> đúng chưa",
            "File <code>.onnx</code> và <code>.onnx.json</code> phải cùng thư mục",
            "Thử chạy <code>piper.exe</code> thủ công trong CMD để xem lỗi",
        ])}

        {H("Lỗi: Ghép audio bị im lặng đầu file", color="#dc3545", size=12)}
        {UL([
            "Dùng chế độ <b>Ghép Nối Tiếp</b> thay vì Timeline nếu không cần sync",
            "Kiểm tra SRT có timestamp hợp lệ không",
        ])}

        {TIP("Sau khi cập nhật app, xoá thư mục <code>ChromeProfile/</code> nếu Chrome bị lỗi khởi động.")}

        {H("📞 Phím Tắt Nhanh")}
        {UL([
            "<b>Ctrl+Click</b> ô Dịch → chỉnh sửa trực tiếp",
            "Tick ✔ nhiều dòng → <b>Dịch dòng chọn</b> để dịch lại cùng lúc",
            "Combo trang bên góc phải bảng → nhảy nhanh đến trang cần xem",
        ])}
        """
        return self._browser(html)

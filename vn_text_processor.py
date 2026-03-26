"""
vn_text_processor.py
====================
Port Python của engine tiền xử lý văn bản tiếng Việt từ tts-worker JS.
Dùng trước khi đưa văn bản vào Piper TTS để đảm bảo đọc đúng:
  - Số → chữ              (250 → "hai trăm năm mươi")
  - Ngày tháng            (15/3/2025 → "ngày mười lăm tháng ba năm hai nghìn không trăm hai mươi lăm")
  - Giờ                   (8h30 → "tám giờ ba mươi phút")
  - Tiền tệ               (250.000đ → "hai trăm năm mươi nghìn đồng")
  - Phần trăm             (12% → "mười hai phần trăm")
  - Đơn vị đo lường       (5km → "năm ki-lô-mét")
  - Số điện thoại         (0912345678 → đọc từng số)
  - Phiên âm tiếng Anh    (love → "lớp")
  - Dọn dẹp ký tự lạ / emoji / URL / email
"""

import re
import unicodedata

# ══════════════════════════════════════════════════════════
# 1. SỐ → CHỮ TIẾNG VIỆT
# ══════════════════════════════════════════════════════════

_ONES = {
    '0':'không','1':'một','2':'hai','3':'ba','4':'bốn',
    '5':'năm','6':'sáu','7':'bảy','8':'tám','9':'chín'
}
_TEENS = {
    '10':'mười','11':'mười một','12':'mười hai','13':'mười ba',
    '14':'mười bốn','15':'mười lăm','16':'mười sáu','17':'mười bảy',
    '18':'mười tám','19':'mười chín'
}
_TENS = {
    '2':'hai mươi','3':'ba mươi','4':'bốn mươi','5':'năm mươi',
    '6':'sáu mươi','7':'bảy mươi','8':'tám mươi','9':'chín mươi'
}

def num_to_words(s: str) -> str:
    """Chuyển chuỗi số nguyên sang chữ tiếng Việt."""
    s = s.lstrip('0') or '0'
    if s.startswith('-'):
        return 'âm ' + num_to_words(s[1:])
    try:
        n = int(s)
    except ValueError:
        return s
    if n == 0:
        return 'không'
    if n < 10:
        return _ONES[str(n)]
    if n < 20:
        return _TEENS[str(n)]
    if n < 100:
        t, o = n // 10, n % 10
        if o == 0:  return _TENS[str(t)]
        if o == 1:  return _TENS[str(t)] + ' mốt'
        if o == 4:  return _TENS[str(t)] + ' tư'
        if o == 5:  return _TENS[str(t)] + ' lăm'
        return _TENS[str(t)] + ' ' + _ONES[str(o)]
    if n < 1_000:
        h, r = n // 100, n % 100
        base = _ONES[str(h)] + ' trăm'
        if r == 0:   return base
        if r < 10:   return base + ' lẻ ' + _ONES[str(r)]
        return base + ' ' + num_to_words(str(r))
    if n < 1_000_000:
        th, r = n // 1_000, n % 1_000
        base = num_to_words(str(th)) + ' nghìn'
        if r == 0:      return base
        if r < 10:      return base + ' không trăm lẻ ' + _ONES[str(r)]
        if r < 100:     return base + ' không trăm ' + num_to_words(str(r))
        return base + ' ' + num_to_words(str(r))
    if n < 1_000_000_000:
        m, r = n // 1_000_000, n % 1_000_000
        base = num_to_words(str(m)) + ' triệu'
        if r == 0:      return base
        if r < 10:      return base + ' không trăm lẻ ' + _ONES[str(r)]
        if r < 100:     return base + ' không trăm ' + num_to_words(str(r))
        return base + ' ' + num_to_words(str(r))
    if n < 1_000_000_000_000:
        b, r = n // 1_000_000_000, n % 1_000_000_000
        base = num_to_words(str(b)) + ' tỷ'
        if r == 0:      return base
        if r < 10:      return base + ' không trăm lẻ ' + _ONES[str(r)]
        if r < 100:     return base + ' không trăm ' + num_to_words(str(r))
        return base + ' ' + num_to_words(str(r))
    # Số quá lớn → đọc từng chữ số
    return ' '.join(_ONES.get(c, c) for c in s)


# ══════════════════════════════════════════════════════════
# 2. CHUẨN HÓA DẤU CHẤM PHÂN CÁCH HÀNG NGHÌN
# ══════════════════════════════════════════════════════════

def _normalize_thousand_sep(text: str) -> str:
    """250.000 → 250000 (loại dấu chấm phân cách hàng nghìn)."""
    def repl(m):
        return m.group(0).replace('.', '')
    return re.sub(r'\d{1,3}(?:\.\d{3})+(?=\s|$|[^\d.,])', repl, text)


# ══════════════════════════════════════════════════════════
# 3. SỐ THẬP PHÂN
# ══════════════════════════════════════════════════════════

def _process_decimals(text: str) -> str:
    """3,14 → "ba phẩy một bốn"."""
    def repl(m):
        int_part  = num_to_words(m.group(1))
        dec_part  = num_to_words(m.group(2).lstrip('0') or '0')
        return f'{int_part} phẩy {dec_part}'
    return re.sub(r'(\d+),(\d+)(?=\s|$|[^\d,])', repl, text)


# ══════════════════════════════════════════════════════════
# 4. PHẦN TRĂM
# ══════════════════════════════════════════════════════════

def _process_percent(text: str) -> str:
    # 10-20% → "mười đến hai mươi phần trăm"
    text = re.sub(
        r'(\d+)\s*[-–—]\s*(\d+)\s*%',
        lambda m: f'{num_to_words(m.group(1))} đến {num_to_words(m.group(2))} phần trăm',
        text
    )
    # 3,5% → "ba phẩy năm phần trăm"
    text = re.sub(
        r'(\d+),(\d+)\s*%',
        lambda m: f'{num_to_words(m.group(1))} phẩy {num_to_words(m.group(2).lstrip("0") or "0")} phần trăm',
        text
    )
    # 12% → "mười hai phần trăm"
    text = re.sub(r'(\d+)\s*%', lambda m: num_to_words(m.group(1)) + ' phần trăm', text)
    return text


# ══════════════════════════════════════════════════════════
# 5. TIỀN TỆ
# ══════════════════════════════════════════════════════════

def _process_currency(text: str) -> str:
    def vnd_repl(m):
        return num_to_words(m.group(1).replace(',', '').replace('.', '')) + ' đồng'
    def usd_repl(m):
        return num_to_words(m.group(1).replace(',', '').replace('.', '')) + ' đô la'

    text = re.sub(r'(\d[\d,.]*)(?:\s*(?:đồng|VND|vnđ))\b', vnd_repl, text, flags=re.IGNORECASE)
    text = re.sub(r'(\d[\d,.]*)\s*đ(?![a-zà-ỹ])', vnd_repl, text, flags=re.IGNORECASE)
    text = re.sub(r'\$\s*(\d[\d,.]*)', usd_repl, text)
    text = re.sub(r'(\d[\d,.]*)\s*(?:USD|\$)\b', usd_repl, text, flags=re.IGNORECASE)
    return text


# ══════════════════════════════════════════════════════════
# 6. GIỜ / THỜI GIAN
# ══════════════════════════════════════════════════════════

def _process_time(text: str) -> str:
    # HH:MM:SS hoặc HH:MM
    def hms_repl(m):
        h, mi, s = m.group(1), m.group(2), m.group(3)
        r = num_to_words(h) + ' giờ'
        if mi: r += ' ' + num_to_words(mi) + ' phút'
        if s:  r += ' ' + num_to_words(s)  + ' giây'
        return r
    text = re.sub(r'(\d{1,2}):(\d{2})(?::(\d{2}))?', hms_repl, text)

    # 8h30 hoặc 8h
    def hm_repl(m):
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return num_to_words(str(h)) + ' giờ ' + num_to_words(str(mi))
        return m.group(0)
    text = re.sub(r'(\d{1,2})h(\d{2})(?![a-zà-ỹ])', hm_repl, text, flags=re.IGNORECASE)

    def h_repl(m):
        h = int(m.group(1))
        if 0 <= h <= 23:
            return num_to_words(str(h)) + ' giờ'
        return m.group(0)
    text = re.sub(r'(\d{1,2})h(?![a-zà-ỹ\d])', h_repl, text, flags=re.IGNORECASE)
    return text


# ══════════════════════════════════════════════════════════
# 7. NGÀY THÁNG
# ══════════════════════════════════════════════════════════

def _valid_day(d): return 1 <= int(d) <= 31
def _valid_month(m): return 1 <= int(m) <= 12
def _valid_year(y): return 1000 <= int(y) <= 9999

def _process_dates(text: str) -> str:
    # DD/MM/YYYY — chỉ xử lý khi ngày và tháng hợp lệ
    def dmY(m):
        d, mo, y = m.group(1), m.group(2), m.group(3)
        if _valid_day(d) and _valid_month(mo) and _valid_year(y):
            return f'ngày {num_to_words(d)} tháng {num_to_words(mo)} năm {num_to_words(y)}'
        return m.group(0)
    text = re.sub(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', dmY, text)

    # MM/YYYY
    def mY(m):
        mo, y = m.group(1), m.group(2)
        if _valid_month(mo) and _valid_year(y):
            return f'tháng {num_to_words(mo)} năm {num_to_words(y)}'
        return m.group(0)
    text = re.sub(r'(\d{1,2})[/-](\d{4})(?![-/]\d)', mY, text)

    # DD/MM — chỉ xử lý khi cả 2 đều hợp lệ VÀ ngày >= 10 (tránh nhận phân số 1/3, 2/5...)
    def dm(m):
        d, mo = m.group(1), m.group(2)
        if int(d) < 10 or not _valid_day(d) or not _valid_month(mo):
            return m.group(0)
        return f'{num_to_words(d)} tháng {num_to_words(mo)}'
    text = re.sub(r'(?<!\d)(\d{1,2})[/-](\d{1,2})(?![-/\d])(?!\d*\s*%)', dm, text)

    # "ngày X" — chỉ khi không đứng liền sau "ngày" đã có
    text = re.sub(
        r'(?<!ngày )ngày\s*(\d+)',
        lambda m: 'ngày ' + num_to_words(m.group(1)) if _valid_day(m.group(1)) else m.group(0),
        text
    )
    # "tháng X"
    text = re.sub(
        r'tháng\s*(\d+)',
        lambda m: 'tháng ' + num_to_words(m.group(1)) if _valid_month(m.group(1)) else m.group(0),
        text
    )
    return text


# ══════════════════════════════════════════════════════════
# 8. KHOẢNG NĂM  (2020–2025)
# ══════════════════════════════════════════════════════════

def _process_year_range(text: str) -> str:
    return re.sub(
        r'(\d{4})\s*[-–—]\s*(\d{4})',
        lambda m: num_to_words(m.group(1)) + ' đến ' + num_to_words(m.group(2)),
        text
    )


# ══════════════════════════════════════════════════════════
# 9. THỨ TỰ  (thứ 2, tập 5, chương 10, v.v.)
# ══════════════════════════════════════════════════════════

_ORDINAL_SPECIAL = {
    '1':'nhất','2':'hai','3':'ba','4':'tư','5':'năm',
    '6':'sáu','7':'bảy','8':'tám','9':'chín','10':'mười'
}

def _process_ordinals(text: str) -> str:
    keywords = r'(?:thứ|lần|bước|phần|chương|tập|số)'
    def repl(m):
        kw, n = m.group(1), m.group(2)
        return kw + ' ' + (_ORDINAL_SPECIAL.get(n, num_to_words(n)))
    return re.sub(rf'({keywords})\s*(\d+)', repl, text, flags=re.IGNORECASE)


# ══════════════════════════════════════════════════════════
# 10. SỐ ĐIỆN THOẠI
# ══════════════════════════════════════════════════════════

def _process_phone(text: str) -> str:
    def digit_by_digit(m):
        return ' '.join(_ONES.get(c, c) for c in m.group(0) if c.isdigit())
    text = re.sub(r'0\d{9,10}', digit_by_digit, text)
    text = re.sub(r'\+84\d{9,10}', digit_by_digit, text)
    return text


# ══════════════════════════════════════════════════════════
# 11. ĐƠN VỊ ĐO LƯỜNG
# ══════════════════════════════════════════════════════════

_UNITS = {
    'km/h': 'ki-lô-mét trên giờ', 'kmh': 'ki-lô-mét trên giờ',
    'm/s':  'mét trên giây',
    'km2':  'ki-lô-mét vuông', 'km²': 'ki-lô-mét vuông',
    'cm2':  'xăng-ti-mét vuông', 'cm²': 'xăng-ti-mét vuông',
    'm2':   'mét vuông', 'm²': 'mét vuông',
    'm3':   'mét khối', 'm³': 'mét khối',
    'km':   'ki-lô-mét', 'dm': 'đề-xi-mét', 'cm': 'xăng-ti-mét',
    'mm':   'mi-li-mét', 'ha': 'héc-ta',
    'kg':   'ki-lô-gam', 'mg': 'mi-li-gam',
    'ml':   'mi-li-lít',
    'min':  'phút', 'sec': 'giây',
    '°C':   'độ C', '°F': 'độ F', '°K': 'độ K',
    'm':    'mét', 'g': 'gam', 'l': 'lít',
}

def _process_units(text: str) -> str:
    # Sắp xếp unit dài trước để tránh xung đột (km trước m)
    for unit, spoken in sorted(_UNITS.items(), key=lambda x: -len(x[0])):
        esc = re.escape(unit)
        pattern = rf'(\d+)\s*{esc}(?=\s|[^\w]|$)'
        text = re.sub(pattern, lambda m, sp=spoken: num_to_words(m.group(1)) + ' ' + sp, text)
    return text


# ══════════════════════════════════════════════════════════
# 12. SỐ CÒN LẠI → CHỮ
# ══════════════════════════════════════════════════════════

def _process_remaining_numbers(text: str) -> str:
    return re.sub(r'\b\d+\b', lambda m: num_to_words(m.group(0)), text)


# ══════════════════════════════════════════════════════════
# 13. KÝ TỰ ĐẶC BIỆT / EMOJI / URL / EMAIL
# ══════════════════════════════════════════════════════════

_EMOJI_RE = re.compile(
    '[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
    '\U0001F1E0-\U0001F1FF\U00002600-\U000026FF\U00002700-\U000027BF'
    '\U0001F900-\U0001F9FF\uFE0F\u200D]+',
    flags=re.UNICODE
)

def _clean_special(text: str) -> str:
    text = _EMOJI_RE.sub('', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'www\.\S+', '', text)
    text = re.sub(r'\S+@\S+\.\S+', '', text)
    text = text.replace('&', ' và ')
    text = text.replace('@', ' a còng ')
    text = text.replace('#', ' thăng ')
    text = re.sub(r'[*_~`^\\()]', '', text)
    return text


def _normalize_punct(text: str) -> str:
    text = re.sub(r'[""„‟]', '"', text)
    text = re.sub(r"[''‚‛]", "'", text)
    text = re.sub(r'[–—−]', '-', text)
    text = re.sub(r'\.{3,}', '...', text)
    text = text.replace('…', '...')
    text = re.sub(r'([!?.])(\1)+', r'\1', text)
    return text


def _normalize_spaces(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


# ══════════════════════════════════════════════════════════
# 14. PHIÊN ÂM TIẾNG ANH → TIẾNG VIỆT
# ══════════════════════════════════════════════════════════

_VN_ACCENT_RE = re.compile(
    r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộ'
    r'ơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]', re.IGNORECASE
)
_VN_ONSETS = {
    'b','c','d','đ','g','h','k','l','m','n','p','q','r','s','t','v','x',
    'ch','gh','gi','kh','ng','nh','ph','qu','th','tr'
}
_VN_ENDINGS = {'p','t','c','m','n','ng','ch','nh'}
_EN_SPECIAL = re.compile(r'[fwzj]', re.IGNORECASE)

def _is_vietnamese(word: str) -> bool:
    w = word.lower().strip()
    if not w: return False
    if _VN_ACCENT_RE.search(w): return True
    if _EN_SPECIAL.search(w): return False
    m = re.match(r'^([^ueoaiy]*)([ueoaiy]+)([^ueoaiy]*)$', w)
    if not m: return False
    onset, vowel, coda = m.group(1), m.group(2), m.group(3)
    if onset and onset not in _VN_ONSETS: return False
    if coda and coda not in _VN_ENDINGS: return False
    if re.search(r'ee|oo|ea|oa|ae|ie', vowel) and vowel not in ('oa','oe','ua','uy'):
        return False
    return True

# Bảng phiên âm pattern (theo thứ tự quan trọng)
_EN_SUFFIX = [
    (r'tion$','ân'), (r'sion$','ân'), (r'age$','ây'), (r'ing$','ing'),
    (r'ture$','chờ'), (r'aught','ót'), (r'ought','ót'), (r'ound','ao'),
    (r'ight','ai'), (r'eigh','ây'), (r'ough','ao'),
]
_EN_ENDINGS_MAP = [
    (r'le$','ồ'), (r'ook$','úc'), (r'ood$','út'), (r'ool$','un'),
    (r'oom$','um'), (r'oon$','un'), (r'oot$','út'), (r'iend$','en'),
    (r'end$','en'), (r'eau$','iu'), (r'ail$','ain'), (r'ain$','ain'),
    (r'ait$','ât'), (r'oat$','ốt'), (r'oad$','ốt'), (r'eep$','íp'),
    (r'eet$','ít'), (r'eel$','in'), (r'all$','âu'), (r'ell$','eo'),
    (r'ill$','iu'), (r'oll$','ôn'), (r'ull$','un'), (r'ang$','ang'),
    (r'eng$','ing'), (r'ong$','ong'), (r'ung$','âng'), (r'air$','e'),
    (r'ear$','ia'), (r'ire$','ai'), (r'ure$','iu'), (r'our$','ao'),
    (r'ore$','o'), (r'ee$','i'), (r'ea$','i'), (r'oo$','u'),
    (r'oa$','oa'), (r'oe$','oe'), (r'ai$','ai'), (r'ay$','ay'),
    (r'au$','au'), (r'aw$','â'), (r'ei$','ây'), (r'ey$','ây'),
    (r'oi$','oi'), (r'oy$','oi'), (r'ou$','u'), (r'ow$','ô'),
    (r'ue$','ue'), (r'ui$','ui'), (r'ie$','ai'), (r'eu$','iu'),
    (r'ar$','a'), (r'er$','ơ'), (r'ir$','ơ'), (r'or$','o'),
    (r'ur$','ơ'), (r'al$','an'), (r'el$','eo'), (r'il$','iu'),
    (r'ol$','ôn'), (r'ul$','un'),
    (r'ate$','ây'), (r'ite$','ai'), (r'ote$','ốt'), (r'ute$','út'),
    (r'ade$','ây'), (r'ide$','ai'), (r'ode$','ốt'), (r'ude$','út'),
    (r'ake$','ây'), (r'ame$','am'), (r'ane$','an'), (r'ike$','íc'),
    (r'oke$','ốc'), (r'ome$','om'), (r'one$','oăn'),
    (r'ase$','ây'), (r'ise$','ai'), (r'ose$','âu'),
    (r'at$','át'), (r'et$','ét'), (r'it$','ít'), (r'ot$','ót'), (r'ut$','út'),
    (r'am$','am'), (r'an$','an'), (r'em$','em'), (r'en$','en'),
    (r'im$','im'), (r'in$','in'), (r'om$','om'), (r'on$','on'),
    (r'um$','âm'), (r'un$','ân'),
]
_EN_CONSONANTS = [
    (r'j','d'), (r'z','d'), (r'w','u'), (r'f','ph'),
    (r's','x'), (r'c','k'), (r'q','ku'),
]

def _transliterate_english(word: str) -> str:
    if not word: return word
    if _is_vietnamese(word): return word
    n = word.lower()
    if n.startswith('y'): n = 'd' + n[1:]
    if n.startswith('d'): n = 'đ' + n[1:]
    for pat, rep in _EN_SUFFIX:
        n = re.sub(pat, rep, n)
    for pat, rep in _EN_ENDINGS_MAP:
        n = re.sub(pat, rep, n)
    for pat, rep in _EN_CONSONANTS:
        n = re.sub(pat, rep, n)
    n = re.sub(r'([bcdfghjklmnpqrstvwxz])y', r'\1i', n)
    n = re.sub(r'y$', 'i', n)
    return n or word

def _process_english_words(text: str) -> str:
    """Phiên âm các từ tiếng Anh trong văn bản (giữ nguyên từ tiếng Việt)."""
    def repl(m):
        w = m.group(0)
        if len(w) <= 1:          # Không phiên âm ký tự đơn lẻ (C, F, K, m...)
            return w
        if _is_vietnamese(w):
            return w
        ph = _transliterate_english(w)
        if w[0].isupper() and ph:
            return ph[0].upper() + ph[1:]
        return ph
    return re.sub(r'\b[a-zA-Z]+\b', repl, text)


# ══════════════════════════════════════════════════════════
# 15. PIPELINE CHÍNH
# ══════════════════════════════════════════════════════════

def process(text: str) -> str:
    """
    Pipeline tiền xử lý văn bản tiếng Việt trước khi đưa vào Piper TTS.

    Thứ tự xử lý (quan trọng — không thay đổi):
      1. Chuẩn hóa Unicode NFC
      2. Dọn emoji / URL / email / ký tự lạ
      3. Chuẩn hóa dấu câu
      4. Khoảng năm (2020–2025)
      5. Ngày tháng (15/3/2025)
      6. Giờ (8h30, 8:30)
      7. Thứ tự (tập 5, chương 3)
      8. Chuẩn hóa dấu chấm hàng nghìn (250.000 → 250000)
      9. Tiền tệ (250.000đ → "hai trăm năm mươi nghìn đồng")
     10. Phần trăm (12%)
     11. Số điện thoại
     12. Số thập phân (3,14)
     13. Đơn vị đo lường (5km)
     14. Phiên âm tiếng Anh
     15. Số còn lại → chữ
     16. Dọn khoảng trắng
    """
    if not text or not isinstance(text, str):
        return text or ''

    text = unicodedata.normalize('NFC', text)
    text = _clean_special(text)
    text = _normalize_punct(text)
    text = _process_year_range(text)
    text = _process_dates(text)
    text = _process_time(text)
    text = _process_ordinals(text)
    text = _normalize_thousand_sep(text)
    text = _process_currency(text)
    text = _process_percent(text)
    text = _process_phone(text)
    text = _process_decimals(text)
    text = _process_units(text)
    text = _process_english_words(text)
    text = _process_remaining_numbers(text)
    text = re.sub(r'\bngày\s+ngày\b', 'ngày', text)   # dọn "ngày ngày" thừa
    text = _normalize_spaces(text)
    return text


# ══════════════════════════════════════════════════════════
# Quick test khi chạy trực tiếp
# ══════════════════════════════════════════════════════════

if __name__ == '__main__':
    tests = [
        "Giá là 250.000đ, giảm 15%.",
        "Cuộc họp lúc 8h30 ngày 15/3/2025.",
        "Tập 12: Chương 3 - The final battle.",
        "Liên hệ 0912345678 hoặc support@email.com.",
        "Nhiệt độ 37°C, tốc độ 90km/h.",
        "Doanh thu năm 2020–2024 tăng 3,5%.",
        "I love you → phiên âm thành?",
        "250 học sinh, 3 lớp, mỗi lớp 1/3.",
    ]
    for t in tests:
        out = process(t)
        print(f'IN : {t}')
        print(f'OUT: {out}')
        print()

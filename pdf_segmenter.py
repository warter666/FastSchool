import base64
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import os

import fitz
from PIL import Image


RE_Q_START = re.compile(r"^\s*(\d{1,3})\s*[.)、]\s*")
RE_OPT_MARK = re.compile(r"([A-Da-d])\s*[.)、]")
RE_OPT_WORD = re.compile(r"^([A-Da-d])[.)、]$")

PAD = float(os.getenv("FASTSCHOOL_PAD", "1.0"))
STEM_LINE_GAP = float(os.getenv("FASTSCHOOL_STEM_GAP", "10.0"))
OPTION_LINE_GAP = float(os.getenv("FASTSCHOOL_OPT_GAP", "5.0"))
INDENT_MIN = float(os.getenv("FASTSCHOOL_INDENT_MIN", "12.0"))


def _tighten_bbox(b: Tuple[float, float, float, float], dy: float = 1.0) -> Tuple[float, float, float, float]:
    x0, y0, x1, y1 = b
    if (y1 - y0) > (2 * dy + 1):
        return (x0, y0 + dy, x1, y1 - dy)
    return b


@dataclass
class LineBox:
    text: str
    bbox: Tuple[float, float, float, float]


def _bbox_union(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _pad_bbox(b: Tuple[float, float, float, float], pad: float, page_rect: fitz.Rect) -> Tuple[float, float, float, float]:
    x0, y0, x1, y1 = b
    x0 = max(page_rect.x0, x0 - pad)
    y0 = max(page_rect.y0, y0 - pad)
    x1 = min(page_rect.x1, x1 + pad)
    y1 = min(page_rect.y1, y1 + pad)
    return (x0, y0, x1, y1)


def _pix_crop_to_data_url(pix: fitz.Pixmap, bbox: Tuple[float, float, float, float], zoom: float) -> str:
    x0, y0, x1, y1 = bbox
    left = int(max(0, x0 * zoom))
    top = int(max(0, y0 * zoom))
    right = int(min(pix.width, x1 * zoom))
    bottom = int(min(pix.height, y1 * zoom))

    if right <= left or bottom <= top:
        return ""

    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    cropped = img.crop((left, top, right, bottom))
    buf = bytearray()
    import io

    with io.BytesIO() as f:
        cropped.save(f, format="PNG", optimize=True)
        buf = f.getvalue()
    b64 = base64.b64encode(buf).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _extract_words(page: fitz.Page) -> List[Tuple[float, float, float, float, str]]:
    words = page.get_text("words")
    out: List[Tuple[float, float, float, float, str]] = []
    for w in words:
        if len(w) < 5:
            continue
        x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
        t = (text or "").strip()
        if not t:
            continue
        out.append((float(x0), float(y0), float(x1), float(y1), t))
    return out


def _extract_lines(page: fitz.Page) -> List[LineBox]:
    d = page.get_text("dict")
    lines: List[LineBox] = []
    for block in d.get("blocks", []):
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text_parts = []
            bbox: Optional[Tuple[float, float, float, float]] = None
            for span in spans:
                t = (span.get("text") or "").strip()
                if not t:
                    continue
                text_parts.append(t)
                sb = span.get("bbox")
                if sb:
                    sb_t = (float(sb[0]), float(sb[1]), float(sb[2]), float(sb[3]))
                    bbox = sb_t if bbox is None else _bbox_union(bbox, sb_t)
            if not text_parts or bbox is None:
                continue
            text = " ".join(text_parts)
            lines.append(LineBox(text=text, bbox=bbox))

    lines.sort(key=lambda l: (l.bbox[1], l.bbox[0]))
    return lines


def segment_pdf_questions(pdf_path: str, zoom: float = 2.0) -> Dict:
    doc = fitz.open(pdf_path)
    questions: List[Dict] = []
    for page_index in range(doc.page_count):
        page = doc.load_page(page_index)
        page_rect = page.rect
        lines = _extract_lines(page)
        if not lines:
            continue

        words = _extract_words(page)

        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        current: Optional[Dict] = None
        stem_bbox: Optional[Tuple[float, float, float, float]] = None
        opt_bboxes: Dict[str, Tuple[float, float, float, float]] = {}
        current_opt: Optional[str] = None
        stem_left: Optional[float] = None
        opt_left: Dict[str, float] = {}
        last_stem_bbox: Optional[Tuple[float, float, float, float]] = None
        last_opt_bbox: Dict[str, Tuple[float, float, float, float]] = {}

        def finalize():
            nonlocal current, stem_bbox, opt_bboxes, current_opt
            if not current:
                return
            if stem_bbox is None:
                current = None
                opt_bboxes = {}
                current_opt = None
                return

            stem_crop = _pix_crop_to_data_url(
                pix,
                _pad_bbox(_tighten_bbox(stem_bbox, dy=1.0), pad=PAD, page_rect=page_rect),
                zoom,
            )
            options_out: Dict[str, Dict] = {}
            for k, b in opt_bboxes.items():
                options_out[k] = {
                    "image": _pix_crop_to_data_url(
                        pix,
                        _pad_bbox(_tighten_bbox(b, dy=1.0), pad=PAD, page_rect=page_rect),
                        zoom,
                    )
                }
            current["parsed"] = {
                "stem_image": stem_crop,
                "options": options_out,
                "answer": None,
            }
            current["page"] = page_index + 1
            questions.append(current)
            current = None
            stem_bbox = None
            opt_bboxes = {}
            current_opt = None

        for line in lines:
            t = line.text.strip()
            if not t:
                continue

            q_m = RE_Q_START.match(t)
            if q_m:
                finalize()
                qid = int(q_m.group(1))
                current = {"id": qid, "type": "选择"}
                stem_bbox = line.bbox
                last_stem_bbox = line.bbox
                stem_left = line.bbox[0]
                opt_left = {}
                last_opt_bbox = {}
                current_opt = None
                continue

            if current is None:
                continue

            opt_marks = list(RE_OPT_MARK.finditer(t))
            if opt_marks:
                current_opt = None
                if len(opt_marks) == 1:
                    k = opt_marks[0].group(1).upper()
                    opt_bboxes[k] = line.bbox if k not in opt_bboxes else _bbox_union(opt_bboxes[k], line.bbox)
                    opt_left[k] = line.bbox[0]
                    last_opt_bbox[k] = line.bbox
                    current_opt = k
                else:
                    x0, y0, x1, y1 = line.bbox
                    y_min = y0 - 1
                    y_max = y1 + 1
                    marker_positions: Dict[str, float] = {}
                    for wx0, wy0, wx1, wy1, wtxt in words:
                        if wy1 < y_min or wy0 > y_max:
                            continue
                        m = RE_OPT_WORD.match(wtxt)
                        if not m:
                            continue
                        k = m.group(1).upper()
                        marker_positions[k] = min(marker_positions.get(k, wx0), wx0)

                    keys = [m.group(1).upper() for m in opt_marks]
                    if all(k in marker_positions for k in keys):
                        keys_sorted = sorted(keys, key=lambda kk: marker_positions[kk])
                        xs = [marker_positions[k] for k in keys_sorted]
                        xs.append(x1)
                        for i, k in enumerate(keys_sorted):
                            seg_bbox = (xs[i], y0, xs[i + 1], y1)
                            opt_bboxes[k] = seg_bbox if k not in opt_bboxes else _bbox_union(opt_bboxes[k], seg_bbox)
                            opt_left[k] = seg_bbox[0]
                            last_opt_bbox[k] = seg_bbox
                        current_opt = keys_sorted[-1]
                    else:
                        w = max(1.0, x1 - x0)
                        n = len(opt_marks)
                        for i, m in enumerate(opt_marks):
                            k = m.group(1).upper()
                            seg_x0 = x0 + (i / n) * w
                            seg_x1 = x0 + ((i + 1) / n) * w
                            seg_bbox = (seg_x0, y0, seg_x1, y1)
                            opt_bboxes[k] = seg_bbox if k not in opt_bboxes else _bbox_union(opt_bboxes[k], seg_bbox)
                            opt_left[k] = seg_bbox[0]
                            last_opt_bbox[k] = seg_bbox
                        current_opt = opt_marks[-1].group(1).upper()
                continue

            if current_opt:
                prev = last_opt_bbox.get(current_opt)
                gap_ok = True
                if prev is not None:
                    gap_ok = (line.bbox[1] - prev[3]) <= OPTION_LINE_GAP
                indent_ok = True
                if stem_left is not None and current_opt in opt_left:
                    indented = (opt_left[current_opt] - stem_left) > INDENT_MIN
                    if indented:
                        indent_ok = line.bbox[0] >= (opt_left[current_opt] - 2)
                    else:
                        indent_ok = False

                if gap_ok and indent_ok:
                    opt_bboxes[current_opt] = _bbox_union(opt_bboxes[current_opt], line.bbox)
                    last_opt_bbox[current_opt] = _bbox_union(last_opt_bbox[current_opt], line.bbox)
                else:
                    current_opt = None

            if not current_opt:
                if last_stem_bbox is not None:
                    if (line.bbox[1] - last_stem_bbox[3]) <= STEM_LINE_GAP:
                        stem_bbox = _bbox_union(stem_bbox, line.bbox) if stem_bbox else line.bbox
                        last_stem_bbox = _bbox_union(last_stem_bbox, line.bbox)
                else:
                    stem_bbox = _bbox_union(stem_bbox, line.bbox) if stem_bbox else line.bbox
                    last_stem_bbox = line.bbox

        finalize()

    doc.close()
    return {"questions": questions, "total": len(questions), "source": "screenshot"}

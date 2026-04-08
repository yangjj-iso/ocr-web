from __future__ import annotations

import re
from typing import Any


MULTI_LAYOUT_CONTINUATION_FAMILIES = {"budget", "contract", "minutes"}
DOCUMENT_FAMILY_LABELS = {"budget": "预算", "contract": "合同", "minutes": "纪要"}

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def strip_html(value: str) -> str:
    return _HTML_TAG_RE.sub(" ", coerce_text(value))


def infer_title_hint(full_text: str) -> str:
    plain_text = strip_html(full_text)
    for raw_line in re.split(r"[\r\n]+", plain_text):
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        return line[:80]
    compact = re.sub(r"\s+", " ", plain_text).strip()
    return compact[:80]


def detect_document_family(value: str) -> str:
    text = coerce_text(value)
    if not text:
        return ""
    if any(keyword in text for keyword in ("预算书", "预算汇总", "预算表", "造价预算", "造价书", "造价")):
        return "budget"
    if any(keyword in text for keyword in ("合同", "协议", "补充协议")):
        return "contract"
    if any(keyword in text for keyword in ("会议纪要", "会议记录", "会议决定", "会议议定事项")):
        return "minutes"

    contract_markers = (
        "甲方",
        "乙方",
        "本合同",
        "付款方式",
        "质保金",
        "质保期",
        "开户行",
        "帐号",
        "验收合格",
    )
    if sum(1 for keyword in contract_markers if keyword in text) >= 3:
        return "contract"

    minutes_markers = (
        "会议传达",
        "会议强调",
        "会议要求",
        "会议指出",
        "纪要如下",
        "出席",
        "请假",
    )
    if sum(1 for keyword in minutes_markers if keyword in text) >= 2:
        return "minutes"

    if "报价" in text:
        return "quote"
    if any(keyword in text for keyword in ("平面图", "立面图", "剖面图", "尺寸图", "细节说明图", "图号")):
        return "drawing"
    if any(keyword in text for keyword in ("施工说明", "设计说明", "说明")):
        return "instruction"
    if "营业执照" in text:
        return "license"
    if any(keyword in text for keyword in ("资质证书", "证书")):
        return "certificate"
    if "目录" in text:
        return "catalog"
    return ""


def infer_document_family_from_text(*, title_hint: str, full_text: str) -> str:
    family = detect_document_family(title_hint)
    if family:
        return family
    text_excerpt = coerce_text(full_text)[:2000]
    return detect_document_family(text_excerpt)


def document_family_label(family: str) -> str:
    return DOCUMENT_FAMILY_LABELS.get(family, family or "同类")


__all__ = [
    "DOCUMENT_FAMILY_LABELS",
    "MULTI_LAYOUT_CONTINUATION_FAMILIES",
    "coerce_text",
    "detect_document_family",
    "document_family_label",
    "infer_document_family_from_text",
    "infer_title_hint",
    "strip_html",
]

"""
OCR Provider 抽象接口

新增 OCR 引擎只需：
  1. 继承 OCRProvider
  2. 实现 recognize()
  3. 在 registry.py 注册
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class OCRLine:
    line_num: int
    text: str
    confidence: float
    bbox: list[Any]


@dataclass(slots=True)
class OCRRegion:
    type: str                                       # text / table / seal / image / ...
    bbox: list[Any]
    bbox_type: str = "rect"                         # "rect" | "poly"
    layout_bbox: list[float] = field(default_factory=list)
    content: str = ""
    html: str | None = None
    table_data: list[list[str]] | None = None
    region_lines: list[dict] = field(default_factory=list)


@dataclass(slots=True)
class OCRPage:
    page_num: int
    regions: list[OCRRegion] = field(default_factory=list)
    lines: list[OCRLine] = field(default_factory=list)


@dataclass(slots=True)
class OCRResult:
    page_count: int
    pages: list[dict[str, Any]]    # 兼容现有 dict 格式
    full_text: str
    mode: str


class OCRProvider(ABC):
    """OCR Provider 抽象基类"""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 标识"""
        ...

    @property
    @abstractmethod
    def supported_modes(self) -> list[str]:
        """支持的识别模式列表"""
        ...

    @abstractmethod
    def recognize(self, file_path: str, mode: str) -> dict[str, Any]:
        """
        执行文档识别

        Args:
            file_path: 文件路径（图片或 PDF）
            mode: 识别模式

        Returns:
            {"page_count": int, "pages": list, "full_text": str, "mode": str}
        """
        ...

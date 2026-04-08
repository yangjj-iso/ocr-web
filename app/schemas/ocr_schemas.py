"""
向后兼容层 — 所有 schema 已拆分到 app.schemas.tasks / batches / qa / evaluation
现有代码 from app.schemas.ocr_schemas import X 仍可正常使用
"""
# Tasks
from app.schemas.tasks import (  # noqa: F401
    OCRTaskOut,
    OCRTaskDetail,
    OCRTaskList,
    TaskProgressRequest,
    TaskProgressItem,
    TaskProgressResponse,
)

# Batches (AI extraction)
from app.schemas.batches import (  # noqa: F401
    AIExtractFieldsRequest,
    AIFieldConflict,
    AIFieldAgreement,
    AIExtractFieldsResponse,
    AIBatchMergeExtractRequest,
    AIBatchSkippedTask,
    AIBatchGroup,
    AIBatchDocument,
    AIBatchSummary,
    AIBatchMergeExtractResponse,
)

# Evaluation
from app.schemas.evaluation import (  # noqa: F401
    BatchEvaluationTruthTaskItem,
    BatchEvaluationTruthDocumentItem,
    BatchEvaluationTruthGetResponse,
    BatchEvaluationTruthPutRequest,
    BatchEvaluationMetricsResponse,
    BatchEvaluationAiReportResponse,
)

# QA
from app.schemas.qa import (  # noqa: F401
    BatchQARequest,
    BatchQAEvidenceItem,
    BatchQACitationItem,
    BatchQAResponse,
    BatchQAFeedbackItem,
    BatchQAHistoryItem,
    BatchQAHistoryResponse,
    BatchQAFeedbackRequest,
    BatchQAFeedbackResponse,
    BatchQAMetricsResponse,
)

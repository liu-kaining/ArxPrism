"""
ArxPrism Models Package
"""

from src.models.schemas import (
    APIResponse,
    PipelineTriggerRequest,
    PipelineTriggerResponse,
    PaperGraphNode,
    PaperGraphRelationship,
    PaperGraphResponse,
    EvolutionTreeNode,
    EvolutionTreeLink,
    EvolutionTreeResponse,
    PaperExtractionResponse,
    ExtractionData,
    KnowledgeGraphNodes,
    CriticalAnalysis,
    ProposedMethod,
)

from src.models.task_models import (
    TaskStatus,
    TaskProgress,
    Task,
    PaperProcessingStatus,
    PaperProcessingResult,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskListResponse,
    TaskSummary,
    DomainPreset,
    DOMAIN_PRESETS,
    get_domain_preset,
    list_domain_presets,
)

__all__ = [
    # Schemas
    "APIResponse",
    "PipelineTriggerRequest",
    "PipelineTriggerResponse",
    "PaperGraphNode",
    "PaperGraphRelationship",
    "PaperGraphResponse",
    "EvolutionTreeNode",
    "EvolutionTreeLink",
    "EvolutionTreeResponse",
    "PaperExtractionResponse",
    "ExtractionData",
    "KnowledgeGraphNodes",
    "CriticalAnalysis",
    "ProposedMethod",
    # Task Models
    "TaskStatus",
    "TaskProgress",
    "Task",
    "PaperProcessingStatus",
    "PaperProcessingResult",
    "TaskCreateRequest",
    "TaskCreateResponse",
    "TaskListResponse",
    "TaskSummary",
    "DomainPreset",
    "DOMAIN_PRESETS",
    "get_domain_preset",
    "list_domain_presets",
]

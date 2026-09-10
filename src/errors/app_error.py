from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base hierárquico — todas as exceções esperadas da aplicação."""

    code: str = "APP_ERROR"
    status_code: int = 500
    public: bool = True

    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def to_dict(self, correlation_id: str | None = None) -> dict[str, Any]:
        body = {"code": self.code, "message": self.message}
        if correlation_id:
            body["correlation_id"] = correlation_id
        return body


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    status_code = 400


class SecurityViolation(AppError):
    code = "SECURITY_VIOLATION"
    status_code = 403


class PromptInjectionDetected(SecurityViolation):
    code = "PROMPT_INJECTION_DETECTED"
    status_code = 403


class ToolExecutionError(AppError):
    code = "TOOL_EXECUTION_ERROR"
    status_code = 502


class GraphMaxStepsError(AppError):
    code = "GRAPH_MAX_STEPS_EXCEEDED"
    status_code = 500


class ApprovalRequiredError(AppError):
    code = "APPROVAL_REQUIRED"
    status_code = 202


class LLMCommunicationError(AppError):
    code = "LLM_COMMUNICATION_ERROR"
    status_code = 502

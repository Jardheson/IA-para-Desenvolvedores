from __future__ import annotations

from src.errors.app_error import (
    AppError,
    ApprovalRequiredError,
    GraphMaxStepsError,
    LLMCommunicationError,
    PromptInjectionDetected,
    SecurityViolation,
    ToolExecutionError,
    ValidationError,
)


def test_app_error_base_attributes():
    err = AppError("mensagem base", context={"a": 1})
    assert err.code == "APP_ERROR"
    assert err.status_code == 500
    assert err.public is True
    assert err.message == "mensagem base"
    assert err.context == {"a": 1}
    assert str(err) == "mensagem base"


def test_app_error_to_dict_without_correlation_id():
    err = AppError("x")
    d = err.to_dict()
    assert d == {"code": "APP_ERROR", "message": "x"}


def test_app_error_to_dict_with_correlation_id():
    err = ValidationError("campo vazio")
    d = err.to_dict(correlation_id="cid-123")
    assert d == {"code": "VALIDATION_ERROR", "message": "campo vazio", "correlation_id": "cid-123"}


def test_validation_error_hierarchy_and_status():
    err = ValidationError("falha")
    assert isinstance(err, AppError)
    assert err.code == "VALIDATION_ERROR"
    assert err.status_code == 400


def test_security_violation_hierarchy():
    err = SecurityViolation("bloqueado")
    assert isinstance(err, AppError)
    assert err.code == "SECURITY_VIOLATION"
    assert err.status_code == 403


def test_prompt_injection_hierarchy():
    err = PromptInjectionDetected("injection")
    assert isinstance(err, SecurityViolation)
    assert isinstance(err, AppError)
    assert err.code == "PROMPT_INJECTION_DETECTED"
    assert err.status_code == 403


def test_tool_execution_error():
    err = ToolExecutionError("ferramenta falhou")
    assert isinstance(err, AppError)
    assert err.code == "TOOL_EXECUTION_ERROR"
    assert err.status_code == 502


def test_graph_max_steps_error():
    err = GraphMaxStepsError("max steps")
    assert isinstance(err, AppError)
    assert err.code == "GRAPH_MAX_STEPS_EXCEEDED"
    assert err.status_code == 500


def test_approval_required_error():
    err = ApprovalRequiredError("aguardando")
    assert isinstance(err, AppError)
    assert err.code == "APPROVAL_REQUIRED"
    assert err.status_code == 202


def test_llm_communication_error():
    err = LLMCommunicationError("timeout")
    assert isinstance(err, AppError)
    assert err.code == "LLM_COMMUNICATION_ERROR"
    assert err.status_code == 502


def test_hierarchy_chain():
    assert issubclass(ValidationError, AppError)
    assert issubclass(SecurityViolation, AppError)
    assert issubclass(PromptInjectionDetected, SecurityViolation)
    assert issubclass(ToolExecutionError, AppError)
    assert issubclass(GraphMaxStepsError, AppError)
    assert issubclass(ApprovalRequiredError, AppError)
    assert issubclass(LLMCommunicationError, AppError)


def test_app_error_context_defaults_to_empty_dict():
    err = AppError("sem contexto")
    assert err.context == {}

from src.observability.logging import get_audit_log


# Backwards compat alias — evita que importações antigas `audit_log.append` quebrem
# após a mudança para factory.
class _AuditLogProxy:
    def append(self, **kwargs):
        return get_audit_log().append(**kwargs)

    def close(self):
        return get_audit_log().close()


audit_log: _AuditLogProxy = _AuditLogProxy()

__all__ = ["audit_log", "get_audit_log"]

from backend.models.entities import AuditLog


def record_audit(db, action: str, user_id: int | None = None, resource_type: str = "system", resource_id: str | None = None, details: dict | None = None):
    db.add(AuditLog(user_id=user_id, action=action, resource_type=resource_type, resource_id=resource_id, details=details or {}))

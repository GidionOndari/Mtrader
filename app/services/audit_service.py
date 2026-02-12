from sqlalchemy.orm import Session

from app.models import AuditAction, AuditTrail


def record_audit(
    db: Session,
    *,
    user_id: int | None,
    action: AuditAction,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    row = AuditTrail(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=ip_address,
    )
    db.add(row)
    db.commit()

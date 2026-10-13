from .auth import AuthContext
from .models import Dataset


def dataset_scope(context: AuthContext, *, deleted: bool = False):
    conditions = [Dataset.deleted_at.is_not(None) if deleted else Dataset.deleted_at.is_(None)]
    if not context.user.is_admin:
        conditions.append(Dataset.owner_id == context.user.id)
    return conditions

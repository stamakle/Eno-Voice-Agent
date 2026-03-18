from fastapi import APIRouter, Depends

from english_tech.auth.deps import get_current_user
from english_tech.observability.metrics import metrics_store

router = APIRouter()


@router.get('/metrics')
def metrics(_user=Depends(get_current_user)):
    return metrics_store.snapshot()

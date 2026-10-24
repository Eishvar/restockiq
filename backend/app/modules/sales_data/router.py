from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.auth import current_user, require_role
from app.db import get_db
from app.modules.planning import refresh
from app.modules.sales_data import service
from app.modules.sales_data.schemas import (
    ConfirmIn, ImportPreview, ImportResult, RemoveIn, RemovalOut, RemovePreview, RemoveResult, SalesOverview,
)
from app.modules.settings.models import User

router = APIRouter(prefix="/sales", tags=["sales data"])


@router.get("/overview", response_model=SalesOverview)
def overview(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """What sales the app has, the files that brought them, and what was taken out (and can be put back)."""
    return service.overview(db, user)


@router.post("/import/preview", response_model=ImportPreview)
def preview_import(file: UploadFile = File(...), user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    """Read a CSV, Excel or PDF file (a PDF is read by AI) and show what saving it would do. Saves no sales."""
    return service.preview_file(db, user, file.filename or "sales", file.file.read())


@router.post("/import/confirm", response_model=ImportResult)
def confirm_import(body: ConfirmIn, background: BackgroundTasks, user: User = Depends(require_role("manager")),
                   db: Session = Depends(get_db)):
    result, remeasure = service.confirm(db, user, body)
    if remeasure:  # a big catch-up changes what the safety buffers should learn from
        background.add_task(refresh.run_recompute, user.tenant_id, user.id, "sales_import")
    return result


@router.get("/remove/preview", response_model=RemovePreview)
def remove_preview(import_id: int | None = Query(None), date_from: date | None = Query(None), date_to: date | None = Query(None),
                   user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    """What removing a file, or a range of days, would take out, and where "today" would move to."""
    return service.remove_preview(db, user, RemoveIn(import_id=import_id, date_from=date_from, date_to=date_to))


@router.post("/remove", response_model=RemoveResult)
def remove(body: RemoveIn, background: BackgroundTasks, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    """Take sales out (they are kept aside, so they can be restored)."""
    result = service.remove(db, user, body)
    background.add_task(refresh.run_recompute, user.tenant_id, user.id, "sales_change")
    return result


@router.post("/removals/{removal_id}/restore", response_model=RemoveResult)
def restore(removal_id: int, background: BackgroundTasks, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    result = service.restore(db, user, removal_id)
    background.add_task(refresh.run_recompute, user.tenant_id, user.id, "sales_change")
    return result


@router.delete("/removals/{removal_id}", response_model=RemovalOut)
def delete_forever(removal_id: int, user: User = Depends(require_role("owner")), db: Session = Depends(get_db)):
    """Owner: erase removed sales for good. This cannot be undone."""
    return service.delete_forever(db, user, removal_id)


@router.get("/template.csv")
def template(user: User = Depends(current_user)):
    return Response(service.TEMPLATE_CSV, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="sales_template.csv"'})

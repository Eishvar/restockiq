from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.auth import current_user, require_role
from app.db import get_db
from app.modules.planning import refresh
from app.modules.pos import service
from app.modules.pos.schemas import ConnectIn, FeedMeDay, FeedMePreview, ImportIn, ImportSummary, PosStatus
from app.modules.settings.models import User

router = APIRouter(prefix="/pos", tags=["pos"])


@router.get("/status", response_model=PosStatus)
def get_status(user: User = Depends(current_user), db: Session = Depends(get_db)):
    result = service.status(db, user)
    db.commit()  # status() may create the tenant's setup row
    return result


@router.post("/connect", response_model=PosStatus)
def connect(body: ConnectIn, user: User = Depends(require_role("owner")), db: Session = Depends(get_db)):
    """Setup step 2. FeedMe only for now; the connection is simulated (sales arrive by file upload)."""
    return service.connect(db, user, body.provider)


@router.post("/import/preview", response_model=ImportSummary)
def preview_import(body: ImportIn, user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    """Read the file and say what importing it would do. Saves nothing."""
    return service.preview(db, user, body.csv_text)


@router.post("/import", response_model=ImportSummary)
def import_sales(body: ImportIn, background: BackgroundTasks, user: User = Depends(require_role("manager")),
                 db: Session = Depends(get_db)):
    summary, remeasure = service.apply_import(db, user, body.filename, body.csv_text)
    if remeasure:  # a big catch-up changes what the safety buffers should learn from
        background.add_task(refresh.run_recompute, user.tenant_id, user.id, "sales_import")
    return summary


# ---- the simulated FeedMe screen (stands in for the real POS; see pos/feedme.py) ----

@router.get("/feedme/days", response_model=list[FeedMeDay])
def feedme_days(user: User = Depends(require_role("manager")), db: Session = Depends(get_db)):
    return service.feedme_days(db, user)


@router.get("/feedme/preview", response_model=FeedMePreview)
def feedme_preview(date_from: date = Query(), date_to: date = Query(), user: User = Depends(require_role("manager")),
                   db: Session = Depends(get_db)):
    return service.feedme_preview(db, user, date_from, date_to)


@router.get("/feedme/export.csv")
def feedme_export(date_from: date = Query(), date_to: date = Query(), user: User = Depends(require_role("manager")),
                  db: Session = Depends(get_db)):
    filename, text = service.feedme_csv(db, user, date_from, date_to)
    return Response(text, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})

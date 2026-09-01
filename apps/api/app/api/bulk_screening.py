import csv
from io import StringIO
from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile

from app.api.deps import ActorDep, DbDep
from app.schemas.bulk_screening import (
    BulkCriteriaConfirmRequest,
    BulkScreeningBatchRead,
    BulkScreeningBatchSummaryRead,
    BulkSupportedFormatsRead,
)
from app.services.bulk_screening import (
    add_resumes_to_batch,
    archive_batch,
    batch_to_read,
    batch_to_summary,
    confirm_ad_hoc_criteria,
    create_ad_hoc_jd_batch,
    create_existing_job_batch,
    discard_draft_batch,
    get_batch,
    list_batches,
    reconcile_ad_hoc_criteria,
    resume_failed_batch,
    safe_bulk_failure_message,
    start_batch,
    supported_bulk_formats,
)

router = APIRouter(prefix="/bulk-screening", tags=["bulk-screening"])


@router.get("/formats", response_model=BulkSupportedFormatsRead)
def api_bulk_supported_formats() -> dict[str, list[str]]:
    return supported_bulk_formats()


@router.get("/batches", response_model=list[BulkScreeningBatchSummaryRead])
def api_list_bulk_batches(db: DbDep, actor: ActorDep):
    return [batch_to_summary(batch) for batch in list_batches(db, actor)]


@router.get("/batches/{batch_id}", response_model=BulkScreeningBatchRead)
def api_get_bulk_batch(db: DbDep, actor: ActorDep, batch_id: str):
    return batch_to_read(get_batch(db, actor, batch_id))


@router.get("/batches/{batch_id}/export.csv")
def api_export_bulk_batch(db: DbDep, actor: ActorDep, batch_id: str):
    batch = get_batch(db, actor, batch_id)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "filename",
            "candidate_name",
            "classification",
            "status",
            "concise_reason",
            "failure_code",
            "failure_message",
        ]
    )
    for item in batch.items:
        writer.writerow(
            [
                item.original_filename,
                item.candidate_name,
                item.classification.value if item.classification else "",
                item.status.value,
                item.concise_reason,
                item.failure_code,
                safe_bulk_failure_message(item.failure_code, item.failure_message),
            ]
        )
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="bulk-screening-{batch.id}.csv"'},
    )


@router.post("/batches/existing-job", response_model=BulkScreeningBatchRead)
def api_create_existing_job_bulk_batch(
    db: DbDep,
    actor: ActorDep,
    job_id: Annotated[str, Form()],
    files: Annotated[list[UploadFile] | None, File()] = None,
    zip_file: Annotated[UploadFile | None, File()] = None,
):
    batch = create_existing_job_batch(db, actor, job_id=job_id, files=files, zip_file=zip_file)
    db.commit()
    return batch_to_read(batch)


@router.post("/batches/ad-hoc-jd", response_model=BulkScreeningBatchRead)
def api_create_ad_hoc_jd_bulk_batch(
    db: DbDep,
    actor: ActorDep,
    jd_file: Annotated[UploadFile, File()],
):
    batch = create_ad_hoc_jd_batch(db, actor, jd_file=jd_file)
    db.commit()
    return batch_to_read(batch)


@router.post("/batches/{batch_id}/confirm-criteria", response_model=BulkScreeningBatchRead)
def api_confirm_ad_hoc_bulk_criteria(
    db: DbDep,
    actor: ActorDep,
    batch_id: str,
    data: BulkCriteriaConfirmRequest,
):
    if data.confirmed:
        batch = confirm_ad_hoc_criteria(db, actor, batch_id, target_designation=data.target_designation)
    else:
        batch = get_batch(db, actor, batch_id)
    db.commit()
    return batch_to_read(batch)


@router.post("/batches/{batch_id}/reconcile-criteria", response_model=BulkScreeningBatchRead)
def api_reconcile_ad_hoc_bulk_criteria(
    db: DbDep,
    actor: ActorDep,
    batch_id: str,
    data: BulkCriteriaConfirmRequest,
):
    batch = reconcile_ad_hoc_criteria(db, actor, batch_id, target_designation=data.target_designation)
    db.commit()
    return batch_to_read(batch)


@router.post("/batches/{batch_id}/resumes", response_model=BulkScreeningBatchRead)
def api_add_bulk_resumes(
    db: DbDep,
    actor: ActorDep,
    batch_id: str,
    files: Annotated[list[UploadFile] | None, File()] = None,
    zip_file: Annotated[UploadFile | None, File()] = None,
):
    batch = add_resumes_to_batch(db, actor, batch_id, files=files, zip_file=zip_file)
    db.commit()
    return batch_to_read(batch)


@router.post("/batches/{batch_id}/start", response_model=BulkScreeningBatchRead)
def api_start_bulk_screening_batch(db: DbDep, actor: ActorDep, batch_id: str):
    batch = start_batch(db, actor, batch_id)
    db.commit()
    return batch_to_read(batch)


@router.post("/batches/{batch_id}/archive", response_model=BulkScreeningBatchRead)
def api_archive_bulk_screening_batch(db: DbDep, actor: ActorDep, batch_id: str):
    batch = archive_batch(db, actor, batch_id)
    db.commit()
    return batch_to_read(batch)


@router.post("/batches/{batch_id}/resume", response_model=BulkScreeningBatchRead)
def api_resume_failed_bulk_screening_batch(db: DbDep, actor: ActorDep, batch_id: str):
    batch = resume_failed_batch(db, actor, batch_id)
    db.commit()
    return batch_to_read(batch)


@router.delete("/batches/{batch_id}", status_code=204)
def api_discard_bulk_screening_batch(db: DbDep, actor: ActorDep, batch_id: str):
    discard_draft_batch(db, actor, batch_id)
    db.commit()
    return Response(status_code=204)

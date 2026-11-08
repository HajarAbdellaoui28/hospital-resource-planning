"""Registre local à travailleur unique pour les jobs d'expérience."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from hospital_planning.domain.contracts import JobResponse
from hospital_planning.domain.enums import JobStatus


@dataclass
class JobRecord:
    """État interne, sérialisé par `JobResponse`."""

    job_id: str
    created_at: datetime
    status: JobStatus = JobStatus.QUEUED
    started_at: datetime | None = None
    finished_at: datetime | None = None
    experiment_ids: list[str] = field(default_factory=list)
    error_message: str | None = None

    def response(self) -> JobResponse:
        return JobResponse(
            job_id=self.job_id,
            status=self.status,
            created_at=self.created_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            experiment_ids=self.experiment_ids,
            error_message=self.error_message,
        )


class JobRegistry:
    """Exécute au plus un job local afin de ne pas surallouer les solveurs."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hospital-job")
        self._records: dict[str, JobRecord] = {}
        self._lock = Lock()

    def submit(self, task: Callable[[], list[str]]) -> JobResponse:
        job_id = f"job-{uuid4().hex}"
        record = JobRecord(job_id=job_id, created_at=datetime.now(UTC))
        with self._lock:
            self._records[job_id] = record
        self._executor.submit(self._run, record, task)
        return record.response()

    def get(self, job_id: str) -> JobResponse | None:
        with self._lock:
            record = self._records.get(job_id)
            return record.response() if record else None

    def _run(self, record: JobRecord, task: Callable[[], list[str]]) -> None:
        with self._lock:
            record.status = JobStatus.RUNNING
            record.started_at = datetime.now(UTC)
        try:
            experiment_ids = task()
        except Exception as error:  # Le job doit conserver son échec sans masquer les autres jobs.
            with self._lock:
                record.status = JobStatus.FAILED
                record.error_message = str(error)
                record.finished_at = datetime.now(UTC)
            return
        with self._lock:
            record.status = JobStatus.COMPLETED
            record.experiment_ids = list(experiment_ids)
            record.finished_at = datetime.now(UTC)

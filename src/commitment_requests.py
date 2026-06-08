from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Iterable, List, Set, Tuple


MonthKey = str
VolumeKey = Tuple[int, int, int, MonthKey]


class RequestType(str, Enum):
    CHANGE_EXISTING_COMMITMENT = "change_existing_commitment"
    ADD_NEW_BUYER = "add_new_buyer"
    ADD_NEW_BUYER_COMMITMENT = "add_new_buyer_commitment"


class RequestStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"
    REVISION_REQUESTED = "revision_requested"


@dataclass
class CommitmentRequestLineItem:
    id: int
    program_item_id: int
    month: MonthKey
    current_committed_volume: float
    requested_committed_volume: float
    delta_volume: float

    def validate(self) -> None:
        if self.current_committed_volume < 0:
            raise ValueError("Current committed volume must be non-negative.")
        if self.requested_committed_volume < 0:
            raise ValueError("Requested committed volume must be non-negative.")
        expected_delta = self.requested_committed_volume - self.current_committed_volume
        if round(expected_delta, 6) != round(self.delta_volume, 6):
            raise ValueError("Delta volume must equal requested volume minus current volume.")


@dataclass
class CommitmentRequest:
    id: int
    program_id: int
    request_type: RequestType
    requesting_buyer_id: int
    target_buyer_id: int
    requested_by_user_id: int
    status: RequestStatus
    reason_comment: str
    created_at: datetime
    line_items: List[CommitmentRequestLineItem] = field(default_factory=list)
    reviewed_by_user_id: int | None = None
    reviewed_at: datetime | None = None
    host_comment: str | None = None

    def validate(self) -> None:
        if not self.reason_comment.strip():
            raise ValueError("Reason/comment is required.")

        if self.request_type == RequestType.CHANGE_EXISTING_COMMITMENT and not self.line_items:
            raise ValueError("Change Existing Commitment requests must include line items.")

        if self.request_type == RequestType.ADD_NEW_BUYER and self.line_items:
            raise ValueError("Add New Buyer requests must not include commitment line items.")

        if self.request_type == RequestType.ADD_NEW_BUYER_COMMITMENT and not self.line_items:
            raise ValueError("Add New Buyer + Commitment requests must include line items.")

        changed_line_found = False
        for line_item in self.line_items:
            line_item.validate()
            if line_item.current_committed_volume != line_item.requested_committed_volume:
                changed_line_found = True

        if self.request_type == RequestType.CHANGE_EXISTING_COMMITMENT and not changed_line_found:
            raise ValueError("At least one line item must change volume.")

    def ensure_reviewable(self) -> None:
        if self.status not in {RequestStatus.PENDING, RequestStatus.REVISION_REQUESTED}:
            raise ValueError(f"Request {self.id} is not reviewable from status {self.status.value}.")


@dataclass
class CommitmentVolumeAuditRecord:
    commitment_request_id: int
    commitment_request_line_item_id: int | None
    program_id: int
    buyer_id: int
    program_item_id: int
    month: MonthKey
    old_volume: float
    new_volume: float
    delta_volume: float
    approved_by_user_id: int
    approved_at: datetime


@dataclass
class CommitmentStore:
    participants: Set[Tuple[int, int]] = field(default_factory=set)
    committed_volumes: Dict[VolumeKey, float] = field(default_factory=dict)
    audit_records: List[CommitmentVolumeAuditRecord] = field(default_factory=list)

    def get_committed_volume(self, program_id: int, buyer_id: int, program_item_id: int, month: MonthKey) -> float:
        return self.committed_volumes.get((program_id, buyer_id, program_item_id, month), 0.0)

    def set_committed_volume(
        self,
        program_id: int,
        buyer_id: int,
        program_item_id: int,
        month: MonthKey,
        committed_volume: float,
    ) -> None:
        self.committed_volumes[(program_id, buyer_id, program_item_id, month)] = committed_volume

    def add_participant(self, program_id: int, buyer_id: int) -> None:
        self.participants.add((program_id, buyer_id))

    def has_participant(self, program_id: int, buyer_id: int) -> bool:
        return (program_id, buyer_id) in self.participants


class CommitmentRequestService:
    def __init__(self, store: CommitmentStore) -> None:
        self.store = store

    def submit(self, request: CommitmentRequest) -> CommitmentRequest:
        request.validate()
        request.status = RequestStatus.PENDING
        return request

    def approve(self, request: CommitmentRequest, reviewed_by_user_id: int, host_comment: str | None = None) -> CommitmentRequest:
        request.ensure_reviewable()
        request.validate()

        approved_at = datetime.utcnow()
        target_buyer_id = request.target_buyer_id

        if request.request_type in {RequestType.ADD_NEW_BUYER, RequestType.ADD_NEW_BUYER_COMMITMENT}:
            self.store.add_participant(request.program_id, target_buyer_id)

        if request.request_type == RequestType.CHANGE_EXISTING_COMMITMENT and not self.store.has_participant(
            request.program_id,
            target_buyer_id,
        ):
            raise ValueError("Target buyer must already belong to the program for commitment changes.")

        for line_item in request.line_items:
            old_volume = self.store.get_committed_volume(
                request.program_id,
                target_buyer_id,
                line_item.program_item_id,
                line_item.month,
            )
            new_volume = line_item.requested_committed_volume
            self.store.set_committed_volume(
                request.program_id,
                target_buyer_id,
                line_item.program_item_id,
                line_item.month,
                new_volume,
            )
            self.store.audit_records.append(
                CommitmentVolumeAuditRecord(
                    commitment_request_id=request.id,
                    commitment_request_line_item_id=line_item.id,
                    program_id=request.program_id,
                    buyer_id=target_buyer_id,
                    program_item_id=line_item.program_item_id,
                    month=line_item.month,
                    old_volume=old_volume,
                    new_volume=new_volume,
                    delta_volume=new_volume - old_volume,
                    approved_by_user_id=reviewed_by_user_id,
                    approved_at=approved_at,
                )
            )

        request.status = RequestStatus.APPROVED
        request.reviewed_by_user_id = reviewed_by_user_id
        request.reviewed_at = approved_at
        request.host_comment = host_comment
        return request

    def decline(self, request: CommitmentRequest, reviewed_by_user_id: int, host_comment: str | None = None) -> CommitmentRequest:
        request.ensure_reviewable()
        request.status = RequestStatus.DECLINED
        request.reviewed_by_user_id = reviewed_by_user_id
        request.reviewed_at = datetime.utcnow()
        request.host_comment = host_comment
        return request

    def request_revision(self, request: CommitmentRequest, reviewed_by_user_id: int, host_comment: str) -> CommitmentRequest:
        request.ensure_reviewable()
        if not host_comment.strip():
            raise ValueError("Host comment is required when requesting revision.")
        request.status = RequestStatus.REVISION_REQUESTED
        request.reviewed_by_user_id = reviewed_by_user_id
        request.reviewed_at = datetime.utcnow()
        request.host_comment = host_comment
        return request


def build_change_request(
    request_id: int,
    program_id: int,
    buyer_id: int,
    requested_by_user_id: int,
    reason_comment: str,
    line_items: Iterable[CommitmentRequestLineItem],
) -> CommitmentRequest:
    return CommitmentRequest(
        id=request_id,
        program_id=program_id,
        request_type=RequestType.CHANGE_EXISTING_COMMITMENT,
        requesting_buyer_id=buyer_id,
        target_buyer_id=buyer_id,
        requested_by_user_id=requested_by_user_id,
        status=RequestStatus.PENDING,
        reason_comment=reason_comment,
        created_at=datetime.utcnow(),
        line_items=list(line_items),
    )


def build_add_buyer_request(
    request_id: int,
    program_id: int,
    host_buyer_id: int,
    target_buyer_id: int,
    requested_by_user_id: int,
    reason_comment: str,
    line_items: Iterable[CommitmentRequestLineItem] | None = None,
) -> CommitmentRequest:
    items = list(line_items or [])
    request_type = (
        RequestType.ADD_NEW_BUYER_COMMITMENT if items else RequestType.ADD_NEW_BUYER
    )
    return CommitmentRequest(
        id=request_id,
        program_id=program_id,
        request_type=request_type,
        requesting_buyer_id=host_buyer_id,
        target_buyer_id=target_buyer_id,
        requested_by_user_id=requested_by_user_id,
        status=RequestStatus.PENDING,
        reason_comment=reason_comment,
        created_at=datetime.utcnow(),
        line_items=items,
    )

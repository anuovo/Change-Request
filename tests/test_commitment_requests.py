import unittest

from src.commitment_requests import (
    CommitmentRequestLineItem,
    CommitmentRequestService,
    CommitmentStore,
    RequestStatus,
    build_add_buyer_request,
    build_change_request,
)


class CommitmentRequestServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = CommitmentStore()
        self.service = CommitmentRequestService(self.store)
        self.program_id = 100
        self.buyer_id = 200
        self.host_user_id = 9000
        self.buyer_user_id = 9100

        self.store.add_participant(self.program_id, self.buyer_id)
        self.store.set_committed_volume(self.program_id, self.buyer_id, 3000, "2026-08", 100.0)

    def test_buyer_can_submit_and_host_approve_commitment_change(self) -> None:
        request = build_change_request(
            request_id=1,
            program_id=self.program_id,
            buyer_id=self.buyer_id,
            requested_by_user_id=self.buyer_user_id,
            reason_comment="Demand increased for August.",
            line_items=[
                CommitmentRequestLineItem(
                    id=10,
                    program_item_id=3000,
                    month="2026-08",
                    current_committed_volume=100.0,
                    requested_committed_volume=140.0,
                    delta_volume=40.0,
                )
            ],
        )

        self.service.submit(request)
        self.assertEqual(self.store.get_committed_volume(self.program_id, self.buyer_id, 3000, "2026-08"), 100.0)

        approved = self.service.approve(request, reviewed_by_user_id=self.host_user_id, host_comment="Approved.")

        self.assertEqual(approved.status, RequestStatus.APPROVED)
        self.assertEqual(self.store.get_committed_volume(self.program_id, self.buyer_id, 3000, "2026-08"), 140.0)
        self.assertEqual(len(self.store.audit_records), 1)
        audit = self.store.audit_records[0]
        self.assertEqual(audit.old_volume, 100.0)
        self.assertEqual(audit.new_volume, 140.0)
        self.assertEqual(audit.delta_volume, 40.0)
        self.assertEqual(audit.approved_by_user_id, self.host_user_id)

    def test_declined_request_does_not_update_committed_volume(self) -> None:
        request = build_change_request(
            request_id=2,
            program_id=self.program_id,
            buyer_id=self.buyer_id,
            requested_by_user_id=self.buyer_user_id,
            reason_comment="Buyer wants to reduce expected volume.",
            line_items=[
                CommitmentRequestLineItem(
                    id=11,
                    program_item_id=3000,
                    month="2026-08",
                    current_committed_volume=100.0,
                    requested_committed_volume=80.0,
                    delta_volume=-20.0,
                )
            ],
        )

        declined = self.service.decline(request, reviewed_by_user_id=self.host_user_id, host_comment="Need more justification.")

        self.assertEqual(declined.status, RequestStatus.DECLINED)
        self.assertEqual(self.store.get_committed_volume(self.program_id, self.buyer_id, 3000, "2026-08"), 100.0)
        self.assertEqual(len(self.store.audit_records), 0)

    def test_host_can_add_new_buyer_with_commitments_using_same_workflow(self) -> None:
        new_buyer_id = 201
        request = build_add_buyer_request(
            request_id=3,
            program_id=self.program_id,
            host_buyer_id=999,
            target_buyer_id=new_buyer_id,
            requested_by_user_id=self.host_user_id,
            reason_comment="Adding a new buyer with launch commitments.",
            line_items=[
                CommitmentRequestLineItem(
                    id=12,
                    program_item_id=3001,
                    month="2026-09",
                    current_committed_volume=0.0,
                    requested_committed_volume=55.0,
                    delta_volume=55.0,
                )
            ],
        )

        approved = self.service.approve(request, reviewed_by_user_id=self.host_user_id)

        self.assertEqual(approved.status, RequestStatus.APPROVED)
        self.assertTrue(self.store.has_participant(self.program_id, new_buyer_id))
        self.assertEqual(self.store.get_committed_volume(self.program_id, new_buyer_id, 3001, "2026-09"), 55.0)
        self.assertEqual(len(self.store.audit_records), 1)

    def test_revision_request_requires_host_comment(self) -> None:
        request = build_change_request(
            request_id=4,
            program_id=self.program_id,
            buyer_id=self.buyer_id,
            requested_by_user_id=self.buyer_user_id,
            reason_comment="Need updated September plan.",
            line_items=[
                CommitmentRequestLineItem(
                    id=13,
                    program_item_id=3000,
                    month="2026-08",
                    current_committed_volume=100.0,
                    requested_committed_volume=105.0,
                    delta_volume=5.0,
                )
            ],
        )

        with self.assertRaises(ValueError):
            self.service.request_revision(request, reviewed_by_user_id=self.host_user_id, host_comment=" ")

    def test_change_request_requires_actual_delta(self) -> None:
        request = build_change_request(
            request_id=5,
            program_id=self.program_id,
            buyer_id=self.buyer_id,
            requested_by_user_id=self.buyer_user_id,
            reason_comment="Trying to submit an unchanged request.",
            line_items=[
                CommitmentRequestLineItem(
                    id=14,
                    program_item_id=3000,
                    month="2026-08",
                    current_committed_volume=100.0,
                    requested_committed_volume=100.0,
                    delta_volume=0.0,
                )
            ],
        )

        with self.assertRaises(ValueError):
            self.service.submit(request)


if __name__ == "__main__":
    unittest.main()

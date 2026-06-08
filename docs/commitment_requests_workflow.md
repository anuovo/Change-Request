# Commitment Requests Workflow

## Goal

Create one unified workflow for all program participation changes:

1. Change Existing Commitment
2. Add New Buyer
3. Add New Buyer + Commitment

This keeps approval logic, audit history, and user expectations consistent.

## Core principles

- `Volumes` shows approved commitments only.
- Pending or declined changes never alter the live committed volume table.
- All commitment changes are represented as a `Commitment Request` with line items.
- Approval writes both the new commitment values and an immutable audit trail.

## Program navigation

Program tabs remain:

- `Pricing`
- `Volumes`
- `Compliance`
- `Participants`
- `Commitment Requests`

## Request types

### 1. Change Existing Commitment

Initiated by a buyer-side user from `Program > Volumes`.

Behavior:

- button label: `Request Commitment Change`
- display current commitments by item and month
- buyer edits requested volumes
- system calculates `delta_volume = requested_committed_volume - current_committed_volume`
- user must provide a reason/comment
- submission creates a `pending` request for host review
- approved values do not apply until host approval

### 2. Add New Buyer

Initiated by a host buyer from `Program > Participants` or `Program > Commitment Requests`.

Behavior:

- button label: `Add Buyer to Program`
- host selects a buyer
- creates a request with type `add_new_buyer`
- may be stored directly as `approved` if the host action is considered self-approving

Use this when a buyer should be attached to the program without immediate volume commitments.

### 3. Add New Buyer + Commitment

Initiated by a host buyer from the same `Add Buyer to Program` entry point.

Behavior:

- host selects buyer
- host enters monthly commitment by item and month
- request type is `add_new_buyer_commitment`
- same request-line structure is used as a normal change request
- if host action is self-approving, save the request as `approved` and apply the commitments immediately

## Status model

Supported statuses:

- `pending`
- `approved`
- `declined`
- `revision_requested`

Recommended transitions:

- `pending -> approved`
- `pending -> declined`
- `pending -> revision_requested`
- `revision_requested -> pending`

Terminal states:

- `approved`
- `declined`

## Buyer-side UX

Location:

- `Program > Volumes`

Primary action:

- `Request Commitment Change`

Form contents:

- buyer identity and program context
- current monthly commitments grid by item/month
- editable requested volume inputs
- read-only current volume
- read-only delta
- required comment/reason

Submission rules:

- at least one line must change for `change_existing_commitment`
- comment is required
- requested volume must be zero or positive
- line items are stored separately from live commitment rows

Post-submit:

- show success message
- keep live `Volumes` unchanged
- show pending request in `Commitment Requests`

## Host-buyer UX

Location:

- `Program > Commitment Requests`

List columns:

- Buyer
- Request type
- Item
- Month
- Current volume
- Requested volume
- Delta
- Reason/comment
- Submitted date
- Status

Available actions for pending requests:

- `Approve`
- `Decline`
- `Request Revision`

Action behavior:

- Approve applies changes, writes audit rows, marks request approved
- Decline leaves commitments unchanged, records host comment if provided
- Request Revision leaves commitments unchanged, records host comment, marks request `revision_requested`

## Data model

### commitment_requests

- `program_id`
- `request_type`
- `requesting_buyer_id`
- `target_buyer_id`
- `requested_by_user_id`
- `status`
- `reason_comment`
- `created_at`
- `reviewed_by_user_id`
- `reviewed_at`
- `host_comment`

### commitment_request_line_items

- `program_item_id`
- `month`
- `current_committed_volume`
- `requested_committed_volume`
- `delta_volume`

### committed_volumes

Live table used by the `Volumes` tab:

- `program_id`
- `buyer_id`
- `program_item_id`
- `month`
- `committed_volume`

### commitment_volume_audit

Immutable audit log for approved changes:

- `commitment_request_id`
- `commitment_request_line_item_id`
- `program_id`
- `buyer_id`
- `program_item_id`
- `month`
- `old_volume`
- `new_volume`
- `delta_volume`
- `approved_by_user_id`
- `approved_at`

## Approval logic

When host approves:

1. Validate request is reviewable.
2. If request adds a buyer, ensure the buyer is attached to the program.
3. For each line item:
4. Load current committed volume for `program + buyer + item + month`.
5. Preserve `old_volume`.
6. Write `new_volume`.
7. Write audit row with before/after values and approver metadata.
8. Mark request `approved`.

When host declines:

1. Validate request is reviewable.
2. Save status `declined`.
3. Save optional host comment.
4. Do not update committed volumes.

When host requests revision:

1. Validate request is reviewable.
2. Save status `revision_requested`.
3. Save host comment explaining the needed change.
4. Do not update committed volumes.

## Recommended API surface

### Buyer actions

- `POST /programs/:program_id/commitment-requests`
- `POST /commitment-requests/:id/resubmit`

### Host actions

- `GET /programs/:program_id/commitment-requests`
- `POST /commitment-requests/:id/approve`
- `POST /commitment-requests/:id/decline`
- `POST /commitment-requests/:id/request-revision`
- `POST /programs/:program_id/commitment-requests/add-buyer`

## Example request payload

```json
{
  "program_id": 42,
  "request_type": "change_existing_commitment",
  "requesting_buyer_id": 12,
  "target_buyer_id": 12,
  "requested_by_user_id": 3001,
  "reason_comment": "Expected seasonal lift in August and September.",
  "line_items": [
    {
      "program_item_id": 900,
      "month": "2026-08",
      "current_committed_volume": 100,
      "requested_committed_volume": 130,
      "delta_volume": 30
    },
    {
      "program_item_id": 900,
      "month": "2026-09",
      "current_committed_volume": 100,
      "requested_committed_volume": 120,
      "delta_volume": 20
    }
  ]
}
```

## Notes on implementation

- Use database transactions around approval.
- Lock the live committed-volume rows during approval to avoid race conditions.
- Recompute or validate line-item `current_committed_volume` at approval time if stale data is a concern.
- Keep `Volumes` free of pending overlays to avoid ambiguity.

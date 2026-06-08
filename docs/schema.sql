CREATE TABLE commitment_requests (
    id BIGSERIAL PRIMARY KEY,
    program_id BIGINT NOT NULL,
    request_type VARCHAR(64) NOT NULL,
    requesting_buyer_id BIGINT NOT NULL,
    target_buyer_id BIGINT NOT NULL,
    requested_by_user_id BIGINT NOT NULL,
    status VARCHAR(32) NOT NULL,
    reason_comment TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_by_user_id BIGINT NULL,
    reviewed_at TIMESTAMP NULL,
    host_comment TEXT NULL,
    CONSTRAINT chk_commitment_request_type
        CHECK (request_type IN (
            'change_existing_commitment',
            'add_new_buyer',
            'add_new_buyer_commitment'
        )),
    CONSTRAINT chk_commitment_request_status
        CHECK (status IN (
            'pending',
            'approved',
            'declined',
            'revision_requested'
        ))
);

CREATE INDEX idx_commitment_requests_program_status
    ON commitment_requests (program_id, status, created_at DESC);

CREATE INDEX idx_commitment_requests_target_buyer
    ON commitment_requests (target_buyer_id, created_at DESC);

CREATE TABLE commitment_request_line_items (
    id BIGSERIAL PRIMARY KEY,
    commitment_request_id BIGINT NOT NULL REFERENCES commitment_requests(id) ON DELETE CASCADE,
    program_item_id BIGINT NOT NULL,
    month DATE NOT NULL,
    current_committed_volume NUMERIC(14, 2) NOT NULL DEFAULT 0,
    requested_committed_volume NUMERIC(14, 2) NOT NULL DEFAULT 0,
    delta_volume NUMERIC(14, 2) NOT NULL,
    CONSTRAINT chk_non_negative_current_volume
        CHECK (current_committed_volume >= 0),
    CONSTRAINT chk_non_negative_requested_volume
        CHECK (requested_committed_volume >= 0)
);

CREATE INDEX idx_request_line_items_request
    ON commitment_request_line_items (commitment_request_id);

CREATE TABLE program_participants (
    id BIGSERIAL PRIMARY KEY,
    program_id BIGINT NOT NULL,
    buyer_id BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (program_id, buyer_id)
);

CREATE TABLE committed_volumes (
    id BIGSERIAL PRIMARY KEY,
    program_id BIGINT NOT NULL,
    buyer_id BIGINT NOT NULL,
    program_item_id BIGINT NOT NULL,
    month DATE NOT NULL,
    committed_volume NUMERIC(14, 2) NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_non_negative_committed_volume
        CHECK (committed_volume >= 0),
    UNIQUE (program_id, buyer_id, program_item_id, month)
);

CREATE INDEX idx_committed_volumes_program_buyer
    ON committed_volumes (program_id, buyer_id);

CREATE TABLE commitment_volume_audit (
    id BIGSERIAL PRIMARY KEY,
    commitment_request_id BIGINT NOT NULL REFERENCES commitment_requests(id),
    commitment_request_line_item_id BIGINT NULL REFERENCES commitment_request_line_items(id),
    program_id BIGINT NOT NULL,
    buyer_id BIGINT NOT NULL,
    program_item_id BIGINT NOT NULL,
    month DATE NOT NULL,
    old_volume NUMERIC(14, 2) NOT NULL,
    new_volume NUMERIC(14, 2) NOT NULL,
    delta_volume NUMERIC(14, 2) NOT NULL,
    approved_by_user_id BIGINT NOT NULL,
    approved_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_commitment_volume_audit_program_buyer
    ON commitment_volume_audit (program_id, buyer_id, approved_at DESC);

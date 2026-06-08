# Program Commitment Requests

This workspace contains a clean, unified workflow design for Program Commitment Requests in Growerstock.

It includes:

- a product and UX workflow in [docs/commitment_requests_workflow.md](/Users/tonynuovo/Documents/Codex/Program%20Change%20Request/docs/commitment_requests_workflow.md)
- a normalized SQL schema in [docs/schema.sql](/Users/tonynuovo/Documents/Codex/Program%20Change%20Request/docs/schema.sql)
- a small reference domain implementation in [src/commitment_requests.py](/Users/tonynuovo/Documents/Codex/Program%20Change%20Request/src/commitment_requests.py)
- executable approval and validation tests in [tests/test_commitment_requests.py](/Users/tonynuovo/Documents/Codex/Program%20Change%20Request/tests/test_commitment_requests.py)

## Design summary

All participation changes use one `commitment_requests` framework:

- `change_existing_commitment`
- `add_new_buyer`
- `add_new_buyer_commitment`

The `Volumes` tab remains the source of truth for approved/current commitments only. Pending changes live under `Commitment Requests`.

## Run tests

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

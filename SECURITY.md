# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.x     | :white_check_mark: |
| < 2.0   | :x:                |

## Threat Model & Invariants

Mellon is an enterprise deployment framework and field toolkit for operational systems.
The primary security objective is deterministic separation between probabilistic reasoning (LLMs) and deterministic invariants (systems of record).

Key principles enforced:
- Zero direct untrusted mutations to transactional databases without cryptographic review.
- Dry-run validation and contract checks via Pydantic v2 schemas.
- Ephemeral execution environments without persistent production credentials.

## Reporting a Vulnerability

If you discover a security vulnerability or sensitive leakage, please do not open a public issue.
Instead, report it directly via GitHub Private Vulnerability Reporting or contact:
`esstipi@gmail.com`

We will review reports within 48 hours and coordinate responsible disclosure.

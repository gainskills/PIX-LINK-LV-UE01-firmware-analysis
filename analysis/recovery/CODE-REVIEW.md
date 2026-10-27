# Read-only backup review

Independent reviewer inspected the reader, adaptive segmentation, full capture and offline validator without AP/network access. No concrete device-write, address-mapping, reconstructed-copy integrity, timeout-cleanup or resume-hash defect identified.

One P2 finding was fixed: `mkdir(mode=0700, exist_ok=True)` does not tighten permissions of an existing destination. `DEST.chmod(0o700)` now runs before acquisition. A regression test first failed with observed0755, then passed with0700. The currently running capture was freshly created0700 and was unaffected.

Reviewer ran17 offline tests successfully before this additional regression was added. Parent validation also includes the localhost-only split-response test. Actual whole-device capture is a separate verification step; tests alone are not evidence of completed backups, JEDEC identity, boot compatibility or recovery.

## Final validation

Reviewer also checked the bounded reconnect/partial-response handling and whole-pair reacquisition changes: no additional issue identified. Rejected pairs are archived, reconstruction starts afresh, and two failed pairs stop acquisition; no majority merging. All four offline pipeline tests passed in the review. Parent ran the complete 20-test suite including the localhost transport fixture: PASS, no AP access.

Live capture subsequently completed both 2 MiB files. Independent verification checked all 128 block pairs, whole-file agreement, private permissions, and original uImage CRCs/SHA. This validates the captured backup, not JEDEC identity, restoration or candidate boot compatibility. The recovery survey console summary was also corrected to report its computed completion field rather than a historical hardcoded false; the evidence JSON already used the computed result.

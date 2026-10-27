# Independent review

Scope: `patch.py`, `builder.py`, `test_patch.py`, `build-manifest.json`; independent read-only reviewer, no AP access, no edits or further delegation. This directory is not a Git repository; review used the files directly.

No concrete defects found. Reviewed exact command matching and legacy tail call; O32 40-byte frame with 16-byte outgoing argument area; saved registers; reader bounds and cleanup; trace register/status preservation and original prologue replay; source hash guards; allowed patch ranges; fixed container size, CRC construction and LZMA roundtrip.

Hardware assumptions remain: PCR0 command/busy bits clear after completion, PCR1 completion/data are fresh for each transaction, MMIO ordering, and pinmux timing. Simulated MMIO assumes these properties. Real cache execution, boot and recovery have not been tested. No hardware safety or root-cause fix claimed.

Reviewer could not independently execute Unicorn inside the sandbox (exit 132); parent executed the suite outside the sandbox with approval, 10 tests passed. Actual written artifacts also passed the separate standard-library/Capstone `verify.py` checks. Machine-readable evidence is adjacent.

## Native argument-register observation

Further disassembly of0x8014fca8 shows the variadic entry also spilling registers t0–t3, and native multi-argument call sites use them. General O32 compatibility is therefore not established. This payload's printf calls use only a0–a3 (format plus at most three values), and its other native calls use at most two arguments, matching the observed register subset. Its40-byte aligned frame and preserved registers remain valid for these specific calls; do not extend logging to additional arguments using O32 stack assumptions. No payload bytes were changed by this clarification.

## Combined baseline scope follow-up

Independent reviewer found an Important scope issue: the existing image inherits the UI/default changes; three diagnostic ranges apply only relative to that UI baseline. Parent independently reproduced byte counts152822/496/152845 and corrected README, builder/manifest baseline wording and verifier labels. A stale full-backup limitation was corrected; actual recovery/boot remain untested. Binary hashes are unchanged. Reviewer verified corrections and independently reproduced the original-baseline/favicon-only in-memory proposal (1064 changed bytes, nice128 compressed708646). Parent additionally checked nice273 (oversize; rejected) and nice64 (708598,166bytes remaining). This remains feasibility evidence, not a new build or hardware validation. See CANDIDATE-SCOPE-REVIEW.md.

## Original-baseline build review

Implemented the previously modeled original/favicon-only baseline in a separate output directory. New contracts were RED against the UI-only builder, then GREEN. Independent reviewer found an Important selected-baseline source guard issue; regression tests reproduced both known-source swaps in temporary trees, then passed after an explicit selected-hash require before any output. Current binaries independently match original-based modeled main,1064changed bytes, unchanged payload and loader, original header exceptCRCs, valid CRCs,708598compressed bytes and166FFpadding. Reviewer inspected the independent verifier and mutation tests; no further blocking findings. Full local diagnostic discovery:21tests,0failures,0errors. Three malformed/tampered artifact cases plus the selected-baseline swap regression are covered; no hardware, recovery or startup claim. Original combined binaries remain unchanged.

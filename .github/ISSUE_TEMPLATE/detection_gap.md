---
name: Detection gap or false positive
about: Report a missed PII entity or an over-redacted false positive
title: '[DETECTION] '
labels: detection
assignees: ''
---

**⚠️ Synthetic Data Only**: Never include real names, phone numbers, BVNs, NINs, account numbers, or real API keys. Use fictional or fabricated values only.

**Type of issue**
- [ ] Missed entity (False Negative)
- [ ] Over-redacted entity (False Positive)

**Entity Type**
[e.g. PERSON, BVN, NIN, ACCOUNT_NO, PHONE, EMAIL]

**Synthetic Input Text**
```text
(Paste synthetic sentence here)
```

**Observed Scrubbed Text**
```text
(What Aegis produced)
```

**Expected Scrubbed Text**
```text
(What should have been produced)
```

**Context or Additional Notes**
(e.g., Nigerian dialect, unusual punctuation, title prefix, etc.)

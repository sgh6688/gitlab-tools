# Security policy

## Supported versions

Security fixes are provided for the latest published release and the current `main` branch.

| Version | Supported |
|---|---|
| 0.3.x | Yes |
| Earlier versions | No |

## Report a vulnerability privately

Do not open a public Issue for a suspected vulnerability or include tokens, private GitLab URLs, internal project names, or exported data in a report.

Use [GitHub private vulnerability reporting](https://github.com/sgh6688/gitlab-tools/security/advisories/new). Include:

- affected version or commit;
- the command or component involved;
- reproduction steps using synthetic data;
- expected and observed behavior;
- impact and suggested mitigation, if known.

You may omit exploit details until a maintainer confirms receipt. The project will coordinate disclosure after a fix is available.

## Scope

Examples of relevant reports include credential exposure, authentication sent to the wrong origin, unsafe redirects, path traversal, symlink or junction escapes, command injection, unsafe Git configuration, and sensitive data written to logs.

Reports that require a user to deliberately provide an attacker-controlled GitLab token or run modified source code are generally outside the threat model, but defensive improvements are still welcome as regular Issues.

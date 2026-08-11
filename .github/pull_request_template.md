## Summary

<!-- What changed, and why? -->

## Verification

<!-- List the exact commands and results used to verify the change. -->

- [ ] `python -m compileall -q gitlab_tools tests`
- [ ] `python -m unittest discover -s tests -v`
- [ ] `git diff --check`
- [ ] Wheel build/install checked when packaging or templates changed

## Compatibility and safety

- [ ] I used synthetic data and did not include tokens, private URLs, organization names, usernames, or exported production data.
- [ ] I preserved Python 3.11 compatibility.
- [ ] I updated English and Chinese documentation for user-facing changes.
- [ ] I did not weaken authentication scoping, redirect handling, path validation, or credential redaction.

## Related Issue

<!-- Example: Closes #123 -->

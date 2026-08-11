# Contributing

Thanks for helping improve `gitlab-tools`. Small, focused changes are easier to review and maintain.

## Before opening a change

- Search existing Issues first.
- Open a feature request before starting a large feature or changing CLI/configuration compatibility.
- Never include a real GitLab token, internal hostname, private IP address, organization name, username, or production export in an Issue, test, example, or commit.
- Use `gitlab.example.com`, `example-org`, and synthetic data in reproductions.

Security vulnerabilities should follow [SECURITY.md](SECURITY.md), not a public Issue.

## Development setup

Python 3.11 or newer is required. Runtime code has no third-party dependencies.

```console
git clone https://github.com/sgh6688/gitlab-tools.git
cd gitlab-tools
python -m venv .venv
```

Activate the environment:

```console
# Windows CMD
.venv\Scripts\activate.bat

# PowerShell
.venv\Scripts\Activate.ps1

# macOS or Linux
source .venv/bin/activate
```

Run the quality gates:

```console
python -m compileall -q gitlab_tools tests
python -m unittest discover -s tests -v
python -m pip wheel --no-deps --wheel-dir dist .
```

## Pull requests

- Keep one purpose per pull request.
- Add or update tests for behavior changes. For bugs, write a failing regression test before the fix.
- Update both English and Chinese documentation when user-facing commands or configuration change.
- Preserve Python 3.11 compatibility and the no-third-party-runtime-dependency rule.
- Do not weaken token scoping, redirect checks, path validation, or credential redaction.
- Confirm `git diff --check` passes.

Explain what changed, why it changed, and how it was tested. Maintainers may ask to split unrelated work.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

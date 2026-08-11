@echo off
setlocal

pushd "%~dp0\..\.." || exit /b 1

if not exist gitlab.config.txt (
  echo gitlab.config.txt not found.
  echo Run from the repository root: py -m gitlab_tools repositories init-config
  popd
  exit /b 1
)

if not exist repositories.config.txt (
  echo repositories.config.txt not found.
  echo Run from the repository root: py -m gitlab_tools repositories init-config
  popd
  exit /b 1
)

py -m gitlab_tools repositories export --gitlab-config gitlab.config.txt --config repositories.config.txt
set "exit_code=%errorlevel%"
popd
exit /b %exit_code%

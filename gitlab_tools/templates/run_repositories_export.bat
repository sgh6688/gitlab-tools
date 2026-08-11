@echo off
setlocal

if not exist gitlab.config.txt (
  echo gitlab.config.txt not found.
  echo Run: py -m gitlab_tools repositories init-config
  exit /b 1
)

if not exist repositories.config.txt (
  echo repositories.config.txt not found.
  echo Run: py -m gitlab_tools repositories init-config
  exit /b 1
)

py -m gitlab_tools repositories export --gitlab-config gitlab.config.txt --config repositories.config.txt

@echo off
setlocal

if not exist milestones.config.txt (
  echo milestones.config.txt not found.
  echo Run: py -m gitlab_tools milestones init-config
  exit /b 1
)

py -m gitlab_tools milestones export --config milestones.config.txt

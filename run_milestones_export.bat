@echo off
setlocal

if not exist milestones.config.txt (
  echo milestones.config.txt not found.
  echo Copy configs\milestones.example.txt to milestones.config.txt and fill in your settings first.
  exit /b 1
)

py -m gitlab_tools milestones export --config milestones.config.txt

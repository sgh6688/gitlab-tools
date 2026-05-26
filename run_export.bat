@echo off
setlocal

if not exist config.txt (
  echo config.txt not found. Copy config.example.txt to config.txt and fill in your settings first.
  exit /b 1
)

py -m gitlab_milestone_exporter --config config.txt

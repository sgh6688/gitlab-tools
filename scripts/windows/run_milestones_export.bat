@echo off
setlocal

pushd "%~dp0\..\.." || exit /b 1

if not exist milestones.config.txt (
  echo milestones.config.txt not found.
  echo Copy configs\milestones.example.txt to milestones.config.txt and fill in your settings first.
  popd
  exit /b 1
)

py -m gitlab_tools milestones export --config milestones.config.txt
set "exit_code=%errorlevel%"
popd
exit /b %exit_code%

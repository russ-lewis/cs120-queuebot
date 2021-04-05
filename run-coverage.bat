@echo OFF

@REM https://github.com/ryanluker/vscode-coverage-gutters/issues/224#issuecomment-530197803
venv\Scripts\coverage.exe run --omit 'venv/*' -m unittest
venv\Scripts\coverage.exe xml -o cov.xml
@REM venv\Scripts\coverage.exe html

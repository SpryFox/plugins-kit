@echo off
:: UE Python Script Runner — wrapper that ensures Python + deps are available.
:: Uses uv to provide an isolated environment with upyrc and pyyaml.
uv run --with upyrc --with pyyaml python "%~dp0ue_runner.py" %*

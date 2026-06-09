@echo off
setlocal

cd /d "%~dp0"

if exist ".env.local" (
  for /f "usebackq tokens=1,* delims==" %%A in (".env.local") do (
    if not "%%A"=="" if not "%%A:~0,1%"=="#" set "%%A=%%B"
  )
)

if not "%~1"=="" (
  if "%~1"=="all" (
    set "LLM_LIMIT="
  ) else (
    set "LLM_LIMIT=%~1"
  )
)

if "%DEEPSEEK_API_KEY%"=="" if "%LLM_API_KEY%"=="" (
  echo Missing DEEPSEEK_API_KEY or LLM_API_KEY.
  echo Create .env.local from .env.local.example and put your key there.
  exit /b 1
)

if "%LLM_MODEL%"=="" set "LLM_MODEL=deepseek-v4-pro"
if "%LLM_BASE_URL%"=="" set "LLM_BASE_URL=https://api.deepseek.com"
if "%LLM_THINKING%"=="" set "LLM_THINKING=disabled"

echo Model: %LLM_MODEL%
echo Base URL: %LLM_BASE_URL%
echo Limit: %LLM_LIMIT%
echo Thinking: %LLM_THINKING%
echo.

set "PYTHONPATH=backend"
python backend\filter_main.py
python backend\prepare_llm_candidates.py
python backend\llm_match_jobs.py
python backend\export_llm_excel.py

echo.
echo Done.
echo Excel: backend\data\filtered\job_applications.xlsx

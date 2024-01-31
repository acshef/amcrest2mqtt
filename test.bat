@ECHO OFF
FOR /F "delims== tokens=1,* eol=#" %%i IN (env_vars) DO SET %%i=%%~j
python -u -m amcrest2mqtt
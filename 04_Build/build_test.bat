@echo off
chcp 65001 > nul

echo Kazuizhi AI V1.9.5 Build Test
python ..\03_V1.9.5_Source\integration_test.py
pause

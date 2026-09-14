# V1.9.5 Actions Trigger Check

Purpose: trigger GitHub Actions after workflow configuration verification.

Expected flow:

push main
-> build_v1.9.5_alpha.yml
-> Windows runner
-> PyInstaller
-> Alpha artifact

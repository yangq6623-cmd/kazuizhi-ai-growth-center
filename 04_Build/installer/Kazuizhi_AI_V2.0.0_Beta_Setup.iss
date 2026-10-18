[Setup]
; Same AppId and install directory preserve all R7/R8 configuration and user data.
AppId={{C8148D45-198A-43BF-BC84-922000000001}
AppName=Kazuizhi AI Enterprise V2.2.2 R8-23 Final Workbench
AppVersion=2.2.2 R8-23 Final Workbench
VersionInfoVersion=2.2.2.23
VersionInfoCompany=Kazuizhi
VersionInfoDescription=Kazuizhi AI Enterprise V2.2.2 R8-23 Final Workbench Installer
VersionInfoProductName=Kazuizhi AI Enterprise
DefaultDirName={localappdata}\Programs\Kazuizhi_AI_Enterprise_V2.0.0_Beta
DefaultGroupName=Kazuizhi AI Enterprise V2.2.2 R8-23 Final Workbench
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\installer_output_v2
OutputBaseFilename=Kazuizhi_AI_Enterprise_V2.2.2_R8-23_Final_Complete_Workbench
Compression=zip
SolidCompression=no
CloseApplications=force
CloseApplicationsFilter=Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe,KazuizhiSupervisor.exe,KazuizhiMonitoring.exe
RestartApplications=no
WizardStyle=modern

[Files]
Source: "..\..\dist_v2\Kazuizhi_AI_Enterprise_V2.0.0_Beta\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
Type: files; Name: "{userdesktop}\Kazuizhi AI Enterprise V2.0.0 Beta.lnk"
Type: files; Name: "{userdesktop}\Kazuizhi AI Enterprise V2.0.0 Beta R1.lnk"
Type: files; Name: "{userdesktop}\卡嘴子 AI 增长运营中心 V2 Beta R2.lnk"
Type: files; Name: "{userdesktop}\卡嘴子 AI 增长运营中心 V2 Beta R3.lnk"
Type: files; Name: "{userdesktop}\卡嘴子 AI 增长运营中心 V2 Beta R4.lnk"
Type: files; Name: "{userdesktop}\卡嘴子 AI 增长运营中心 V2 Beta R5.lnk"
Type: files; Name: "{userdesktop}\卡嘴子 AI 增长运营中心 V2 Beta R6.lnk"
Type: files; Name: "{userdesktop}\卡嘴子 AI 增长运营中心 V2 Beta R7.lnk"
Type: files; Name: "{userdesktop}\卡嘴子 AI 增长运营中心 V2 Beta R7.1.lnk"
Type: files; Name: "{userdesktop}\卡嘴子 AI 增长运营中心 V2 Beta R7 Final.lnk"
Type: files; Name: "{userdesktop}\卡嘴子 AI 增长运营中心 V2.1 R8 Final.lnk"
Type: files; Name: "{userdesktop}\卡嘴子 AI 真实运营工作台 V2.2 R8.lnk"
Type: files; Name: "{userstartup}\卡嘴子 AI 后台自动运行 R8-23.lnk"
Type: files; Name: "{userstartup}\卡嘴子 AI 第一阶段后台守护.lnk"

[Icons]
Name: "{userdesktop}\卡嘴子 AI 完整运营工作台 R8-23"; Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"
Name: "{group}\卡嘴子 AI 完整运营工作台 R8-23"; Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\Install-KazuizhiPhase1Supervisor.ps1"" -ExePath ""{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"" -AppDir ""{app}"""; Flags: runhidden waituntilterminated
Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"; Description: "启动卡嘴子 AI 完整运营工作台 R8-23"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\Uninstall-KazuizhiPhase1Supervisor.ps1"""; Flags: runhidden waituntilterminated; RunOnceId: "KazuizhiPhase1SupervisorRemove"

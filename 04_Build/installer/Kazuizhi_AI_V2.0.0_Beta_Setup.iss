[Setup]
; Same AppId and install directory preserve all R7/R8 configuration and user data.
AppId={{C8148D45-198A-43BF-BC84-922000000001}
AppName=Kazuizhi AI Enterprise V2.2.0 R8 Operational
AppVersion=2.2.0 R8 Operational
VersionInfoVersion=2.2.0.20
VersionInfoCompany=Kazuizhi
VersionInfoDescription=Kazuizhi AI Enterprise V2.2.0 R8 Operational Installer
VersionInfoProductName=Kazuizhi AI Enterprise
DefaultDirName={localappdata}\Programs\Kazuizhi_AI_Enterprise_V2.0.0_Beta
DefaultGroupName=Kazuizhi AI Enterprise V2.2.0 R8 Operational
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\installer_output_v2
OutputBaseFilename=Kazuizhi_AI_Enterprise_V2.2.0_R8_Operational
; Non-solid ZIP avoids the opaque high-entropy self-extracting layout that triggered #236.
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

[Icons]
Name: "{userdesktop}\卡嘴子 AI 真实运营工作台 V2.2 R8"; Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"
Name: "{group}\卡嘴子 AI 真实运营工作台 V2.2 R8"; Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"

[Run]
Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"; Description: "启动卡嘴子 AI 真实运营工作台 V2.2 R8"; Flags: nowait postinstall skipifsilent

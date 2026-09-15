[Setup]
AppId={{A27C56E8-01F2-4B5B-A7D9-915887600003}
AppName=Kazuizhi AI Enterprise R3
AppVersion=1.9.5.3 Enterprise R3
DefaultDirName={autopf}\Kazuizhi AI Enterprise R3
DefaultGroupName=Kazuizhi AI Enterprise R3
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
OutputDir=..\..\installer_output
OutputBaseFilename=Kazuizhi_AI_V1.9.5_Enterprise_R3_Setup
Compression=lzma
SolidCompression=yes

[InstallDelete]
; Clean only the isolated R3 dashboard directory before copying a fresh build.
Type: filesandordirs; Name: "{app}\_internal\web"

[Files]
; Enterprise R3 build output. PyInstaller output has already been validated by workflow.
Source: "..\..\dist\Kazuizhi_AI_V1.9.5_Enterprise\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\Kazuizhi AI Enterprise R3"; Filename: "{app}\Kazuizhi_AI_V1.9.5_Enterprise.exe"
Name: "{group}\Kazuizhi AI Enterprise R3"; Filename: "{app}\Kazuizhi_AI_V1.9.5_Enterprise.exe"

[Run]
Filename: "{app}\Kazuizhi_AI_V1.9.5_Enterprise.exe"; Description: "启动 Kazuizhi AI Enterprise R3"; Flags: nowait postinstall skipifsilent

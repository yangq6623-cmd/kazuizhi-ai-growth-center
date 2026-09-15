[Setup]
AppName=Kazuizhi AI
AppVersion=1.9.5.2 Enterprise R2
DefaultDirName={autopf}\Kazuizhi AI
DefaultGroupName=Kazuizhi AI
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
OutputDir=..\..\installer_output
OutputBaseFilename=Kazuizhi_AI_V1.9.5_Enterprise_R2_Setup
Compression=lzma
SolidCompression=yes

[InstallDelete]
; Force-remove previous dashboard frontend resources before copying Enterprise R2
Type: filesandordirs; Name: "{app}\_internal\web"

[Files]
; Enterprise R2 build output only
Source: "..\..\dist\Kazuizhi_AI_V1.9.5_Enterprise\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\Kazuizhi AI Enterprise R2"; Filename: "{app}\Kazuizhi_AI_V1.9.5_Enterprise.exe"
Name: "{group}\Kazuizhi AI Enterprise R2"; Filename: "{app}\Kazuizhi_AI_V1.9.5_Enterprise.exe"

[Run]
Filename: "{app}\Kazuizhi_AI_V1.9.5_Enterprise.exe"; Description: "启动 Kazuizhi AI Enterprise R2"; Flags: nowait postinstall skipifsilent

[Setup]
AppName=Kazuizhi AI
AppVersion=1.9.5 Enterprise
DefaultDirName={autopf}\Kazuizhi AI
DefaultGroupName=Kazuizhi AI
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
OutputDir=..\..\installer_output
OutputBaseFilename=Kazuizhi_AI_V1.9.5_Enterprise_Setup
Compression=lzma
SolidCompression=yes

[Files]
Source: "..\..\dist\Kazuizhi_AI_V1.9.5_Enterprise\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\Kazuizhi AI"; Filename: "{app}\Kazuizhi_AI_V1.9.5_Enterprise.exe"
Name: "{group}\Kazuizhi AI"; Filename: "{app}\Kazuizhi_AI_V1.9.5_Enterprise.exe"

[Run]
Filename: "{app}\Kazuizhi_AI_V1.9.5_Enterprise.exe"; Description: "启动 Kazuizhi AI Enterprise"; Flags: nowait postinstall skipifsilent

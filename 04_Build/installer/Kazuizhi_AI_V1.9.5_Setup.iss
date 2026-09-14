[Setup]
AppName=Kazuizhi AI
AppVersion=1.9.5
DefaultDirName={autopf}\Kazuizhi AI
DefaultGroupName=Kazuizhi AI
OutputBaseFilename=Kazuizhi_AI_V1.9.5_Setup
Compression=lzma
SolidCompression=yes

[Files]
Source: "..\..\dist\Kazuizhi_AI_V1.9.5_Alpha.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\Kazuizhi AI"; Filename: "{app}\Kazuizhi_AI_V1.9.5_Alpha.exe"
Name: "{group}\Kazuizhi AI"; Filename: "{app}\Kazuizhi_AI_V1.9.5_Alpha.exe"

[Run]
Filename: "{app}\Kazuizhi_AI_V1.9.5_Alpha.exe"; Description: "启动 Kazuizhi AI"; Flags: nowait postinstall skipifsilent

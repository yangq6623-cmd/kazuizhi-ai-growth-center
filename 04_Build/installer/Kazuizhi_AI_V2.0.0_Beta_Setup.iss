[Setup]
AppId={{C8148D45-198A-43BF-BC84-922000000001}
AppName=Kazuizhi AI Enterprise V2.0.0 Beta
AppVersion=2.0.0 Beta
VersionInfoVersion=2.0.0.0
DefaultDirName={localappdata}\Programs\Kazuizhi_AI_Enterprise_V2.0.0_Beta
DefaultGroupName=Kazuizhi AI Enterprise V2.0.0 Beta
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\installer_output_v2
OutputBaseFilename=Kazuizhi_AI_Enterprise_V2.0.0_Beta_Setup
Compression=lzma2
SolidCompression=yes
CloseApplications=yes

[Files]
Source: "..\..\dist_v2\Kazuizhi_AI_Enterprise_V2.0.0_Beta\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userdesktop}\Kazuizhi AI Enterprise V2.0.0 Beta"; Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"
Name: "{group}\Kazuizhi AI Enterprise V2.0.0 Beta"; Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"

[Run]
Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"; Description: "启动 Kazuizhi AI Enterprise V2.0.0 Beta"; Flags: nowait postinstall skipifsilent

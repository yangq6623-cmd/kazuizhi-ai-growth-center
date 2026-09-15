[Setup]
AppId={{C8148D45-198A-43BF-BC84-922000000001}
AppName=Kazuizhi AI Enterprise V2.0.0 Beta R1
AppVersion=2.0.0 Beta R1
VersionInfoVersion=2.0.0.1
DefaultDirName={localappdata}\Programs\Kazuizhi_AI_Enterprise_V2.0.0_Beta
DefaultGroupName=Kazuizhi AI Enterprise V2.0.0 Beta R1
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\installer_output_v2
OutputBaseFilename=Kazuizhi_AI_Enterprise_V2.0.0_Beta_R1_Setup
Compression=lzma2
SolidCompression=yes
CloseApplications=yes

[Files]
Source: "..\..\dist_v2\Kazuizhi_AI_Enterprise_V2.0.0_Beta\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userdesktop}\Kazuizhi AI Enterprise V2.0.0 Beta R1"; Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"
Name: "{group}\Kazuizhi AI Enterprise V2.0.0 Beta R1"; Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"

[Run]
Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"; Description: "启动 Kazuizhi AI Enterprise V2.0.0 Beta R1"; Flags: nowait postinstall skipifsilent

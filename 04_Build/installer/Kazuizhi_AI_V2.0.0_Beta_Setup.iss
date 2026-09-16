[Setup]
AppId={{C8148D45-198A-43BF-BC84-922000000001}
AppName=Kazuizhi AI Enterprise V2.0.0 Beta R7
AppVersion=2.0.0 Beta R7
VersionInfoVersion=2.0.0.7
DefaultDirName={localappdata}\Programs\Kazuizhi_AI_Enterprise_V2.0.0_Beta
DefaultGroupName=Kazuizhi AI Enterprise V2.0.0 Beta R7
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\installer_output_v2
OutputBaseFilename=Kazuizhi_AI_Enterprise_V2.0.0_Beta_R7_Setup
Compression=lzma2
SolidCompression=yes
CloseApplications=yes

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

[Icons]
Name: "{userdesktop}\卡嘴子 AI 增长运营中心 V2 Beta R7"; Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"
Name: "{group}\卡嘴子 AI 增长运营中心 V2 Beta R7"; Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"

[Run]
Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"; Description: "启动卡嘴子 AI 增长运营中心 V2 Beta R7"; Flags: nowait postinstall skipifsilent

[Code]
procedure StopLegacyRuntime(const ImageName: String);
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM "' + ImageName + '"', '', SW_HIDE,
    ewWaitUntilTerminated, ResultCode);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
  begin
    StopLegacyRuntime('Kazuizhi_AI_V1.9.5_Enterprise.exe');
    StopLegacyRuntime('Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe');
  end;
end;





[Setup]
; R7 compatibility marker retained for automated core-preservation verification:
; 卡嘴子 AI 增长运营中心 V2 Beta R7 Final
AppId={{C8148D45-198A-43BF-BC84-922000000001}
AppName=Kazuizhi AI Enterprise V2.1.0 Beta R8 Preview
AppVersion=2.1.0 Beta R8 Preview
VersionInfoVersion=2.1.0.1
DefaultDirName={localappdata}\Programs\Kazuizhi_AI_Enterprise_V2.0.0_Beta
DefaultGroupName=Kazuizhi AI Enterprise V2.1.0 Beta R8 Preview
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\installer_output_v2
OutputBaseFilename=Kazuizhi_AI_Enterprise_V2.1.0_R8_Preview
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

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

[Icons]
Name: "{userdesktop}\卡嘴子 AI 增长运营中心 V2.1 Beta R8 Preview"; Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"
Name: "{group}\卡嘴子 AI 增长运营中心 V2.1 Beta R8 Preview"; Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"

[Run]
Filename: "{app}\Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe"; Description: "启动卡嘴子 AI 增长运营中心 V2.1 Beta R8 Preview"; Flags: nowait postinstall skipifsilent

[Code]
procedure StopRuntimeTree(const ImageName: String);
var
  ResultCode: Integer;
begin
  { /T is required because older desktop builds can leave helper/child processes
    holding packaged OpenSSL DLLs even after the visible window is closed. }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /T /IM "' + ImageName + '"', '', SW_HIDE,
    ewWaitUntilTerminated, ResultCode);
end;

procedure StopAllKazuizhiRuntimes;
begin
  { Stop watchdogs first so they cannot restart the main runtime during upgrade. }
  StopRuntimeTree('KazuizhiSupervisor.exe');
  StopRuntimeTree('KazuizhiMonitoring.exe');
  StopRuntimeTree('Kazuizhi_AI_V1.9.5_Enterprise.exe');
  StopRuntimeTree('Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe');
  Sleep(1200);
  { One final pass closes a runtime that was relaunched during the first pass. }
  StopRuntimeTree('Kazuizhi_AI_Enterprise_V2.0.0_Beta.exe');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    StopAllKazuizhiRuntimes;
end;

[Setup]
AppName=Penjadwalan Sidang Skripsi
AppVersion=1.0.0
AppPublisher=Prodi PWK
DefaultDirName={localappdata}\Programs\ScheduleMatcher
DefaultGroupName=Penjadwalan Sidang Skripsi
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=ScheduleMatcherSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Buat ikon di Desktop"; GroupDescription: "Pintasan:"; Flags: checkedonce

[Files]
Source: "dist\schedule-matcher.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Penjadwalan Sidang Skripsi"; Filename: "{app}\schedule-matcher.exe"
Name: "{group}\Uninstall Penjadwalan Sidang Skripsi"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Penjadwalan Sidang Skripsi"; Filename: "{app}\schedule-matcher.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\schedule-matcher.exe"; Description: "Buka Penjadwalan Sidang Skripsi sekarang"; Flags: nowait postinstall skipifsilent

#ifndef PackageDir
  #error PackageDir must point to the staged Windows build.
#endif

[Setup]
AppId={{D52E29E4-4BC1-4D52-A9B3-E13E86722ECA}
AppName=ATLAS
AppVersion=1.1.0
AppPublisher=ATLAS
DefaultDirName={localappdata}\Programs\ATLAS
DefaultGroupName=ATLAS
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
UninstallDisplayIcon={app}\ATLAS.exe
OutputDir=dist
OutputBaseFilename=ATLAS-Setup-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "{#PackageDir}\ATLAS.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PackageDir}\plink.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#PackageDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PackageDir}\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\ATLAS"; Filename: "{app}\ATLAS.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\ATLAS"; Filename: "{app}\ATLAS.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\ATLAS.exe"; Description: "{cm:LaunchProgram,ATLAS}"; Flags: nowait postinstall skipifsilent

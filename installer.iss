#define MyAppName "MergeMasterPDF"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.2"
#endif
#define MyAppPublisher "Alan Juarez"
#define MyAppExeName "MergeMasterPDF.exe"
#ifndef MySourceDir
  #define MySourceDir "dist\\MergeMasterPDF"
#endif
#ifndef MyOutputDir
  #define MyOutputDir "installer_output"
#endif
#ifndef MyOutputBaseFilename
  #define MyOutputBaseFilename "MergeMasterPDF_Setup"
#endif

[Setup]
AppId={{D6B45F7A-3E37-4A3D-A2A0-9D2A7C541234}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir={#MyOutputDir}
OutputBaseFilename={#MyOutputBaseFilename}
SetupIconFile=icono.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
LicenseFile=LICENSE.txt

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Opciones adicionales:"

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "config.json"
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "CHANGELOG.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "LICENSE.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\MergeMasterPDF"; Filename: "{app}\MergeMasterPDF.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\MergeMasterPDF"; Filename: "{app}\MergeMasterPDF.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MergeMasterPDF.exe"; Description: "Abrir MergeMasterPDF"; Flags: nowait postinstall skipifsilent

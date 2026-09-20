; Instalador do Saci -- Inno Setup 6.
;
; Compilar (depois de gerar dist/Saci com "py -m PyInstaller saci.spec"):
;     "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" saci.iss
;
; Gera Output\Saci-Setup-<versao>.exe.
;
; Decisões da Etapa 7 (PLAN.md):
;   - instala em %LOCALAPPDATA%\Programs\Saci -- por usuário, NÃO exige
;     administrador (PrivilegesRequired=lowest)
;   - atalhos no Menu Iniciar e, opcionalmente, na Área de Trabalho
;   - detecta ausência do WebView2 e oferece o instalador oficial da
;     Microsoft antes de prosseguir
;   - desinstalar remove o programa; pergunta se apaga %APPDATA%\Saci
;     (chaves, histórico, catálogo) -- nunca apaga sem perguntar

#define MyAppName "Saci"
#ifndef MyAppVersion
  #define MyAppVersion "0.2.0"
#endif
#define MyAppPublisher "Bruno Fontes"
#define MyAppURL "https://github.com/fontesmidias/saci"
#define MyAppExeName "Saci.exe"

[Setup]
AppId={{8B6A6C6E-4C0B-4C0A-9C4A-5A3F6B7B4A19}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases

; Por usuário: instala em %LOCALAPPDATA%, sem pedir administrador.
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline

OutputDir=Output
OutputBaseFilename=Saci-Setup-{#MyAppVersion}
SetupIconFile=saci\saci.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

; O .exe não é assinado (custo do certificado fora do escopo do
; projeto — ver README). O SmartScreen do Windows vai avisar
; "aplicativo não reconhecido" nas primeiras execuções; documentado
; no README com o passo "Mais informações -> Executar assim mesmo".

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Iniciar o Saci automaticamente com o Windows"; GroupDescription: "Opções"; Flags: unchecked

[Files]
; DefaultDirName+/onedir inteiro: o .exe e a pasta _internal ao lado.
Source: "dist\{#MyAppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Abre o app ao final da instalação -- só se o usuário deixar marcado.
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; O instalador só copiou {app}; %APPDATA%\Saci (dados do usuário) é
; tratado à parte no [Code], com confirmação -- nunca apagado direto aqui.

[Code]
const
  WebView2ProbeKey = 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2DownloadURL = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';

function WebView2Instalado(): Boolean;
var
  Versao: String;
begin
  { Mesma chave que o runtime do WebView2 registra ao instalar (Evergreen
    Runtime), verificada por outros instaladores baseados em pywebview. }
  Result := RegQueryStringValue(HKLM, WebView2ProbeKey, 'pv', Versao)
    or RegQueryStringValue(HKCU, WebView2ProbeKey, 'pv', Versao);
end;

function InitializeSetup(): Boolean;
var
  Resposta: Integer;
begin
  Result := True;
  if not WebView2Instalado() then
  begin
    Resposta := MsgBox(
      'O Saci precisa do Microsoft Edge WebView2 Runtime para exibir sua janela.' + #13#10 + #13#10 +
      'Ele não foi encontrado nesta máquina. Na maioria dos PCs com Windows 10/11 ' +
      'atualizado ele já vem instalado; se este aviso apareceu, provavelmente falta.' + #13#10 + #13#10 +
      'Abrir a página oficial de download agora (recomendado), instalar por lá, ' +
      'e depois rodar este instalador de novo?' + #13#10 + #13#10 +
      'Escolha "Não" para continuar mesmo assim -- o Saci pode não abrir a janela ' +
      'até o WebView2 ser instalado.',
      mbConfirmation, MB_YESNO
    );
    if Resposta = IDYES then
    begin
      ShellExec('open', WebView2DownloadURL, '', '', SW_SHOWNORMAL, ewNoWait, Resposta);
      Result := False; { cancela a instalação; o usuário roda de novo depois }
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  { Marcar "iniciar com o Windows" na tela de tarefas grava a mesma
    chave HKCU que o próprio app usa (saci/autostart.py) -- assim o
    instalador e o menu da bandeja nunca divergem sobre onde a
    preferência mora. }
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('autostart') then
  begin
    RegWriteStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run',
      'Saci', '"' + ExpandConstant('{app}\{#MyAppExeName}') + '"');
  end;
end;

function InitializeUninstall(): Boolean;
begin
  { Sempre remove a entrada de autostart ao desinstalar -- nunca deixar
    uma chave apontando para um .exe que não existe mais. Silencioso
    (sem verificar existência): DeleteValue não falha se a chave já
    não estiver lá. }
  RegDeleteValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Saci');
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  PastaDados: String;
  Resposta: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    PastaDados := ExpandConstant('{userappdata}\Saci');
    if DirExists(PastaDados) then
    begin
      Resposta := MsgBox(
        'O Saci foi desinstalado.' + #13#10 + #13#10 +
        'Suas chaves de API, histórico de uso e catálogo de modelos continuam em:' + #13#10 +
        PastaDados + #13#10 + #13#10 +
        'Apagar esses dados também? Esta ação não pode ser desfeita.',
        mbConfirmation, MB_YESNO
      );
      if Resposta = IDYES then
        DelTree(PastaDados, True, True, True);
    end;
  end;
end;

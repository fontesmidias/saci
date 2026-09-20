# Changelog

Todas as mudanças relevantes do Saci são documentadas aqui.
*English version: [CHANGELOG.md](CHANGELOG.md).*
Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) · Versionamento: [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

## [0.2.0] — 19/09/2026

O aplicativo de desktop. Beta: o instalador e o `.exe` empacotado são novos
e só foram testados pelo autor numa máquina — espere arestas.

### Adicionado
- **Instalador para Windows** (`saci.iss`, Inno Setup): instala em
  `%LOCALAPPDATA%\Programs\Saci`, sem exigir administrador. Detecta a
  ausência do WebView2 Runtime antes de instalar e oferece o download
  oficial. Ao desinstalar, pergunta antes de apagar `%APPDATA%\Saci`, e
  sempre remove a entrada de autostart no registro, para nunca deixar uma
  chave apontando para um `.exe` que já não existe.
- **Aplicativo na bandeja** (`saci-app` / `Saci.exe`): um ícone em forma de
  gorro que muda de cor conforme o uso da cota (verde/amarelo/vermelho),
  janela nativa para o painel, e um menu — Abrir painel, Configurações,
  Perfil (submenu), Verificar catálogo agora, Abrir pasta de logs, Iniciar
  com o Windows, Sair. Fechar a janela só a esconde; uma segunda execução
  detecta a instância já em uso (via `/health`, não só a porta) e abre o
  navegador nela em vez de iniciar duas vezes.
- **Tela de configurações** (`/settings`): cola, testa (sem salvar) e salva
  chaves de API por provedor, com o valor sempre mascarado de volta
  (`gsk_••••f7dR`) — a chave nunca é reenviada ao navegador em texto puro.
  Também edita a ordem da cascata, o fuso horário e o perfil padrão, antes
  só editáveis no `.env`.
- **Dados movidos para `%APPDATA%\Saci`** quando instalado: `.env`,
  `usage.db`, `prefs.json`, `logs/saci.log` (com rotação, 2 MB × 3
  arquivos). Dados de uma instalação de desenvolvimento existente são
  copiados — nunca movidos — na primeira vez que o app empacotado roda.
- **Migrações de banco versionadas** (`saci/migrations.py`): mudanças de
  schema agora são aditivas ou baseadas em `RENAME`, nunca `DROP TABLE` —
  um bug real corrigido no processo (a chave antiga de `quota`, só por
  `provider`, era descartada a cada mudança de schema, apagando o estado
  de cota em uso).
- **Iniciar com o Windows**, alternável pelo menu da bandeja; grava em
  `HKCU`, sem precisar de administrador.

### Corrigido
Dois bugs que só se manifestavam dentro do `.exe` empacotado, invisíveis em
qualquer teste rodado a partir do código-fonte (foi o próprio processo de
empacotamento que os revelou):
- O app crashava silenciosamente ao iniciar: `Analysis(["saci/app.py"])`
  fazia o PyInstaller tratá-lo como script top-level, quebrando todo import
  relativo (`from . import paths`) dentro dele. Corrigido com
  `saci_launcher.py`, um ponto de entrada fino fora do pacote `saci` que o
  importa normalmente.
- O servidor às vezes nunca aceitava conexões (de 3s a mais de 100s para
  responder, de forma imprevisível), porque a detecção automática de loop
  de eventos do `uvicorn.run()` podia travar dentro do executável
  congelado. Corrigido passando `loop="asyncio"` explicitamente.

Também corrigido: o catálogo de modelos quebrava contra o LLM7 (`Error
binding parameter: type 'dict' is not supported`) porque esse provedor
informa o tamanho de contexto como um objeto aninhado em vez de um número
simples.

Também corrigido: se a thread do servidor morresse por uma exceção não
tratada, ela morria em silêncio — o `.exe` empacotado não tem console
(`--windowed`), então o traceback não ia a lugar nenhum e a bandeja só
mostrava "indisponível" sem dizer o motivo. Agora a thread do servidor
captura e registra a exceção em `saci.log`.

### Verificado
O instalador roda de forma silenciosa e desatendida (`/VERYSILENT`) sem
precisar de administrador; o executável instalado cria `%APPDATA%\Saci`
corretamente, serve o painel e a tela de configurações, e responde
requisições reais de chat. Três inicializações consecutivas do `.exe`
empacotado depois do fix do asyncio: as três prontas em 3 segundos.

## [0.1.0] — 19/09/2026

Primeiro lançamento público. Beta: funciona no dia a dia do autor; espere arestas.

### Adicionado
- **Cascata de fallback** entre provedores gratuitos. Em 429 (cota), 5xx, timeout,
  404/410 (modelo removido) ou 413 (requisição grande demais), o próximo modelo é
  tentado — por *modelo*, não por provedor, porque o Groq, por exemplo, conta
  tokens por modelo.
- **Perfis de tarefa** expostos como nomes de modelo OpenAI: `saci-code`,
  `saci-plan`, `saci-agent`, `saci-fast`, `saci-long`, `saci-pt`. Prompts acima de
  ~24 mil caracteres são promovidos para `agent` automaticamente (o Groq os rejeita
  com 413).
- **Servidor local compatível com a OpenAI** (`http://127.0.0.1:8000/v1`) —
  verificado com Cline (VS Code) e Aider (terminal). Streaming, blocos multimodais
  em `content` e o papel `developer` são tratados.
- **Catálogo automático de modelos**: na inicialização e a cada hora, o `/models`
  de cada provedor é buscado, filtrado para modelos de chat, e cada modelo *novo* é
  sondado uma vez (200 ok · 402/403 pago · 404/410 removido · 429 sem cota).
  Provedores novos entram na cascata sozinhos após a primeira sondagem. Só o
  OpenRouter publica preço; nos demais, "grátis" significa "respondeu 200 com a sua
  chave".
- **Controle de cota** a partir dos headers oficiais onde eles existem (Groq,
  Mistral) e por contagem local nos outros — a interface sempre diz qual é a fonte.
  O reset diário de cada provedor é mostrado como hora de relógio no seu fuso
  (`LLM_ROUTER_TZ`, padrão São Paulo).
- **Painel** (`/dashboard`): barras de cota, contagem regressiva ao vivo até o
  reset, veredito por modelo, troca de perfil, fixar um modelo, "verificar catálogo
  agora", consumo de RAM.
- **Extensão do VS Code para a barra de status** (instalação local):
  `⚡ groq 1% · 21:00`; clicar abre um seletor para trocar de perfil ou fixar
  qualquer modelo verificado.
- **CLI**: `saci "pergunta"`, `--usage`, `--catalog`, `--refresh`, `--status`,
  `--profiles`; aceita arquivos por pipe.
- **Atalhos para Windows** (`saci-on`, `saci-off`, `saci-panel`, `saci-usage`,
  `saci-logs`, `saci-status`) sobre o PM2, resistentes à queda do daemon.
- Exemplo de configuração do Aider (`~/.aider.conf.yml`) apontando para o roteador.

### Provedores verificados (19/09/2026)
Groq · Google AI Studio · Mistral · NVIDIA NIM · OpenRouter (`:free`) ·
LLM7.io (sem chave) · SambaNova · Hugging Face · Hyperbolic (crédito pré-pago,
sinalizado). O Cerebras devolve 402 em conta gratuita; o cadastro no SiliconFlow
não foi aprovado.

[Não lançado]: https://github.com/fontesmidias/saci/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/fontesmidias/saci/releases/tag/v0.2.0
[0.1.0]: https://github.com/fontesmidias/saci/releases/tag/v0.1.0

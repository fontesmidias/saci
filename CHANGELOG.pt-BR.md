# Changelog

Todas as mudanças relevantes do Saci são documentadas aqui.
*English version: [CHANGELOG.md](CHANGELOG.md).*
Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) · Versionamento: [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

Planejado para a 0.2.0 — o aplicativo de desktop:
- Ícone na bandeja com a cota ao vivo (`groq 1% · 21:00`) e janela nativa para o painel
- Tela de configurações para colar as chaves de API e reordenar provedores (sem editar `.env`)
- Dados em `%APPDATA%\Saci` (chaves, histórico, catálogo), para que atualizações nunca os toquem
- Arquivo de log, iniciar com o Windows, "verificar atualizações"
- Instalador para Windows; o aplicativo substitui o PM2

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

[Não lançado]: https://github.com/fontesmidias/saci/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/fontesmidias/saci/releases/tag/v0.1.0

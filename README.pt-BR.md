# Saci

> **Um roteador de LLMs gratuitas. Quando uma acaba, ele pula para a próxima.**
> *Sempre dá um jeito.* — [English version](README.md)

[![CI](https://github.com/fontesmidias/saci/actions/workflows/ci.yml/badge.svg)](https://github.com/fontesmidias/saci/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.pt-BR.md)
[![Status: beta](https://img.shields.io/badge/status-beta-orange.svg)](CHANGELOG.pt-BR.md)

O Saci é para quem **não pode pagar APIs de LLM** — estudantes, times pequenos,
quem está entre uma assinatura e outra. Ele transforma as camadas gratuitas de
Groq, Google AI Studio, Mistral, NVIDIA NIM, OpenRouter e outros em **um único
endpoint local compatível com a OpenAI** que nunca fica sem resposta:

- **Cascata de fallback, por modelo.** Cota estourada (429), modelo removido
  (404/410), provedor fora do ar (5xx), prompt grande demais (413) — o Saci tenta
  o próximo modelo. Ele controla a cota *por modelo*, porque o Groq conta tokens
  por modelo, não por conta.
- **Cota que você enxerga.** Barras ao vivo, a hora em que cada cota reseta *no
  seu fuso*, e um rótulo honesto em cada número: `oficial` (dos headers do
  provedor) ou `estimado` (nossa contagem local).
- **Um catálogo que se mantém sozinho.** A cada hora o Saci busca a lista de
  modelos de cada provedor, descarta os que não são de chat e sonda cada modelo
  *novo* uma vez. Só o que respondeu `200` com a sua chave entra na cascata.
  Coloque uma chave e o provedor entra sozinho.
- **Funciona com as ferramentas que você já usa.** Verificado com **Cline**
  (VS Code) e **Aider** (terminal). Qualquer coisa que fale a API da OpenAI serve.

O nome vem do [Saci](https://pt.wikipedia.org/wiki/Saci_(folclore)), o travesso de
uma perna só do folclore brasileiro, que sempre dá um jeito.

---

## Começo rápido (Windows)

```powershell
git clone https://github.com/fontesmidias/saci
cd saci
py -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
copy .env.example .env        # cole pelo menos uma chave (veja a tabela abaixo)
saci-on                       # servidor em http://127.0.0.1:8000 — fica de pé via PM2
saci-panel                    # painel no navegador
```

O `saci-on` precisa do [PM2](https://pm2.keymetrics.io/) (`npm i -g pm2`). Sem ele,
rode `.venv\Scripts\python.exe server.py` num terminal que você deixe aberto.
Linux/macOS: `python -m saci.server` — os atalhos `.cmd` ainda são só para Windows.

### Chaves gratuitas (sem cartão de crédito)

| Provedor | Onde pegar a chave | Por que está na cascata |
|---|---|---|
| Groq | https://console.groq.com/keys | Disparado o mais rápido (~0,5 s); 1.000 req/dia |
| Google AI Studio | https://aistudio.google.com/apikey | Maior contexto, 1.500 req/dia |
| Mistral | https://console.mistral.ai/ | O `codestral` é excelente para código |
| NVIDIA NIM | https://build.nvidia.com/ | Modelos abertos grandes (lento, mas grátis) |
| OpenRouter | https://openrouter.ai/keys | Dezenas de modelos `:free` — o único que publica preço |
| SambaNova | https://cloud.sambanova.ai/ | Llama/DeepSeek, 30 RPM |
| Hugging Face | https://huggingface.co/settings/tokens | Modelos abertos serverless |
| LLM7.io | *não precisa de chave* | Último recurso, sem cadastro |

O Hyperbolic também é suportado, mas gasta **crédito pré-pago** — o Saci sinaliza
isso em todos os lugares.

---

## Como usar

### No Cline, no Aider ou em qualquer cliente OpenAI

| Campo | Valor |
|---|---|
| Base URL | `http://127.0.0.1:8000/v1` |
| API key | qualquer coisa (o servidor é local e não verifica) |
| Modelo | `saci-code` · `saci-plan` · `saci-agent` · `saci-fast` · `saci-long` · `saci-pt` |

Cada "modelo" é um **perfil de tarefa** — uma cascata ordenada para aquele trabalho:

| Perfil | Para quê | Começa por |
|---|---|---|
| `saci-code` | escrever / refatorar código | Groq `gpt-oss-120b`, Mistral `codestral` |
| `saci-plan` | arquitetura, trade-offs | Groq `gpt-oss-120b`, Gemini |
| `saci-agent` | agentes de código (prompts enormes) | Mistral, Gemini — quem aceita requisições do tamanho que dá 413 |
| `saci-fast` | perguntas rápidas | Groq `gpt-oss-20b` |
| `saci-long` | documentos longos | Gemini (contexto de 1M) |
| `saci-pt` | português do Brasil, texto formal | Gemini, Groq |

Prompts acima de ~24 mil caracteres são promovidos para `saci-agent`
automaticamente, seja qual for o modelo pedido — por isso o Cline simplesmente
funciona.

Aider: use um [`~/.aider.conf.yml`](CONTRIBUTING.pt-BR.md) com
`openai-api-base: http://127.0.0.1:8000/v1` e `model: openai/saci-code`.

### No terminal

```powershell
saci "explique índices de banco de dados em uma frase"
saci -p code "função Python que valida CPF"
type app.py | saci -p code "adicione testes:"
saci --usage        # cota por provedor e modelo, horários de reset
saci --catalog      # todos os modelos descobertos e seus vereditos
saci --refresh      # descobrir e sondar agora
```

### O painel e a barra de status

O `saci-panel` abre `http://127.0.0.1:8000/dashboard`:

- barra de cota por provedor, **"reseta às 21:00"** com contagem regressiva ao vivo
- todo modelo descoberto com seu veredito — `ok`, `pago`, `removido`,
  `sem cota agora` — e um botão **usar** para fixar um deles
- troca de perfil, "verificar catálogo agora", consumo de RAM do servidor

A pasta `vscode-statusbar/` é uma extensão local minúscula do VS Code: ela mostra
`⚡ groq 1% · 21:00` na barra de status; clicar abre um seletor para trocar de
perfil ou fixar qualquer modelo verificado. Instale copiando a pasta para
`%USERPROFILE%\.vscode\extensions\local.saci-status-0.1.0` e recarregando a janela.

---

## Como o "grátis" é decidido

Esta é a parte que toda "lista de LLMs grátis" erra, então vamos ao ponto:

- **Só o OpenRouter publica preço** na sua lista de modelos.
- Groq, Google, Mistral, NVIDIA e o resto publicam *nomes*. Alguns desses nomes
  devolvem `404`, `410`, `402` ou `403` no instante em que você chama.
- Por isso o Saci **sonda**: uma requisição de três palavras por modelo novo, uma
  única vez. `200` → utilizável. `402/403` → pago, não é testado de novo por 30
  dias. `404/410` → removido. `429` → nova tentativa em uma hora. Os modelos `ok`
  são reconferidos a cada 14 dias, para pegar remoções silenciosas.

O resultado é uma lista que você não escreveu e não mantém — e esse é o objetivo.

## Controle de cota, com honestidade

| Provedor | Fonte | O que sabemos |
|---|---|---|
| Groq, Mistral | **oficial** — headers da resposta | requisições e tokens restantes, hora do reset |
| OpenRouter | oficial — `/v1/key` | uso acumulado |
| Google, NVIDIA, outros | **estimado** — contagem local | chamadas e tokens de hoje contra o limite diário conhecido |

Todo número na interface carrega seu rótulo. Um modelo que passou de 95% da cota
vai para o *fim* da cascata em vez de ser descartado: se a cota resetou desde a
última verificação, ele ainda tem a sua vez.

## Situação (verificada em 19/09/2026)

| Provedor | Funciona | Latência | Observações |
|---|---|---|---|
| Groq | ✅ | 0,3–2 s | 6 modelos de chat verificados; o mais rápido |
| Google AI Studio | ✅ | 1–25 s | Os `gemini-2.5-*` **sumiram** (404), apesar do que as listas dizem |
| Mistral | ✅ | 0,5–2 s | 12 grátis, 2 pagos (`labs-*`), camada gratuita é 1 req/s |
| NVIDIA NIM | ⚠️ | 15–70 s | 46 dos 62 modelos de chat listados devolvem 404/410/503 |
| OpenRouter | ⚠️ | varia | 25 grátis de 419; os `:free` são disputados |
| LLM7.io | ⚠️ | ~3 s | sem chave; saída instável, só como último recurso |
| Hyperbolic | 💳 | — | crédito pré-pago, sinalizado |
| Cerebras | ❌ | — | 402 em conta gratuita |

## Instalar, atualizar, desinstalar (Windows)

**Hoje (0.1, instalação de desenvolvedor):**

| Tarefa | Como |
|---|---|
| Instalar | `git clone` → `py -m venv .venv` → `pip install -e .` → preencher o `.env` |
| Ligar | `saci-on` (fica em segundo plano via PM2) |
| Desligar | `saci-off` |
| Atualizar | `git pull` e depois `saci-off && saci-on` |
| Desinstalar | `saci-off` e apagar a pasta. Nada é escrito fora dela. |

Suas chaves (`.env`), o histórico (`usage.db`) e as preferências (`prefs.json`)
ficam na pasta do projeto e nunca são commitados.

**A partir da 0.2 (instalador):** baixe o `.exe` em
[Releases](https://github.com/fontesmidias/saci/releases), dê dois cliques e
pronto — sem Python, sem PM2, sem terminal. Atualizar e desinstalar passam a ser
pelas Configurações do Windows → Aplicativos, e seus dados ficam em
`%APPDATA%\Saci`, a menos que você peça para removê-los.

## Planejado

- **0.2 — aplicativo de desktop:** ícone na bandeja, janela nativa, tela de
  configurações para as chaves, dados em `%APPDATA%`, instalador para Windows.
  Aposenta o PM2 e os arquivos `.cmd`.
- Inicializador multiplataforma (Linux/macOS com atalhos de primeira classe).
- Limitador de taxa por modelo, para agentes que disparam requisições em paralelo.

Veja o [CHANGELOG.pt-BR.md](CHANGELOG.pt-BR.md).

## Como contribuir

O PR mais útil é um provedor que funciona ou um limite que mudou — veja
[CONTRIBUTING.pt-BR.md](CONTRIBUTING.pt-BR.md). Uma regra só: cole a saída da
sondagem. Catálogos mentem.

Notas de segurança em [SECURITY.pt-BR.md](SECURITY.pt-BR.md): as chaves ficam na
sua máquina, o servidor escuta em `127.0.0.1` e não tem autenticação — não o
exponha.

## Licença

[MIT](LICENSE) © Bruno Fontes

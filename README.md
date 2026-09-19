# LLM Router

Cascata de fallback entre provedores de LLM **gratuitos**. Se um provedor
estoura a cota (429), cai (5xx) ou remove um modelo (404/410), o router
passa automaticamente para o próximo — sem intervenção.

Inspirado no [awesome-ai-free-tiers](https://github.com/4pixeltechBR/awesome-ai-free-tiers),
mas com uma diferença central: **nenhum modelo entra na configuração sem
ter respondido a uma chamada real**. Catálogos publicados (inclusive o
daquele repositório) listam modelos que retornam 404 ou 410 na prática.

## Instalação

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

Preencha o `.env` com suas chaves. Ele está no `.gitignore` e nunca é commitado.

### Onde pegar as chaves (todas sem cartão de crédito)

| Provedor | Link | Formato |
|---|---|---|
| Groq | https://console.groq.com/keys | `gsk_...` |
| Google AI Studio | https://aistudio.google.com/apikey | `AIzaSy...` ou `AQ.Ab8...` |
| Mistral | https://console.mistral.ai/ | 32 caracteres |
| NVIDIA NIM | https://build.nvidia.com/ | `nvapi-...` |
| OpenRouter | https://openrouter.ai/keys | `sk-or-v1-...` |

## Uso

```powershell
py ask.py "o que e um indice em banco de dados"

py ask.py -p code "funcao Python que valida CPF"
py ask.py -p plan "como estruturar um sistema de RH multi-empresa"

py ask.py -v -p code "refatore isso"     # mostra qual provedor atendeu
py ask.py --status                       # testa todos os provedores
py ask.py --profiles                     # lista os perfis

type arquivo.py | py ask.py -p code "adicione testes:"
```

### Perfis

| Perfil | Para quê | Primeiro da fila |
|---|---|---|
| `code` | gerar/refatorar código | Groq `gpt-oss-120b` (~2s) |
| `plan` | arquitetura, decisões, quebra de tarefas | Groq `gpt-oss-120b` (~5s) |
| `fast` | perguntas rápidas | Groq `gpt-oss-20b` (~1s) |
| `long` | textos longos, contexto grande | Google `gemini-3.6-flash` |
| `pt` | português corporativo, documentos | Google `gemini-3.6-flash` |

### Como biblioteca

```python
from llmrouter import LLMRouter

router = LLMRouter(profile="code")
r = router.ask("funcao que valida CNPJ")

print(r.content)
print(r.provider, r.model, r.latency)   # quem atendeu
print(r.attempts)                        # quem falhou antes
```

## Manutenção

Provedores gratuitos mudam de catálogo com frequência. Quando algo quebrar:

```powershell
py scripts/discover.py     # quais modelos existem hoje
py ask.py --status         # quais respondem agora
py scripts/smoke_test.py   # mede latência dos candidatos
```

Depois atualize `llmrouter/providers.py` com o que passou.

## Estado verificado (19/09/2026)

| Provedor | Status | Latência | Observação |
|---|---|---|---|
| Groq | ✅ | 0.5–2s | Mais rápido e estável |
| Google AI Studio | ✅ | 1.5–24s | Cota alta; `gemini-3.8-flash` dá 503 em pico |
| Mistral | ✅ | 0.5–2s | `codestral-latest` é ótimo para código |
| NVIDIA NIM | ⚠️ | 15–70s | Muitos IDs dão 404/410/503 |
| OpenRouter | ⚠️ | — | Modelos `:free` quase sempre em 429 |
| Cerebras | ❌ | — | HTTP 402: exige plano pago |

### Modelos descontinuados que listas desatualizadas ainda citam

`gemini-2.5-flash` (404) · `gemini-2.5-pro` (404) · `meta/llama-3.3-70b-instruct`
na NVIDIA (410) · `qwen/qwen3-coder-480b` na NVIDIA (410)

## Nota sobre os modelos gratuitos

Eles têm corte de conhecimento e **não sabem quais LLMs existem hoje** —
ao serem perguntados sobre isso, sugerem modelos já descontinuados. Use-os
para executar tarefas, não para decidir sobre o próprio ecossistema de IA.

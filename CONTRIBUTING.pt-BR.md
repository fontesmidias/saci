# Como contribuir com o Saci

Obrigado por aparecer. O Saci existe para quem não pode pagar APIs de LLM, então
as contribuições mais valiosas são as sem glamour: um provedor que funciona, um
limite que mudou, um modelo que morreu. *English version: [CONTRIBUTING.md](CONTRIBUTING.md).*

## A regra única

**Nada entra na configuração sem ter respondido a uma requisição real.**
Catálogos mentem: modelos listados em `/models` devolvem 404, 410 ou 402 o tempo
todo. Se você adicionar ou mudar um provedor ou modelo, cole no PR a saída de
`saci --catalog` (ou o resultado da sondagem). A revisão é basicamente isso.

## Rodando localmente

```powershell
git clone https://github.com/fontesmidias/saci
cd saci
py -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
copy .env.example .env      # coloque pelo menos uma chave
saci-on                     # servidor + catálogo de hora em hora (Windows, via PM2)
saci --usage                # ou: .venv\Scripts\python.exe -m saci.cli --usage
```

No Linux/macOS rode `python -m saci.server` diretamente; os atalhos `.cmd` ainda
são só para Windows (um inicializador multiplataforma é bem-vindo).

## Adicionar um provedor

1. `saci/providers.py` — acrescente um `Provider(...)`. Deixe `models=[]`: o
   catálogo descobre e sonda. Use `cost="credits"` se ele gasta saldo pré-pago.
2. `saci/usage.py` — adicione em `KNOWN_LIMITS` o que você *sabe* (RPM/RPD, fuso
   do reset, `period`). Não saber é aceitável; marque `source="local"`.
3. `saci/catalog.py` — só se o `/models` dele precisar de filtragem especial
   (`_is_chat`) ou publicar preço (`_free_by_catalog`).
4. `.env.example` — o nome da variável e onde conseguir a chave.
5. Rode `saci --refresh` e cole o resultado no PR.

## Relatar mudança de cota ou limite

Abra uma issue com o provedor, o limite antigo, o novo e onde você viu (headers,
painel, documentação). Limites mudam em silêncio; é assim que a tabela continua
honesta.

## Estilo de código

`ruff check saci` precisa passar. Siga o código ao redor: módulos pequenos,
comentários que expliquem o *porquê*, português ou inglês nos comentários, tanto
faz. Mantenha o código simples o bastante para um modelo de 27B conseguir
alterar — isso é um objetivo de projeto, não uma piada.

As regras invioláveis do projeto estão em [CLAUDE.md](CLAUDE.md) e são
verificadas por `python scripts/check_rules.py`. Rode antes de abrir o PR.

## Pull requests

- Um assunto por PR.
- Se o comportamento mudou, acrescente uma linha no `CHANGELOG.md` **e** no
  `CHANGELOG.pt-BR.md`, na seção *Unreleased* / *Não lançado*.
- Não commite `.env`, `usage.db`, `prefs.json` nem logs (estão ignorados;
  confira mesmo assim).
- Documentação é sempre bilíngue e completa nos dois idiomas: se mexer no
  `README.md`, mexa no `README.pt-BR.md` no mesmo commit.

# Open Heavens — Guia Open Groups a partir do YouTube

Pipeline da **Open Heavens Church** (Coimbra, Portugal). Lê o vídeo do culto no YouTube, extrai as legendas, **segmenta o culto com Claude** para isolar a ministração, gera um **resumo pastoral em PT-PT e EN**, e produz o **Guia Open Groups** (PDF com identidade visual do manual) — dois ficheiros, um em cada língua.

> `v0.3` — Saída enxuta: apenas `guia_open_groups_pt.pdf` + `guia_open_groups_en.pdf` na pasta em que o comando é invocado.

## Porquê segmentar antes de resumir?

A transcrição é do **culto completo** — abertura, louvor, avisos, ofertas, oração, ministração, momento profético, encerramento. Pedir ao modelo para resumir tudo dilui a mensagem central com letras de cânticos e anúncios.

A fase **segmentação** resolve isso:

```mermaid
flowchart LR
    URL[URL YouTube] --> T[transcrição YouTube]
    T --> S["Claude #1<br/>segmentação JSON"]
    S --> Min[ministração isolada]
    Min --> R["Claude #2<br/>resumo pastoral"]
    R --> G[Guia Open Groups PDF (PT + EN)]
```

## Instalação rápida — `curl | bash`

Não precisas de clonar o repo. A partir de qualquer pasta:

```bash
curl -fsSL https://raw.githubusercontent.com/renatoruis/oh-doc-generator/main/install.sh \
  | bash -s "https://www.youtube.com/live/VIDEO_ID"
```

O script faz tudo por ti:

1. **Detecta o OS** (macOS / Debian / Fedora / Arch) e verifica dependências.
2. **Auto-instala o que falta** via `brew` (macOS) ou `apt-get`/`dnf`/`pacman` (Linux):
   - `git`, `python@3.12`, libs WeasyPrint (Pango, Cairo, Fontconfig, HarfBuzz, …).
   - No macOS, instala o Homebrew se não existir.
3. Verifica (e instala opcionalmente) o **`claude` CLI**.
4. Clona o repositório para `/tmp/oh-XXXXXX/repo`.
5. Cria um `venv` e instala as dependências Python.
6. Corre o pipeline (`open-heavens run …`).
7. Copia **`guia_open_groups_pt.pdf`** e **`guia_open_groups_en.pdf`** para a pasta onde executaste o comando.
8. Apaga `/tmp/oh-XXXXXX/`.

Variáveis opcionais:

| Env var | Default | Efeito |
|---------|---------|--------|
| `OH_REPO_BRANCH` | `main` | Branch a clonar |
| `OH_EXTRA_ARGS` | — | Args extra para `open-heavens run` (ex.: `--skip-segment`) |
| `OH_KEEP_WORKDIR` | `0` | Mantém `/tmp/oh-…/` para debug |
| `OH_AUTO_INSTALL` | `1` | Auto-instala deps faltantes |
| `OH_SKIP_DEPS` | `0` | Salta verificação/instalação automática |

### Pré-requisitos mínimos (se `OH_AUTO_INSTALL=0`)

- **Python 3.10+**
- **`claude` CLI** no PATH ([Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code/quickstart)) — sem ele, corre com `OH_EXTRA_ARGS="--skip-claude"` para parar depois da extracção.
- **WeasyPrint** precisa de Pango / Cairo / Fontconfig instalados:
  - macOS: `brew install pango cairo fontconfig libffi pkg-config harfbuzz gdk-pixbuf`
  - Debian/Ubuntu: `sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libharfbuzz0b libgdk-pixbuf-2.0-0`

## Instalação local (desenvolvimento)

```bash
git clone https://github.com/renatoruis/oh-doc-generator.git
cd oh-doc-generator
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Depois:

```bash
./main.py "https://www.youtube.com/live/VIDEO_ID"
# ou
open-heavens run "https://www.youtube.com/live/VIDEO_ID"
```

Os dois PDFs aparecem na pasta actual. A pasta de trabalho `./entrega/` é removida no fim.

## Fases do pipeline

```
[1/5] metadados (yt-dlp)
[2/5] legendas (youtube-transcript-api)
[3/5] segmentação do culto (Claude #1)
[4/5] resumo da ministração (Claude #2)
[5/5] guias Open Groups (PDF PT + EN → copiados para a pasta actual)
```

No final, uma **tabela rich** com os PDFs gerados.

## Saída

| Ficheiro | Conteúdo |
|----------|----------|
| `guia_open_groups_pt.pdf` | Guia em Português (capa · como usar · resumo · 3 perguntas) |
| `guia_open_groups_en.pdf` | Mesma estrutura em English |

> A pasta `entrega/` é usada como workdir temporário e **apagada no fim**. Para manter (debug), passa `--keep-workdir` ou `OH_KEEP_WORKDIR=1`.

## Flags úteis

| Flag | O que faz |
|------|-----------|
| `--skip-claude` | Só extrai legendas — salta segmentação + resumo |
| `--skip-segment` | Salta a segmentação; resumo sobre transcrição inteira |
| `--force` | Refaz segmentação/resumo mesmo com cache local (se `--keep-workdir`) |
| `--keep-workdir` | Mantém `./entrega/<video_id>/` com todos os artefactos intermédios |
| `-d ./pasta` | Pasta de destino para os PDFs (default: directório actual) |
| `-o ./pasta` | Pasta de trabalho (default: `./entrega`; removida no fim) |
| `--claude-bin` | Caminho alternativo para o `claude` CLI |
| `--claude-extra "…"` | Argumentos extra (shlex) para o Claude CLI |

## Comandos avançados

```bash
open-heavens extract URL           # só transcrição
open-heavens summarize FILE.json   # resumo via API Anthropic
open-heavens prepare-claude FILE   # gera prompts para colar no Cursor
open-heavens ministracao URL       # só segmentação + resumo (sem guia)
```

## Estrutura do repositório

| Caminho | Conteúdo |
|---------|----------|
| `src/youtube_extract/` | Código Python (pipeline, CLI, parsers, render) |
| `src/youtube_extract/templates/` | Template Jinja2 do guia + prompts |
| `src/utils/logos/` | Monograma O+H e wordmark (SVG) |
| `src/utils/fonts/Nohemi/` | Slot para instalar a Nohemi (self-host) |
| `tests/` | Smoke tests |
| `install.sh` | Script `curl \| bash` (clone → gerar → copiar → limpar) |
| `main.py` | Entry simples: `./main.py URL` ou `./main.py <comando>` |

### Nohemi (tipografia oficial)

A **Nohemi** (Pangram Pangram) é a fonte da marca. Como não é livre, não está no repo. Coloca os `.woff2` em `src/utils/fonts/Nohemi/`. Sem eles, o guia faz fallback para **Space Grotesk** (Google Fonts).

## Desenvolvimento

```bash
pip install -e '.[dev]'
pre-commit install
ruff check src tests
pytest -q
```

## Requisitos

- **Legendas do vídeo** precisam existir no YouTube. Sem legendas, não há transcrição.
- **Claude Code CLI** ou `ANTHROPIC_API_KEY` (para a via API).

## Ajustar os prompts

- [`src/youtube_extract/templates/prompts/segmentacao.md.j2`](src/youtube_extract/templates/prompts/segmentacao.md.j2) — tipos de bloco + schema JSON.
- [`src/youtube_extract/templates/prompts/ministracao.md.j2`](src/youtube_extract/templates/prompts/ministracao.md.j2) — resumo pastoral PT/EN + perguntas.

---

_«Céus abertos — vida de fé além do tradicional.»_ · Open Heavens Church · Coimbra · Portugal

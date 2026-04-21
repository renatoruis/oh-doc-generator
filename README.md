# Open Heavens — Guia Open Groups a partir do YouTube

Gera dois PDFs (PT + EN) do **Guia Open Groups** a partir de um vídeo de culto no YouTube da [Open Heavens Church](https://openheavenschurch.pt).

O pipeline extrai as legendas, usa o Claude para isolar a ministração e produzir um resumo pastoral, e compõe o guia com a identidade visual da igreja.

**Plataforma:** macOS (Apple Silicon ou Intel).

---

## Correr (one-liner)

```bash
curl -fsSL https://raw.githubusercontent.com/renatoruis/oh-doc-generator/main/install.sh \
  | bash -s "https://www.youtube.com/live/VIDEO_ID"
```

O script trata de tudo:

1. Instala o Homebrew se faltar.
2. `brew install` de `git`, `python@3.12` e libs do WeasyPrint (pango, cairo, fontconfig, harfbuzz, gdk-pixbuf, libffi, pkg-config).
3. Instala o `claude` CLI se faltar.
4. Clona o repo para `/tmp/oh-XXXX`, cria `venv`, instala o pacote.
5. Gera o guia.
6. **Copia `guia_open_groups_pt.pdf` e `guia_open_groups_en.pdf`** para a pasta onde correste o comando.
7. Limpa `/tmp/oh-XXXX`.

### Variáveis opcionais

| Env var | Default | O que faz |
|---|---|---|
| `OH_REPO_BRANCH` | `main` | Branch a clonar |
| `OH_EXTRA_ARGS` | — | Args extra para `open-heavens run` (ex.: `"--skip-segment"`) |
| `OH_KEEP_WORKDIR` | `0` | `=1` mantém `/tmp/oh-XXXX` para debug |

---

## Uso local (desenvolvimento)

```bash
git clone https://github.com/renatoruis/oh-doc-generator.git
cd oh-doc-generator
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

./main.py "https://www.youtube.com/live/VIDEO_ID"
# equivalente:
open-heavens run "https://www.youtube.com/live/VIDEO_ID"
```

Os 2 PDFs aparecem na pasta actual. A pasta de trabalho `./entrega/` é removida no fim (passa `--keep-workdir` para debug).

### Flags úteis

| Flag | Efeito |
|---|---|
| `--skip-claude` | Só extrai legendas (sem resumo → PDFs ficam sem conteúdo útil) |
| `--skip-segment` | Salta a segmentação (1 chamado Claude a menos; resumo sobre transcrição inteira) |
| `--force` | Refaz segmentação/resumo ignorando cache |
| `--keep-workdir` | Mantém `./entrega/<video_id>/` no fim |
| `-d ./pasta` | Pasta de destino dos PDFs (default: CWD) |

### Testes

```bash
ruff check src tests
pytest -q
```

---

## O que sai

Dois ficheiros A4 paginados, cada um em PT ou EN:

| Página | Conteúdo |
|---|---|
| 1 | Capa (obsidian + lime) com título, data e vídeo |
| 2 | Como usar o guia no Open Group (caixa branca com checklist + fluxo sugerido) |
| 3+ | Resumo da ministração (tema, contexto, pontos principais, referências bíblicas com links YouVersion, aplicação) |
| última | 3 perguntas de discussão em cartões numerados |

Rodapé automático em cada página com `Open Heavens Church · <data> | pág. N / M`.

---

## Requisitos

- macOS com shell e sudo (para o Homebrew).
- Legendas existentes no vídeo do YouTube (auto-geradas ou manuais).
- `claude` CLI autenticado (ou `ANTHROPIC_API_KEY` se quiseres usar a via API — ver `open-heavens summarize`).

---

## Licença

- **Código:** [MIT](./LICENSE).
- **Assets da marca** (logos em `src/utils/logos/`, prompts em `src/youtube_extract/templates/`, constantes em `src/youtube_extract/brand/`): propriedade da Open Heavens Church — uso só com autorização escrita.

---

_«Céus abertos — vida de fé além do tradicional.»_ · Open Heavens Church · Coimbra · Portugal

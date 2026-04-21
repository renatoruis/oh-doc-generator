#!/usr/bin/env bash
# Open Heavens — gerador de Guia Open Groups em PDF (PT + EN).
# Plataforma suportada: macOS (Apple Silicon ou Intel) com Homebrew.
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/renatoruis/oh-doc-generator/main/install.sh | bash -s <youtube-url>
#
# Env vars (opcionais):
#   OH_REPO_URL      URL git do repositório (default: https://github.com/renatoruis/oh-doc-generator.git)
#   OH_REPO_BRANCH   Branch a usar (default: main)
#   OH_KEEP_WORKDIR  Se =1, mantém o workdir em /tmp para debug
#   OH_EXTRA_ARGS    Args extra para `open-heavens run` (ex.: "--skip-segment")

set -euo pipefail

# ────────────────────────── UI ──────────────────────────
if [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]]; then
  c_b=$'\033[1m'; c_d=$'\033[2m'; c_g=$'\033[32m'; c_y=$'\033[33m'; c_r=$'\033[31m'; c_c=$'\033[36m'; c_0=$'\033[0m'
else
  c_b=""; c_d=""; c_g=""; c_y=""; c_r=""; c_c=""; c_0=""
fi
ok()   { echo "${c_g}✓${c_0} $*"; }
warn() { echo "${c_y}!${c_0} $*" >&2; }
die()  { echo "${c_r}✗${c_0} $*" >&2; exit 1; }
step() { echo ""; echo "${c_b}${c_c}→${c_0} ${c_b}$*${c_0}"; }

# ────────────────────────── OS check ──────────────────────────
[[ "$(uname -s)" == "Darwin" ]] || die "Este instalador é só para macOS."

# ────────────────────────── args ──────────────────────────
VIDEO_URL="${1:-}"
if [[ -z "${VIDEO_URL}" ]]; then
  cat <<EOF >&2
Uso: curl -fsSL <install.sh> | bash -s <youtube-url>

Exemplo:
  curl -fsSL https://raw.githubusercontent.com/renatoruis/oh-doc-generator/main/install.sh \\
    | bash -s https://www.youtube.com/live/XXXXXXXXXXX
EOF
  exit 1
fi

REPO_URL="${OH_REPO_URL:-https://github.com/renatoruis/oh-doc-generator.git}"
REPO_BRANCH="${OH_REPO_BRANCH:-main}"
KEEP_WORKDIR="${OH_KEEP_WORKDIR:-0}"
EXTRA_ARGS="${OH_EXTRA_ARGS:-}"

ORIG_DIR="$(pwd)"
WORK_DIR="$(mktemp -d -t oh-XXXXXX)"
REPO_DIR="${WORK_DIR}/repo"

cleanup() {
  if [[ "${KEEP_WORKDIR}" == "1" ]]; then
    echo "${c_d}↳ workdir preservado: ${WORK_DIR}${c_0}"
  else
    rm -rf "${WORK_DIR}"
  fi
}
trap cleanup EXIT

has() { command -v "$1" >/dev/null 2>&1; }

# ────────────────────────── Homebrew ──────────────────────────
step "Verificar Homebrew"
if ! has brew; then
  warn "Homebrew não encontrado — a instalar (pode pedir password do sudo)."
  NONINTERACTIVE=1 /bin/bash -c \
    "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Activa brew no PATH da sessão actual
  if   [[ -x /opt/homebrew/bin/brew ]]; then eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew   ]]; then eval "$(/usr/local/bin/brew shellenv)"
  fi
  has brew || die "Falhei a instalar Homebrew. Vê https://brew.sh."
fi
ok "Homebrew em $(command -v brew)"

# ────────────────────────── brew formulae ──────────────────────────
step "Instalar dependências via brew (se faltarem)"
BREW_PKGS=(git python@3.12 pango cairo fontconfig libffi pkg-config harfbuzz gdk-pixbuf)
missing=()
for p in "${BREW_PKGS[@]}"; do
  brew list --formula "$p" >/dev/null 2>&1 || missing+=("$p")
done
if ((${#missing[@]})); then
  echo "${c_d}  brew install ${missing[*]}${c_0}"
  brew install "${missing[@]}"
else
  echo "${c_d}  (nada a instalar — tudo presente)${c_0}"
fi

# ────────────────────────── Python 3.10+ ──────────────────────────
PY=""
for v in 3.12 3.11 3.10; do
  if command -v "python${v}" >/dev/null 2>&1; then PY="python${v}"; break; fi
done
[[ -n "${PY}" ]] || die "Não encontrei python3.10/3.11/3.12 depois de instalar python@3.12."
ok "python      $(${PY} -c 'import sys; print("%d.%d" % sys.version_info[:2])') (${PY})"
ok "git         $(git --version | awk '{print $3}')"

# ────────────────────────── Claude Code CLI ──────────────────────────
step "Verificar Claude Code CLI"
if ! has claude; then
  warn "'claude' não encontrado — a instalar oficialmente."
  curl -fsSL https://claude.ai/install.sh | bash || warn "Instalador do Claude falhou; continua sem ele."
  # PATH comum após instalação
  for dir in "$HOME/.claude/bin" "$HOME/.local/bin"; do
    [[ -d "$dir" ]] && export PATH="$dir:$PATH"
  done
fi
if has claude; then
  ok "claude      $(claude --version 2>/dev/null | awk '{print $NF}' | head -1)"
else
  warn "A prosseguir sem 'claude' — o resumo vai ficar indisponível."
  warn "Podes forçar com: OH_EXTRA_ARGS='--skip-claude' (PDFs ficarão sem resumo)."
fi

# ────────────────────────── Clone ──────────────────────────
step "Clonar ${REPO_URL} (${REPO_BRANCH})"
git clone --depth 1 --branch "${REPO_BRANCH}" "${REPO_URL}" "${REPO_DIR}" >/dev/null 2>&1 \
  || die "git clone falhou (verifica OH_REPO_URL / OH_REPO_BRANCH)."
ok "repo em ${REPO_DIR}"

cd "${REPO_DIR}"

# ────────────────────────── venv + pip ──────────────────────────
step "Criar venv e instalar pacote Python"
"${PY}" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -e .

python -c 'import weasyprint' 2>/tmp/oh-wp.log || {
  cat /tmp/oh-wp.log >&2 || true
  die "WeasyPrint não carrega apesar das libs brew. Abre issue com o log acima."
}
ok "weasyprint  $(python -c 'import weasyprint; print(weasyprint.__version__)')"

# ────────────────────────── gerar PDFs ──────────────────────────
step "Gerar PDFs a partir de: ${VIDEO_URL}"
# shellcheck disable=SC2086
open-heavens run "${VIDEO_URL}" --dest "${ORIG_DIR}" ${EXTRA_ARGS}

echo ""
ok "PDFs em: ${ORIG_DIR}"
ls -1 "${ORIG_DIR}"/guia_open_groups_*.pdf 2>/dev/null || true

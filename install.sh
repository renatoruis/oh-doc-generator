#!/usr/bin/env bash
# Open Heavens — gerador de Guia Open Groups (PDF PT + EN).
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/renatoruis/oh-doc-generator/main/install.sh | bash -s <youtube-url-ou-id>
#
# Env vars:
#   OH_REPO_URL       URL git do repositório (default: https://github.com/renatoruis/oh-doc-generator.git)
#   OH_REPO_BRANCH    Branch a usar (default: main)
#   OH_KEEP_WORKDIR   Se =1, mantém o workdir em /tmp para debug
#   OH_EXTRA_ARGS     Args extra para `open-heavens run` (ex.: "--skip-segment")
#   OH_SKIP_DEPS      Se =1, salta instalação automática de dependências
#   OH_AUTO_INSTALL   Se =1, instala deps sem perguntar (default no curl|bash)

set -euo pipefail

# ────────────────────────── UI helpers ──────────────────────────
c_reset=$'\033[0m'; c_bold=$'\033[1m'; c_dim=$'\033[2m'
c_green=$'\033[32m'; c_yellow=$'\033[33m'; c_red=$'\033[31m'; c_cyan=$'\033[36m'
if [[ ! -t 1 ]] || [[ -n "${NO_COLOR:-}" ]]; then
  c_reset=""; c_bold=""; c_dim=""; c_green=""; c_yellow=""; c_red=""; c_cyan=""
fi
ok()   { echo "${c_green}✓${c_reset} $*"; }
warn() { echo "${c_yellow}!${c_reset} $*" >&2; }
fail() { echo "${c_red}✗${c_reset} $*" >&2; exit 1; }
step() { echo ""; echo "${c_bold}${c_cyan}→${c_reset} ${c_bold}$*${c_reset}"; }

# ────────────────────────── args ──────────────────────────
VIDEO_URL="${1:-}"
if [[ -z "${VIDEO_URL}" ]]; then
  cat <<'EOF' >&2
Uso: curl -fsSL <install.sh> | bash -s <youtube-url>

Exemplo:
  curl -fsSL https://raw.githubusercontent.com/renatoruis/oh-doc-generator/main/install.sh \
    | bash -s https://www.youtube.com/live/XXXXXXXXXXX
EOF
  exit 1
fi

REPO_URL="${OH_REPO_URL:-https://github.com/renatoruis/oh-doc-generator.git}"
REPO_BRANCH="${OH_REPO_BRANCH:-main}"
KEEP_WORKDIR="${OH_KEEP_WORKDIR:-0}"
EXTRA_ARGS="${OH_EXTRA_ARGS:-}"
SKIP_DEPS="${OH_SKIP_DEPS:-0}"
AUTO_INSTALL="${OH_AUTO_INSTALL:-1}"

ORIG_DIR="$(pwd)"
WORK_DIR="$(mktemp -d -t oh-XXXXXX)"
REPO_DIR="${WORK_DIR}/repo"

cleanup() {
  if [[ "${KEEP_WORKDIR}" == "1" ]]; then
    echo "${c_dim}↳ workdir preservado: ${WORK_DIR}${c_reset}"
  else
    rm -rf "${WORK_DIR}"
  fi
}
trap cleanup EXIT

# ────────────────────────── OS detection ──────────────────────────
OS="$(uname -s)"
case "${OS}" in
  Darwin) OS_KIND="macos" ;;
  Linux)
    if [[ -f /etc/debian_version ]]; then OS_KIND="debian"
    elif [[ -f /etc/fedora-release ]]; then OS_KIND="fedora"
    elif [[ -f /etc/arch-release ]]; then OS_KIND="arch"
    else OS_KIND="linux"; fi
    ;;
  *) OS_KIND="other" ;;
esac

has() { command -v "$1" >/dev/null 2>&1; }

# ────────────────────────── dependency install helpers ──────────────────────────
brew_install_missing() {
  local pkgs=("$@") missing=()
  for p in "${pkgs[@]}"; do
    if ! brew list --formula "$p" >/dev/null 2>&1 && ! brew list --cask "$p" >/dev/null 2>&1; then
      missing+=("$p")
    fi
  done
  if ((${#missing[@]})); then
    echo "${c_dim}  brew install ${missing[*]}${c_reset}"
    brew install "${missing[@]}" >/dev/null
  fi
}

install_homebrew() {
  warn "Homebrew não encontrado."
  if [[ "${AUTO_INSTALL}" != "1" ]]; then
    fail "Instala em https://brew.sh e corre outra vez, ou define OH_AUTO_INSTALL=1."
  fi
  echo "${c_dim}  A instalar Homebrew (pode pedir password)…${c_reset}"
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Add brew to PATH for current session
  if [[ -x /opt/homebrew/bin/brew ]]; then eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then eval "$(/usr/local/bin/brew shellenv)"
  fi
  has brew || fail "Falhei a instalar Homebrew."
}

install_claude_cli() {
  warn "Claude Code CLI ('claude') não encontrado."
  cat >&2 <<EOF
  Instalação recomendada (oficial):
    curl -fsSL https://claude.ai/install.sh | bash
  Docs: https://docs.anthropic.com/en/docs/claude-code/quickstart

  Para continuar sem Claude (só extracção, sem resumo/guia útil), define:
    OH_EXTRA_ARGS="--skip-claude"
EOF
  if [[ "${AUTO_INSTALL}" == "1" ]] && has curl; then
    echo "${c_dim}  A instalar Claude Code CLI…${c_reset}"
    curl -fsSL https://claude.ai/install.sh | bash || warn "Falha a instalar claude — segue as instruções manuais acima."
    # shellcheck disable=SC1091
    if [[ -f "$HOME/.claude/bin/claude" ]]; then export PATH="$HOME/.claude/bin:$PATH"; fi
  fi
}

# ────────────────────────── step: verificar dependências ──────────────────────────
step "Verificar dependências (OS: ${OS_KIND})"

if [[ "${SKIP_DEPS}" == "1" ]]; then
  warn "OH_SKIP_DEPS=1 — a saltar auto-instalação."
else
  case "${OS_KIND}" in
    macos)
      if ! has brew; then install_homebrew; fi
      ok "Homebrew em $(command -v brew)"
      # Formulas necessárias (git + python@3.12 + weasyprint runtime libs)
      brew_install_missing git python@3.12 pango cairo fontconfig libffi pkg-config harfbuzz gdk-pixbuf
      ;;
    debian)
      if ! has apt-get; then fail "sistema Debian-like sem apt-get?"; fi
      if ! has sudo && [[ $EUID -ne 0 ]]; then fail "precisa de sudo para instalar pacotes apt."; fi
      SUDO=""; [[ $EUID -ne 0 ]] && SUDO="sudo"
      echo "${c_dim}  $SUDO apt-get update && apt-get install …${c_reset}"
      $SUDO apt-get update -qq >/dev/null
      $SUDO apt-get install -y -qq \
        git python3 python3-venv python3-pip \
        libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libharfbuzz0b \
        libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info >/dev/null
      ;;
    fedora)
      SUDO=""; [[ $EUID -ne 0 ]] && SUDO="sudo"
      $SUDO dnf install -y -q git python3 python3-pip pango cairo harfbuzz gdk-pixbuf2 libffi >/dev/null
      ;;
    arch)
      SUDO=""; [[ $EUID -ne 0 ]] && SUDO="sudo"
      $SUDO pacman -S --noconfirm --needed git python python-pip pango cairo harfbuzz gdk-pixbuf2 libffi >/dev/null
      ;;
    *)
      warn "OS não reconhecido (${OS}). Instala manualmente: git, python3.10+, pango, cairo, fontconfig."
      ;;
  esac
fi

# Verificação final explícita (com ou sem auto-install)
has git        && ok "git         $(git --version | awk '{print $3}')"        || fail "git não encontrado."
has python3    || fail "python3 não encontrado."

# Escolhe Python 3.10+
PY="python3"
for v in 3.12 3.11 3.10; do
  if command -v "python${v}" >/dev/null 2>&1; then PY="python${v}"; break; fi
done
PY_VERSION="$(${PY} -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
"${PY}" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || fail "precisa de Python 3.10+ (actual: ${PY_VERSION}). No macOS: brew install python@3.12"
ok "python      ${PY_VERSION} (${PY})"

# Claude CLI (opcional mas recomendado)
if has claude; then
  ok "claude      $(claude --version 2>/dev/null | head -1 | awk '{print $NF}')"
else
  install_claude_cli
  if has claude; then
    ok "claude      $(claude --version 2>/dev/null | head -1 | awk '{print $NF}')"
  else
    warn "A prosseguir sem 'claude' — o resumo via Claude CLI ficará indisponível."
  fi
fi

# ────────────────────────── step: clonar ──────────────────────────
step "Clonar ${REPO_URL} (${REPO_BRANCH})"
git clone --depth 1 --branch "${REPO_BRANCH}" "${REPO_URL}" "${REPO_DIR}" >/dev/null 2>&1 \
  || fail "git clone falhou. Verifica OH_REPO_URL / OH_REPO_BRANCH."
ok "repo em ${REPO_DIR}"

cd "${REPO_DIR}"

# ────────────────────────── step: venv + deps ──────────────────────────
step "Criar venv e instalar dependências Python"
"${PY}" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -e .

# WeasyPrint runtime check
python -c 'import weasyprint' 2>/tmp/oh-wp-err.log || {
  warn "WeasyPrint não carrega:"
  cat /tmp/oh-wp-err.log >&2 || true
  cat >&2 <<'EOF'
  Instala as libs de sistema e tenta de novo:
    macOS:   brew install pango cairo fontconfig libffi pkg-config harfbuzz gdk-pixbuf
    Debian:  sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libharfbuzz0b libgdk-pixbuf-2.0-0
EOF
  exit 1
}
ok "weasyprint  $(python -c 'import weasyprint; print(weasyprint.__version__)')"

# ────────────────────────── step: gerar PDFs ──────────────────────────
step "Gerar PDFs para: ${VIDEO_URL}"
# shellcheck disable=SC2086
open-heavens run "${VIDEO_URL}" --dest "${ORIG_DIR}" ${EXTRA_ARGS}

echo ""
ok "PDFs copiados para: ${ORIG_DIR}"
ls -1 "${ORIG_DIR}"/guia_open_groups_*.pdf 2>/dev/null || true

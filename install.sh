#!/usr/bin/env bash
# Open Heavens — gerador de Guia Open Groups (PDF PT + EN).
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/renatoruis/oh-doc-generator/main/install.sh | bash -s <youtube-url-ou-id>
#
# Variáveis de ambiente opcionais:
#   OH_REPO_URL      URL git do repositório (default: https://github.com/renatoruis/oh-doc-generator.git)
#   OH_REPO_BRANCH   Branch a usar (default: main)
#   OH_KEEP_WORKDIR  Se definida (=1), mantém o workdir em /tmp para debug
#   OH_EXTRA_ARGS    Args extra passados a `open-heavens run` (ex.: "--skip-segment")

set -euo pipefail

VIDEO_URL="${1:-}"
if [[ -z "${VIDEO_URL}" ]]; then
  echo "Uso: curl -fsSL <install.sh> | bash -s <youtube-url>" >&2
  echo "Ex.: curl -fsSL https://raw.githubusercontent.com/renatoruis/oh-doc-generator/main/install.sh | bash -s https://youtu.be/XXXXXXXXXXX" >&2
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
    echo "↳ workdir preservado: ${WORK_DIR}"
  else
    rm -rf "${WORK_DIR}"
  fi
}
trap cleanup EXIT

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "✗ falta '$1' no PATH" >&2; exit 127; }
}

echo "→ Verificar dependências básicas"
need git
need python3

# Escolhe python3.10+ se disponível
PY="python3"
if command -v python3.12 >/dev/null 2>&1; then PY="python3.12"
elif command -v python3.11 >/dev/null 2>&1; then PY="python3.11"
elif command -v python3.10 >/dev/null 2>&1; then PY="python3.10"
fi

"${PY}" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || { echo "✗ precisa de Python 3.10+ (actual: $(${PY} --version))" >&2; exit 1; }

echo "→ Clonar ${REPO_URL} (${REPO_BRANCH}) em ${REPO_DIR}"
git clone --depth 1 --branch "${REPO_BRANCH}" "${REPO_URL}" "${REPO_DIR}" >/dev/null

cd "${REPO_DIR}"

echo "→ Criar venv e instalar dependências"
"${PY}" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -e .

# WeasyPrint precisa de Pango/Cairo/Fontconfig instalados no sistema.
# Em macOS: brew install pango cairo fontconfig libffi pkg-config
# Em Debian/Ubuntu: apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libharfbuzz0b
python -c 'import weasyprint' 2>/dev/null || {
  cat >&2 <<'EOF'
✗ WeasyPrint não carrega. Instala as libs de sistema e tenta de novo:
    macOS:   brew install pango cairo fontconfig libffi pkg-config
    Debian:  sudo apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libharfbuzz0b
EOF
  exit 1
}

echo "→ Gerar PDFs para: ${VIDEO_URL}"
# shellcheck disable=SC2086
open-heavens run "${VIDEO_URL}" --dest "${ORIG_DIR}" ${EXTRA_ARGS}

echo ""
echo "✓ PDFs copiados para: ${ORIG_DIR}"
ls -1 "${ORIG_DIR}"/guia_open_groups_*.pdf 2>/dev/null || true

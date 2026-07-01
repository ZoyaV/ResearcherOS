#!/usr/bin/env bash
# Install tectonic into .tools/tectonic for NeurIPS paper PDF compilation.
set -euo pipefail

KOI_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS_DIR="$KOI_ROOT/.tools"
TECTONIC_BIN="$TOOLS_DIR/tectonic"
TECTONIC_VERSION="0.15.0"

if [[ -x "$TECTONIC_BIN" ]]; then
  exit 0
fi

if [[ -n "${KOI_TECTONIC_BIN:-}" && -x "${KOI_TECTONIC_BIN}" ]]; then
  exit 0
fi

if command -v tectonic >/dev/null 2>&1 || command -v pdflatex >/dev/null 2>&1; then
  exit 0
fi

os="$(uname -s | tr '[:upper:]' '[:lower:]')"
arch="$(uname -m)"
case "$os-$arch" in
  darwin-arm64)
    asset="tectonic-${TECTONIC_VERSION}-aarch64-apple-darwin.tar.gz"
    ;;
  darwin-x86_64)
    asset="tectonic-${TECTONIC_VERSION}-x86_64-apple-darwin.tar.gz"
    ;;
  linux-x86_64)
    asset="tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz"
    ;;
  linux-aarch64|linux-arm64)
    asset="tectonic-${TECTONIC_VERSION}-aarch64-unknown-linux-musl.tar.gz"
    ;;
  *)
    echo "koi-install-tectonic: unsupported platform $os/$arch" >&2
    echo "Install tectonic or pdflatex manually, or set KOI_TECTONIC_BIN." >&2
    exit 1
    ;;
esac

url="https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/${asset}"
mkdir -p "$TOOLS_DIR"
echo "koi-install-tectonic: downloading ${asset}…" >&2
curl -fsSL "$url" | tar -xz -C "$TOOLS_DIR"
chmod +x "$TECTONIC_BIN"
echo "koi-install-tectonic: installed $("$TECTONIC_BIN" --version 2>&1 | head -1)" >&2

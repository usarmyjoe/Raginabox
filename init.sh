#!/bin/sh
# Generates .env with fresh random secrets. Refuses to overwrite.
set -e
[ -f .env ] && { echo ".env already exists"; exit 1; }
umask 077
printf 'JWT_SECRET=%s\nQDRANT_API_KEY=%s\nEMBED_MODEL=nomic-embed-text\nLLM_MODEL=llama3.2:1b\n' \
  "$(openssl rand -hex 32)" "$(openssl rand -hex 24)" > .env
echo "wrote .env"

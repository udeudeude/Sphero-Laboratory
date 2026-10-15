#!/bin/bash
set -e
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo 'Python 3 is required. Install Python from python.org.'
  read -r -p 'Press Return to close…'
  exit 1
fi
if [ ! -d .venv ]; then
  echo 'Creating isolated Python environment…'
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import spherov2; import bleak' >/dev/null 2>&1; then
  echo 'Installing Bluetooth dependencies…'
  .venv/bin/python -m pip install -r requirements.txt
fi
echo 'Starting Sphero Laboratory…'
.venv/bin/python server.py

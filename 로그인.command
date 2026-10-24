#!/bin/bash
cd "$(dirname "$0")"
export PYTHONUNBUFFERED=1
.venv/bin/python -m app renew
echo
read -n 1 -s -r -p "닫으려면 아무 키나 누르세요."
echo

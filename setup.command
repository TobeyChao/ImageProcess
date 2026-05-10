#!/bin/bash
clear
cd "$(dirname "$0")"

if ! command -v python3 &>/dev/null; then
    echo "  Python 3 not found. Please install Python 3.10+ first:"
    echo "  https://www.python.org/downloads/"
    echo "  or: brew install python"
    echo ""
    read -p "  按 Enter 退出 "
    exit 1
fi

python3 main.py
if [ $? -ne 0 ]; then
    read -p "  按 Enter 退出 "
fi
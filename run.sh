#!/bin/bash
export OPENAI_API_KEY="sk-CZJoEJbiGjIMcTR82L54UnAc1fiTEYMIkUypR4ZBDdU1LjnE"
export OPENAI_BASE_URL="https://api.dev88.tech/v1"
cd ~/.opencode-project
echo "$@" | ~/.opencode/bin/opencode run -m openai/gpt-5

#!/bin/sh

set -eu

if ollama list | awk 'NR>1 {print $1}' | grep -Fxq "$MODEL"; then
  echo "$MODEL already present"
else
  ollama pull "$MODEL"
  echo "$MODEL ready"
fi
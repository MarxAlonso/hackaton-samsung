#!/usr/bin/env bash
# Pipeline completo: datos → simulación → entrenamiento → monitoreo → reentrenamiento → exportación.
# Cada paso falla en voz alta (set -e): si algo sale mal, no se publica un modelo a medias.
set -euo pipefail
cd "$(dirname "$0")/src"
if [ -x ../.venv/Scripts/python ]; then PY="../.venv/Scripts/python"
elif [ -x ../.venv/bin/python ]; then PY="../.venv/bin/python"
else PY="python"; fi
export MLFLOW_DISABLE_AGENT_HINT=1

echo "== 1/6 Ingesta (incremental) =="      && "$PY" ingest.py
echo "== 2/6 Simulación de casos =="        && "$PY" simulate.py
echo "== 3/6 Entrenamiento y evaluación ==" && "$PY" train.py
echo "== 4/6 Monitoreo de deriva =="        && "$PY" monitor.py
echo "== 5/6 Campeón vs retador =="         && "$PY" retrain.py
echo "== 6/6 Exportación a web y API =="    && "$PY" export.py

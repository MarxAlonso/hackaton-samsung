#!/usr/bin/env bash
# Pipeline completo: datos → casos reales → entrenamiento → monitoreo → reentrenamiento → validación externa → exportación.
# Cada paso falla en voz alta (set -e): si algo sale mal, no se publica un modelo a medias.
set -euo pipefail
cd "$(dirname "$0")/src"
if [ -x ../.venv/Scripts/python ]; then PY="../.venv/Scripts/python"
elif [ -x ../.venv/bin/python ]; then PY="../.venv/bin/python"
else PY="python"; fi
export MLFLOW_DISABLE_AGENT_HINT=1

echo "== 1/8 Clima y El Niño (incremental) =="              && "$PY" ingest.py
echo "== 2/8 Casos reales del CDC-MINSA (solo si cambiaron) ==" && "$PY" ingest_cases.py
echo "== 3/8 Tabla semanal de casos =="                      && "$PY" build_cases.py
echo "== 4/8 Entrenamiento y evaluación =="                  && "$PY" train.py
echo "== 5/8 Monitoreo de deriva =="                         && "$PY" monitor.py
echo "== 6/8 Campeón vs retador =="                          && "$PY" retrain.py
echo "== 7/8 Validación externa 2026 (Piura) =="            && "$PY" validate_gore.py > /dev/null
echo "== 8/8 Exportación a web y API =="                     && "$PY" export.py

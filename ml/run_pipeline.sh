#!/usr/bin/env bash
# Pipeline completo: datos → casos reales → entrenamiento → monitoreo → reentrenamiento → validación externa → exportación (incluye los casos 2026 del CDC por distrito).
# Cada paso falla en voz alta (set -e): si algo sale mal, no se publica un modelo a medias.
set -euo pipefail
cd "$(dirname "$0")/src"
if [ -x ../.venv/Scripts/python ]; then PY="../.venv/Scripts/python"
elif [ -x ../.venv/bin/python ]; then PY="../.venv/bin/python"
else PY="python"; fi
export MLFLOW_DISABLE_AGENT_HINT=1

echo "== 1/10 Clima y El Niño (incremental) =="              && "$PY" ingest.py
echo "== 2/10 Casos reales del CDC-MINSA (solo si cambiaron) ==" && "$PY" ingest_cases.py
echo "== 3/10 Casos 2026 por distrito (sala situacional del CDC; si falla, se conserva el último) ==" && { "$PY" ingest_dge_sala.py || echo "  (se conserva el informe anterior)"; }
echo "== 4/10 Tabla semanal de casos =="                      && "$PY" build_cases.py
echo "== 5/10 Entrenamiento y evaluación =="                  && "$PY" train.py
echo "== 6/10 Monitoreo de deriva =="                         && "$PY" monitor.py
echo "== 7/10 Campeón vs retador =="                          && "$PY" retrain.py
echo "== 8/10 Validación externa 2026 (Piura) =="            && "$PY" validate_gore.py > /dev/null
echo "== 9/10 Calibración con el acumulado oficial del año ==" && "$PY" validate_ytd.py
echo "== 10/10 Exportación a web y API =="                     && "$PY" export.py

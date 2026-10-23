"""API REST de Alerta Salud Niño.

uvicorn main:app --reload   →   http://localhost:8000/docs
"""
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from optimizer import optimize
from scoring import load, plan_inputs, predict_district

app = FastAPI(
    title="Alerta Salud Niño — API",
    description="Riesgo de dengue, lluvias extremas y plan de brigadas por distrito (próximas 4 semanas).",
    version="1.1.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

Escenario = Literal["actual", "2023", "2017"]


class PredictRequest(BaseModel):
    district_id: str = Field(..., examples=["piu-castilla"])
    escenario: Escenario = "actual"
    lluvia_pct: float = Field(0, ge=0, le=150, description="0 = clima observado; 100 = lluvias como 2023")
    temp_delta: float = Field(0, ge=-3, le=5, description="Grados °C a sumar a la temperatura")


class BatchRequest(BaseModel):
    items: list[PredictRequest] = Field(..., min_length=1, max_length=100)


class OptimizeRequest(BaseModel):
    escenario: Escenario = "actual"
    departamento: Literal["Tumbes", "Piura", "Lambayeque"] | None = None
    brigadas: int = Field(12, ge=0, le=500, description="Brigadas de control vectorial disponibles por 4 semanas")
    hab_por_brigada: int = Field(15000, ge=1000, le=100000, description="Habitantes que cubre una brigada en 4 semanas")
    efectividad: float = Field(0.30, ge=0, le=1, description="Fracción de casos evitada con cobertura total (supuesto editable)")
    criterio: Literal["probable", "prudente"] = "probable"
    costo_brigada: float | None = Field(None, ge=0, description="S/ por brigada por 4 semanas (supuesto)")
    costo_caso: float | None = Field(None, ge=0, description="S/ por caso atendido (supuesto)")


@app.get("/health")
def health():
    data, bundles = load()
    return {"status": "ok", "modelo_generado": data["generado"],
            "semana_actual": data["escenarios"]["actual"]["semana"],
            "modelo_en_produccion": data["escenarios"]["actual"]["modelo"],
            "reentrenamiento": (data.get("reentrenamiento") or {}).get("decision")}


@app.get("/distritos")
def distritos():
    data, _ = load()
    return [{k: d[k] for k in ("district_id", "district", "province", "department")}
            for d in data["distritos"]]


@app.post("/predict")
def predict(req: PredictRequest):
    try:
        return predict_district(req.district_id, req.escenario, req.lluvia_pct, req.temp_delta)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Distrito desconocido: {req.district_id}")


@app.post("/predict/batch")
def predict_batch(req: BatchRequest):
    return [predict(item) for item in req.items]


@app.post("/optimize")
def optimize_plan(req: OptimizeRequest):
    """Reparte las brigadas disponibles entre los distritos para evitar la mayor cantidad de casos."""
    rows = plan_inputs(req.escenario, req.departamento)
    return optimize(rows, req.brigadas, req.hab_por_brigada, req.efectividad, req.criterio, req.costo_brigada, req.costo_caso)


@app.get("/metricas")
def metricas():
    data, _ = load()
    return data["metricas"]


@app.get("/monitoreo")
def monitoreo():
    """Deriva de datos, desempeño por trimestre y resultado del último reentrenamiento campeón–retador."""
    data, _ = load()
    return {"monitoreo": data.get("monitoreo"), "reentrenamiento": data.get("reentrenamiento")}

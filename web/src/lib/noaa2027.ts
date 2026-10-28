// Generado por ml/src/export.py a partir de los pronósticos de NOAA CPC. No editar a mano.
export const NOAA2027 = {
  "descargado": "2026-10-28",
  "emitido": "2026-10",
  "estado_alerta": "El Niño Advisory",
  "discusion_emitida": "2026-10-08",
  "proxima_discusion": "12 November 2026",
  "evento_historico": {
    "definicion": "RONI de 3 meses de +2,5 °C o más: superaría todos los El Niño desde 1950",
    "probabilidades_pct": {
      "September-November": 54,
      "October-December": 83,
      "November-January": 70
    }
  },
  "indices_ultimo_mes_C": {
    "nino34": 2.1,
    "nino3": 3.0,
    "nino12": 3.9
  },
  "temporadas": [
    {
      "etiqueta": "sep 2026 – nov 2026",
      "el_nino_pct": 100,
      "neutral_pct": 0,
      "muy_fuerte_pct": 100,
      "fuerte_pct": 0
    },
    {
      "etiqueta": "oct 2026 – dic 2026",
      "el_nino_pct": 100,
      "neutral_pct": 0,
      "muy_fuerte_pct": 100,
      "fuerte_pct": 0
    },
    {
      "etiqueta": "nov 2026 – ene 2027",
      "el_nino_pct": 100,
      "neutral_pct": 0,
      "muy_fuerte_pct": 96,
      "fuerte_pct": 4
    },
    {
      "etiqueta": "dic 2026 – feb 2027",
      "el_nino_pct": 100,
      "neutral_pct": 0,
      "muy_fuerte_pct": 81,
      "fuerte_pct": 16
    },
    {
      "etiqueta": "ene 2027 – mar 2027",
      "el_nino_pct": 100,
      "neutral_pct": 0,
      "muy_fuerte_pct": 46,
      "fuerte_pct": 37
    },
    {
      "etiqueta": "feb 2027 – abr 2027",
      "el_nino_pct": 98,
      "neutral_pct": 2,
      "muy_fuerte_pct": 6,
      "fuerte_pct": 32
    },
    {
      "etiqueta": "mar 2027 – may 2027",
      "el_nino_pct": 85,
      "neutral_pct": 15,
      "muy_fuerte_pct": 0,
      "fuerte_pct": 5
    },
    {
      "etiqueta": "abr 2027 – jun 2027",
      "el_nino_pct": 45,
      "neutral_pct": 54,
      "muy_fuerte_pct": 0,
      "fuerte_pct": 0
    },
    {
      "etiqueta": "may 2027 – jul 2027",
      "el_nino_pct": 17,
      "neutral_pct": 70,
      "muy_fuerte_pct": 0,
      "fuerte_pct": 0
    }
  ],
  "nino12_observado": [
    {
      "mes": "2026-08",
      "valor": 4.09
    },
    {
      "mes": "2026-09",
      "valor": 4.7
    },
    {
      "mes": "2026-10",
      "valor": 5.26
    }
  ],
  "nino12_pronostico": [
    {
      "mes": "2026-11",
      "media": 3.97,
      "p10": 3.66,
      "p90": 4.26,
      "miembros": 40
    },
    {
      "mes": "2026-12",
      "media": 3.9,
      "p10": 3.61,
      "p90": 4.23,
      "miembros": 40
    },
    {
      "mes": "2027-01",
      "media": 3.62,
      "p10": 3.31,
      "p90": 3.96,
      "miembros": 40
    },
    {
      "mes": "2027-02",
      "media": 2.94,
      "p10": 2.54,
      "p90": 3.35,
      "miembros": 40
    },
    {
      "mes": "2027-03",
      "media": 2.48,
      "p10": 2.11,
      "p90": 2.78,
      "miembros": 40
    },
    {
      "mes": "2027-04",
      "media": 2.22,
      "p10": 1.85,
      "p90": 2.59,
      "miembros": 40
    },
    {
      "mes": "2027-05",
      "media": 2.89,
      "p10": 2.44,
      "p90": 3.32,
      "miembros": 40
    },
    {
      "mes": "2027-06",
      "media": 3.47,
      "p10": 2.89,
      "p90": 4.21,
      "miembros": 40
    },
    {
      "mes": "2027-07",
      "media": 2.28,
      "p10": 0.76,
      "p90": 4.05,
      "miembros": 40
    }
  ],
  "nino12_maximo": {
    "mes": "2026-11",
    "media": 3.97,
    "p10": 3.66,
    "p90": 4.26,
    "miembros": 40
  }
} as const;

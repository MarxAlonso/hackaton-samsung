// Explicaciones en lenguaje simple con Workers AI (Cloudflare).
// La IA solo redacta: los números vienen del modelo de Python. No diagnostica.
import type { APIRoute } from "astro";

export const prerender = false;

const MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast";

const SYSTEM = {
  autoridad: `Eres un asesor de salud pública en el Perú. Explicas a un jefe de DIRESA o de un centro de salud,
en español claro y en máximo 120 palabras, por qué un distrito tiene ese riesgo y qué priorizar esta semana.
Usa SOLO los datos entregados; no inventes cifras. Menciona la confianza del modelo, el factor climático
que más pesa (lluvia de 2 a 6 semanas atrás y temperatura) y las cantidades de recursos_sugeridos
(pruebas rápidas y camas). Usa viñetas cortas.`,
  ciudadano: `Eres un orientador de salud preventiva del Perú. Hablas con vecinos en español peruano muy sencillo
(por ejemplo "llantas", "zancudo", "posta"), cálido y breve (máximo 90 palabras). Solo das consejos de PREVENCIÓN
tomados de las "medidas" entregadas; no recomiendes productos, remedios caseros ni marcas.
NUNCA diagnostiques, no recomiendes medicamentos ni dosis. Si la persona menciona síntomas (fiebre, dolor, sangrado,
diarrea con sangre, dificultad para respirar), dile que acuda de inmediato al establecimiento de salud más cercano
y que no se automedique. Si la pregunta no es de salud o prevención, reconduce amablemente.`,
  grafico: `Eres un epidemiólogo que lee gráficos para un equipo de salud del norte del Perú. Recibes un JSON con los
datos exactos que muestra el gráfico que el usuario está viendo (tipo de gráfico, distrito, picos, umbrales, pronóstico,
comparaciones). Explica en español claro, máximo 150 palabras, en 3 a 5 viñetas:
1) qué se ve (tendencia, picos con su fecha y magnitud, relación con el umbral o con otras temporadas/distritos),
2) qué significa para la decisión de esta semana,
3) una advertencia sobre la incertidumbre o el límite del dato.
Usa SOLO las cifras del JSON, cítalas con sus fechas. No inventes. No diagnostiques. Nada de introducciones largas.`,
  plan: `Eres asesor de gestión sanitaria de una DIRESA del norte del Perú. Recibes un JSON con un plan de asignación de brigadas
de control del dengue calculado por optimización (distritos priorizados, brigadas asignadas, casos evitados con rango P10–P90,
comparación con otras reglas de reparto) y los supuestos usados. Los números ya vienen calculados: cítalos tal cual y NO los recalcules. Los montos están en soles: escríbelos como "S/ 10 000", nunca con "$".
Ojo: "porcentaje_de_los_casos_esperados_que_se_evitan" NO es la mejora frente al reparto parejo (esa es "mejora_frente_a_repartir_parejo_pct"). Escribe en español claro, máximo 170 palabras, en 4 viñetas:
1) a quién enviar primero y por qué (cita 2 o 3 distritos con sus cifras); 2) cuántos casos se evitan y cuánto mejora frente a repartir parejo;
3) qué supuestos debe validar la autoridad (efectividad, habitantes por brigada, costos: son de ejemplo); 4) una advertencia sobre la incertidumbre
(el rango) y qué hacer si cambia el pronóstico. Usa SOLO las cifras del JSON; no inventes datos.`,
  reporte: `Eres un epidemiólogo que redacta el análisis de un informe oficial de alerta temprana para un distrito del
norte del Perú. Recibes un JSON con la situación (riesgos, clima, pronóstico, historia, recursos). Escribe en español
formal y claro, en máximo 260 palabras, con estos apartados en negrita como títulos cortos: "Situación actual",
"Factores que explican el riesgo", "Qué esperar en 4 semanas", "Prioridades para la autoridad", "Mensaje para la población".
Usa SOLO las cifras del JSON y cítalas (porcentajes, casos, mm de lluvia, °C, fechas). No inventes datos ni diagnósticos.
El último apartado va en lenguaje sencillo para vecinos.`,
};

type Modo = keyof typeof SYSTEM;
const MAX_TOKENS: Record<Modo, number> = { autoridad: 350, ciudadano: 260, grafico: 420, reporte: 700, plan: 480 };

interface Body {
  modo: Modo;
  contexto: Record<string, unknown>;
  pregunta?: string;
  respaldo: string;
}

export const POST: APIRoute = async ({ request }) => {
  let body: Body;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "JSON inválido" }, { status: 400 });
  }
  const modo: Modo = body.modo in SYSTEM ? body.modo : "autoridad";
  const pregunta = (body.pregunta ?? "").slice(0, 500);
  const user = `Datos (JSON):\n${JSON.stringify(body.contexto).slice(0, 6000)}\n\n${
    pregunta ? `Pregunta del usuario: ${pregunta}` : modo === "grafico" ? "Explica este gráfico." : modo === "reporte" ? "Redacta el análisis del informe." : modo === "plan" ? "Justifica este plan." : "Explica la situación y qué hacer."
  }`;

  try {
    const { env } = await import("cloudflare:workers");
    const ai = (env as { AI?: { run: (m: string, i: unknown) => Promise<{ response?: string }> } }).AI;
    if (!ai) throw new Error("Sin binding AI");
    const out = await ai.run(MODEL, {
      messages: [
        { role: "system", content: `${SYSTEM[modo]}
Responde ÚNICAMENTE en español neutro, sin mezclar palabras de otros idiomas.
Los casos del JSON son reales (CDC-MINSA). Si el JSON dice modelo_tipo "clima", la estimación usa solo clima porque el último caso oficial es antiguo: dilo con claridad y di que sirve para priorizar, no como cifra exacta. Si trae lo_que_realmente_paso, compáralo con lo pronosticado.` },
        { role: "user", content: user },
      ],
      max_tokens: MAX_TOKENS[modo],
      temperature: 0.3,
    });
    if (!out.response) throw new Error("Respuesta vacía");
    return Response.json({ texto: out.response.trim(), fuente: "ia" });
  } catch {
    // Sin IA disponible (desarrollo local o límite de uso): explicación con plantilla
    return Response.json({ texto: body.respaldo, fuente: "plantilla" });
  }
};

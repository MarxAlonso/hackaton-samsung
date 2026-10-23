// Cliente del endpoint /api/explicar con texto de respaldo armado en el navegador.
export async function explain(modo: "autoridad" | "ciudadano" | "grafico" | "reporte" | "plan", contexto: object, respaldo: string, pregunta?: string) {
  try {
    const r = await fetch("/api/explicar", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ modo, contexto, pregunta, respaldo }),
    });
    if (!r.ok) throw new Error(String(r.status));
    return (await r.json()) as { texto: string; fuente: "ia" | "plantilla" };
  } catch {
    return { texto: respaldo, fuente: "plantilla" as const };
  }
}

const SYMPTOMS = /fiebre|dolor|sangr|v[oó]mit|diarrea|respir|desmay|mareo|ronchas|sarpullido|tengo|mi hij/i;

export function citizenFallback(pregunta: string, distrito: string, acciones: string[]) {
  if (SYMPTOMS.test(pregunta)) {
    return `Si tú o alguien de tu familia tiene síntomas, acude hoy al establecimiento de salud más cercano y no te automediques. ` +
      `Mientras tanto, toma líquidos y descansa. En ${distrito}, recuerda: ${acciones[0].toLowerCase()}`;
  }
  return `En ${distrito} lo más útil esta semana es:\n• ${acciones.slice(0, 3).join("\n• ")}\n` +
    `Si aparece fiebre u otro síntoma, acude al centro de salud.`;
}

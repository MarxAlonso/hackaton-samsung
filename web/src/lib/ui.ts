// Piezas de interfaz compartidas: apartado desplegable y botón «?» de ayuda.
// Se usan desde páginas Astro (componentes Acc y Help) y desde el HTML que arman los scripts.
import { icon } from "./icons";

/** Botón redondo «?» que abre la explicación de `key` (ver glossary.ts). */
const soloTexto = (s: string) => s.replace(/<[^>]*>/g, "").replace(/["<>&]/g, "").trim();
export const helpBtn = (key: string, label = "") => {
  const l = soloTexto(label);
  return `<button type="button" class="help" data-help="${key}" aria-label="¿Qué significa${l ? ` «${l}»` : ""}?" title="¿Qué significa?">?</button>`;
};

export interface AccOpts {
  title: string;
  /** Contenido del apartado (HTML). */
  body: string;
  /** Una línea visible aunque el apartado esté cerrado: el dato clave o de qué trata. */
  summary?: string;
  open?: boolean;
  icon?: string;
  /** Clave del glosario para el botón «?». */
  ayuda?: string;
  id?: string;
  cls?: string;
}

/** Encabezado clicable del apartado (lo que se ve cerrado). */
export function accSummary(o: Pick<AccOpts, "title" | "summary" | "icon" | "ayuda">) {
  return `<summary>
    ${o.icon ? `<span class="acc-ico">${icon(o.icon, 20)}</span>` : ""}
    <span class="acc-text">
      <span class="acc-title">${o.title}${o.ayuda ? helpBtn(o.ayuda, o.title) : ""}</span>
      ${o.summary ? `<span class="acc-sum">${o.summary}</span>` : ""}
    </span>
    <span class="acc-chev" aria-hidden="true">${icon("arrowRight", 18)}</span>
  </summary>`;
}

/** Apartado desplegable: cerrado muestra título y una línea; abierto, el detalle. */
export const acc = (o: AccOpts) =>
  `<details class="acc ${o.cls ?? ""}"${o.id ? ` id="${o.id}"` : ""}${o.open ? " open" : ""}>${accSummary(o)}<div class="acc-body">${o.body}</div></details>`;

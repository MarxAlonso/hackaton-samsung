// Movimiento discreto y accesible: aparición al hacer scroll y números que cuentan.
// Si la persona pidió menos movimiento (prefers-reduced-motion), todo se muestra de inmediato y sin animar.

const reduce = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Elementos con [data-reveal] aparecen al entrar en pantalla (una sola vez). */
export function initReveal(root: ParentNode = document) {
  const els = [...root.querySelectorAll<HTMLElement>("[data-reveal]")];
  if (!els.length) return;
  if (reduce() || !("IntersectionObserver" in window)) {
    els.forEach((e) => e.classList.add("in"));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    for (const en of entries) {
      if (!en.isIntersecting) continue;
      const el = en.target as HTMLElement;
      el.style.transitionDelay = `${Math.min(Number(el.dataset.reveal || 0), 600)}ms`;
      el.classList.add("in");
      io.unobserve(el);
    }
  }, { rootMargin: "0px 0px -4% 0px", threshold: 0.05 });
  els.forEach((e) => io.observe(e));
  // Red de seguridad: nada debe quedarse invisible por un fallo del observador (p. ej. impresión o navegadores viejos)
  setTimeout(() => els.forEach((e) => e.classList.add("in")), 2500);
  addEventListener("beforeprint", () => els.forEach((e) => e.classList.add("in")));
}

/** Números con [data-count="1234"] cuentan desde 0 cuando se ven. Respeta el formato de miles de Perú. */
export function initCountUp(root: ParentNode = document) {
  const els = [...root.querySelectorAll<HTMLElement>("[data-count]")];
  if (!els.length) return;
  const fmt = (v: number, dec: number) => v.toLocaleString("es-PE", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  const run = (el: HTMLElement) => {
    const target = Number(el.dataset.count);
    const dec = Number(el.dataset.dec ?? 0);
    const prefix = el.dataset.prefix ?? "", suffix = el.dataset.suffix ?? "";
    if (!Number.isFinite(target) || reduce()) { el.textContent = prefix + fmt(target, dec) + suffix; return; }
    const dur = 900, t0 = performance.now();
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / dur);
      const eased = 1 - Math.pow(1 - k, 3);
      el.textContent = prefix + fmt(target * eased, dec) + suffix;
      if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };
  if (!("IntersectionObserver" in window)) { els.forEach(run); return; }
  const done = new WeakSet<Element>();
  const go = (el: HTMLElement) => { if (!done.has(el)) { done.add(el); run(el); } };
  const io = new IntersectionObserver((entries) => {
    for (const en of entries) if (en.isIntersecting) { go(en.target as HTMLElement); io.unobserve(en.target); }
  }, { threshold: 0.2 });
  els.forEach((e) => io.observe(e));
  setTimeout(() => els.forEach(go), 2500);
}

export function initMotion() {
  initReveal();
  initCountUp();
}

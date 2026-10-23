// Iconos SVG de línea (estilo Lucide), 24×24, color = currentColor. Sin emojis en la web.
const wrap = (body: string, size = 20) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${body}</svg>`;

const BODIES: Record<string, string> = {
  textSize: `<path d="M3 19L8.5 5 14 19M5 14.5h7"/><path d="M15 19l3-8 3 8M16 16.5h4"/>`,
  volume: `<path d="M11 5L6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>`,
  stop: `<rect x="6" y="6" width="12" height="12" rx="2"/>`,
  flag: `<path d="M5 21V4M5 4h11l-1.5 4L16 12H5"/>`,
  home: `<path d="M3 11l9-8 9 8"/><path d="M5 10v10a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1V10"/>`,
  hospital: `<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M12 8v6M9 11h6M8 21v-4h8v4"/>`,
  pin: `<path d="M12 22s7-6.4 7-12a7 7 0 1 0-14 0c0 5.6 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/>`,
  sparkles: `<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 17l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z"/><path d="M4 3l.5 1.5L6 5l-1.5.5L4 7l-.5-1.5L2 5l1.5-.5z"/>`,
  alertOctagon: `<path d="M7.9 2h8.2L22 7.9v8.2L16.1 22H7.9L2 16.1V7.9z"/><path d="M12 8v4M12 16h.01"/>`,
  alertTriangle: `<path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>`,
  checkCircle: `<circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.3 2.3L16 10"/>`,
  sun: `<circle cx="12" cy="12" r="4.5"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>`,
  moon: `<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>`,
  mosquito: `<ellipse cx="12" cy="13" rx="2.2" ry="5"/><circle cx="12" cy="6.5" r="1.6"/><path d="M12 5l-2-3M12 5l2-3M10 11L4 8M14 11l6-3M10 14l-5 3M14 14l5 3M11 18l-2 4M13 18l2 4"/>`,
  water: `<path d="M2 15c2 0 2-1.5 4-1.5S8 15 10 15s2-1.5 4-1.5 2 1.5 4 1.5 2-1.5 4-1.5M2 19c2 0 2-1.5 4-1.5S8 19 10 19s2-1.5 4-1.5 2 1.5 4 1.5 2-1.5 4-1.5M8 10l4-6 4 6"/>`,
  droplet: `<path d="M12 3c-4 5-6 8.5-6 11.5a6 6 0 0 0 12 0C18 11.5 16 8 12 3z"/><path d="M9 15a3 3 0 0 0 3 3"/>`,
  lungs: `<path d="M12 3v8M12 11c-1 1-2 1.5-3 1.5M12 11c1 1 2 1.5 3 1.5"/><path d="M8.5 7C6 7 3 11 3 16c0 2.5 1.5 4 3.5 4S10 18.5 10 16V9.5C10 8 9.5 7 8.5 7zM15.5 7C18 7 21 11 21 16c0 2.5-1.5 4-3.5 4S14 18.5 14 16V9.5C14 8 14.5 7 15.5 7z"/>`,
  rain: `<path d="M17 16a4 4 0 0 0 .5-8 6 6 0 0 0-11.5 1.5A3.5 3.5 0 0 0 6.5 16"/><path d="M8 18l-1 3M12 18l-1 3M16 18l-1 3"/>`,
  thermometer: `<path d="M14 14.8V5a2 2 0 0 0-4 0v9.8a4 4 0 1 0 4 0z"/><path d="M12 9v6"/>`,
  wave: `<path d="M2 12c2.5 0 2.5-3 5-3s2.5 3 5 3 2.5-3 5-3 2.5 3 5 3"/><path d="M2 18c2.5 0 2.5-3 5-3s2.5 3 5 3 2.5-3 5-3 2.5 3 5 3"/>`,
  map: `<path d="M9 4L3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>`,
  chart: `<path d="M3 20h18"/><path d="M5 16l4-5 4 3 6-8"/>`,
  grid: `<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>`,
  layers: `<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5M3 17l9 5 9-5"/>`,
  compare: `<path d="M8 3v18M16 3v18"/><path d="M3 8h5M3 16h5M16 6h5M16 14h5"/>`,
  database: `<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>`,
  cpu: `<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>`,
  user: `<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>`,
  arrowRight: `<path d="M5 12h14M13 6l6 6-6 6"/>`,
  info: `<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>`,
  send: `<path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4z"/>`,
  activity: `<path d="M3 12h4l3-8 4 16 3-8h4"/>`,
  shield: `<path d="M12 2l8 3v6c0 5-3.5 9-8 11-4.5-2-8-6-8-11V5z"/><path d="M9 12l2 2 4-4"/>`,
  calendar: `<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>`,
  trendingUp: `<path d="M3 17l6-6 4 4 8-8"/><path d="M14 7h7v7"/>`,
  smartphone: `<rect x="6" y="2" width="12" height="20" rx="2.5"/><path d="M11 18h2"/>`,
  bell: `<path d="M6 8a6 6 0 0 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10.3 20a2 2 0 0 0 3.4 0"/>`,
  bellOff: `<path d="M8.7 3A6 6 0 0 1 18 8c0 2.6.4 4.5.9 5.8M6.3 6.3C6.1 6.9 6 7.4 6 8c0 7-3 8-3 8h13"/><path d="M10.3 20a2 2 0 0 0 3.4 0M2 2l20 20"/>`,
  share: `<path d="M12 15V3M8 7l4-4 4 4"/><path d="M6 11H5a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-6a2 2 0 0 0-2-2h-1"/>`,
  scale: `<path d="M12 3v18M7 21h10M5 7h14"/><path d="M5 7l-3 8a3.5 3.5 0 0 0 6 0zM19 7l-3 8a3.5 3.5 0 0 0 6 0z"/>`,
  target: `<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.2"/>`,
  fileText: `<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6M9 9h2"/>`,
  refresh: `<path d="M20 11a8 8 0 0 0-14.5-4.5L4 8"/><path d="M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.5 4.5L20 16"/><path d="M20 20v-4h-4"/>`,
  users: `<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18.5 14a6.5 6.5 0 0 1 3 6"/>`,
  coins: `<ellipse cx="9" cy="7" rx="6" ry="3"/><path d="M3 7v5c0 1.7 2.7 3 6 3s6-1.3 6-3V7"/><path d="M15 10.5c3.3 0 6 1.3 6 3v4c0 1.7-2.7 3-6 3-2.4 0-4.4-.7-5.4-1.7"/>`,
  award: `<circle cx="12" cy="9" r="6"/><path d="M8.5 14.5L7 22l5-3 5 3-1.5-7.5"/>`,
  download: `<path d="M12 3v12M7 10l5 5 5-5"/><path d="M4 20h16"/>`,
  flood: `<path d="M3 20h18"/><path d="M5 20v-6l7-6 7 6v6"/><path d="M2 16c2 0 2-1.2 4-1.2s2 1.2 4 1.2 2-1.2 4-1.2 2 1.2 4 1.2 2-1.2 4-1.2"/>`,
};

export function icon(name: keyof typeof BODIES | string, size = 20): string {
  const body = BODIES[name] ?? BODIES.info;
  return wrap(body, size);
}

export type IconName = keyof typeof BODIES;

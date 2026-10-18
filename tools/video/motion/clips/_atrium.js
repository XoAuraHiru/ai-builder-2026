// Shared by every Atrium clip: the brand, the narration's timing, and captions drawn like the recorded scenes'.
const D = __DATA__;
const $ = (id) => document.getElementById(id);
const C = {  // design system 0.2
  canvas: '#FFFFFF', wash: '#FAFAF7', sand1: '#F2F1EC', sand2: '#EBEAE4', sand3: '#DCDAD1',
  ink: '#1C1B17', ink2: '#3E3C35', muted: '#6F6C62', faint: '#9A968A',
  green: '#3F8160', green1: '#E0EDE4', green0: '#F0F6F2', green8: '#1D4532',
  coral: '#E8705F', coral7: '#B23F2E', coral0: '#FDEDEA', amber: '#E2B23E', amber0: '#FCF3D9',
  ai: '#7C74DB', ai7: '#4B44A6', ai0: '#F2F1FC', ai1: '#DCD9F7',
};
// more line icons on the engine's 24 grid (Lucide, ISC licence)
Object.assign(M.IC, {
  landmark: ['M3 22h18', 'M6 18v-7', 'M10 18v-7', 'M14 18v-7', 'M18 18v-7', 'M12 2l8 5H4z'],
  users: ['M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2', 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z', 'M22 21v-2a4 4 0 0 0-3-3.87', 'M16 3.13a4 4 0 0 1 0 7.75'],
  pie: ['M21.21 15.89A10 10 0 1 1 8 2.83', 'M22 12A10 10 0 0 0 12 2v10z'],
  swap: ['M8 3 4 7l4 4', 'M4 7h16', 'm16 21 4-4-4-4', 'M20 17H4'],
  book: ['M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20'],
  shield: ['M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z', 'm9 12 2 2 4-4'],
  mic: ['M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z', 'M19 10v2a7 7 0 0 1-14 0v-2', 'M12 19v3'],
  bell: ['M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9', 'M10.3 21a1.94 1.94 0 0 0 3.4 0'],
  share: ['M18 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z', 'M6 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z', 'M18 22a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z', 'm8.59 13.51 6.83 3.98', 'm15.41 6.51-6.82 3.98'],
  filecheck: ['M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z', 'M14 2v4a2 2 0 0 0 2 2h4', 'm9 15 2 2 4-4'],
  trend: ['m22 7-8.5 8.5-5-5L2 17', 'M16 7h6v6'],
  scale: ['m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z', 'm2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z', 'M7 21h10', 'M12 3v18', 'M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2'],
  server: ['M20 3H4a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2Z', 'M20 13H4a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-4a2 2 0 0 0-2-2Z', 'M6 7h.01', 'M6 17h.01'],
  database: ['M12 8c4.97 0 9-1.34 9-3s-4.03-3-9-3-9 1.34-9 3 4.03 3 9 3Z', 'M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5', 'M3 12c0 1.66 4 3 9 3s9-1.34 9-3'],
  globe: ['M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20Z', 'M2 12h20', 'M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z'],
  key: ['m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4', 'm21 2-9.6 9.6', 'M7.5 21a5.5 5.5 0 1 0 0-11 5.5 5.5 0 0 0 0 11Z'],
  bolt: ['M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z'],
  person: ['M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2', 'M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z'],
});
const WORDS = D.beats.flatMap((b) => b.words);
// When the narrator says a word (the first match at or after `from`), or `fallback` when it is never said.
function at(word, from = 0, fallback = null) {
  const re = new RegExp('^' + word, 'i');
  for (const w of WORDS) if (w[1] >= from && re.test(w[0].replace(/[^\w'+-]/g, ''))) return w[1];
  return fallback;
}
// Captions, as in the recorded scenes: a dark pill at the bottom, one readable piece at a time.
function captions(scale = 1) {
  const cap = document.createElement('div');
  Object.assign(cap.style, { position: 'absolute', left: '50%', bottom: (35 * scale) + 'px', transform: 'translateX(-50%)',
    maxWidth: (1360 * scale) + 'px', width: 'max-content', padding: `${15 * scale}px ${27 * scale}px ${16 * scale}px`,
    borderRadius: (19 * scale) + 'px', background: 'rgba(28,27,23,.86)', color: '#fff', fontSize: (25.3 * scale) + 'px',
    lineHeight: (36 * scale) + 'px', fontWeight: 500, letterSpacing: '-.005em', textAlign: 'center', textWrap: 'balance',
    fontFamily: "'Schibsted Grotesk', sans-serif", fontFeatureSettings: 'normal', zIndex: 20, opacity: 0 });
  $('stage').appendChild(cap);
  const pieces = D.beats.flatMap((b) => b.captions);
  return (t) => {
    const p = pieces.find(([a, b]) => t >= a && t < b);
    if (!p) { cap.style.opacity = 0; return; }
    M.setText(cap, p[2]);
    cap.style.opacity = Math.min(1, (t - p[0]) / 0.25, (p[1] - t) / 0.25).toFixed(3);
  };
}
function chipHTML(icon, text, fg, bg, size = 26) {
  return `<span style="display:inline-flex;align-items:center;gap:${size * 0.4}px;padding:${size * 0.35}px ${size * 0.7}px;border-radius:999px;background:${bg};color:${fg};font-size:${size}px;font-weight:600;white-space:nowrap">${icon ? M.icon(icon, size * 0.95, fg, 2.2) : ''}${text}</span>`;
}

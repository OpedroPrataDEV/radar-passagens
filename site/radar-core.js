/* Lógica pura do site (sem DOM): estatísticas do histórico, comparação de preço e gráficos em SVG. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.RadarCore = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  const MIN_DIAS = 3;  // dias de coleta mínimos para falar em histórico
  const MIN_OBS = 5;   // observações mínimas para comparar preços

  const utc = iso => { const [y, m, d] = iso.slice(0, 10).split('-').map(Number); return Date.UTC(y, m - 1, d); };
  const addDias = (iso, n) => new Date(utc(iso) + n * 864e5).toISOString().slice(0, 10);
  const diaSemana = iso => (new Date(utc(iso)).getUTCDay() + 6) % 7;  // 0 = segunda
  const brl = n => 'R$ ' + n.toFixed(2).replace('.', ',');
  const ddmm = iso => iso.slice(8, 10) + '/' + iso.slice(5, 7);
  const rotulo = x => (/^\d{4}-\d{2}-\d{2}/.test(x) ? ddmm(x) : x);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  // Chave de viagem, igual à do Python: fonte|AAAA-MM-DDTHH:MM|empresa
  const chaveViagem = t => `${t.fonte}|${t.data}T${t.hora}|${t.empresa}`;
  const lerChave = k => { const [fonte, saida, empresa] = k.split('|'); return { fonte, data: saida.slice(0, 10), hora: saida.slice(11, 16), empresa }; };

  // Reconstrói o preço de cada dia entre a primeira observação e `ate` (o preço vale até mudar).
  function expandir(s) {
    const p = (s && s.p) || [];
    if (!p.length) return [];
    const fim = s.ate && s.ate >= p[0][0] ? s.ate : p[0][0];
    const out = [];
    let i = 0;
    for (let d = p[0][0], n = 0; d <= fim && n < 800; d = addDias(d, 1), n++) {
      while (i + 1 < p.length && p[i + 1][0] <= d) i++;
      out.push({ dia: d, preco: p[i][1] });
    }
    return out;
  }

  // Viagens do histórico de uma rota que atendem aos filtros {dias, horaMin, horaMax}.
  function filtrar(rotaHist, f) {
    const dias = new Set((f && f.dias) || []);
    const out = [];
    for (const [chave, v] of Object.entries((rotaHist && rotaHist.viagens) || {})) {
      const c = lerChave(chave);
      if (dias.size && !dias.has(diaSemana(c.data))) continue;
      if (f && f.horaMin && c.hora < f.horaMin) continue;
      if (f && f.horaMax && c.hora > f.horaMax) continue;
      out.push({ chave, ...c, v });
    }
    return out;
  }

  const observacoes = viagens => viagens.flatMap(t => expandir(t.v).map(o => ({ dia: o.dia, preco: o.preco, chave: t.chave })));

  function estatisticas(obs) {
    if (!obs.length) return null;
    let min = Infinity, max = -Infinity, soma = 0;
    const dias = new Set();
    for (const o of obs) { if (o.preco < min) min = o.preco; if (o.preco > max) max = o.preco; soma += o.preco; dias.add(o.dia); }
    const ord = [...dias].sort();
    return { min, max, media: soma / obs.length, n: obs.length, dias: dias.size, primeiro: ord[0], ultimo: ord[ord.length - 1] };
  }

  function serieDiaria(obs) {
    const g = new Map();
    for (const o of obs) {
      const x = g.get(o.dia) || { dia: o.dia, min: Infinity, max: -Infinity, soma: 0, n: 0 };
      x.min = Math.min(x.min, o.preco); x.max = Math.max(x.max, o.preco); x.soma += o.preco; x.n++;
      g.set(o.dia, x);
    }
    return [...g.values()].sort((a, b) => (a.dia < b.dia ? -1 : 1)).map(x => ({ dia: x.dia, min: x.min, max: x.max, media: x.soma / x.n, n: x.n }));
  }

  const suficiente = est => !!est && est.dias >= MIN_DIAS && est.n >= MIN_OBS;

  // Compara um preço com o histórico observado. Sem base suficiente, diz isso em vez de opinar.
  function veredito(preco, obs) {
    const est = estatisticas(obs);
    if (!suficiente(est)) return { nivel: 'sem-base', texto: 'Sem histórico suficiente para comparar' };
    const pct = Math.round(100 * obs.filter(o => o.preco > preco).length / obs.length);
    if (preco <= est.min) return { nivel: 'minimo', pct, texto: 'Menor preço já registrado' };
    if (pct >= 75) return { nivel: 'barato', pct, texto: `Mais barata que ${pct}% dos preços registrados` };
    if (pct <= 25) return { nivel: 'caro', pct, texto: `Acima de ${100 - pct}% dos preços registrados` };
    return { nivel: 'normal', pct, texto: 'Dentro do preço habitual' };
  }

  // Menor preço de cada data entre as viagens atuais [{data, preco}] (corte transversal de hoje, não é histórico).
  function porData(viagens) {
    const g = new Map();
    for (const v of viagens) g.set(v.data, Math.min(g.has(v.data) ? g.get(v.data) : Infinity, v.preco));
    return [...g.entries()].sort().map(([x, y]) => ({ x, y }));
  }

  function limites(vals) {
    let lo = Math.min(...vals), hi = Math.max(...vals);
    if (lo === hi) { lo -= 1; hi += 1; }
    const m = (hi - lo) * 0.12;
    return [Math.max(0, lo - m), hi + m];
  }

  function eixoY(lo, hi, L, W, R, Y) {
    return [lo, (lo + hi) / 2, hi].map(v => `<line class="gl" x1="${L}" x2="${W - R}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}"/><text class="gt" x="${L - 6}" y="${(Y(v) + 4).toFixed(1)}" text-anchor="end">${Math.round(v)}</text>`).join('');
  }

  // Gráfico de linha: pts [{x, y}], opções {w, h, media, aria}. Devolve '' com menos de 2 pontos.
  function svgLinha(pts, o = {}) {
    if (!pts || pts.length < 2) return '';
    const W = o.w || 640, H = o.h || 220, L = 40, R = 12, T = 14, B = 28;
    const [lo, hi] = limites(pts.map(p => p.y).concat(o.media != null ? [o.media] : []));
    const X = i => L + i * (W - L - R) / (pts.length - 1);
    const Y = v => T + (hi - v) * (H - T - B) / (hi - lo);
    const f = n => n.toFixed(1);
    const linha = pts.map((p, i) => `${f(X(i))},${f(Y(p.y))}`).join(' ');
    const area = `${f(X(0))},${H - B} ${linha} ${f(X(pts.length - 1))},${H - B}`;
    const media = o.media != null ? `<line class="gm" x1="${L}" x2="${W - R}" y1="${f(Y(o.media))}" y2="${f(Y(o.media))}"/><text class="gt" x="${W - R}" y="${f(Y(o.media) - 5)}" text-anchor="end">média ${brl(o.media)}</text>` : '';
    const u = pts[pts.length - 1];
    return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.aria || 'Evolução do preço')}">${eixoY(lo, hi, L, W, R, Y)}<polygon class="ga" points="${area}"/><polyline class="gline" points="${linha}"/>${media}<circle class="gd" cx="${f(X(pts.length - 1))}" cy="${f(Y(u.y))}" r="4"/><text class="gt" x="${L}" y="${H - 8}">${rotulo(pts[0].x)}</text><text class="gt" x="${W - R}" y="${H - 8}" text-anchor="end">${rotulo(u.x)}</text></svg>`;
  }

  // Gráfico de barras: pts [{x, y}], opções {w, h, ref, aria}. Barras até `ref` ganham a classe "ok".
  function svgBarras(pts, o = {}) {
    if (!pts || !pts.length) return '';
    const W = o.w || 640, H = o.h || 220, L = 40, R = 12, T = 14, B = 28;
    const [, hi] = limites(pts.map(p => p.y).concat(o.ref != null ? [o.ref] : [0]));
    const Y = v => T + (hi - v) * (H - T - B) / hi;
    const f = n => n.toFixed(1);
    const passo = (W - L - R) / pts.length, bw = Math.max(3, Math.min(34, passo * 0.68));
    const cada = Math.ceil(pts.length / 8);
    const barras = pts.map((p, i) => {
      const x = L + i * passo + (passo - bw) / 2;
      const ok = o.ref != null && p.y <= o.ref;
      const lab = i % cada === 0 ? `<text class="gt" x="${f(x + bw / 2)}" y="${H - 8}" text-anchor="middle">${rotulo(p.x)}</text>` : '';
      return `<rect class="gb${ok ? ' ok' : ''}" x="${f(x)}" y="${f(Y(p.y))}" width="${f(bw)}" height="${f(H - B - Y(p.y))}" rx="2"><title>${rotulo(p.x)}: ${brl(p.y)}</title></rect>${lab}`;
    }).join('');
    const ref = o.ref != null ? `<line class="gref" x1="${L}" x2="${W - R}" y1="${f(Y(o.ref))}" y2="${f(Y(o.ref))}"/><text class="gt" x="${W - R}" y="${f(Y(o.ref) - 5)}" text-anchor="end">seu limite ${brl(o.ref)}</text>` : '';
    return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.aria || 'Menor preço por data')}">${eixoY(0, hi, L, W, R, Y)}${barras}${ref}</svg>`;
  }

  // Série fictícia, só para mostrar o visual do gráfico. Quem usar DEVE rotular como exemplo ilustrativo.
  function exemplo() {
    return Array.from({ length: 14 }, (_, i) => ({ x: 'dia ' + (i + 1), y: Math.round((46 + 9 * Math.sin(i / 2.2) - i * 0.5) * 10) / 10 }));
  }

  return { MIN_DIAS, MIN_OBS, addDias, diaSemana, brl, ddmm, esc, chaveViagem, lerChave, expandir, filtrar, observacoes, estatisticas, serieDiaria, suficiente, veredito, porData, svgLinha, svgBarras, exemplo };
});

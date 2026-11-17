const test = require('node:test');
const assert = require('node:assert/strict');
const C = require('../../site/radar-core.js');

const viagem = (p, ate) => ({ p, ate });
const hist = {
  viagens: {
    'buser|2026-11-19T07:20|Buser': viagem([['2026-11-14', 90], ['2026-11-16', 80]], '2026-11-17'), // qui 07:20
    'buser|2026-11-19T19:20|Buser': viagem([['2026-11-14', 60]], '2026-11-17'),                       // qui 19:20
    'buser|2026-11-20T07:20|Buser': viagem([['2026-11-14', 40]], '2026-11-15'),                       // sex 07:20
  },
};

test('expandir repete o preço até ele mudar e para em "ate"', () => {
  const s = viagem([['2026-11-14', 90], ['2026-11-16', 80]], '2026-11-17');
  assert.deepEqual(C.expandir(s).map(o => [o.dia, o.preco]), [['2026-11-14', 90], ['2026-11-15', 90], ['2026-11-16', 80], ['2026-11-17', 80]]);
  assert.deepEqual(C.expandir({ p: [], ate: '2026-11-17' }), []);
  assert.equal(C.expandir({ p: [['2026-11-14', 50]], ate: '2026-11-10' }).length, 1); // "ate" inválido não quebra
});

test('chave de viagem é igual à do Python e faz ida e volta', () => {
  const k = C.chaveViagem({ fonte: 'buser', data: '2026-11-19', hora: '07:20', empresa: 'Buser' });
  assert.equal(k, 'buser|2026-11-19T07:20|Buser');
  assert.deepEqual(C.lerChave(k), { fonte: 'buser', data: '2026-11-19', hora: '07:20', empresa: 'Buser' });
});

test('filtrar por dia da semana e faixa de horário', () => {
  assert.equal(C.filtrar(hist, {}).length, 3);
  assert.equal(C.filtrar(hist, { dias: [3] }).length, 2);                 // quintas
  assert.equal(C.filtrar(hist, { dias: [3], horaMin: '12:00' }).length, 1); // só 19:20
  assert.equal(C.filtrar(hist, { horaMax: '08:00' }).length, 2);
  assert.equal(C.filtrar(null, {}).length, 0);
});

test('estatísticas e série diária vêm só de observações reais', () => {
  const obs = C.observacoes(C.filtrar(hist, {}));
  const est = C.estatisticas(obs);
  assert.equal(est.min, 40); assert.equal(est.max, 90); assert.equal(est.n, obs.length);
  assert.equal(est.primeiro, '2026-11-14'); assert.equal(est.ultimo, '2026-11-17');
  const serie = C.serieDiaria(obs);
  assert.deepEqual(serie.map(s => s.dia), ['2026-11-14', '2026-11-15', '2026-11-16', '2026-11-17']);
  assert.equal(serie[0].min, 40); assert.equal(serie[0].max, 90);
  assert.equal(C.estatisticas([]), null);
});

test('suficiente exige dias e observações mínimos', () => {
  const poucos = C.observacoes(C.filtrar({ viagens: { 'buser|2026-11-19T07:20|Buser': viagem([['2026-11-14', 50]], '2026-11-15') } }, {}));
  assert.equal(C.suficiente(C.estatisticas(poucos)), false);
  assert.equal(C.suficiente(C.estatisticas(C.observacoes(C.filtrar(hist, {})))), true);
});

test('veredito não opina sem base e compara com o histórico quando há', () => {
  assert.equal(C.veredito(50, []).nivel, 'sem-base');
  const obs = C.observacoes(C.filtrar(hist, {}));
  assert.equal(C.veredito(40, obs).nivel, 'minimo');
  assert.equal(C.veredito(10, obs).nivel, 'minimo');
  assert.equal(C.veredito(95, obs).nivel, 'caro');
  assert.match(C.veredito(95, obs).texto, /Acima de/);
});

test('porData pega o menor preço de cada data, em ordem', () => {
  const r = C.porData([{ data: '2026-11-20', preco: 44.9 }, { data: '2026-11-19', preco: 83.9 }, { data: '2026-11-19', preco: 27.9 }]);
  assert.deepEqual(r, [{ x: '2026-11-19', y: 27.9 }, { x: '2026-11-20', y: 44.9 }]);
});

test('svgLinha: vazio com menos de 2 pontos, válido e sem NaN com 2 ou mais', () => {
  assert.equal(C.svgLinha([{ x: '2026-11-14', y: 50 }]), '');
  const svg = C.svgLinha([{ x: '2026-11-14', y: 50 }, { x: '2026-11-15', y: 50 }], { media: 50, aria: 'a "b"' });
  assert.match(svg, /<svg[\s\S]*<\/svg>/); assert.doesNotMatch(svg, /NaN|Infinity/);
  assert.match(svg, /14\/11/); assert.match(svg, /aria-label="a &quot;b&quot;"/);   // y constante e aria escapado
});

test('svgBarras marca as barras dentro do limite', () => {
  const svg = C.svgBarras([{ x: '2026-11-19', y: 27.9 }, { x: '2026-11-20', y: 44.9 }], { ref: 30 });
  assert.equal((svg.match(/class="gb ok"/g) || []).length, 1);
  assert.equal((svg.match(/class="gb"/g) || []).length, 1);
  assert.match(svg, /seu limite R\$ 30,00/); assert.doesNotMatch(svg, /NaN|Infinity/);
  assert.equal(C.svgBarras([]), '');
});

test('exemplo ilustrativo nunca parece data real', () => {
  const ex = C.exemplo();
  assert.ok(ex.length >= 2 && ex.every(p => /^dia \d+$/.test(p.x)));
  assert.match(C.svgLinha(ex), /dia 1/);
});

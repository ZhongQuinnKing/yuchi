#!/usr/bin/env node
/* 双端一致性回归：JS 分析器 vs Python 分析器，逐样本硬比对。
   散文：比分数与句数（py 走 --json）；诗：比行数与变异系数（py 走 --poem 文本）。
   任一样本不一致 → 退出码 1（CI 直接拦）。 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const here = __dirname;
const html = fs.readFileSync(path.join(here, 'web', 'index.html'), 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.error('未找到 script'); process.exit(1); }
const code = m[1].split('/* ================= 界面 ================= */')[0];
const fn = new Function(code + '\nreturn { analyze, analyzePoem };');
const { analyze, analyzePoem } = fn();

function load(p) {
  return fs.readFileSync(path.join(here, p), 'utf8')
    .split('\n').filter(l => !l.trim().startsWith('#')).join('\n');
}
function py(args) {
  return execSync(`python3 yuchi.py ${args}`, { encoding: 'utf8', cwd: here });
}

const PROSE = [
  'samples/luxun_qiuye.txt', 'samples/ai_sample.txt', 'samples/human/h_01.txt',
  'samples/ai_gen/ai_01.txt', 'samples/s_edge_quote.txt', 'samples/s_edge_mixed.txt',
  'samples/s_edge_glue_false.txt', 'samples/s_style_gongwen.txt',
  'samples/s_style_wechat.txt', 'samples/s_edge_dialogue.txt',
];
const POEMS = ['samples/poem_good.txt', 'samples/poem_flat.txt'];

let allOk = true;

console.log('── 散文样本：JS vs Python（分数 / 句数）──');
for (const f of PROSE) {
  const js = analyze(load(f));
  const pyData = JSON.parse(py(`"${f}" --json`));
  const same = js.score === pyData.score && js.n === pyData.metrics.sents;
  console.log(`${f}\tJS ${js.score}/${js.n}  PY ${pyData.score}/${pyData.metrics.sents}\t${same ? '✓' : '✗ 不一致'}`);
  if (!same) allOk = false;
}

console.log('\n── 诗样本：JS vs Python（行数 / 变异系数）──');
for (const f of POEMS) {
  const js = analyzePoem(load(f));
  const t = py(`"${f}" --poem`);
  const nPy = (t.match(/行数 (\d+)/) || [])[1];
  const cvPy = (t.match(/变异系数 ([\d.]+)/) || [])[1];
  const same = String(js.n) === nPy && Math.abs(js.cv - Number(cvPy)) < 0.005;
  console.log(`${f}\tJS ${js.n} 行 CV ${js.cv.toFixed(2)}  PY ${nPy} 行 CV ${cvPy}\t${same ? '✓' : '✗ 不一致'}`);
  if (!same) allOk = false;
}

console.log('\n── 近体诗：py 平仄标注与韵脚冒烟 ──');
const shi = py('"samples/shi_qijue.txt" --poem');
const shiOk = shi.includes('平仄标注') && shi.includes('韵脚');
console.log(`samples/shi_qijue.txt  ${shiOk ? '✓ 平仄与韵脚已在' : '✗'}`);
if (!shiOk) allOk = false;

console.log('\n── 纯英文：py 太短保护 ──');
const en = JSON.parse(py('"samples/s_edge_english.txt" --json'));
const enOk = en.error !== undefined;
console.log(`samples/s_edge_english.txt  ${enOk ? '✓ 已拦截' : '✗'}`);
if (!enOk) allOk = false;

console.log(allOk ? '\n✓ 双端一致（全部样本）' : '\n✗ 存在不一致，见上');
process.exit(allOk ? 0 : 1);

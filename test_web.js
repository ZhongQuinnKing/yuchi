#!/usr/bin/env node
/* 网页版一致性回归测试：提取 index.html 中的分析器，
   对样本跑分，与 yuchi.py 的结果逐项对照。 */
const fs = require('fs');
const path = require('path');

const here = __dirname;
const html = fs.readFileSync(path.join(here, 'web', 'index.html'), 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.error('未找到 script'); process.exit(1); }
const code = m[1].split('/* ================= 界面 ================= */')[0];
const fn = new Function(code + '\nreturn { analyze };');
const { analyze } = fn();

function load(p) {
  return fs.readFileSync(path.join(here, p), 'utf8')
    .split('\n').filter(l => !l.trim().startsWith('#')).join('\n');
}

const files = [
  'samples/luxun_qiuye.txt',
  'samples/ai_sample.txt',
  'samples/human/h_01.txt',
  'samples/ai_gen/ai_01.txt',
];
for (const f of files) {
  const r = analyze(load(f));
  console.log(`${f}\t分数 ${r.score}\t句数 ${r.n}\t大句CV ${r.cv.toFixed(2)}` +
              `\t小句CV ${r.clauseCv.toFixed(2)}\t平滑段 ${r.flatN}\t结构 ${r.struct}`);
}

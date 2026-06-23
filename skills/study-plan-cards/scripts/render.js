#!/usr/bin/env node
// Orchestrator: study-plan-cards → delegates rendering to study-cards engine.
// Usage:
//   node render.js --mode=from-plan-file [--source=cards/plan.json] [--output-dir=cards/] [--themes=light,dark]
//   node render.js --mode=from-state [--source=state/tasks.yaml] [--output-dir=cards/]
//   node render.js --mode=from-topics [--source=cards/plan.json]   # CardPlan built by agent
//   node render.js --mode=full [--plan-source=...] [--stats-source=...] [--output-dir=cards/]
const path = require('path');
const { execFileSync } = require('child_process');
const { parseArgs, ensureDir } = require('../../study-cards/lib/cli');
const { DEFAULT_THEME } = require('../../study-cards/lib/palette');

const ENGINE = path.join(__dirname, '..', '..', 'study-cards');
const args = parseArgs(process.argv);
const mode = args.mode || 'from-plan-file';
const outputDir = path.resolve(args['output-dir'] || 'cards');
const themes = args.themes || DEFAULT_THEME;

ensureDir(outputDir);

function runEngine(script, engineArgs) {
  execFileSync(process.execPath, [path.join(ENGINE, script), ...engineArgs], {
    stdio: 'inherit',
    env: process.env,
  });
}

function flag(name, value) {
  return value == null ? [] : [`--${name}=${value}`];
}

function renderPlan(source) {
  const src = source || path.join(outputDir, 'plan.json');
  const engineArgs = [
    ...flag('source', src),
    ...flag('output-dir', outputDir),
    ...flag('themes', themes),
  ];
  if (args['no-weeks']) engineArgs.push('--no-weeks');
  runEngine('render.js', engineArgs);
}

function renderStats(source) {
  const src = source || path.join('state', 'tasks.yaml');
  runEngine('render-stats.js', [
    ...flag('source', src),
    ...flag('output-dir', outputDir),
    ...flag('themes', themes),
  ]);
}

console.log(`study-plan-cards → study-cards (${mode}) → ${outputDir}`);

switch (mode) {
  case 'from-plan-file':
    renderPlan(args.source);
    break;
  case 'from-topics':
    // Agent assembles CardPlan JSON from exam-topics/profile.md, then reuses plan renderer.
    renderPlan(args.source || path.join(outputDir, 'plan.json'));
    break;
  case 'from-state':
    renderStats(args.source);
    break;
  case 'full':
    renderPlan(args['plan-source'] || args.source);
    renderStats(args['stats-source']);
    break;
  default:
    console.error(`Unknown mode "${mode}". Use: from-plan-file | from-topics | from-state | full`);
    process.exit(1);
}

console.log(`Output: ${outputDir}`);

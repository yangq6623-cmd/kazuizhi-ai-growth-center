const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.resolve(__dirname, '../../05_V2.0.0_Source/web/analytics.js'), 'utf8');
const section = (start, end) => source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)));
const elements = new Map();
const $ = id => {
  if (!elements.has(id)) elements.set(id, {textContent: '', className: ''});
  return elements.get(id);
};
const context = vm.createContext({$, esc: String, coreMissingLabels: () => '', renderCoreBusinessMetrics: () => {}});
vm.runInContext([
  source.match(/const CORE_BUSINESS_FIELDS = \[[\s\S]*?\];/)[0],
  section('function coreBusinessSnapshot(', 'function coreCompleteness('),
  section('function coreCompleteness(', 'function renderCoreBusinessMetrics('),
  section('function renderAnalyticsFromSource(', 'async function loadAnalytics('),
].join('\n'), context);

const sourceStatus = {
  status: 'configured', status_label: '等待验证',
  last_error: '无法连接卡嘴子真实经营数据接口',
  source: 'production_readonly', remote_as_of: '2026-10-28T06:45:00+08:00',
  summary: {
    funnel: {mini_program_visits: 0, repair_requests: 1, leads: 0},
    users: {new_today: 0}, orders: {today: 0, completed: 20, cancelled: 0},
  },
};
context.sourceStatus = sourceStatus;
vm.runInContext("renderAnalyticsFromSource(sourceStatus, {status: 'verified'})", context);
assert.doesNotMatch($('analytics-status').textContent, /已验证接入.*0\/7/);
assert.match($('analytics-status').textContent, /接口当前不可用/);
assert.match($('analytics-source').textContent, /2026-10-28/);
assert.match($('analytics-source').textContent, /无法连接/);

context.sourceStatus = {status: 'configured', last_error: '无法连接卡嘴子真实经营数据接口'};
vm.runInContext("renderAnalyticsFromSource(sourceStatus, {status: 'verified'})", context);
assert.match($('analytics-status').textContent, /当前未接入/);
assert.doesNotMatch($('analytics-badge').textContent, /0\/7/);

sourceStatus.status = 'connected';
sourceStatus.last_error = null;
sourceStatus.source = 'production_readonly';
sourceStatus.remote_as_of = '2026-10-28T06:45:00+08:00';
sourceStatus.summary = {
  funnel: {mini_program_visits: 0, repair_requests: 1, leads: 0},
  users: {new_today: 0}, orders: {today: 0, completed: 20, cancelled: 0},
};
context.sourceStatus = sourceStatus;
vm.runInContext("renderAnalyticsFromSource(sourceStatus, {status: 'verified'})", context);
assert.match($('analytics-status').textContent, /7\/7/);
assert.match($('analytics-badge').textContent, /7\/7/);
console.log('PASS: disconnected source shows historical age/error; connected source shows verified 7/7');

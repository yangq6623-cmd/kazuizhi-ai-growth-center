'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..', '..');
const sourcePath = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(root, '05_V2.0.0_Source', 'web', 'operational-device.js');
const source = fs.readFileSync(sourcePath, 'utf8');
const requests = [];
const assignedImageSources = [];
const elements = new Map();

class FakeClassList {
  constructor(active = false) {
    this.values = new Set(active ? ['active'] : []);
  }
  add(value) { this.values.add(value); }
  remove(value) { this.values.delete(value); }
  contains(value) { return this.values.has(value); }
  toggle(value, enabled) {
    if (enabled) this.values.add(value);
    else this.values.delete(value);
  }
}

function fakeElement(id) {
  if (elements.has(id)) return elements.get(id);
  const listeners = new Map();
  const element = {
    id,
    textContent: '',
    className: '',
    classList: new FakeClassList(id === 'device'),
    dataset: {},
    disabled: false,
    hidden: false,
    naturalWidth: 720,
    naturalHeight: 1280,
    listeners,
    addEventListener(name, handler) { listeners.set(name, handler); },
    querySelector() { return null; },
    removeAttribute(name) { if (name === 'src') this.src = ''; },
    setPointerCapture() {},
    getBoundingClientRect() { return {left: 0, top: 0, width: 720, height: 1280}; },
  };
  let src = '';
  Object.defineProperty(element, 'src', {
    get() { return src; },
    set(value) { src = String(value); if (id === 'device-screen') assignedImageSources.push(src); },
  });
  elements.set(id, element);
  return element;
}

const device = {
  connected: true,
  device_id: 'ELE-AL00-TEST',
  model: 'ELE-AL00',
  android_version: '10',
  battery: 95,
  screen_state: 'awake',
  screen_state_label: '亮屏/可操作',
  control_mode: 'human',
  screen: {width: 1080, height: 2244},
};
const deviceStatus = {
  devices: [device],
  primary_device_id: device.device_id,
  adb: {path: 'adb.exe'},
  message: '已连接',
};

async function fakeFetch(url, options = {}) {
  const request = {url: String(url), options};
  requests.push(request);
  if (request.url.startsWith('/api/r8/device/status')) {
    return {ok: true, status: 200, json: async () => deviceStatus};
  }
  if (request.url.startsWith('/api/r8/device/live-status')) {
    return {
      ok: true,
      status: 200,
      json: async () => ({
        state: 'streaming',
        fps: 18.5,
        frame_count: 42,
        last_frame_age_ms: 86,
        restart_count: 1,
      }),
    };
  }
  if (request.url === '/api/r8/device/action') {
    return {ok: true, status: 200, json: async () => ({ok: true})};
  }
  if (request.url.includes('/api/r8/device/screenshot')) {
    throw new Error('normal realtime mode must never request PNG screenshots');
  }
  throw new Error(`unexpected request: ${request.url}`);
}

const documentListeners = new Map();
const document = {
  visibilityState: 'visible',
  getElementById: fakeElement,
  querySelectorAll() { return []; },
  addEventListener(name, handler) { documentListeners.set(name, handler); },
  createElement(name) {
    if (name !== 'canvas') return fakeElement(`created-${name}`);
    return {
      width: 0,
      height: 0,
      getContext() { return {drawImage() {}}; },
      toDataURL() { return 'data:image/jpeg;base64,last-frame'; },
    };
  },
};

const context = {
  console,
  document,
  fetch: fakeFetch,
  setTimeout,
  clearTimeout,
  Date,
  Math,
  Number,
  Promise,
  Uint8Array,
  URL,
  encodeURIComponent,
};
context.window = context;
context.syncOperationalDeviceStatus = () => {};
context.notify = () => {};
vm.createContext(context);
vm.runInContext(source, context, {filename: 'operational-device.js'});

const delay = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

(async () => {
  await delay(20);
  await context.deviceCenterActivate();
  await delay(850);

  assert(
    assignedImageSources.some(value => value.startsWith('/api/r8/device/live?device_id=')),
    'Operational main image must connect directly to the persistent live stream',
  );
  assert(
    requests.some(request => request.url.startsWith('/api/r8/device/live-status')),
    'Operational page must poll lightweight live status separately',
  );
  assert.strictEqual(
    requests.filter(request => request.url.includes('/api/r8/device/screenshot')).length,
    0,
    'normal live mode must not continue the old screenshot polling loop',
  );
  assert.strictEqual(fakeElement('device-live-fps').textContent, '18.5 FPS');
  assert.strictEqual(fakeElement('device-live-latency').textContent, '86 ms');
  assert.strictEqual(fakeElement('device-live-fallback').textContent, '否');
  assert.match(fakeElement('device-live-state').textContent, /streaming/);

  const image = fakeElement('device-screen');
  image.listeners.get('pointerdown')({clientX: 200, clientY: 300, pointerId: 1});
  image.listeners.get('pointerup')({clientX: 200, clientY: 300, pointerId: 1});
  await delay(20);
  assert(
    requests.some(request => request.url === '/api/r8/device/action'),
    'ADB pointer control must remain available while the video stream is running',
  );
  assert.strictEqual(
    requests.filter(request => request.url.includes('/api/r8/device/screenshot')).length,
    0,
    'ADB control must not trigger a PNG refresh in normal live mode',
  );

  context.deviceCenterDeactivate();
  await delay(20);
  assert(
    !fakeElement('device-screen').src.includes('/api/r8/device/live'),
    'leaving the device page must close the browser live-stream request',
  );
  const liveAssignmentsBeforeResume = assignedImageSources.filter(value => value.startsWith('/api/r8/device/live?device_id=')).length;
  await context.deviceCenterActivate();
  await delay(20);
  assert(
    assignedImageSources.filter(value => value.startsWith('/api/r8/device/live?device_id=')).length > liveAssignmentsBeforeResume,
    'returning to the device page must automatically restore the live stream',
  );
  context.deviceCenterDeactivate();
  console.log('PASS: Operational live mode uses persistent stream, independent status/control, and zero PNG polling');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});

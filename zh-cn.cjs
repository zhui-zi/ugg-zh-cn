'use strict';

const { app, webContents, webFrameMain } = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, 'zh-cn-renderer.js'), 'utf8');
const attached = new WeakSet();

function allowed(url) {
  try {
    const target = new URL(url);
    if (target.protocol !== 'https:') return false;
    if (/aditude|oauth|login|signup|recover-account|reset-password|verification/i.test(target.pathname)) return false;
    if (target.hostname === 'static.bigbrain.gg') return /^\/app\/[^/]+\/ugg-[^/]+\.html$/.test(target.pathname);
    if (target.hostname === 'tracklock.gg') return /^\/app(?:\/|$)/.test(target.pathname) || /^\/heroes\/[^/]+\/build\/?$/.test(target.pathname);
    if (['u.gg', 'www.u.gg'].includes(target.hostname)) return /^\/(lol|wow|valorant)(?:\/|$)/.test(target.pathname);
    return false;
  } catch {
    return false;
  }
}

function inject(frame) {
  try {
    if (!frame || frame.isDestroyed() || !allowed(frame.url)) return;
    frame.executeJavaScript(source, false).catch(error => console.warn('[U.GG zh-CN] Translation unavailable:', error.message));
  } catch (error) {
    console.warn('[U.GG zh-CN] Frame unavailable:', error.message);
  }
}

function attach(contents) {
  if (attached.has(contents) || contents.isDestroyed()) return;
  attached.add(contents);
  contents.on('dom-ready', () => {
    try { for (const frame of contents.mainFrame.framesInSubtree) inject(frame); }
    catch (error) { console.warn('[U.GG zh-CN] Page unavailable:', error.message); }
  });
  contents.on('did-frame-finish-load', (_event, _main, processId, routingId) => {
    inject(webFrameMain.fromId(processId, routingId));
  });
}

app.on('web-contents-created', (_event, contents) => attach(contents));
app.whenReady().then(() => {
  for (const contents of webContents.getAllWebContents()) attach(contents);
});

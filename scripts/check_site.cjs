// Optional real-browser check; run against the static preview, not the Python game server.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {chromium} = require('playwright');
const url = process.argv[2] || 'http://127.0.0.1:8872/site/';
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'mission-pages-check-'));

async function rpc(page, route, payload) {
  return page.evaluate(async args => {
    try {
      const data = args.mutate ? await window.MissionBrowser.request(args.route, args.payload)
        : await window.MissionBrowser.request(args.route);
      return {status: 200, data};
    } catch (error) { return {status: error.status || 500, error: error.message}; }
  }, {route, payload, mutate: payload !== undefined});
}
function actionFor(view) {
  const spec = view.action_spec;
  switch (spec.type) {
    case 'prepare': case 'audit': return {type: spec.type, ability: null};
    case 'select_crew': return {type: spec.type, crew: spec.players.slice(0, spec.crew_size)};
    case 'pledge': return {type: spec.type, quantity: 0};
    case 'vote': return {type: spec.type, approve: true, influence: 0, complaints: []};
    case 'contribute': return {type: spec.type, tokens: {blue: 0, red: 0, green: 0}};
    case 'report': return {type: spec.type, statements: [{player_id: view.viewer, verb: 'gave', quantity: 0, color: 'blue'}]};
    default: throw new Error(`Unexpected action ${spec.type}`);
  }
}

(async () => {
  const browser = await chromium.launch({channel: process.env.BROWSER_CHANNEL || 'chrome', headless: true});
  try {
    const context = await browser.newContext({viewport: {width: 1440, height: 960}, reducedMotion: 'reduce'});
    await context.addInitScript(() => {
      try { localStorage.setItem('table-pace', '0'); } catch (_) {} // Initial about:blank has no storage origin.
    });
    const errors = [], networkAPI = [], external = [];
    context.on('page', page => page.on('pageerror', error => errors.push(error.message)));
    context.on('request', request => {
      if (new URL(request.url()).pathname.startsWith('/api/')) networkAPI.push(request.url());
      if (new URL(request.url()).origin !== new URL(url).origin) external.push(request.url());
    });
    const page = await context.newPage();
    await page.goto(url);
    await page.getByRole('button', {name: 'Take a seat'}).waitFor({timeout: 30000});
    await page.getByRole('button', {name: 'Take a seat'}).click();
    await page.locator('.table-heading').waitFor();
    const gameURL = page.url();
    const gameID = await page.evaluate(() => state.game.id);
    const route = `/api/games/${gameID}`;
    const ready = await rpc(page, route + '/resume', {paced: false});
    assert.equal(ready.status, 200, ready.error);
    const view = ready.data.observation;
    const second = await context.newPage();
    await second.goto(gameURL);
    await second.locator('.table-heading').waitFor({timeout: 30000});
    const decision = {request_id: view.request_id, revision: view.revision, action: actionFor(view), paced: true};
    assert.equal((await rpc(page, route + '/actions', decision)).status, 200);
    const saved = (await rpc(page, route + '/state')).data;
    const stale = await rpc(second, route + '/actions', {...decision, action: {...decision.action, type: 'stale'}});
    assert.equal(stale.status, 409, stale.error);
    assert.deepEqual((await rpc(second, route + '/state')).data, saved);
    await page.reload();
    await page.locator('.table-heading').waitFor({timeout: 30000});
    assert.deepEqual((await rpc(page, route + '/state')).data, saved);
    console.log('Save/reload, separate-tab updates, and stale-action protection passed.');

    // Each tab creates a distinct game while sharing the persisted library.
    const created = await Promise.all([page, second].map(p => rpc(p, '/api/games', {human_seat: 0, paced: true})));
    const catalog = (await rpc(page, '/api/games')).data.games;
    for (const result of created) assert.ok(catalog.some(g => g.id === result.data.game.id));
    console.log('Concurrent tabs preserve both new games.');

    // One small complete bot game exercises actual WASM replay construction.
    await page.goto(url);
    await page.getByRole('button', {name: 'Watch a sample game'}).waitFor({timeout: 30000});
    const sampleStarted = Date.now();
    await page.getByRole('button', {name: 'Watch a sample game'}).click();
    await page.locator('#designer-toggle').waitFor({timeout: 90000}).catch(async error => {
      console.error(await page.locator('body').innerText());
      throw error;
    });
    console.log(`Sample game and initial replay loaded in ${(Date.now() - sampleStarted) / 1000}s.`);
    await page.locator('#designer-toggle').check();
    await page.locator('#replay-player-assessment').waitFor();
    await page.getByRole('button', {name: 'Go to latest step'}).click();
    await page.locator('#replay-player-assessment tbody tr').first().waitFor({timeout: 30000});
    const position = await page.evaluate(() => state.replay.position);
    await page.locator('[data-command="inspect-player"][data-id="p3"]').click();
    await page.waitForFunction(() => state.replay.viewing_seat === 'p3');
    assert.equal(await page.evaluate(() => state.replay.position), position);
    assert.equal(await page.locator('#replay-player-assessment tbody tr').count(), 7);
    await page.locator('#replay-player-assessment').screenshot({path: path.join(artifacts, 'rankings-desktop.png')});
    await page.setViewportSize({width: 390, height: 844});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.locator('#replay-player-assessment').screenshot({path: path.join(artifacts, 'rankings-mobile.png')});
    await page.getByRole('button', {name: 'Go to start'}).click();
    await page.getByText('No player rankings recorded for this seat at this point in the replay.').waitFor();
    await page.locator('#designer-toggle').uncheck();
    await page.locator('#replay-player-assessment').waitFor({state: 'detached'});
    await page.reload();
    await page.locator('#designer-toggle').waitFor({timeout: 30000});
    assert.equal(await page.evaluate(() => state.game.status), 'FINISHED');
    assert.deepEqual(errors, []);
    assert.deepEqual(networkAPI, []);
    assert.deepEqual(external, []);
    console.log(`Completed replay, rankings, rewind, mobile layout, and static-only network checks passed. Screenshots: ${artifacts}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

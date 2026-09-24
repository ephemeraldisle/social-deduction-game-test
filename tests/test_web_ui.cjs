// Dependency-free tests of client projections and decision construction.
// Browser rendering is checked separately; these tests do not emulate a browser.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function resolvedClient() {
  const c = client();
  c.run(`state.observation.phase='report';state.observation.action_spec={type:'report',min_statements:1};
    state.observation.public.crew=['p1','p6'];
    state.observation.history=[
      {type:'mission_drawn',attempt:1,mission:{number:1,threshold:10,pot:{blue:2,red:0,green:0}}},
      {type:'crew_selected',attempt:1,chairman:'p3',crew:['p1','p6']},
      {type:'pledges_revealed',attempt:1,pledges:{p1:{blue:4,red:0,green:0},p6:{blue:3,red:0,green:1}}},
      {type:'attempt_resolved',attempt:1,mission:{number:1,threshold:10,crew_size:2,pot:{blue:7,red:2,green:1},winner:'blue'},
        score:{blue:1,red:0},wallets:{p1:1,p6:1},penalty:false}];
    state.observation.public.mission=state.observation.history[3].mission;
    captureResolution(state.observation);`);
  return c;
}

function client() {
  const source = fs.readFileSync(path.join(__dirname, '../mission_game/web/app.js'), 'utf8').replace(/\nboot\(\);\s*$/, '');
  const listeners = {};
  const context = vm.createContext({
    console, URLSearchParams, setTimeout, clearTimeout,
    document: {addEventListener: (type, callback) => { listeners[type] = callback; }, querySelector: () => null},
    window: {addEventListener() {}},
    location: {hash: '#library'},
  });
  vm.runInContext(source, context);
  const observation = {
    game_id: 'test', viewer: 'p0', phase: 'pledge', request_id: 'test:1:p0', revision: 1,
    action_spec: {type: 'pledge', max_total: 5}, status: 'ACTIVE',
    public: {players: Array.from({length: 8}, (_, i) => ({id: `p${i}`, name: ['Abby', 'Ben', 'Casey', 'Drew', 'Ellis', 'Fran', 'Gray', 'Harper'][i], wallet: 5})),
      mission: {number: 1, threshold: 10, crew_size: 3, pot: {blue: 0, red: 0, green: 0}, winner: null},
      rules: {abilities_enabled:false}, public_badges: {}, attempt: 1, rejections: 0, chairman: 'p0', crew: ['p0', 'p1', 'p2'], pledges: {}, votes: [], score: {blue: 0, red: 0}},
    private: {team: 'blue', objective: {id: 'loyalist', text: 'Win with Blue.'}, ability: {id: 'disabled'},
      last_contribution: null, submissions: []}, history: [],
  };
  context.fixture = observation;
  vm.runInContext('state.mode = "table"; state.game = {id: "test", title: "Test table"}; state.observation = fixture; resetDraft(fixture);', context);
  return {run: code => vm.runInContext(code, context), context, listeners};
}

test('AI prediction table labels uncertainty, links checkpoints, and escapes model evidence', () => {
  const c = client();
  c.context.predictions = [{mission: 1, position: 42, player_id: 'p0', summary: '<script>bad</script>',
    estimates: Array.from({length: 8}, (_, i) => ({player_id: `p${i}`, p_blue: i ? 0.6 : 1, evidence: '<img src=x>'}))}];
  const html = c.run('agentPredictionsHTML(predictions)');
  assert.ok(html.includes('AI team predictions'));
  assert.ok(html.includes('60%'));
  assert.ok(html.includes('data-position="42"'));
  assert.ok(html.includes('Red is the remaining probability'));
  assert.ok(html.includes('&lt;script&gt;bad&lt;/script&gt;'));
  assert.ok(!html.includes('<img src=x>'));
  assert.equal(c.run('agentPredictionsHTML()'), '');
});

test('token controls cannot submit over budget, negative, fractional, or empty values', () => {
  const c = client();
  for (const values of ['{blue:6,red:0,green:0}', '{blue:3,red:3,green:0}', '{blue:-1,red:0,green:0}', '{blue:0.5,red:0,green:0}', '{blue:NaN,red:0,green:0}']) {
    assert.equal(c.run(`state.draft.tokens=${values}; legalDraft()`), false);
  }
  assert.equal(c.run('state.draft.tokens={blue:2,red:0,green:3}; legalDraft()'), true);
  assert.equal(c.run('JSON.stringify(draftAction())'), '{"type":"pledge","tokens":{"blue":2,"red":0,"green":3}}');
});

test('crew selection and voting require an explicit complete choice', () => {
  const c = client();
  c.run('state.observation.action_spec={type:"select_crew",crew_size:3}; state.draft.crew=["p0","p1"];');
  assert.equal(c.run('legalDraft()'), false);
  c.run('state.draft.crew.push("p2")');
  assert.equal(c.run('legalDraft()'), true);
  c.run('state.observation.action_spec={type:"vote"};');
  assert.equal(c.run('legalDraft()'), false);
  c.run('state.draft.approve=false;state.draft.complaints=[{modifier:"less",player_id:"",color:""}]');
  assert.equal(c.run('legalDraft()'), false);
  c.run('state.draft.complaints[0].color="red"');
  assert.equal(c.run('legalDraft()'), true);
  assert.equal(c.run('JSON.stringify(draftAction())'), '{"type":"vote","approve":false,"complaints":[{"modifier":"less","color":"red"}]}');
});

test('crew reporting requires statements, false claims are allowed, and off-crew has no report controls', () => {
  const c = client();
  c.run('state.observation.action_spec={type:"report",min_statements:1}; state.draft.statements=[]');
  assert.equal(c.run('legalDraft()'), false);
  c.run('state.draft.statements=[{player_id:"p7",verb:"took",quantity:999,color:"red"}]');
  assert.equal(c.run('legalDraft()'), true);
  c.run('state.draft.statements[0].quantity=2147483648');
  assert.equal(c.run('legalDraft()'), false);
  c.run('state.observation.phase="report"; state.observation.public.crew=["p1","p2"]; state.observation.action_spec=null');
  assert.equal(c.run('legalDraft()'), false);
  const html = c.run('actionHTML(state.observation)');
  assert.ok(!html.includes('Seal my report'));
  assert.ok(!html.includes('data-kind="statements"'));
});

test('No requires a single complaint and switching to Yes clears it', () => {
  const c = client();
  c.run('state.observation.action_spec={type:"vote"}; setVoteChoice(false)');
  assert.equal(c.run('legalDraft()'), false);
  assert.equal(c.run('state.draft.complaints.length'), 1);
  let html = c.run('actionHTML(state.observation)');
  assert.ok(html.includes('Why are you voting No?'));
  assert.ok(!html.includes('data-command="add-row"'));
  assert.ok(!html.includes('data-command="remove-row"'));
  c.run('state.draft.complaints[0]={modifier:"more",player_id:"p0",color:""}');
  assert.equal(c.run('legalDraft()'), true);
  c.run('state.draft.complaints.push({color:"red"})');
  assert.equal(c.run('legalDraft()'), false);
  c.run('setVoteChoice(true)');
  assert.equal(c.run('legalDraft()'), true);
  assert.equal(c.run('JSON.stringify(draftAction().complaints)'), '[]');
  assert.ok(!c.run('actionHTML(state.observation)').includes('Required complaint'));
  c.run('setVoteChoice(false)');
  assert.equal(c.run('legalDraft()'), false);
});

test('vote prompt names the proposer while pledges and ballots stay on the table', () => {
  const c = client();
  c.run(`state.observation.action_spec={type:"vote"};state.observation.phase="vote";
    state.observation.public.chairman="p5";state.observation.public.crew=["p1","p6"];
    state.observation.public.pledges={p1:{blue:3,red:0,green:2},p6:{blue:0,red:0,green:0},p3:{blue:99,red:0,green:0}};
    state.observation.public.votes=[{player_id:"p5",approve:true},{player_id:"p6",approve:false},{player_id:"p7",approve:true}];`);
  const html = c.run('actionHTML(state.observation)');
  assert.ok(html.includes('Does Fran’s crew have your vote?'));
  const board = c.run('playersHTML(state.observation)');
  assert.ok(board.includes('Pledged 3 Blue + 2 Green'));
  assert.ok(board.includes('Pledged 0 tokens'));
  assert.ok(board.includes('2 Yes · 1 No · 3/8 voted'));
  assert.ok(!html.includes('vote-crew'));
  assert.ok(!board.includes('99 Blue'));
  assert.ok(!html.includes('99 Blue'));
  assert.ok(!html.includes('Review the crew and its pledges'));
  assert.ok(!html.includes('Five Yes votes are needed'));
  c.run('state.observation.public.players[5].name="<img src=x>";state.observation.public.votes=[]');
  const fresh = c.run('actionHTML(state.observation)');
  assert.ok(fresh.includes('Does &lt;img src=x&gt;’s crew have your vote?'));
  assert.ok(!fresh.includes('<img'));
  assert.ok(c.run('missionHTML(state.observation)').includes('0 Yes · 0 No · 0/8 voted'));
});

test('No complaints appear on voter cards, escape names, and clear with a new proposal', () => {
  const c = client();
  c.run(`state.observation.public.players[2].name="<img src=x>";
    state.observation.public.votes=[{player_id:"p0",approve:false,complaints:[{modifier:"more",player_id:"p0"}]},
    {player_id:"p1",approve:false,complaints:[{modifier:"less",player_id:"p2"}]}];`);
  for (const mode of ['table', 'replay']) {
    c.context.viewMode = mode;
    const html = c.run('state.mode=viewMode; playersHTML(state.observation)');
    assert.ok(html.includes('Voted No'));
    assert.ok(html.includes('More me'));
    assert.ok(html.includes('Less &lt;img'));
    assert.ok(!html.includes('<img'));
  }
  c.run('state.observation.public.votes=[]');
  assert.ok(!c.run('playersHTML(state.observation)').includes('player-complaint'));
  c.run(`state.observation.history=[{type:"crew_selected",attempt:1,chairman:"p0",crew:["p0","p1"]},
    {type:"vote",attempt:1,player_id:"p0",approve:false,complaints:[{modifier:"more",player_id:"p0"}]},
    {type:"proposal_rejected",attempt:1},{type:"crew_selected",attempt:1,chairman:"p1",crew:["p1","p2"]}];`);
  const next = c.run('playersHTML(state.observation)');
  assert.ok(next.includes('Voted No · Proposal 1'));
  assert.ok(next.includes('More me'));
});

test('untrusted player names and claims are escaped in the board and history', () => {
  const c = client();
  c.run('state.observation.public.players[0].name="<img src=x onerror=alert(1)>"');
  const board = c.run('playersHTML(state.observation)');
  assert.ok(!board.includes('<img'));
  assert.ok(board.includes('&lt;img'));
  const history = c.run('eventHTML({type:"reports_revealed",reports:{p0:[{player_id:"p0",verb:"gave",quantity:1,color:"blue"}]}})');
  assert.ok(!history.includes('<img'));
  assert.ok(history.includes('CLAIM'));
});

test('replay shows a private sealed decision without rendering live action controls', () => {
  const c = client();
  c.run(`state.mode="replay"; state.observation.private.submissions=[{action:{type:"pledge",tokens:{blue:2,red:1,green:0}}}];
    state.replay={observation:state.observation,designer:null,designer_enabled:false,can_inspect:false,viewing_seat:"p0",step:0,total_steps:1,timeline:[{step:0,attempt:1,label:"Your pledge is sealed"}]};`);
  const html = c.run('tableHTML()');
  assert.ok(html.includes('Last private decision · Pledge'));
  assert.ok(html.includes('2 Blue + 1 Red'));
  assert.ok(!html.includes('id="decision-form"'));
  assert.ok(!html.includes('Behind the result'));
  assert.ok(!html.includes('id="designer-toggle"'));
  assert.ok(!html.includes('id="replay-seat"'));
  c.run('state.replay.can_inspect=true');
  assert.ok(c.run('tableHTML()').includes('id="designer-toggle"'));
});

test('changing replay perspective or designer view keeps the shared position in requests and links', async () => {
  const c = client(), requests = [], links = [];
  c.context.recordRequest = path => requests.push(path);
  c.context.history = {replaceState: (_, __, url) => links.push(url)};
  c.run(`render=()=>{};state.mode="replay";
    state.replay={step:17,position:42,viewing_seat:"p0",designer_enabled:false};
    api=async path=>{recordRequest(path);const params=new URLSearchParams(path.split("?")[1]);
      return {step:params.get("designer")==="true" ? 42 : 12,position:42,total_steps:100,
        viewing_seat:params.get("seat"),designer_enabled:params.get("designer")==="true",observation:fixture};};`);
  c.listeners.change({target:{id:'replay-seat',value:'p3',dataset:{}}});
  await new Promise(setImmediate);
  assert.equal(c.run('state.replay.viewing_seat'),'p3');
  assert.equal(c.run('state.replay.step'),12);
  c.listeners.change({target:{id:'designer-toggle',checked:true,dataset:{}}});
  await new Promise(setImmediate);
  assert.equal(c.run('state.replay.step'),42);
  for (const url of [...requests, ...links]) {
    const params = new URLSearchParams(url.split('?')[1]);
    assert.equal(params.get('position'),'42');
    assert.equal(params.get('seat'),'p3');
    assert.equal(params.has('step'),false);
  }
  assert.equal(new URLSearchParams(requests[1].split('?')[1]).get('designer'),'true');
});

test('penalty attempts are described as no crew rather than a new selection', () => {
  const c = client();
  c.run('state.observation.phase="report";state.observation.public.crew=[];state.observation.public.rejections=8;state.observation.action_spec={type:"report",min_statements:0}');
  const html = c.run('playersHTML(state.observation)');
  assert.ok(html.includes('five-Red penalty'));
  assert.ok(!html.includes('The chairman is choosing'));
});

test('a new request resets drafts but rerendering the same request preserves them', () => {
  const c = client();
  c.run('state.draft.tokens.blue=4; resetDraft(state.observation)');
  assert.equal(c.run('state.draft.tokens.blue'), 4);
  c.run('state.observation.request_id="test:2:p0"; resetDraft(state.observation)');
  assert.equal(c.run('state.draft.tokens.blue'), 0);
});

test('private objective progress remains hidden when the engine supplies no global total', () => {
  const c = client();
  c.run(`state.observation.private.objective={id:"opposition_patron",text:"Your card instructions.",
    progress:{label:"Table-wide paid deposits",text:"Global progress is hidden.",value:null,target:20,condition_met:null}}`);
  const html = c.run('privateHTML(state.observation)');
  assert.ok(html.includes('Global progress is hidden.'));
  assert.ok(!html.includes('condition still needed'));
  assert.ok(!html.includes('condition currently met'));
  assert.match(html, /data-private-detail="p0:objective:opposition_patron"\s*>/);
  assert.ok(html.includes('Blue wins + 20+ Red tokens paid into missions.'));
  const summaries = [...html.matchAll(/<summary>(.*?)<\/summary>/gs)].map(m => m[1]).join(' ');
  assert.ok(!summaries.includes('Global progress'));
  assert.ok(!summaries.includes('Your card instructions.'));
  c.run('state.observation.private.team="red"');
  assert.equal(c.run('objectiveSummary(state.observation)'), 'Red wins + 20+ Blue tokens paid into missions.');
});

test('compact private cards retain expanded explanations and adapt after swaps or replay seat changes', () => {
  const c = client();
  c.run('state.observation.private.ability={id:"thief",text:"Full thief instructions.",uses_remaining:1}');
  let html=c.run('privateHTML(state.observation)');
  assert.ok(html.includes('Steal up to 3 tokens once.'));
  assert.match(html, /data-private-detail="p0:ability:thief"\s*>/);
  c.listeners.toggle({target:{dataset:{privateDetail:'p0:ability:thief'},isConnected:true,open:true}});
  assert.match(c.run('privateHTML(state.observation)'), /data-private-detail="p0:ability:thief" open>/);
  c.run('state.observation.viewer="p1"');
  assert.match(c.run('privateHTML(state.observation)'), /data-private-detail="p1:ability:thief"\s*>/);
  c.run('state.observation.viewer="p0";state.observation.private.objective.id="close_race"');
  for (const target of [3,4]) {
    c.run(`state.observation.public.rules.missions_to_win=${target}`);
    assert.equal(c.run('objectiveSummary(state.observation)'), `Blue wins ${target}–${target-1}.`);
  }
  c.run('state.observation.private.objective.id="contrarian"');
  assert.equal(c.run('objectiveSummary(state.observation)'), 'Your team loses; Red wins.');
});

test('final personal outcome uses the engine explanation for Contrarian and failed conditions', () => {
  const c = client();
  c.run(`state.observation.phase="game_over"; state.observation.public.result={winner:"red"};
    state.observation.private.result={won:true,wallet:7,text:"Your team lost, fulfilling Contrarian. You won."};`);
  const html = c.run('actionHTML(state.observation)');
  assert.ok(html.includes('Your team lost, fulfilling Contrarian. You won.'));
  assert.ok(!html.includes('You won with your team.'));
  c.run('state.observation.private.result={won:false,wallet:7,text:"Your team won, but your personal condition was not satisfied."}');
  assert.ok(c.run('actionHTML(state.observation)').includes('personal condition was not satisfied'));
});

test('designer inspection shows saved bot explanations and escapes their contents', () => {
  const c = client();
  c.run(`state.replay={designer_enabled:true};
    fixtureDesigner={players:[],sealed_submissions:{},last_resolution:null,
      last_action:{player_id:"p1",action:{type:"vote",approve:false}},
      bot_decision:{policy_version:"straightforward.1",reason:"Voted No: forecast favors Red.",
        details:{forecast:"<img src=x onerror=alert(1)>"},limitations:["No trust inference."]}};`);
  const html = c.run('designerHTML(fixtureDesigner)');
  assert.ok(html.includes('WHY THIS BOT ACTED'));
  assert.ok(html.includes('Voted No: forecast favors Red.'));
  assert.ok(html.includes('No trust inference.'));
  assert.ok(!html.includes('<img'));
  assert.ok(html.includes('&lt;img'));
  assert.equal(c.run('designerHTML(null)'), '');
  c.run('fixtureDesigner.bot_decision=null');
  assert.ok(c.run('designerHTML(fixtureDesigner)').includes('No saved bot explanation'));
});

test('social designer details show separate beliefs, personality and attributed evidence', () => {
  const c = client();
  c.run(`socialDetails={traits:{selfishness:.9,caution:.2,skepticism:.3},objective:"saver",tactical_side:"blue",
    forecast_pot:{blue:6.2,red:1.1,green:0},approval_likelihood:.6,vote_likelihoods:{p1:.7},
    outcome_likelihoods:{blue:.55,red:.25,incomplete:.2,personal_win:.55,personal_loss:.25,continues:.2},
    beliefs:{p1:{blue_preference:.4,pledge_reliability:.3,report_credibility:.8,inclusion_demand:.9,
      evidence:[{event_id:12,text:"<img src=x> claimed Red."}]}}};`);
  const html = c.run('socialInsightsHTML(socialDetails)');
  for (const text of ['Self-interest 90%', 'Risk caution 20%', 'Keeps pledges', 'Report credibility', 'Wants inclusion', 'Ben', '60%', '70%', 'Event 12', '&lt;img', 'Blue 55%', 'Red 25%', 'Unfinished 20%', 'Personal result this attempt', 'Game continues 20%']) {
    assert.ok(html.includes(text), text);
  }
  assert.ok(!html.includes('<img'));
  assert.equal(c.run('socialInsightsHTML({})'), '');
  c.run('socialDetails.concealing_red_intent=true; socialDetails.advertised_pot={blue:8,red:0,green:0}; socialDetails.planned_deposit={blue:0,red:5,green:0}');
  const covert = c.run('socialInsightsHTML(socialDetails)');
  assert.ok(covert.includes('Private forecast'));
  assert.ok(covert.includes('Forecast with my public promise'));
  assert.ok(covert.includes('Private spending plan:</b> 5 Red'));
});

test('private ability controls build passes, targets, off-crew deposits, and color changes', () => {
  const c = client();
  for (const id of ['scout', 'switcher', 'auditor']) {
    c.context.abilityId = id;
    c.run('state.observation.action_spec={type:abilityId === "auditor" ? "audit" : "prepare",ability:{id:abilityId,targets:["p1","p2"]}};state.draft.ability.target="p1";state.draft.ability.active=false;');
    assert.equal(c.run('legalDraft()'), true);
    assert.equal(c.run('draftAction().ability'), null);
    c.run('state.draft.ability.active=true');
    assert.equal(c.run('JSON.stringify(draftAction().ability)'), '{"target":"p1"}');
    assert.ok(c.run('actionHTML(state.observation)').includes('data-ability="target"'));
    c.run('state.draft.ability.target="p7"');
    assert.equal(c.run('legalDraft()'), false);
  }
  c.run('state.observation.action_spec={type:"contribute",on_crew:false,max_total:0,ability:{id:"stowaway",colors}};state.draft.ability.color="green"');
  assert.equal(c.run('JSON.stringify(draftAction())'), '{"type":"contribute","tokens":{"blue":0,"red":0,"green":0},"ability":{"color":"green"}}');
  assert.ok(!c.run('actionHTML(state.observation)').includes('id="token-blue"'));
  c.run('state.observation.action_spec.ability={id:"recolorer",colors};state.draft.ability.from="blue";state.draft.ability.to="blue"');
  assert.equal(c.run('legalDraft()'), false);
  c.run('state.draft.ability.to="red"');
  assert.equal(c.run('legalDraft()'), true);
  assert.equal(c.run('JSON.stringify(draftAction().ability)'), '{"from":"blue","to":"red"}');
});

test('combined contribution and theft respects independent budgets and rejects invalid amounts', () => {
  const c = client();
  c.run('state.observation.action_spec={type:"contribute",on_crew:true,max_total:5,ability:{id:"thief",targets:["p1"]}};state.draft.ability.active=true;state.draft.tokens.blue=5');
  assert.equal(c.run('legalDraft()'), true);
  c.run('state.draft.ability.tokens={blue:2,red:2,green:0}');
  assert.equal(c.run('legalDraft()'), false);
  c.run('state.draft.ability.tokens={blue:0,red:0,green:0}');
  assert.equal(c.run('legalDraft()'), false);
  c.run('state.draft.ability.source="wallet";state.draft.ability.target="p1";state.draft.ability.amount=3');
  assert.equal(c.run('legalDraft()'), true);
  assert.equal(c.run('JSON.stringify(draftAction().ability)'), '{"source":"wallet","target":"p1","amount":3}');
  for (const amount of [0, 4, -1, .5, NaN]) {
    c.context.amount = amount;
    c.run('state.draft.ability.amount=amount');
    assert.equal(c.run('legalDraft()'), false);
  }
  c.run('state.draft.ability.active=false');
  assert.equal(c.run('legalDraft()'), true);
  c.run('state.draft.tokens.blue=6');
  assert.equal(c.run('legalDraft()'), false);
});

test('own receipts, use counters, and official badges render without live controls in replay', () => {
  const c = client();
  c.run(`state.observation.private.ability={id:"scout",text:"Your own instructions.",uses_remaining:0};
    state.observation.private.receipts=[{type:"scout",attempt:1,target:"p1",team:"red"},
      {type:"objective_changed",attempt:2,objective:{name:"Saver",text:"Need 10 tokens.",progress:{text:"Current wallet: 5."}}}];
    state.observation.public.public_badges={p3:"blue"};state.observation.public.players[1].name="<img src=x>";`);
  const html = c.run('privateHTML(state.observation)');
  assert.ok(html.includes('Once per game · Used'));
  assert.ok(html.includes('is Red.'));
  assert.ok(html.includes('objective changed to Saver'));
  assert.ok(html.includes('&lt;img'));
  assert.ok(!html.includes('<img'));
  assert.ok(!html.includes('decision-form'));
  assert.ok(c.run('playersHTML(state.observation)').includes('Blue · Official badge'));
});

test('score display follows each table target, including old saves', () => {
  const c=client();
  c.run('state.observation.public.rules.missions_to_win=4; state.observation.public.score.blue=3');
  let html=c.run('missionHTML(state.observation)');
  assert.ok(html.includes('First team to 4 missions wins'));
  assert.ok(html.includes('Blue: 3 of 4 missions'));
  assert.equal((html.match(/<i class="on"><\/i>/g)||[]).length,3);
  c.run('state.observation.public.rules.missions_to_win=3');
  assert.ok(c.run('missionHTML(state.observation)').includes('First team to 3 missions wins'));
});

test('wallet deltas exclude income while still using the correct pre-resolution balance', () => {
  const c=client();
  c.run(`state.observation.history=[
    {id:1,attempt:1,type:'vote_income',wallets:{p0:6,p1:6}},
    {id:2,attempt:1,type:'attempt_resolved',wallets:{p0:2,p1:7}},
    {id:3,attempt:1,type:'income',wallets:{p0:3,p1:8}}];`);
  const rows=JSON.parse(c.run('JSON.stringify(walletLedger(state.observation).filter(r=>r.pid==="p0"))'));
  assert.deepEqual(rows.map(r=>[r.before,r.after,r.delta,r.reason]),[[6,2,-4,'Mission resolution']]);
  const html=c.run('playersHTML(state.observation)');
  assert.ok(html.includes('6 → 2 (-4), attempt 1'));
  assert.ok(!html.includes('Vote revenue'));
  assert.ok(!html.includes('Attempt income'));
  assert.ok(!html.includes('No recorded change'));
});

test('mission comparison preserves prior pots and distinguishes reset after a win', () => {
  const c=client();
  c.run(`state.observation.history=[
    {id:1,attempt:1,type:'mission_drawn',mission:{number:1,pot:{blue:0,red:0,green:0}}},
    {id:2,attempt:1,type:'attempt_resolved',mission:{number:1,pot:{blue:2,red:3,green:1}}},
    {id:3,attempt:2,type:'attempt_resolved',mission:{number:1,pot:{blue:5,red:3,green:2}}}];
    state.observation.public.mission.pot={blue:5,red:3,green:2};`);
  let html=c.run('potComparisonHTML(state.observation)');
  assert.match(html, /^<details[^>]*id="pot-comparison"\s*>/);
  c.listeners.toggle({target:{id:'pot-comparison',isConnected:true,open:true}});
  assert.ok(html.includes('Mission 1 · After attempt 1 → Current mission 1'));
  assert.ok(html.includes('<td>2</td><td>5</td><td>+3</td>'));
  c.run(`state.observation.history.push({id:4,attempt:3,type:'mission_drawn',mission:{number:2,pot:{blue:0,red:0,green:0}}});
    state.observation.public.mission.number=2;state.observation.public.mission.pot={blue:0,red:0,green:0};`);
  html=c.run('potComparisonHTML(state.observation)');
  assert.ok(html.includes('Last mission closed at 5 Blue + 3 Red + 2 Green'));
  assert.ok(html.includes('Its tokens left play'));
  c.run('state.potReference="2"');
  assert.ok(c.run('potComparisonHTML(state.observation)').includes('<td>2</td><td>0</td><td>-2</td>'));
  assert.match(c.run('potComparisonHTML(state.observation)'), /^<details[^>]* open>/);
  c.listeners.toggle({target:{id:'pot-comparison',isConnected:true,open:false}});
  assert.match(c.run('potComparisonHTML(state.observation)'), /^<details[^>]*id="pot-comparison"\s*>/);
});

test('player history includes every public vote and claims without leaking own private actions', () => {
  const c=client();
  c.run(`state.observation.history=[
    {id:1,attempt:1,type:'crew_selected',chairman:'p1',crew:['p1','p2']},
    {id:2,attempt:1,type:'pledges_revealed',pledges:{p1:{blue:2,red:0,green:0}}},
    {id:3,attempt:1,type:'vote',player_id:'p1',approve:false,complaints:[{modifier:'more',color:'blue'}]},
    {id:4,attempt:1,type:'vote',player_id:'p1',approve:true,complaints:[]},
    {id:5,attempt:1,type:'reports_revealed',reports:{p1:[{player_id:'p2',verb:'took',quantity:77,color:'red'}]}}];
    state.observation.private.submissions=[{revision:1,action:{type:'contribute',tokens:{blue:0,red:9,green:0},ability:null}}];`);
  const theirs=c.run('playerHistoryHTML(state.observation,"p1")');
  assert.ok(theirs.includes('Voted No'));assert.ok(theirs.includes('Voted Yes'));
  assert.ok(theirs.includes('Pledged 2 Blue'));
  assert.ok(theirs.includes('took 77 Red'));assert.ok(theirs.includes('Player claim'));
  assert.ok(!theirs.includes('Committed 9 Red'));
  const mine=c.run('playerHistoryHTML(state.observation,"p0")');
  assert.ok(mine.includes('Committed 9 Red'));assert.ok(mine.includes('Your private decisions'));
});

test('player history and crew selection have separate accessible controls', () => {
  const c=client();c.run('state.observation.action_spec={type:"select_crew",crew_size:2}; state.playerHistory="p1"');
  const html=c.run('playersHTML(state.observation)');
  assert.ok(html.includes('data-command="player-history" data-id="p1" aria-expanded="true"'));
  assert.ok(html.includes('data-command="select-player" data-id="p1"'));
  assert.ok(html.includes('Add to crew'));
  assert.ok(html.includes('Ben · Action history'));
});

test('paced waiting never presents automatic cover slots as human decisions', () => {
  const c=client();c.run('state.canAdvance=true; state.observation.action_spec={type:"prepare",ability:null};state.observation.phase="preparation"');
  assert.equal(c.run('legalDraft()'),false);
  assert.ok(!c.run('actionHTML(state.observation)').includes('Seal my choice'));
  assert.ok(c.run('pacingHTML()').includes('Next step'));
  c.run('state.canAdvance=false');
  assert.ok(c.run('pacingHTML()').includes('YOUR TURN'));
});

test('auto pacing pauses, respects speed, and discards timers after navigation', () => {
  const c=client();let callback,delay,calls=0;
  c.context.setTimeout=(fn,ms)=>{callback=fn;delay=ms;return 1;};c.context.clearTimeout=()=>{};
  c.context.countAdvance=()=>{calls++;};
  c.run('advanceTable=countAdvance;state.canAdvance=true;state.pace=3500;scheduleAdvance()');
  assert.equal(delay,3500);callback();assert.equal(calls,1);
  c.run('state.generation++');callback();assert.equal(calls,1);
  for(const setup of ['state.livePaused=true','state.livePaused=false;state.pace=0','state.pace=800;state.busy=true','state.busy=false;state.canAdvance=false']){
    callback=null;c.run(setup+';scheduleAdvance()');assert.equal(callback,null);
  }
});

test('custom seconds persist, pause during editing, and reject invalid timer values', () => {
  const c=client();let callback,delay,saved;
  c.context.localStorage={getItem:()=>saved ?? null,setItem:(_,value)=>{saved=value;}};
  c.context.setTimeout=(fn,ms)=>{callback=fn;delay=ms;return 1;};
  c.context.clearTimeout=()=>{callback=null;};
  c.run('state.canAdvance=true');
  const input={id:'table-pace',value:'2.75'};
  c.context.document.activeElement=input;
  c.listeners.focusin({target:input});
  c.listeners.change({target:input});
  assert.equal(callback,null);
  assert.equal(c.run('readPace()'),2750);
  assert.equal(c.run('state.pace'),2750);
  c.context.document.activeElement=null;
  c.listeners.focusout({target:input});
  assert.equal(delay,2750);
  assert.equal(typeof callback,'function');
  for (const invalid of ['', '-1', 'NaN', 'Infinity', '2147484']) {
    input.value=invalid;c.listeners.change({target:input});
    assert.equal(c.run('state.pace'),2750);
    assert.equal(saved,'2750');
  }
  input.value='0';c.listeners.change({target:input});
  assert.equal(callback,null);
  assert.equal(c.run('readPace()'),0);
  input.value='0.25';c.listeners.change({target:input});
  assert.equal(c.run('readPace()'),250);
  assert.equal(c.run('state.livePaused'),true);
  assert.equal(callback,null);
  assert.ok(c.run('pacingHTML()').includes('value="0.25"'));
  for (const badSaved of ['', '-1', 'Infinity', '2147483648']) {
    saved=badSaved;assert.equal(c.run('readPace()'),1800);
  }
});

test('paced advance response from an old route cannot overwrite the current table', async () => {
  const c=client();let resolve;
  c.context.pending=new Promise(r=>{resolve=r;});
  c.run('api=()=>pending;render=()=>{};state.canAdvance=true;state.stepKey="1:1:0";advancePromise=advanceTable()');
  c.run('state.generation++;state.mode="library";state.busy=false;state.game={id:"new-table"}');
  resolve({game:{id:'old-table'},observation:{phase:'vote'}});
  await c.run('advancePromise');
  assert.equal(c.run('state.game.id'),'new-table');
  assert.equal(c.run('state.mode'),'library');
});

test('last step explains a vote, its reason, and the proposed crew on resume', () => {
  const c=client();
  c.run(`state.observation.history=[
    {id:1,attempt:1,type:'crew_selected',chairman:'p0',crew:['p5','p6']},
    {id:2,attempt:1,type:'vote',player_id:'p5',approve:false,complaints:[{modifier:'more',player_id:'p5'}]}];
    state.canAdvance=true;state.observation.action_spec=null;`);
  const step=JSON.parse(c.run('JSON.stringify(latestStep(state.observation))'));
  assert.equal(step.title,'Fran votes No. Reason: More me.');
  assert.ok(step.lines.includes('Abby’s crew: Fran, Gray.'));
  const board=c.run('playersHTML(state.observation)');
  assert.ok(board.includes('More me'));
  assert.equal(c.run('actionHTML(state.observation)'), '');
});

test('last step lists actual revealed pledges and never shows an unrevealed bot pledge', () => {
  const c=client();
  c.run(`state.observation.history=[{id:1,attempt:1,type:'crew_selected',chairman:'p0',crew:['p5','p6']}];
    before=JSON.parse(JSON.stringify(state.observation));
    state.observation.history.push({id:2,attempt:1,type:'pledges_revealed',pledges:{p5:{blue:0,red:1,green:0},p6:{blue:5,red:0,green:0}}});`);
  const step=JSON.parse(c.run('JSON.stringify(latestStep(state.observation,before))'));
  assert.deepEqual(step.lines,['Fran pledges 1 Red.','Gray pledges 5 Blue.']);
  assert.ok(!c.run('JSON.stringify(latestStep(before))').includes('pledges 5'));
});

test('vote histories retain the correct crew across repeated proposals in one attempt', () => {
  const c=client();
  c.run(`state.observation.history=[
    {id:1,attempt:1,type:'crew_selected',chairman:'p0',crew:['p0','p6']},
    {id:2,attempt:1,type:'vote',player_id:'p5',approve:false,complaints:[{modifier:'less',player_id:'p6'}]},
    {id:3,attempt:1,type:'vote_income',wallets:{p0:6,p5:6}},
    {id:4,attempt:1,type:'proposal_rejected',rejections:1},
    {id:5,attempt:1,type:'crew_selected',chairman:'p1',crew:['p2','p3']},
    {id:6,attempt:1,type:'vote',player_id:'p5',approve:true,complaints:[]},
    {id:7,attempt:1,type:'income',wallets:{p0:7,p5:7}}];`);
  const html=c.run('playerHistoryHTML(state.observation,"p5")');
  assert.match(html,/Proposal 1.*Voted No.*Less Gray.*Abby’s crew: Abby, Gray/s);
  assert.match(html,/Proposal 2.*Voted Yes.*Ben’s crew: Casey, Drew/s);
  assert.ok(!html.includes('Event '));
  assert.ok(!/revenue|income|wallet/i.test(html));
  const history=c.run('historyHTML(state.observation)');
  assert.ok(!/revenue|income|Everyone receives/i.test(history));
});

test('final ballot keeps its explanation along with approval, without income messages', () => {
  const c=client();
  c.run(`state.observation.history=[{id:1,attempt:1,type:'crew_selected',chairman:'p0',crew:['p1','p6']}];
    before=JSON.parse(JSON.stringify(state.observation));
    state.observation.history.push(
      {id:2,attempt:1,type:'vote',player_id:'p7',approve:false,complaints:[{modifier:'less',player_id:'p6'}]},
      {id:3,attempt:1,type:'vote_income',amount_each:1},
      {id:4,attempt:1,type:'proposal_approved',yes_votes:5});`);
  for (const input of ['latestStep(state.observation,before)','latestStep(state.observation)']) {
    const step=JSON.parse(c.run(`JSON.stringify(${input})`));
    assert.equal(step.title,'Harper votes No. Reason: Less Gray.');
    assert.ok(step.lines.includes('Crew approved with 5 Yes votes.'));
    assert.ok(!JSON.stringify(step).includes('income'));
  }
});

test('resuming during a new proposal never attaches an older rejection to its latest vote', () => {
  const c=client();
  c.run(`state.observation.history=[
    {id:1,attempt:1,type:'crew_selected',chairman:'p0',crew:['p1','p2']},
    {id:2,attempt:1,type:'vote',player_id:'p7',approve:false,complaints:[]},
    {id:3,attempt:1,type:'proposal_rejected'},
    {id:4,attempt:1,type:'crew_selected',chairman:'p1',crew:['p5','p6']},
    {id:5,attempt:1,type:'vote',player_id:'p1',approve:true,complaints:[]}];`);
  const step=JSON.parse(c.run('JSON.stringify(latestStep(state.observation))'));
  assert.equal(step.title,'Ben votes Yes.');
  assert.deepEqual(step.lines,['Ben’s crew: Fran, Gray.']);
});

test('own sealed choice survives reload while automatic cover passes do not replace a meaningful step', () => {
  const c=client();
  c.run(`state.observation.history=[{id:1,attempt:1,type:'crew_selected',chairman:'p1',crew:['p0','p1']}];
    state.observation.own_submission_received=true;
    state.observation.private.submissions=[{action:{type:'pledge',tokens:{blue:3,red:0,green:0}}}];`);
  assert.ok(c.run('JSON.stringify(latestStep(state.observation))').includes('Pledged 3 Blue'));
  c.run(`before=JSON.parse(JSON.stringify(state.observation));before.action_spec={type:'prepare',ability:null};
    state.observation.private.submissions.push({action:{type:'prepare',ability:null}});`);
  assert.equal(c.run('latestStep(state.observation,before)'),null);
});

test('last-step text escapes player names and keeps report reveal ahead of automatic income and mission draw', () => {
  const c=client();
  c.run(`state.observation.public.players[6].name='<img src=x>';
    state.observation.public.crew=['p6'];state.observation.public.pledges={p6:{blue:5,red:0,green:0}};
    state.observation.history=[{id:1,attempt:1,type:'pledges_revealed',pledges:{p6:{blue:5,red:0,green:0}}}];
    state.canAdvance=true;state.observation.action_spec=null;`);
  let html=c.run('playersHTML(state.observation)');
  assert.ok(html.includes('&lt;img src=x&gt;'));assert.ok(!html.includes('<img'));
  assert.ok(html.includes('5 Blue'));
  c.run(`before=JSON.parse(JSON.stringify(state.observation));
    state.observation.history.push(
      {id:2,attempt:1,type:'reports_revealed',reports:{p5:[{player_id:'p5',verb:'gave',quantity:3,color:'blue'}]}},
      {id:3,attempt:1,type:'income',amount_each:1},
      {id:4,attempt:2,type:'mission_drawn',mission:{number:2,threshold:9,crew_size:2}});`);
  const step=JSON.parse(c.run('JSON.stringify(latestStep(state.observation,before))'));
  assert.equal(step.title,'The crew reveals its reports.');
  assert.deepEqual(step.lines,['Fran reports: Fran gave 3 Blue.']);
});

test('the table leads with eight seats, highlights the next voter, and keeps history on demand', () => {
  const c = client();
  c.run(`state.observation.phase="vote";state.observation.action_spec={type:"vote"};
    state.observation.public.chairman="p5";
    state.observation.public.votes=[{player_id:"p5",approve:true},{player_id:"p6",approve:true}];`);
  const html = c.run('tableHTML()');
  assert.equal((html.match(/data-player="p/g)||[]).length,8);
  assert.match(html, /class="player-card [^"]*current[^"]*" data-player="p7"/);
  assert.ok(html.indexOf('id="players-area"') < html.indexOf('class="pacing-bar"'));
  assert.ok(html.includes('id="history-area" hidden'));
  for (const removed of ['Recent activity','class="table-nav"','LAST STEP','Green funds. Blue & Red compete.']) assert.ok(!html.includes(removed));
  c.run('state.historyVisible=true');
  assert.ok(c.run('tableHTML()').includes('id="table-history"'));
});

test('player communications use public history, distinguish reports from facts, and retain earlier proposal context', () => {
  const c = client();
  c.run(`state.observation.public.players[1].name="<img src=x>";
    state.observation.private.submissions=[{action:{type:"contribute",tokens:{red:99}}}];
    state.observation.history=[
      {id:1,attempt:1,type:"crew_selected",chairman:"p0",crew:["p0","p1"]},
      {id:2,attempt:1,type:"vote",player_id:"p0",approve:false,complaints:[{modifier:"more",color:"blue"}]},
      {id:3,attempt:1,type:"proposal_rejected",rejections:1},
      {id:4,attempt:1,type:"crew_selected",chairman:"p1",crew:["p1","p2"]},
      {id:5,attempt:1,type:"pledges_revealed",pledges:{p1:{blue:2,red:0,green:0}}},
      {id:6,attempt:1,type:"reports_revealed",reports:{p1:[{player_id:"p1",verb:"gave",quantity:7,color:"red"}]}},
      {id:7,attempt:1,type:"vote_income",amount_each:1}];`);
  const html = c.run('playersHTML(state.observation)');
  assert.ok(html.includes('Voted No · Proposal 1'));
  assert.ok(html.includes('More Blue'));
  assert.ok(html.includes('Report · claim'));
  assert.ok(html.includes('&lt;img src=x&gt; gave 7 Red'));
  assert.ok(!html.includes('<img'));
  assert.ok(!html.includes('99'));
  assert.ok(!html.includes('income'));
  c.run('state.observation.public.attempt=2');
  assert.equal(c.run('playerSignal(state.observation,"p1").context'), 'Attempt 1');
});

test('history filters retain resolved outcomes and mission context without displaying filtered events', () => {
  const c = client();
  c.run(`state.observation.history=[
    {id:1,attempt:3,type:"mission_drawn",mission:{number:2,threshold:10,crew_size:2}},
    {id:2,attempt:3,type:"crew_selected",chairman:"p1",crew:["p1","p2"]},
    {id:3,attempt:3,type:"attempt_resolved",mission:{number:2,winner:"blue",threshold:10,pot:{blue:10,red:0,green:0}},wallets:{p1:0}},
    {id:4,attempt:3,type:"reports_revealed",reports:{p1:[{player_id:"p1",verb:"gave",quantity:5,color:"blue"}]}},
    {id:5,attempt:4,type:"mission_drawn",mission:{number:3,threshold:12,crew_size:3}}];
    state.historyFilter="claims";`);
  const claims = c.run('historyHTML(state.observation)');
  assert.ok(claims.includes('Mission 2 · Attempt 3'));
  assert.ok(claims.includes('Blue mission win · 1 event'));
  assert.match(claims, /data-attempt="3" open/);
  assert.ok(!claims.includes('In progress'));
  assert.ok(!claims.includes('Wallets after resolution'));
  c.run('state.historyFilter="votes"');
  const votes = c.run('historyHTML(state.observation)');
  assert.ok(votes.includes('Proposal 1 · Ben is chairman'));
  assert.ok(votes.includes('Blue mission win'));
  assert.ok(!votes.includes('Ben says:'));
});

test('reading sections pauses both live modes and replay without advancing or changing the draft', () => {
  const c = client();
  const focused = [];
  c.context.document.querySelector = selector => selector === '#table-history' ? {
    scrollIntoView() {}, focus() { focused.push(selector); },
  } : null;
  c.run('state.draft.tokens.blue=3;state.livePaused=false;state.canAdvance=false;jumpToSection("table-history")');
  assert.equal(c.run('state.livePaused'), true);
  assert.equal(c.run('state.draft.tokens.blue'), 3);
  c.run('state.livePaused=false;state.canAdvance=true;jumpToSection("table-history")');
  assert.equal(c.run('state.livePaused'), true);
  c.run('state.mode="replay";state.playing=true;state.replay={step:7};jumpToSection("table-history")');
  assert.equal(c.run('state.playing'), false);
  assert.equal(c.run('state.replay.step'), 7);
  assert.equal(focused.length, 3);
});

test('history expand and collapse apply across filters and preserve the pending decision', async () => {
  const c = client();
  const area = {innerHTML: ''};
  c.context.document.querySelector = selector => selector === '#history-area' ? area : null;
  c.run(`state.observation.history=[
    {id:1,attempt:1,type:"crew_selected",chairman:"p0",crew:["p0","p1"]},
    {id:2,attempt:2,type:"crew_selected",chairman:"p1",crew:["p1","p2"]}];
    state.historyFilter="results";state.draft.tokens.blue=4;`);
  await c.run('command({dataset:{command:"history-expand"}})');
  assert.equal(c.run('state.historyOpen[1] && state.historyOpen[2]'), true);
  assert.equal(c.run('state.livePaused'), true);
  c.run('state.historyFilter="all"');
  assert.equal((c.run('historyHTML(state.observation)').match(/data-attempt="\d+" open/g) || []).length, 2);
  await c.run('command({dataset:{command:"history-collapse"}})');
  assert.equal(c.run('state.historyOpen[1] || state.historyOpen[2]'), false);
  assert.equal(c.run('state.draft.tokens.blue'), 4);
  assert.ok(!area.innerHTML.includes('data-attempt="2" open'));
});

test('Scout visibly reveals the target without publishing the private result or hiding the chairman', () => {
  const c = client();
  assert.equal(c.run('knownTeam(state.observation,"p1")'), null);
  c.run(`state.observation.public.chairman="p1";
    state.observation.private.receipts=[{type:"scout",target:"p1",team:"red",attempt:1}];`);
  const html = c.run('playersHTML(state.observation)');
  const card = html.match(/<article[^>]*data-player="p1"[\s\S]*?<\/article>/)[0];
  assert.ok(card.includes('known-red'));
  assert.ok(card.includes('avatar red'));
  assert.ok(card.includes('player-team-badge red'));
  assert.ok(card.includes('Red<small>Scouted</small>'));
  assert.ok(card.includes('Only you know'));
  assert.ok(card.includes('Chairman'));
  assert.equal(c.run('Object.keys(state.observation.public.public_badges).length'), 0);
  assert.ok(!c.run('historyHTML(state.observation)').includes('Scouted'));
  assert.equal(c.run('knownTeam(state.observation,"p2")'), null);
  assert.equal(c.run('knownTeam(state.observation,"p0").team'), 'blue');
});

test('Scout knowledge follows the viewing seat and recorded moment, and claims never reveal teams', () => {
  const c = client();
  c.run(`state.mode="replay";state.observation.private.receipts=[{type:"scout",target:"p1",team:"red"}];
    state.replay={observation:state.observation,designer_enabled:false};`);
  assert.equal(c.run('knownTeam(state.observation,"p1").team'), 'red');
  c.run('state.observation.private.receipts=[]');
  assert.equal(c.run('knownTeam(state.observation,"p1")'), null);
  c.run(`state.observation.viewer="p2";state.observation.private.team="red";
    state.observation.history=[{type:"reports_revealed",attempt:1,reports:{p1:[{player_id:"p1",verb:"gave",quantity:5,color:"red"}]}}];`);
  assert.equal(c.run('knownTeam(state.observation,"p1")'), null);
  c.run('state.observation.public.public_badges={p3:"blue"}');
  assert.equal(c.run('knownTeam(state.observation,"p3").source'), 'Official badge');
  c.run('state.replay.designer={players:[{id:"p1",team:"blue"}]}');
  assert.equal(c.run('knownTeam(state.observation,"p1")'), null);
  c.run('state.replay.designer_enabled=true');
  assert.equal(c.run('knownTeam(state.observation,"p1").source'), 'Designer view');
  c.run('state.mode="table"');
  assert.equal(c.run('knownTeam(state.observation,"p1")'), null);
});

test('voting marks only the actual crew and names it centrally, independently of team knowledge', () => {
  const c = client();
  c.run(`state.observation.phase="vote";state.observation.action_spec={type:"vote"};
    state.observation.public.crew=["p1","p3"];
    state.observation.private.receipts=[{type:"scout",target:"p1",team:"red"}];
    state.observation.public.public_badges={p3:"blue"};state.draft.crew=["p5","p6"];`);
  const html = c.run('playersHTML(state.observation)');
  assert.equal((html.match(/class="crew-label"/g)||[]).length, 2);
  assert.ok(html.includes('Proposed crew</span><strong>Ben · Drew</strong>'));
  for (const pid of ['p1','p3']) {
    const card = html.match(new RegExp(`<article[^>]*data-player="${pid}"[\\s\\S]*?<\\/article>`))[0];
    assert.ok(card.includes('✓ Crew'));
    assert.ok(card.includes('on crew'));
  }
  assert.ok(html.includes('Red<small>Scouted</small>'));
  assert.ok(html.includes('Blue<small>Public</small>'));
  c.run('state.observation.public.crew=["p5","p6"];state.observation.public.players[5].name="<img src=x>"');
  const next = c.run('missionHTML(state.observation)');
  assert.ok(next.includes('&lt;img src=x&gt; · Gray'));
  assert.ok(!next.includes('Ben · Drew'));
  assert.ok(!next.includes('<img'));
});

test('crew roster follows the editable selection but replay uses the recorded crew', () => {
  const c = client();
  c.run('state.observation.action_spec={type:"select_crew",crew_size:3};state.draft.crew=["p4","p5"]');
  assert.ok(c.run('missionHTML(state.observation)').includes('Your crew</span><strong>Ellis · Fran'));
  c.run('state.mode="replay"');
  const replay = c.run('missionHTML(state.observation)');
  assert.ok(replay.includes('Abby · Ben · Casey'));
  assert.ok(!replay.includes('Ellis · Fran'));
});

test('each crew pledge has one dedicated tray independent of votes and reports', () => {
  const c = client();
  c.run(`state.observation.public.crew=['p1','p3','p6'];
    state.observation.public.pledges={p1:{blue:3,red:0,green:2},p3:{blue:0,red:0,green:0},p6:{blue:0,red:4,green:0}};
    state.observation.history=[{type:'crew_selected',attempt:1,chairman:'p0',crew:['p1','p3','p6']},
      {type:'pledges_revealed',attempt:1,pledges:state.observation.public.pledges},
      {type:'vote',attempt:1,player_id:'p1',approve:true,complaints:[]},
      {type:'reports_revealed',attempt:1,reports:{p6:[{player_id:'p6',verb:'gave',quantity:2,color:'green'}]}}];`);
  const html = c.run('playersHTML(state.observation)');
  assert.equal((html.match(/data-pledge-player=/g)||[]).length,3);
  for (const pid of ['p1','p3','p6']) {
    assert.equal((html.match(new RegExp(`data-pledge-player="${pid}"`,'g'))||[]).length,1);
    const card = html.match(new RegExp(`<article[^>]*data-player="${pid}"[\\s\\S]*?<\\/article>`))[0];
    assert.ok(!card.includes('Pledged'));
    assert.ok(!card.includes('pledge-tray'));
  }
  assert.ok(html.includes('Voted Yes'));
  assert.ok(html.includes('Report · claim'));
  assert.ok(html.includes('Ben · Pledged 3 Blue + 2 Green'));
  assert.ok(html.includes('Drew · Pledged 0 tokens'));
  assert.equal(c.run('playerSignal(state.observation,"p3")'),null);
});

test('pledge trays distinguish zero from unrevealed without exposing private or stale pledges', () => {
  const c = client();
  c.run(`state.observation.private.submissions=[{action:{type:'pledge',tokens:{blue:31,red:0,green:0}}}];
    state.observation.public.pledges={p1:{blue:0,red:0,green:0},p7:{blue:99,red:0,green:0}};`);
  const hidden = c.run('pledgeTrayHTML(state.observation,"p0")');
  assert.ok(hidden.includes('Unrevealed'));
  assert.ok(!hidden.includes('31'));
  const zero = c.run('pledgeTrayHTML(state.observation,"p1")');
  assert.ok(zero.includes('class="pledge-tray revealed"'));
  assert.ok(zero.includes('<strong>0</strong>'));
  assert.ok(!zero.includes('Unrevealed'));
  assert.ok(!c.run('playersHTML(state.observation)').includes('99'));
  c.run('state.observation.action_spec={type:"select_crew",crew_size:2};state.draft.crew=["p1","p7"]');
  const draft = c.run('playersHTML(state.observation)');
  assert.equal((draft.match(/class="pledge-tray unrevealed"/g)||[]).length,2);
  assert.ok(!draft.includes('99'));
});

test('full crews disable adding another player while preserving remove and history controls', () => {
  const c = client();
  c.run('state.observation.action_spec={type:"select_crew",crew_size:2};state.draft.crew=["p1","p2"]');
  const full = c.run('playersHTML(state.observation)');
  assert.match(full, /data-command="select-player" data-id="p3"[^>]*disabled/);
  assert.doesNotMatch(full, /data-command="select-player" data-id="p1"[^>]*disabled/);
  assert.doesNotMatch(full, /data-command="player-history"[^>]*disabled/);
  c.run('state.draft.crew.pop()');
  assert.doesNotMatch(c.run('playersHTML(state.observation)'), /data-command="select-player" data-id="p3"[^>]*disabled/);
});

test('manual stepping restores focus to the transport control without moving it during auto play', async () => {
  const c = client();
  let focused = 0;
  const next = {dataset:{command:'live-next'},focus(){focused++;}};
  c.context.document.activeElement = next;
  c.context.document.querySelector = selector => selector === '[data-command="live-next"]' ? next : null;
  c.run('render=()=>{};announce=()=>{};state.canAdvance=true;api=async()=>({game:state.game,observation:fixture,can_advance:true,step_key:"new"})');
  await c.run('advanceTable()');
  assert.equal(focused,1);
  c.context.document.activeElement = null;
  await c.run('advanceTable()');
  assert.equal(focused,1);
});

test('token steppers recover from an empty input and cannot exceed the wallet', async () => {
  const c = client();
  const input = {value:''};
  c.context.document.querySelector = selector => selector === '#token-blue' ? input : null;
  c.run('syncAction=()=>{};state.draft.tokens.blue=NaN');
  await c.run('command({dataset:{command:"token",color:"blue",delta:"1"}})');
  assert.equal(c.run('state.draft.tokens.blue'),1);
  c.run('state.draft.tokens={blue:1,red:4,green:0}');
  await c.run('command({dataset:{command:"token",color:"blue",delta:"1"}})');
  assert.equal(c.run('state.draft.tokens.blue'),1);
});

test('resolution blocks auto advance, manual advance, and the next decision until continued', async () => {
  const c = resolvedClient();let timers=0,requests=0;
  c.context.setTimeout=()=>{timers++;};
  c.context.countRequest=()=>{requests++;};
  c.run('state.canAdvance=true;state.pace=1;api=countRequest;scheduleAdvance()');
  await c.run('advanceTable()');
  assert.equal(timers,0);assert.equal(requests,0);
  assert.ok(c.run('pacingHTML()').includes('Paused for the result'));
  assert.equal(c.run('actionHTML(state.observation)'),'');
  c.run('state.canAdvance=false;state.draft.statements=[{player_id:"p0",verb:"gave",quantity:1,color:"blue"}]');
  assert.equal(c.run('legalDraft()'),false);
  c.run('render=()=>{}');
  await c.run('command({dataset:{command:"resolution-continue"}})');
  assert.equal(c.run('legalDraft()'),true);
  c.run('captureResolution(state.observation)');
  assert.equal(c.run('state.resolutionHold'),null);
});

test('revealed claims hold the resolved crew and pot after the engine starts the next mission', async () => {
  const c=resolvedClient();
  c.run(`state.resolutionHold=null;
    state.observation.history.push(
      {type:'reports_revealed',attempt:1,reports:{p1:[{player_id:'p1',verb:'gave',quantity:99,color:'red'}],p6:[{player_id:'p1',verb:'took',quantity:2,color:'blue'}]}},
      {type:'income',attempt:1,wallets:{p1:2,p6:2}},
      {type:'mission_drawn',attempt:2,mission:{number:2,pot:{blue:0,red:0,green:0}}});
    state.observation.public.attempt=2;state.observation.public.crew=[];state.observation.public.pledges={};
    state.observation.public.mission={number:2,threshold:12,crew_size:3,pot:{blue:0,red:0,green:0},winner:null};
    state.observation.phase='select_crew';state.observation.action_spec={type:'select_crew',crew_size:3};
    state.observation.private.last_contribution={tokens:{blue:777,red:0,green:0}};
    state.draft.crew=['p4'];captureResolution(state.observation);`);
  const board=c.run('playersHTML(state.observation)');
  assert.ok(board.includes('Mission 1 complete!'));
  assert.ok(board.includes('Crew claims revealed'));
  assert.ok(board.includes('I gave 99 Red'));
  assert.ok(board.includes('Ben took 2 Blue'));
  assert.ok(board.includes('Report · claim'));
  assert.equal((board.match(/class="crew-label"/g)||[]).length,2);
  assert.ok(board.includes('data-pledge-player="p1"'));
  assert.ok(board.includes('data-pledge-player="p6"'));
  assert.ok(!board.includes('data-pledge-player="p4"'));
  assert.ok(!board.includes('select-player'));
  assert.ok(!board.includes('777'));
  assert.ok(!board.includes('Up next'));
  assert.ok(board.includes('Next mission'));
  assert.equal(c.run('total(displayedResolution(state.observation).event.mission.pot)'),10);
  c.run('render=()=>{}');
  await c.run('command({dataset:{command:"resolution-continue"}})');
  assert.equal(c.run('displayedResolution(state.observation)'),null);
  assert.ok(c.run('playersHTML(state.observation)').includes('Mission 2'));
});

test('resolution announcements distinguish winning, unfinished, all-Green, and penalty pots', () => {
  const c=resolvedClient();
  let html=c.run('missionHTML(state.observation)');
  assert.ok(html.includes('Mission 1 complete!'));assert.ok(html.includes('Blue wins'));
  assert.ok(html.includes('+1 mission'));assert.ok(html.includes('celebration'));
  assert.ok(html.includes('2 → 10'));assert.ok(html.includes('+8 this attempt'));
  c.run('state.observation.history[3].mission.winner="red"');
  assert.ok(c.run('missionHTML(state.observation)').includes('winner-red'));
  c.run('state.observation.history[3].mission.winner=null;state.observation.history[3].mission.pot={blue:2,red:0,green:1}');
  html=c.run('missionHTML(state.observation)');
  assert.ok(html.includes('Attempt 1 resolved'));assert.ok(html.includes('7 more to fill'));
  assert.ok(!html.includes('celebration'));
  c.run('state.observation.history[3].mission.pot={blue:0,red:0,green:10}');
  assert.ok(c.run('missionHTML(state.observation)').includes('All Green · mission stays open'));
  c.run('state.observation.history[3].penalty=true');
  html=c.run('playersHTML(state.observation)');
  assert.ok(html.includes('No crew · rejection penalty'));
  assert.ok(!html.includes('class="crew-label"'));
});

test('replay pauses at both reveal boundaries, never projects a later result, and ends without an invalid seek', async () => {
  const c=resolvedClient();
  c.run('state.mode="replay";state.resolutionSeen=null;state.playing=true;captureResolution(state.observation)');
  assert.equal(c.run('state.playing'),false);
  c.run('state.resolutionHold=null;state.playing=true;state.observation.history.push({type:"reports_revealed",attempt:1,reports:{}});captureResolution(state.observation)');
  assert.equal(c.run('state.playing'),false);
  c.run('state.replay={step:5,total_steps:6};render=()=>{};seek=()=>{throw Error("Should not seek past end")};');
  await c.run('command({dataset:{command:"resolution-continue"}})');
  assert.equal(c.run('state.resolutionHold'),null);
  c.run('state.observation.history=state.observation.history.slice(0,3);state.observation.phase="contribute";captureResolution(state.observation)');
  assert.equal(c.run('displayedResolution(state.observation)'),null);
  assert.ok(!c.run('playersHTML(state.observation)').includes('Mission 1 complete!'));
});

test('a later crew cannot inherit the previous result, and result claims escape player text', () => {
  const c=resolvedClient();
  c.run(`state.observation.public.players[1].name='<img src=x>';
    state.observation.history.push({type:'reports_revealed',attempt:1,reports:{p6:[{player_id:'p1',verb:'gave',quantity:4,color:'blue'}]}});
    captureResolution(state.observation);`);
  assert.ok(c.run('playersHTML(state.observation)').includes('&lt;img src=x&gt; gave 4 Blue'));
  assert.ok(!c.run('playersHTML(state.observation)').includes('<img src=x>'));
  c.run(`state.observation.history.push({type:'crew_selected',attempt:2,chairman:'p4',crew:['p2','p3']});captureResolution(state.observation);`);
  assert.equal(c.run('resolutionMoment(state.observation)'),null);
  assert.equal(c.run('state.resolutionHold'),null);
});

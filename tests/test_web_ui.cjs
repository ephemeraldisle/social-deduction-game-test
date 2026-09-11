// Dependency-free tests of client projections and decision construction.
// Browser rendering is checked separately; these tests do not emulate a browser.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

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

test('vote prompt names the proposer and shows only the current crew pledges and ballots', () => {
  const c = client();
  c.run(`state.observation.action_spec={type:"vote"};state.observation.phase="vote";
    state.observation.public.chairman="p5";state.observation.public.crew=["p1","p6"];
    state.observation.public.pledges={p1:{blue:3,red:0,green:2},p6:{blue:0,red:0,green:0},p3:{blue:99,red:0,green:0}};
    state.observation.public.votes=[{player_id:"p5",approve:true},{player_id:"p6",approve:false},{player_id:"p7",approve:true}];`);
  const html = c.run('actionHTML(state.observation)');
  assert.ok(html.includes('Does Fran’s crew have your vote?'));
  assert.ok(html.includes('<strong>Ben</strong><span>3 Blue + 2 Green</span>'));
  assert.ok(html.includes('<strong>Gray</strong><span>0 tokens</span>'));
  assert.ok(html.includes('2 Yes</span> · <span class="vote-no">1 No</span> · 3/8 voted'));
  assert.ok(!html.includes('99 Blue'));
  assert.ok(!html.includes('Review the crew and its pledges'));
  assert.ok(!html.includes('Five Yes votes are needed'));
  c.run('state.observation.public.players[5].name="<img src=x>";state.observation.public.votes=[]');
  const fresh = c.run('actionHTML(state.observation)');
  assert.ok(fresh.includes('Does &lt;img src=x&gt;’s crew have your vote?'));
  assert.ok(!fresh.includes('<img'));
  assert.ok(fresh.includes('0 Yes</span> · <span class="vote-no">0 No</span> · 0/8 voted'));
});

test('No complaints appear on voter cards, escape names, and clear with a new proposal', () => {
  const c = client();
  c.run(`state.observation.public.players[2].name="<img src=x>";
    state.observation.public.votes=[{player_id:"p0",approve:false,complaints:[{modifier:"more",player_id:"p0"}]},
    {player_id:"p1",approve:false,complaints:[{modifier:"less",player_id:"p2"}]}];`);
  for (const mode of ['table', 'replay']) {
    c.context.viewMode = mode;
    const html = c.run('state.mode=viewMode; playersHTML(state.observation)');
    assert.ok(html.includes('Reason for No'));
    assert.ok(html.includes('More me'));
    assert.ok(html.includes('Less &lt;img'));
    assert.ok(!html.includes('<img'));
  }
  c.run('state.observation.public.votes=[]');
  assert.ok(!c.run('playersHTML(state.observation)').includes('player-complaint'));
  c.run(`state.observation.history=[{type:"crew_selected"},
    {type:"vote",player_id:"p0",approve:false,complaints:[{modifier:"more",player_id:"p0"}]},
    {type:"proposal_rejected"},{type:"crew_selected"}];`);
  const next = c.run('playersHTML(state.observation)');
  assert.ok(next.includes('Previous proposal · Rejected'));
  assert.ok(next.includes('Abby voted No:</b> More me'));
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
  assert.ok(c.run('pacingHTML()').includes('Automatic play waits for your decision'));
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
  const html=c.run('actionHTML(state.observation)');
  assert.ok(html.includes('Fran votes No. Reason: More me.'));
  assert.ok(html.includes('Abby’s crew: Fran, Gray.'));
  assert.ok(!html.includes('Waiting for the table'));
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
    state.observation.history=[{id:1,attempt:1,type:'pledges_revealed',pledges:{p6:{blue:5,red:0,green:0}}}];
    state.canAdvance=true;state.observation.action_spec=null;`);
  let html=c.run('actionHTML(state.observation)');
  assert.ok(html.includes('&lt;img src=x&gt; pledges 5 Blue.'));assert.ok(!html.includes('<img'));
  c.run(`before=JSON.parse(JSON.stringify(state.observation));
    state.observation.history.push(
      {id:2,attempt:1,type:'reports_revealed',reports:{p5:[{player_id:'p5',verb:'gave',quantity:3,color:'blue'}]}},
      {id:3,attempt:1,type:'income',amount_each:1},
      {id:4,attempt:2,type:'mission_drawn',mission:{number:2,threshold:9,crew_size:2}});`);
  const step=JSON.parse(c.run('JSON.stringify(latestStep(state.observation,before))'));
  assert.equal(step.title,'The crew reveals its reports.');
  assert.deepEqual(step.lines,['Fran reports: Fran gave 3 Blue.']);
});

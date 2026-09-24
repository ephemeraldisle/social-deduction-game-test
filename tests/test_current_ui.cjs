// Current rules UI smoke checks; no historical replay or bot assertions.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function client(storage = new Map()) {
  const listeners = {};
  const context = vm.createContext({console, URLSearchParams, setTimeout, clearTimeout, listeners,
    localStorage:{getItem(key){return storage.get(key) ?? null;},setItem(key,value){storage.set(key,value);}},
    document:{addEventListener(type,handler){listeners[type]=handler;},querySelector(){return null;}}, window:{addEventListener(){}}, location:{hash:'#library'}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../mission_game/web/app.js'),'utf8').replace(/\nboot\(\);\s*$/, ''),context);
  vm.runInContext(`state.mode='table';state.game={id:'smoke'};state.observation={game_id:'smoke',viewer:'p0',phase:'pledge',request_id:'1',revision:1,status:'ACTIVE',
    action_spec:{type:'pledge',max_total:20},history:[],
    public:{players:Array.from({length:8},(_,i)=>({id:'p'+i,name:'Player '+i})),mission:{number:6,threshold:30,crew_size:2,pot:{blue:8,red:8,green:0}},
      rules:{missions_to_win:4},public_badges:{},attempt:8,rejections:0,chairman:'p0',crew:['p0','p1'],pledges:{p0:0,p1:8},votes:[],score:{blue:2,red:2},reserve:2,reserve_credit:3},
    private:{wallet:20,team:'blue',objective:{id:'loyalist'},ability:{id:'disabled'},last_contribution:null,submissions:[]}};resetDraft(state.observation);`,context);
  return code => vm.runInContext(code,context);
}

test('avatar guesses persist per game and seat without changing knowledge or decisions',()=>{
  const storage=new Map(), run=client(storage);
  const observation=run('JSON.stringify(state.observation)'), action=run('JSON.stringify(draftAction())');
  assert.equal(run('setPlayerGuess(state.observation,"p1","blue")'),true);
  assert.equal(run('knownTeam(state.observation,"p1")'),null);
  assert.equal(run('JSON.stringify(state.observation)'),observation);
  assert.equal(run('JSON.stringify(draftAction())'),action);
  const reload=client(storage);
  assert.equal(reload('playerGuess(state.observation,"p1")'),'blue');
  assert.equal(reload('state.observation.viewer="p2";playerGuess(state.observation,"p1")'),null);
  assert.equal(reload('state.observation.viewer="p0";state.observation.game_id="another";playerGuess(state.observation,"p1")'),null);
  assert.equal(reload('state.observation.game_id="smoke";playerGuess(state.observation,"p1")'),'blue');
  assert.equal(reload('setPlayerGuess(state.observation,"p1","")'),true);
  assert.equal(client(storage)('playerGuess(state.observation,"p1")'),null);
  storage.set(run('allegianceNotesKey(state.observation)'),'{broken');
  assert.equal(client(storage)('playerGuess(state.observation,"p1")'),null);
});

test('guesses are clearly tentative, yield to confirmed teams and stay out of replay',()=>{
  const run=client();
  run('setPlayerGuess(state.observation,"p1","red");');
  let html=run('playersHTML(state.observation)');
  assert.ok(html.includes('seat-guess red'));
  assert.ok(html.includes('Your guess'));
  assert.ok(!html.includes('known-red'));
  assert.ok(html.includes('data-command="mark-player" data-id="p1"'));
  assert.ok(!html.includes('data-command="mark-player" data-id="p0"'));
  // Native avatar and history controls must not be nested buttons.
  let inButton=false;
  for(const tag of html.matchAll(/<\/?button\b[^>]*>/g)) {
    if(tag[0].startsWith('</')) inButton=false;
    else { assert.equal(inButton,false,'nested button'); inButton=true; }
  }
  for(const invalid of ['"green"','"Blue"','null']) assert.equal(run(`setPlayerGuess(state.observation,"p1",${invalid})`),false);
  assert.equal(run('setPlayerGuess(state.observation,"p0","red")'),false);
  assert.equal(run('setPlayerGuess(state.observation,"missing","red")'),false);
  run('state.observation.private.receipts=[{type:"scout",target:"p1",team:"blue"}];');
  html=run('playersHTML(state.observation)');
  assert.ok(html.includes('Scouted'));
  assert.ok(!html.includes('seat-guess'));
  assert.equal(run('setPlayerGuess(state.observation,"p1","red")'),false);
  run('state.observation.private.receipts=[];state.observation.public.public_badges.p1="blue";');
  assert.equal(run('playerGuess(state.observation,"p1")'),null);
  run('state.observation.public.public_badges={};state.mode="replay";');
  html=run('playersHTML(state.observation)');
  assert.ok(!html.includes('mark-player'));
  assert.ok(!html.includes('Your guess'));
  assert.equal(run('setPlayerGuess(state.observation,"p1","red")'),false);
});

test('avatar picker pauses play, saves and clears without resetting the draft or opening history',async()=>{
  const run=client();
  run(`var focused=0, dialog={dataset:{},open:false,innerHTML:'',showModal(){this.open=true;},close(){this.open=false;},querySelector(){return {focus(){}};}};
    var board={innerHTML:''}, announcement={textContent:''};
    document.querySelector=selector=>selector==='#allegiance-dialog'?dialog:selector==='#players-area'?board:selector==='#announcer'?announcement:selector.startsWith('[data-command="mark-player"]')?{focus(){focused++;}}:null;
    state.draft.tokens.blue=7;state.canAdvance=true;state.livePaused=false;
    state.liveTimer=setTimeout(()=>{throw new Error('Autoplay was not paused');},10000);`);
  await run('command({dataset:{command:"mark-player",id:"p1"}})');
  assert.equal(run('dialog.open && state.livePaused && state.liveTimer===null'),true);
  assert.ok(run('dialog.innerHTML').includes('YOUR PRIVATE GUESS'));
  await run('command({dataset:{command:"set-allegiance",value:"red"}})');
  assert.equal(run('playerGuess(state.observation,"p1")'),'red');
  assert.equal(run('dialog.open'),false);
  assert.equal(run('focused'),1);
  assert.equal(run('state.playerHistory'),null);
  assert.equal(run('state.draft.tokens.blue'),7);
  assert.ok(run('board.innerHTML').includes('seat-guess red'));
  await run('command({dataset:{command:"mark-player",id:"p1"}})');
  await run('command({dataset:{command:"set-allegiance",value:""}})');
  assert.equal(run('playerGuess(state.observation,"p1")'),null);
  // A stale picker cannot write into a different seat or game.
  await run('command({dataset:{command:"mark-player",id:"p1"}})');
  run('state.observation.game_id="another";');
  await run('command({dataset:{command:"set-allegiance",value:"red"}})');
  assert.equal(run('playerGuess(state.observation,"p1")'),null);
});

test('one quantity pledges, including zero, and private wallets render correctly',()=>{
  const run=client();
  assert.equal(run('JSON.stringify(draftAction())'),'{"type":"pledge","quantity":0}');
  assert.equal(run('legalDraft()'),true);
  assert.equal(run('state.draft.tokens.blue=21;legalDraft()'),false);
  const controls=run('actionHTML(state.observation)');
  assert.ok(controls.includes('id="token-blue"'));
  assert.ok(!controls.includes('id="token-red"'));
  const board=run('playersHTML(state.observation)');
  assert.ok(board.includes('Pledged 0 tokens'));
  assert.equal((board.match(/aria-label="Wallet hidden"/g)||[]).length,7);
  assert.ok(board.includes('20 ◉'));
  assert.ok(board.includes('2.3 Green in reserve'));
  assert.ok(run('state.observation.public.reserve=0;state.observation.public.reserve_credit=8;playersHTML(state.observation)').includes('0.8 Green in reserve'));
  assert.ok(!board.includes('toward the next token'));
  assert.ok(!board.includes('undefined'));
});

test('last submitted No complaint survives requests, reload and a Yes toggle',()=>{
  const run=client();
  run(`state.observation.private.submissions=[{action:{type:'vote',approve:false,complaints:[{modifier:'more',player_id:'p0'}]}},{action:{type:'vote',approve:true,complaints:[]}}];
    state.observation.action_spec={type:'vote',max_influence:20};state.observation.request_id='2';resetDraft(state.observation);setVoteChoice(false);`);
  assert.equal(run('JSON.stringify(draftAction().complaints)'), '[{"modifier":"more","player_id":"p0"}]');
  run('setVoteChoice(true);setVoteChoice(false)');
  assert.equal(run('draftAction().complaints[0].player_id'),'p0');
  run(`state.draftKey=null;resetDraft(state.observation);setVoteChoice(false)`);
  assert.equal(run('draftAction().complaints[0].modifier'),'more');
});

test('vote spending validation and pooled tally match the rule',()=>{
  const run=client();
  run(`state.observation.action_spec={type:'vote',max_influence:20};setVoteChoice(true);state.draft.influence=18;`);
  assert.equal(run('legalDraft()'),true);
  assert.equal(run('draftAction().influence'),18);
  assert.ok(run('influenceSummary()').includes('2 Yes + 8 tokens'));
  for (const invalid of ['21','-1','1.5','NaN']) assert.equal(run(`state.draft.influence=${invalid};legalDraft()`),false);
  assert.equal(run(`voteTally([{approve:true,influence:6},{approve:true,influence:7}]).yes.votes`),3);
});

test('Green cards explain the rules and free influence appears in previews and vote records',()=>{
  const run=client();
  run(`state.observation.private.objective={id:'green_machine'};
    state.observation.private.ability={id:'green_thumb'};
    state.observation.action_spec={type:'vote',max_influence:20,vote_bonus:5};
    setVoteChoice(true);state.draft.influence=5;`);
  assert.ok(run('objectiveSummary(state.observation)').includes('20+ Green added across the table, from any source'));
  assert.ok(run('abilitySummary("green_thumb")').includes('5 free influence'));
  assert.ok(run('influenceSummary()').includes('15 tokens left in your wallet'));
  assert.ok(run('influenceSummary()').includes('2 Yes + 0 tokens'));
  assert.ok(run('influenceSummary()').includes('+5 free influence'));
  assert.equal(run('draftAction().influence'),5);
  assert.equal(run('draftAction().bonus'),undefined);
  run(`setVoteChoice(false,{color:'blue'});state.draft.influence=0;`);
  assert.ok(run('influenceSummary()').includes('1 No + 5 tokens'));
  assert.ok(run('influenceSummary()').includes('20 tokens left in your wallet'));
  run(`state.observation.history=[{type:'vote',attempt:8,player_id:'p0',approve:false,influence:0,bonus:5,complaints:[{color:'blue'}]}];`);
  assert.ok(run('playersHTML(state.observation)').includes('Voted No · +5 bonus'));
  assert.ok(run('eventHTML(state.observation.history[0])').includes('+5 bonus influence'));
  assert.ok(run('playerHistoryHTML(state.observation,"p0")').includes('+5 bonus influence'));
  assert.ok(run('resolvedVoteHTML(state.observation.history[0],state.observation)').includes('+5 bonus'));
});

test('global token goals show exact trackers while cards are collapsed',()=>{
  const run=client();
  run(`state.observation.private.objective={id:'opposition_patron',name:'Opposition Patron',
    progress:{label:'Red paid across the table',value:19,target:20,own_paid:4,condition_met:false}};`);
  let html=run('privateHTML(state.observation)');
  const summary=html.slice(html.indexOf('<summary>'),html.indexOf('</summary>'));
  assert.ok(summary.includes('19 / 20'));
  assert.ok(summary.includes('Red paid across the table'));
  assert.ok(summary.includes('value="19"'));
  assert.ok(!summary.includes('4 / 20'));
  run(`state.observation.private.objective.progress.value=26;state.observation.private.objective.progress.condition_met=true;`);
  html=run('privateHTML(state.observation)');
  assert.ok(html.includes('26 / 20'));
  assert.ok(html.includes('value="20"'));
  assert.ok(html.includes('Token goal met'));
  run(`state.observation.private.objective={id:'green_machine',progress:{label:'Green added across the table',value:0,target:20}};`);
  html=run('privateHTML(state.observation)');
  assert.ok(html.includes('0 / 20'));
  assert.ok(html.includes('Green added across the table'));
  assert.ok(!html.includes('undefined'));
  assert.equal(run('objectiveTrackerHTML({id:"loyalist"})'),'');
});

test('history uses resolved aggregate counters and pledges use income already received',()=>{
  const run=client();
  run(`state.observation.public.token_totals={paid:{blue:999,red:999,green:999},green_added:999};
    state.observation.public.rules.proposal_income=1;
    state.observation.private.wallet=6;state.observation.action_spec.max_total=6;`);
  const controls=run('actionHTML(state.observation)');
  assert.ok(controls.includes('Proposal income is already in your wallet.'));
  assert.ok(controls.includes('max="6"'));
  const history=run(`attemptResultHTML({attempt:1,mission:state.observation.public.mission,
    token_totals:{paid:{blue:30,red:24,green:11},green_added:35}})`);
  assert.ok(history.includes('Table totals'));
  assert.ok(history.includes('30 Blue'));
  assert.ok(history.includes('24 Red'));
  assert.ok(history.includes('Green added: 35'));
  assert.ok(!history.includes('999'));
  assert.equal(run('eventHTML({type:"proposal_income",amount_each:1})'),'');
});

test('pot and report resolutions both show color before/after values and deltas',()=>{
  const run=client();
  run(`state.observation.history=[
    {type:'crew_selected',attempt:8,chairman:'p0',crew:['p0','p1']},
    {type:'vote',attempt:8,player_id:'p0',approve:false,complaints:[{color:'red'}],influence:99},
    {type:'proposal_rejected',attempt:8},
    {type:'crew_selected',attempt:8,chairman:'p1',crew:['p0','p1']},
    ...Array.from({length:8},(_,i)=>({type:'vote',attempt:8,player_id:'p'+i,approve:i<5,influence:i===7?3:0,complaints:i<5?[]:[{modifier:'more',player_id:'p'+i}]})),
    {type:'attempt_resolved',id:1,attempt:8,mission:{...state.observation.public.mission,pot:{blue:16,red:16,green:0},winner:'blue'},
    previous_pot:{blue:8,red:8,green:0},score:{blue:3,red:2},penalty:false,reserve_added:0}];state.observation.phase='report';`);
  for (const report of [false,true]) {
    if(report) run(`state.observation.history.push({type:'reports_revealed',id:2,attempt:8,reports:{p0:[{player_id:'p0',verb:'gave',quantity:8,color:'blue'}]}});
      state.observation.phase='preparation';state.observation.public.attempt=9;state.observation.public.votes=[];state.observation.public.crew=[];`);
    run('captureResolution(state.observation)');
    const html=run('missionHTML(state.observation)');
    assert.ok(html.includes('8 → <b>16</b> Blue'));
    assert.ok(html.includes('8 → <b>16</b> Red'));
    assert.equal((html.match(/\+8 this attempt/g)||[]).length,2);
    assert.ok(html.includes('Mission 6 complete!'));
    const board=run('playersHTML(state.observation)');
    assert.equal((board.match(/Voted Yes/g)||[]).length,5);
    assert.equal((board.match(/Voted No/g)||[]).length,3);
    assert.ok(board.includes('Voted No · 3 tokens'));
    assert.ok(board.includes('More me'));
    assert.ok(!board.includes('99 tokens'));
    assert.ok(!board.includes('data-pledge-player'));
    assert.ok(board.includes(report ? 'I gave 8 Blue' : 'Report pending'));
  }
  assert.ok(!run('eventHTML(state.observation.history.find(e=>e.type==="attempt_resolved"))').includes('Wallets'));
});

test('game over immediately shows every personal outcome and final votes without requesting reports',async()=>{
  const run=client();
  run(`state.observation.phase='game_over';state.observation.action_spec=null;
    state.observation.public.result={winner:'blue',players:Object.fromEntries(state.observation.public.players.map(p=>[p.id,{won:['p1','p3'].includes(p.id)}]))};
    state.observation.private.result={won:false,text:'Your team won, but your personal condition was not satisfied.'};
    state.observation.history=[{type:'crew_selected',attempt:8,crew:['p0','p1']},
      ...Array.from({length:8},(_,i)=>({type:'vote',attempt:8,player_id:'p'+i,approve:i<5,complaints:[]})),
      {type:'attempt_resolved',attempt:8,mission:{...state.observation.public.mission,winner:'blue'},previous_pot:{blue:0,red:0,green:0},score:{blue:4,red:2}},
      {type:'game_over',attempt:8,winner:'blue'}];captureResolution(state.observation);`);
  assert.ok(run('state.resolutionHold'));
  const panel=run('actionHTML(state.observation)');
  assert.equal((panel.match(/<li>/g)||[]).length,8);
  assert.equal((panel.match(/✦ Won/g)||[]).length,2);
  assert.equal((panel.match(/Did not win/g)||[]).length,6);
  for(let i=0;i<8;i++) assert.ok(panel.includes('Player '+i));
  const board=run('playersHTML(state.observation)');
  assert.equal((board.match(/✦ Won/g)||[]).length,2);
  assert.equal((board.match(/Did not win/g)||[]).length,6);
  assert.equal((board.match(/Voted (Yes|No)/g)||[]).length,8);
  assert.ok(!/Report pending|crew reports next|>Crew reports/.test(board));
  assert.ok(board.includes('Final results'));
  assert.ok(run('resolutionAnnouncement(state.observation)').includes('Everyone’s final results'));
  assert.ok(!run('pacingHTML()').includes('Next step'));
  run('state.mode="replay";');
  assert.ok(run('replaySidebarHTML({observation:state.observation,timeline:[]})').includes('Every player’s result'));
  run('render=()=>{};var jumpedTo=null;jumpToSection=id=>{jumpedTo=id;};');
  await run(`command({dataset:{command:'resolution-continue'}})`);
  assert.equal(run('jumpedTo'),'final-results');
  run('state.observation.public.result.winner=null;Object.values(state.observation.public.result.players).forEach(r=>r.won=false);');
  assert.ok(run('finalResultsHTML(state.observation)').includes('This game is unresolved.'));
  assert.equal((run('finalResultsHTML(state.observation)').match(/Did not win/g)||[]).length,8);
});

test('auditor selects a crew member or passes using one dropdown after reports',()=>{
  const run=client();
  run(`state.observation.phase='audit';state.observation.request_id='audit1';
    state.observation.action_spec={type:'audit',ability:{id:'auditor',targets:['p0','p1']}};
    state.observation.history=[{type:'crew_selected',attempt:8,crew:['p0','p1']},
      {type:'attempt_resolved',attempt:8,mission:state.observation.public.mission,previous_pot:{blue:0,red:0,green:0}},
      {type:'reports_revealed',attempt:8,reports:{p0:[{player_id:'p0',verb:'gave',quantity:9,color:'blue'}],p1:[]}}];
    resetDraft(state.observation);captureResolution(state.observation);`);
  let board=run('playersHTML(state.observation)');
  assert.ok(board.includes('I gave 9 Blue'));
  assert.ok(board.includes('Inspect reports'));
  assert.ok(!board.includes('Report pending'));
  run('state.resolutionHold=null;');
  let html=run('actionHTML(state.observation)');
  assert.equal((html.match(/<select /g)||[]).length,1);
  assert.ok(html.includes('Don’t inspect'));
  assert.ok(!html.includes('Use your ability?'));
  assert.ok(!html.includes('once-per-game'));
  assert.equal(run('JSON.stringify(draftAction())'),'{"type":"audit","ability":null}');
  assert.equal(run('legalDraft()'),true);
  run(`listeners.change({target:{dataset:{ability:'target'},value:'p1'}})`);
  assert.equal(run('JSON.stringify(draftAction())'),'{"type":"audit","ability":{"target":"p1"}}');
  assert.equal(run('legalDraft()'),true);
  assert.ok(run('actionHTML(state.observation)').includes('value="p1" selected'));
  run(`listeners.change({target:{dataset:{ability:'target'},value:''}})`);
  assert.equal(run('draftAction().ability'),null);
  assert.equal(run('legalDraft()'),true);
  run(`listeners.change({target:{dataset:{ability:'target'},value:'p7'}})`);
  assert.equal(run('legalDraft()'),false);
});

test('player history connects proposals to the matching mission result and opens that result',async()=>{
  const run=client();
  run(`state.observation.history=[
    {type:'mission_drawn',attempt:8,mission:{number:6,pot:{blue:0,red:0,green:0}}},
    {type:'crew_selected',attempt:8,chairman:'p0',crew:['p0','p1']},
    {type:'vote',attempt:8,player_id:'p0',approve:false,influence:2,complaints:[{modifier:'more',player_id:'p0'}]},
    {type:'proposal_rejected',attempt:8},
    {type:'crew_selected',attempt:8,chairman:'p1',crew:['p0','p1']},
    {type:'vote',attempt:8,player_id:'p0',approve:true,influence:0,complaints:[]},
    {type:'proposal_approved',attempt:8,yes_votes:5},
    {type:'attempt_resolved',attempt:8,mission:{number:6,threshold:30,pot:{blue:16,red:16,green:0},winner:'blue'},previous_pot:{blue:8,red:8,green:0}},
    {type:'mission_drawn',attempt:9,mission:{number:7,pot:{blue:0,red:0,green:0}}},
    {type:'crew_selected',attempt:9,chairman:'p0',crew:['p0','p1']}];`);
  const html=run(`playerHistoryHTML(state.observation,'p0')`);
  assert.ok(html.includes('Mission 6 · Attempt 8'));
  assert.ok(html.includes('Mission 7 · Attempt 9'));
  assert.ok(html.includes('Blue wins mission 6'));
  assert.ok(html.includes('32 / 30 tokens'));
  assert.ok(html.includes('+8 Blue'));
  assert.ok(html.includes('Proposal 1 · Crew rejected'));
  assert.ok(html.includes('Proposal 2 · Crew approved'));
  assert.ok(html.includes('data-command="history-attempt" data-attempt="8"'));
  const full=run('historyHTML(state.observation)');
  assert.ok(full.includes('Blue wins mission 6'));
  assert.ok(full.includes('id="attempt-result-8"'));
  run('render=()=>{};var jumpedTo=null;jumpToSection=id=>{jumpedTo=id;};');
  await run(`command({dataset:{command:'history-attempt',attempt:'8'}})`);
  assert.equal(run('jumpedTo'),'attempt-result-8');
  assert.equal(run('state.historyVisible && state.historyOpen[8] && state.historyFilter==="all"'),true);
});

test('revealed player cards show private roles only in inspection and change seat at the same moment',async()=>{
  const run=client();
  run(`state.mode='replay';state.replay={designer_enabled:true,can_inspect:true,observation:state.observation,step:12,position:42,viewing_seat:'p0',
    designer:{players:state.observation.public.players.map(p=>({...p,team:'blue',objective:'exact_change',ability:'auditor',ability_used:false}))}};`);
  let html=run('playersHTML(state.observation)');
  assert.equal((html.match(/<small>Objective<\/small>/g)||[]).length,8);
  assert.equal((html.match(/<small>Ability<\/small>/g)||[]).length,8);
  assert.ok(html.includes('Exact Change'));
  assert.ok(html.includes('Auditor'));
  assert.ok(html.includes('data-command="inspect-player" data-id="p3"'));
  assert.ok(html.includes('data-command="player-history" data-id="p3"'));
  run('var requestedView=null,jumpedTo=null;seek=async(...args)=>{requestedView=args;state.replay.viewing_seat=args[1];};jumpToSection=id=>{jumpedTo=id;};state.playing=true;');
  await run(`command({dataset:{command:'inspect-player',id:'p3'}})`);
  assert.equal(run('JSON.stringify(requestedView)'), '[12,"p3",true,42]');
  assert.equal(run('jumpedTo'), 'replay-player-assessment');
  assert.equal(run('state.playing'), false);
  run('state.replay.designer_enabled=false;');
  html=run('playersHTML(state.observation)');
  assert.ok(!html.includes('Exact Change'));
  assert.ok(!html.includes('data-command="inspect-player"'));
  run('state.replay.designer_enabled=true;state.mode="table";');
  assert.ok(!run('playersHTML(state.observation)').includes('Exact Change'));
  run('state.mode="replay";state.replay.observation={...state.observation};');
  assert.ok(!run('playersHTML(state.observation)').includes('Exact Change'));
});

test('selected replay player rankings include every other seat in preference order and stay private',async()=>{
  const run=client();
  run(`state.mode='replay';state.replay={designer_enabled:true,viewing_seat:'p3',observation:state.observation,step:42,position:42,
    designer:{bot_decision:{player_id:'p6',reason:'Another bot just acted'},player_assessment:{player_id:'p3',position:28,action_type:'vote',details:{
      beliefs:Object.fromEntries(state.observation.public.players.filter(p=>p.id!=='p3').map((p,i)=>[p.id,{
        blue_preference:i/6,pledge_reliability:.7,report_credibility:.8,inclusion_demand:0,
        known_team:p.id==='p7'?'blue':null,evidence:[{event_id:8,text:'Observed <claim>'}]}]))}}}};`);
  let html=run('replayPlayerAssessmentHTML(state.replay)');
  assert.ok(html.includes('Player 3’s player rankings'));
  assert.ok(html.includes('decision 28 · Vote'));
  assert.equal((html.match(/<th scope="row">/g)||[]).length,7);
  assert.ok(html.indexOf('<th scope="row">Player 7')<html.indexOf('<th scope="row">Player 0'));
  assert.ok(!html.includes('<th scope="row">Player 3'));
  assert.ok(html.includes('Known Blue'));
  assert.ok(html.includes('70%') && html.includes('80%'));
  assert.ok(html.includes('Observed &lt;claim&gt;'));
  assert.ok(!html.includes('Another bot just acted'));
  run('var requestedView=null;seek=async(...args)=>{requestedView=args;};');
  await run(`command({dataset:{command:'replay-assessment',position:'28'}})`);
  assert.equal(run('JSON.stringify(requestedView)'), '[42,"p3",true,28]');
  // A rewind before the first assessment must clear the old rankings.
  run('state.replay.designer.player_assessment=null;');
  html=run('replayPlayerAssessmentHTML(state.replay)');
  assert.ok(html.includes('No player rankings recorded'));
  assert.ok(!html.includes('<table'));
  run('state.replay.designer_enabled=false;');
  assert.equal(run('replayPlayerAssessmentHTML(state.replay)'),'');
  run('state.replay.designer_enabled=true;state.mode="table";');
  assert.equal(run('replayPlayerAssessmentHTML(state.replay)'),'');
  run('state.mode="replay";state.replay.observation={...state.observation};');
  assert.equal(run('replayPlayerAssessmentHTML(state.replay)'),'');
});

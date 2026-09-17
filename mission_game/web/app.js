/* Thin player interface. Legal decisions and game outcomes come from Python. */
"use strict";
const $ = (selector, root = document) => root.querySelector(selector);
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[char]));
const colors = ["blue", "red", "green"];
const title = text => String(text || "").replaceAll("_", " ").replace(/\b\w/g, char => char.toUpperCase());
const total = vector => colors.reduce((sum, color) => sum + Number(vector?.[color] || 0), 0);
const state = {token: null, games: [], mode: "library", game: null, observation: null, replay: null,
  draft: {}, draftKey: null, error: "", busy: false, filter: "all", historyFilter: "all", historyOpen: {},
  generation: 0, timer: null, playing: false, liveTimer: null, pace: readPace(), livePaused: false,
  canAdvance: false, stepKey: null, transition: "", lastStep: null, playerHistory: null, potReference: "", potComparisonOpen: false, privateDetailsOpen: {}};

function validPace(value) { return Number.isFinite(value) && value >= 0 && value <= 2147483647; }
function readPace() {
  try { const saved = localStorage.getItem("table-pace"); if (saved?.trim() && validPace(Number(saved))) return Number(saved); } catch (_) {}
  return 1800;
}
function savePace() { try { localStorage.setItem("table-pace", String(state.pace)); } catch (_) {} }
function pacingStatus() {
  return state.observation.phase === "game_over" ? "GAME COMPLETE" : !state.canAdvance ? "YOUR TURN" : state.livePaused || !state.pace ? "PAUSED" : "FOLLOW THE TABLE";
}
function updatePace(input) {
  const milliseconds = Number(input.value) * 1000;
  if (!input.value.trim() || !validPace(milliseconds)) { input.value = state.pace / 1000; return; }
  state.pace = milliseconds;
  if (!state.pace) state.livePaused = true;
  savePace();
  // Preserve focus and pending button clicks while editing the speed.
  const status = $("#pace-status"), toggle = $('[data-command="live-toggle"]');
  if (status) status.textContent = pacingStatus();
  if (toggle) toggle.textContent = state.livePaused || !state.pace ? "Auto play" : "Pause";
  scheduleAdvance();
}
function clearLiveTimer() { clearTimeout(state.liveTimer); state.liveTimer = null; }
function scheduleAdvance() {
  clearLiveTimer();
  if (state.mode !== "table" || !state.canAdvance || state.busy || state.livePaused || !state.pace || document.hidden || document.activeElement?.id === "table-pace" || $("#help-dialog")?.open) return;
  const generation = state.generation, key = state.stepKey;
  state.liveTimer = setTimeout(() => {
    if (generation === state.generation && key === state.stepKey) advanceTable();
  }, state.pace);
}
function acceptTable(data) {
  const previous = state.observation?.game_id === data.observation.game_id ? state.observation : null;
  state.lastStep = latestStep(data.observation, previous) || (previous && state.lastStep) || latestStep(data.observation);
  state.game = data.game; state.observation = data.observation;
  state.canAdvance = Boolean(data.can_advance); state.stepKey = data.step_key;
  state.transition = state.lastStep.title;
  resetDraft(data.observation);
}
async function advanceTable() {
  if (state.busy || !state.canAdvance || state.mode !== "table") return;
  clearLiveTimer();
  const id = state.game.id, generation = state.generation;
  state.busy = true; render();
  try {
    const data = await api(`/api/games/${encodeURIComponent(id)}/advance`, {step_key: state.stepKey});
    if (generation !== state.generation || state.mode !== "table") return;
    acceptTable(data); announce(state.lastStep.title);
  } catch (error) {
    if (generation !== state.generation) return;
    state.livePaused = true;
    if (error.status === 409) {
      try { const data = await api(`/api/games/${encodeURIComponent(id)}/state`); if (generation === state.generation) acceptTable(data); }
      catch (_) {}
    }
    toast(error.message, true);
  } finally {
    if (generation === state.generation) { state.busy = false; render(); }
  }
}
function pacingHTML() {
  const finished = state.observation.phase === "game_over";
  const waiting = !finished && !state.canAdvance;
  return `<section class="pacing-bar" aria-label="Table playback controls"><div><span class="eyebrow" id="pace-status">${pacingStatus()}</span><p role="status">${esc(state.transition || title(state.observation.phase))}</p>${waiting ? '<small>Automatic play waits for your decision.</small>' : ""}</div><div class="pace-controls"><label>Seconds / step <input id="table-pace" type="number" inputmode="decimal" min="0" max="2147483.647" step="any" value="${state.pace / 1000}" aria-label="Seconds per step (0 for manual)" title="Seconds between steps. 0 for manual." ${state.busy ? "disabled" : ""}></label><button class="button small" data-command="live-toggle" ${finished ? "disabled" : ""}>${state.livePaused || !state.pace ? "Auto play" : "Pause"}</button><button class="button small primary" data-command="live-next" ${!state.canAdvance || state.busy ? "disabled" : ""}>${state.busy ? "Advancing…" : "Next step →"}</button></div></section>`;
}
// Attach votes and pledges to the proposal visible when they happened.
function contextualEvents(observation) {
  let context = {mission: 1, attempt: null, proposal: 0, crew: [], chairman: null};
  return observation.history.map((event, index) => {
    if (event.attempt !== context.attempt) context = {...context, attempt: event.attempt, proposal: 0, crew: [], chairman: null};
    if (event.type === "mission_drawn") context = {...context, mission: event.mission.number};
    if (event.type === "crew_selected") context = {...context, proposal: context.proposal + 1, crew: [...event.crew], chairman: event.chairman};
    return {event, index, ...context};
  });
}
function crewContext(entry, observation) {
  if (!entry.crew.length) return "";
  return `${entry.chairman ? `${nameOf(entry.chairman, observation)}’s crew` : "Proposed crew"}: ${entry.crew.map(pid => nameOf(pid, observation)).join(", ")}.`;
}
function describeStep(entry, observation) {
  const e = entry.event, name = pid => nameOf(pid, observation), context = crewContext(entry, observation);
  if (e.type === "vote") return {title: `${name(e.player_id)} votes ${e.approve ? "Yes" : "No"}.${e.complaints?.length ? ` Reason: ${e.complaints.map(c => complaintText(c, e.player_id, observation)).join("; ")}.` : ""}`, lines: context ? [context] : []};
  if (e.type === "crew_selected") return {title: `${name(e.chairman)} proposes a crew.`, lines: [e.crew.map(name).join(", ")]};
  if (e.type === "pledges_revealed") {
    const lines = Object.entries(e.pledges).map(([pid, vector]) => `${name(pid)} pledges ${tokenText(vector)}.`);
    return lines.length === 1 ? {title: lines[0], lines: []} : {title: "The crew reveals its pledges.", lines};
  }
  if (e.type === "proposal_approved") return {title: `Crew approved with ${e.yes_votes} Yes votes.`, lines: context ? [context] : []};
  if (e.type === "proposal_rejected") return {title: "The crew is rejected.", lines: context ? [context] : []};
  if (e.type === "attempt_resolved") return {title: e.mission.winner ? `${title(e.mission.winner)} wins mission ${e.mission.number}.` : "The mission stays open.", lines: [`${tokenText(e.mission.pot)} · ${total(e.mission.pot)}/${e.mission.threshold} funded.`, ...(e.penalty ? ["The rejection penalty was applied."] : [])]};
  if (e.type === "reports_revealed") return {title: "The crew reveals its reports.", lines: Object.entries(e.reports).map(([pid, claims]) => `${name(pid)} reports: ${claims.map(c => `${name(c.player_id)} ${c.verb} ${c.quantity} ${title(c.color)}`).join("; ")}.`)};
  if (e.type === "mission_drawn") return {title: `Mission ${e.mission.number} begins.`, lines: [`${e.mission.threshold} tokens needed · Crew of ${e.mission.crew_size}.`]};
  if (e.type === "game_over") return {title: e.winner ? `${title(e.winner)} wins the game.` : "The game ends unresolved.", lines: []};
  return null;
}
function latestStep(observation, previous = null) {
  const entries = contextualEvents(observation);
  const own = observation.private.submissions.at(-1)?.action;
  const newOwn = previous ? observation.private.submissions.length > previous.private.submissions.length : observation.own_submission_received;
  const privateStep = newOwn && own && (own.tokens || own.statements || own.ability || previous?.action_spec?.ability)
    ? {title: `Your ${title(own.type).toLowerCase()} is sealed.`, lines: [privateActionText(own)]} : null;
  if (!previous && privateStep) return privateStep;
  const fresh = entries.slice(previous ? previous.history.length : 0).filter(entry => !["game_started", "income", "vote_income"].includes(entry.event.type));
  let entry;
  if (previous) {
    // A completed batch can also draw the next mission or award the vote.
    // Keep its actual choice/result prominent instead of the bookkeeping.
    for (const kind of ["game_over", "attempt_resolved", "reports_revealed", "vote"]) {
      entry = fresh.findLast(x => x.event.type === kind);
      if (entry) break;
    }
  }
  entry ||= fresh.at(-1);
  if (!previous && entry && ["proposal_approved", "proposal_rejected"].includes(entry.event.type)) {
    entry = fresh.findLast(x => x.event.type === "vote" && x.attempt === entry.attempt && x.proposal === entry.proposal) || entry;
  }
  if (entry) {
    const step = describeStep(entry, observation);
    const outcome = fresh.findLast(x => x.index > entry.index && x.attempt === entry.attempt && x.proposal === entry.proposal && ["proposal_approved", "proposal_rejected"].includes(x.event.type));
    if (entry.event.type === "vote" && outcome) step.lines.push(describeStep(outcome, observation).title);
    return step;
  }
  if (previous && observation.private.receipts?.length > (previous.private.receipts?.length || 0)) {
    return {title: "Your private result arrives.", lines: [receiptText(observation.private.receipts.at(-1))]};
  }
  if (privateStep) return privateStep;
  if (previous && previous.phase !== observation.phase) {
    const titles = {preparation: "Private preparation begins.", select_crew: "Private preparation is complete.", report: "Inspections are complete."};
    if (titles[observation.phase]) return {title: titles[observation.phase], lines: []};
  }
  return previous ? null : {title: "The table is dealt.", lines: []};
}
function currentStep(observation) {
  return (observation === state.observation && state.lastStep) || latestStep(observation);
}

function walletLedger(observation) {
  let balances = Object.fromEntries(observation.public.players.map(p => [p.id, 5]));
  const rows = [];
  for (const event of observation.history) {
    if (!event.wallets) continue;
    const reason = "Mission resolution";
    for (const [pid, after] of Object.entries(event.wallets)) {
      const before = balances[pid];
      if (event.type === "attempt_resolved" && after !== before) rows.push({pid, before, after, delta: after - before, reason, attempt: event.attempt, event: event.id});
    }
    balances = {...event.wallets};
  }
  return rows;
}
function signed(n) { return n > 0 ? `+${n}` : String(n); }
function walletChangeHTML(change) {
  if (!change) return "";
  const explanation = `Last mission result: ${change.before} → ${change.after} (${signed(change.delta)}), attempt ${change.attempt}`;
  return `<span class="wallet-delta ${change.delta > 0 ? "gain" : "loss"}" title="${esc(explanation)}" aria-label="${esc(explanation)}">${signed(change.delta)}</span>`;
}

function missionCheckpoints(observation) {
  return observation.history.filter(e => ["mission_drawn", "attempt_resolved"].includes(e.type)).map(e => ({
    id: e.id, attempt: e.attempt, number: e.mission.number, pot: e.mission.pot,
    label: `Mission ${e.mission.number} · ${e.type === "mission_drawn" ? "Starting pot" : `After attempt ${e.attempt}`}`,
  }));
}
function potComparisonHTML(observation) {
  const checkpoints = missionCheckpoints(observation), current = observation.public.mission;
  const matching = checkpoints.filter(c => c.number === current.number);
  const reference = checkpoints.find(c => String(c.id) === state.potReference) || matching.at(-2) || matching[0] || {pot: {blue:0,red:0,green:0}, label:"Starting pot"};
  const previousMission = checkpoints.filter(c => c.number < current.number).at(-1);
  return `<details class="pot-comparison" id="pot-comparison" ${state.potComparisonOpen ? "open" : ""}><summary>Compare mission tokens</summary><div class="pot-comparison-body"><div class="row spread"><label class="caption">From <select id="pot-reference" aria-label="Earlier mission token state"><option value="">Previous state (automatic)</option>${checkpoints.map(c => `<option value="${c.id}" ${String(c.id) === state.potReference ? "selected" : ""}>${esc(c.label)}</option>`).join("")}</select></label></div><p class="caption">${esc(reference.label)} → Current mission ${current.number}</p><table><thead><tr><th>Tokens</th><th>Before</th><th>Now</th><th>Change</th></tr></thead><tbody>${[...colors,"total"].map(c => { const before = c === "total" ? total(reference.pot) : reference.pot[c]; const now = c === "total" ? total(current.pot) : current.pot[c]; return `<tr><th>${c !== "total" ? `<i class="token-dot ${c}"></i> ` : ""}${title(c)}</th><td>${before}</td><td>${now}</td><td>${signed(now-before)}</td></tr>`; }).join("")}</tbody></table>${previousMission ? `<p class="caption">Last mission closed at ${esc(tokenText(previousMission.pot))}. Its tokens left play.</p>` : ""}<p class="caption">Changes show net totals after all effects. They do not reveal individual deposits.</p></div></details>`;
}
function privateActionText(action) {
  let text = action.tokens ? `${action.type === "pledge" ? "Pledged" : "Committed"} ${tokenText(action.tokens)}` : action.statements ? `Sealed report: ${action.statements.map(c => `${nameOf(c.player_id)} ${c.verb} ${c.quantity} ${title(c.color)}`).join("; ")}` : title(action.type);
  if ("ability" in action) {
    const a = action.ability;
    text += !a ? " · Ability passed" : a.source === "wallet" ? ` · Requested ${a.amount} from ${nameOf(a.target)}’s wallet` : a.source === "mission" ? ` · Requested ${tokenText(a.tokens)} from the mission` : a.from ? ` · Change ${title(a.from)} to ${title(a.to)}` : a.color ? ` · Off-crew deposit: 1 ${title(a.color)}` : ` · Targeted ${nameOf(a.target)}`;
  }
  return text;
}
function playerHistoryHTML(observation, pid) {
  if (!pid) return "";
  const rows = [];
  const add = (entry, text, withCrew = false) => rows.push(`<li><span class="caption">Attempt ${entry.attempt}${entry.proposal ? ` · Proposal ${entry.proposal}` : ""}</span><p>${text}</p>${withCrew && entry.crew.length ? `<p class="history-crew">${esc(crewContext(entry, observation))}</p>` : ""}</li>`);
  for (const entry of contextualEvents(observation)) {
    const event = entry.event;
    if (event.type === "crew_selected") {
      if (event.chairman === pid) add(entry, `Proposed ${event.crew.map(p => esc(nameOf(p, observation))).join(", ")}.`);
      else if (event.crew.includes(pid)) add(entry, `Selected for ${esc(nameOf(event.chairman, observation))}’s crew.`, true);
    }
    if (event.type === "pledges_revealed" && event.pledges[pid]) add(entry, `Pledged ${esc(tokenText(event.pledges[pid]))}.`, true);
    if (event.type === "vote" && event.player_id === pid) add(entry, `<b>Voted ${event.approve ? "Yes" : "No"}.</b>${event.complaints?.length ? ` Reason: ${esc(event.complaints.map(c => complaintText(c,pid,observation)).join("; "))}.` : ""}`, true);
    if (event.type === "reports_revealed" && event.reports[pid]) add(entry, `Reported: ${esc(event.reports[pid].map(c => `${nameOf(c.player_id, observation)} ${c.verb} ${c.quantity} ${title(c.color)}`).join("; "))}. <span class="caption">Player claim</span>`);
  }
  const own = pid === observation.viewer ? observation.private.submissions.filter(r => !["select_crew","vote"].includes(r.action.type) && (r.action.tokens || r.action.statements || r.action.ability)) : [];
  return `<section class="player-history panel" id="player-history" aria-label="${esc(nameOf(pid, observation))} action history"><div class="row spread"><h3>${esc(nameOf(pid, observation))} · Action history</h3><button class="icon-button" data-command="close-player-history" aria-label="Close player history">×</button></div><ol>${rows.join("") || '<li>No public actions yet.</li>'}</ol>${own.length ? `<h4>Your private decisions</h4><ol>${own.map((r,i) => `<li><span class="caption">${i+1} · ${title(r.action.type)}</span><p>${esc(privateActionText(r.action))}</p></li>`).join("")}</ol>` : ""}</section>`;
}

async function api(path, payload) {
  const options = {headers: {"Accept": "application/json"}};
  if (payload !== undefined) {
    options.method = "POST";
    options.headers["Content-Type"] = "application/json";
    options.headers["X-Table-Token"] = state.token;
    options.body = JSON.stringify(payload);
  }
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error?.message || "The table could not be reached.");
    error.status = response.status;
    throw error;
  }
  return data;
}

let toastTimer;
function toast(message, error = false) {
  clearTimeout(toastTimer);
  const element = $("#toast");
  element.textContent = message;
  element.classList.toggle("error", error);
  element.hidden = false;
  toastTimer = setTimeout(() => { element.hidden = true; }, 5500);
}
function announce(message) { $("#announcer").textContent = message; }
function nameOf(id, observation = state.observation) {
  return observation?.public.players.find(player => player.id === id)?.name || id;
}
function tokenText(vector) {
  return colors.filter(c => vector?.[c]).map(c => `${vector[c]} ${title(c)}`).join(" + ") || "0 tokens";
}
function tokenMini(vector) {
  return `<span class="mini-tokens">${colors.filter(c => vector?.[c]).map(c => `<span title="${title(c)}"><i class="token-dot ${c}"></i>${vector[c]}<span class="sr-only"> ${c}</span></span>`).join("") || "0 tokens"}</span>`;
}
function personOptions(selected, optional = false) {
  return `${optional ? '<option value="">Any player</option>' : ""}${state.observation.public.players.map(p => `<option value="${p.id}" ${p.id === selected ? "selected" : ""}>${esc(p.name)}${p.id === state.observation.viewer ? " (you)" : ""}</option>`).join("")}`;
}
function colorOptions(selected, optional = false) {
  return `${optional ? '<option value="">Any color</option>' : ""}${colors.map(c => `<option value="${c}" ${c === selected ? "selected" : ""}>${title(c)}</option>`).join("")}`;
}
function ownReports(observation) {
  const receipt = observation.private.last_contribution;
  if (!receipt || receipt.attempt !== observation.public.attempt) return [];
  const claims = colors.filter(c => receipt.tokens[c]).map(c => ({player_id: observation.viewer, verb: "gave", quantity: receipt.tokens[c], color: c}));
  return claims.length ? claims : [{player_id: observation.viewer, verb: "gave", quantity: 0, color: "blue"}];
}
function resetDraft(observation) {
  const key = `${observation.game_id}:${observation.request_id}`;
  if (state.draftKey === key) return;
  state.draftKey = key;
  state.error = "";
  state.draft = {crew: [], tokens: {blue: 0, red: 0, green: 0}, approve: null, complaints: [],
    statements: observation.action_spec?.min_statements ? ownReports(observation) : [],
    ability: {active: false, target: observation.action_spec?.ability?.targets?.[0] || "", source: "mission",
      amount: 1, color: "blue", from: "red", to: "blue", tokens: {blue: 0, red: 1, green: 0}}};
}

function libraryHTML() {
  const games = state.games.filter(game => state.filter === "all" || (state.filter === "active" ? game.can_resume : !game.can_resume));
  const cards = games.map(game => {
    const finished = ["FINISHED", "UNRESOLVED"].includes(game.status);
    const date = new Date(game.updated_at * 1000).toLocaleString(undefined, {month: "short", day: "numeric", hour: "numeric", minute: "2-digit"});
    const winner = Object.entries(game.score).find(([, score]) => score === (game.missions_to_win || 3))?.[0];
    return `<article class="panel game-card">
      <div><div class="row spread"><span class="eyebrow">${game.sample ? "RECORDED BOT GAME" : "YOUR TABLE"}</span><span class="pill ${game.can_resume ? "live" : ""}">${game.can_resume ? "In progress" : game.status === "UNRESOLVED" ? "Unresolved" : finished ? "Completed" : "Paused recording"}</span></div>
      <h3>${esc(game.title)}</h3><p class="caption">Mission ${game.mission} · Attempt ${game.attempt}<br>${game.mode === "development_abilities" ? "Private objectives & abilities" : game.mode === "development_objectives" ? "Private objectives · Abilities off" : "Common rules · All Loyalists"}</p></div>
      <div class="row spread"><div class="game-score"><span><i class="token-dot blue"></i> Blue <b>${game.score.blue}</b></span><span><i class="token-dot red"></i> Red <b>${game.score.red}</b></span></div>${winner ? `<span class="caption">${title(winner)} wins</span>` : ""}</div>
      <div class="game-card-footer">${game.can_resume ? `<button class="button primary small" data-command="open-table" data-id="${esc(game.id)}">Resume table <span aria-hidden="true">↗</span></button>` : ""}
      <button class="button small ${finished ? "primary" : "subtle"}" data-command="open-replay" data-id="${esc(game.id)}">${finished ? "Watch replay" : "Review so far"} <span aria-hidden="true">→</span></button></div>
      <p class="caption">Saved ${esc(date)}</p>
    </article>`;
  }).join("");
  return `<section class="welcome"><div><span class="eyebrow">EIGHT PLAYERS. EVERY CHOICE LEAVES A TRACE.</span><h1>A seat at the table.<br>A reason to watch.</h1><p>Propose a crew, make a promise, and decide what to put on the line. Follow the table as each mission unfolds.</p>
    <div class="row"><button class="button primary" data-command="new-game">Take a seat <span aria-hidden="true">↗</span></button><button class="button" data-command="sample">Watch a sample game <span aria-hidden="true">▷</span></button></div>
    <label class="new-game-seat">Your seat <select id="new-seat" aria-label="Your seat for a new game">${["Abby", "Ben", "Casey", "Drew", "Ellis", "Fran", "Gray", "Harper"].map((name, i) => `<option value="${i}">${i + 1} · ${name}</option>`).join("")}</select></label>
    <p class="caption">5 Blue · 3 Red · Contrarian disabled<br>Private objectives & abilities · Computer opponents</p></div>
    <div class="table-art" aria-hidden="true"><div class="art-table"><div class="art-card"><span><i></i></span></div><div class="art-card"><span><i></i></span></div><div class="art-card"><span><i></i></span></div></div>${["A", "B", "C", "D", "E", "F", "G", "H"].map(n => `<span class="art-seat">${n}</span>`).join("")}</div></section>
    <section aria-labelledby="library-title"><div class="section-head library-head"><div><span class="eyebrow">PICK UP WHERE YOU LEFT OFF</span><h2 id="library-title">Your game library</h2></div><div class="library-filter" aria-label="Filter saved games">${[["all", "All games"], ["active", "In progress"], ["finished", "Replays"]].map(([value, label]) => `<button class="${state.filter === value ? "active" : ""}" data-command="filter" data-value="${value}" aria-pressed="${state.filter === value}">${label}</button>`).join("")}</div></div>
    <div class="library-grid">${cards || '<div class="panel empty-library">No tables here yet. Take a seat or generate a sample game to explore.</div>'}</div></section>`;
}

function missionHTML(observation) {
  const p = observation.public, m = p.mission, sum = total(m.pot), denominator = Math.max(sum, m.threshold);
  const stages = [["select_crew", "Crew"], ["pledge", "Pledge"], ["vote", "Vote"], ["contribute", "Commit"], ["report", "Report"]];
  if (p.rules.abilities_enabled) {
    stages.unshift(["preparation", "Prepare"]);
    stages.splice(stages.length - 1, 0, ["audit", "Inspect"]);
  }
  let stage = stages.findIndex(([phase]) => phase === observation.phase);
  if (observation.phase === "game_over") stage = stages.length;
  const result = m.winner ? `${title(m.winner)} won this mission. Its ${sum} tokens leave play after the result.` : sum >= m.threshold && m.pot.blue + m.pot.red === 0 ? "Fully funded, but all Green. A Blue or Red token is needed to award this mission." : `${Math.max(0, m.threshold - sum)} more tokens to fund this mission. Blue wins a tie with Red.`;
  return `<section class="mission" aria-label="Current mission and team score"><div class="mission-top"><div><span class="eyebrow">MISSION ${String(m.number).padStart(2, "0")} · ATTEMPT ${p.attempt}</span><h2>${m.winner ? "The mission is decided." : "Fund the mission."}</h2></div>
    <div class="mission-score" aria-label="First team to ${p.rules.missions_to_win || 3} missions wins">${["blue", "red"].map(c => `<div class="team-points" aria-label="${title(c)}: ${p.score[c]} of ${p.rules.missions_to_win || 3} missions"><strong>${title(c)} <span class="sr-only">${p.score[c]}</span></strong><div class="score-pips ${c}" aria-hidden="true">${Array.from({length:p.rules.missions_to_win || 3}, (_,i) => i).map(i => `<i class="${i < p.score[c] ? "on" : ""}"></i>`).join("")}</div></div>`).join("")}</div></div>
    <div class="funding"><div class="funding-label"><b>${sum}</b> / ${m.threshold} tokens</div><span class="funding-status">${m.winner ? `${title(m.winner)} mission +1` : `Crew of ${m.crew_size}`}</span><div class="funding-track" role="meter" aria-label="Mission funding" aria-valuemin="0" aria-valuemax="${denominator}" aria-valuenow="${sum}">${colors.map(c => `<span class="${c}" style="width:${m.pot[c] / denominator * 100}%"></span>`).join("")}</div></div>
    <div class="mission-bottom"><div class="pot-legend">${colors.map(c => `<span><i class="token-dot ${c}"></i>${m.pot[c]} ${title(c)}</span>`).join("")}</div><span class="caption">Green funds. Blue & Red compete.</span></div>
    <div class="mission-outcome">${result}</div>${potComparisonHTML(observation)}</section>
    <div class="phase-strip" aria-label="Attempt phases">${stages.map(([phase, label], i) => `<span class="phase-step ${i === stage ? "active" : i < stage ? "done" : ""}" ${i === stage ? 'aria-current="step"' : ""}><i>${i < stage ? "✓" : i + 1}</i>${label}</span>`).join("")}</div>`;
}

function complaintText(claim, speaker, observation = state.observation) {
  return [claim.modifier ? title(claim.modifier) : "", claim.player_id ? (claim.player_id === speaker ? "me" : nameOf(claim.player_id, observation)) : "", claim.color ? title(claim.color) : ""].filter(Boolean).join(" ");
}
function setVoteChoice(approve) {
  state.draft.approve = approve;
  state.draft.complaints = approve ? [] : [state.draft.complaints[0] || {modifier: "", player_id: "", color: ""}];
}

function previousComplaintsHTML(observation) {
  if (observation.public.votes.length) return "";
  const history = observation.history;
  const end = history.findLastIndex(e => ["proposal_approved", "proposal_rejected"].includes(e.type));
  if (end < 0) return "";
  const votes = [];
  for (let i = end - 1; i >= 0 && history[i].type !== "crew_selected"; i--) {
    if (history[i].type === "vote" && !history[i].approve) votes.unshift(history[i]);
  }
  if (!votes.length) return "";
  return `<section class="previous-complaints" aria-label="Previous proposal complaints"><h3>Previous proposal · ${history[end].type === "proposal_rejected" ? "Rejected" : "Approved"}</h3><div class="row wrap">${votes.map(v => `<span><b>${esc(nameOf(v.player_id))} voted No:</b> ${esc(complaintText(v.complaints[0], v.player_id))}</span>`).join("")}</div></section>`;
}

function playersHTML(observation) {
  const p = observation.public, selecting = state.mode === "table" && observation.action_spec?.type === "select_crew";
  const selected = selecting ? state.draft.crew : p.crew;
  const ledger = walletLedger(observation);
  const votes = Object.fromEntries(p.votes.map(v => [v.player_id, v]));
  const nextVoter = observation.phase === "vote" ? p.players[(p.players.findIndex(x => x.id === p.chairman) + p.votes.length) % 8].id : null;
  return `<section class="players-section" aria-labelledby="players-title"><div class="players-head"><h3 id="players-title">Around the table</h3><span class="caption">${selecting ? "Select your crew below" : `${esc(nameOf(p.chairman))} is chairman`} · Click a player for history</span></div>
    <div class="player-grid">${p.players.map(player => {
      const chosen = selected.includes(player.id), mine = player.id === observation.viewer, chairman = player.id === p.chairman;
      const revealedTeam = state.replay?.designer?.players.find(x => x.id === player.id)?.team || p.public_badges?.[player.id];
      const pledge = p.pledges[player.id];
      const vote = votes[player.id];
      return `<article class="player-card ${chosen ? "selected" : ""} ${player.id === nextVoter ? "current" : ""}"><button class="player-main" data-command="player-history" data-id="${player.id}" aria-expanded="${state.playerHistory === player.id}" aria-label="${esc(player.name)}${chairman ? ", chairman" : ""}, ${player.wallet} tokens. Show action history">
        <div class="player-identity"><span class="player-avatar"><span class="avatar ${chairman ? "chair-mark" : revealedTeam || (mine ? "you" : "")}" ${chairman ? 'role="img" title="Chairman" aria-label="Chairman"' : 'aria-hidden="true"'}>${chairman ? "♜" : esc(player.name.slice(0, 1))}</span>${revealedTeam ? `<span class="player-team-badge ${revealedTeam}" role="img" title="${title(revealedTeam)}${p.public_badges?.[player.id] ? " · Official badge" : " team"}" aria-label="${title(revealedTeam)}${p.public_badges?.[player.id] ? " · Official badge" : " team"}">${p.public_badges?.[player.id] ? "✓" : title(revealedTeam).slice(0,1)}</span>` : ""}</span><span class="player-name">${esc(player.name)}${mine ? " · You" : ""}</span></div>
        <div class="player-wallet"><span>Wallet</span><span class="wallet-number">${player.wallet} <span aria-hidden="true">◉</span>${walletChangeHTML(ledger.findLast(r => r.pid === player.id))}</span></div>
        <div class="player-foot">${pledge ? `<span title="Pledged ${esc(tokenText(pledge))}">${tokenMini(pledge)}</span>` : `<span>${chosen ? "On the crew" : "Off crew"}</span>`}${vote ? `<span class="${vote.approve ? "vote-yes" : "vote-no"}">${vote.approve ? "Yes ✓" : "No ×"}</span>` : chosen ? '<span class="crew-check" aria-label="Selected">✓</span>' : ""}</div>
        ${vote && !vote.approve && vote.complaints?.length ? `<p class="player-complaint"><span>Reason for No</span>${esc(complaintText(vote.complaints[0], player.id))}</p>` : ""}
      </button>${selecting ? `<button class="crew-pick button small" data-command="select-player" data-id="${player.id}" aria-pressed="${chosen}">${chosen ? "Remove from crew" : "Add to crew"}</button>` : ""}</article>`;
    }).join("")}</div>
    <div class="proposal-bar"><p>${p.crew.length ? `<strong>Proposed crew:</strong> ${p.crew.map(pid => esc(nameOf(pid))).join(", ")}<br><span class="muted">${Object.keys(p.pledges).length ? `Pledged ${Object.values(p.pledges).reduce((n, v) => n + total(v), 0)} tokens in total. Promises are not binding.` : "Pledges will be revealed together before voting."}</span>` : p.rejections === 8 ? "No crew was approved. Eight rejected proposals triggered the five-Red penalty." : "The chairman is choosing a crew for this attempt."}</p><span class="vote-tally">${p.votes.length ? `<b>${p.votes.filter(v => v.approve).length} Yes</b> · ${p.votes.filter(v => !v.approve).length} No<br><span class="caption">5 Yes needed · ${p.votes.length}/8 voted</span>` : `<span class="caption">${p.rejections}/8 proposals rejected</span>`}</span></div>${previousComplaintsHTML(observation)}${playerHistoryHTML(observation, state.playerHistory)}</section>`;
}

function objectiveSummary(observation) {
  const own = title(observation.private.team), other = own === "Blue" ? "Red" : "Blue";
  const target = observation.public.rules.missions_to_win || 3;
  return {
    loyalist: `Win with ${own}.`,
    saver: `${own} wins; finish with 10+ tokens.`,
    spendthrift: `${own} wins; finish with 0 tokens.`,
    exact_change: `${own} wins; finish with exactly 7 tokens.`,
    opposition_patron: `${own} wins + 20+ ${other} tokens paid into missions.`,
    close_race: `${own} wins ${target}–${target - 1}.`,
    reliable_partner: `Match 2 pledges of 2+ tokens; ${own} wins.`,
    passenger: `Complete a mission on crew paying 0; ${own} wins.`,
    contrarian: `Your team loses; ${other} wins.`,
  }[observation.private.objective.id] || "Expand for your win condition.";
}
function abilitySummary(id) {
  return {
    thief: "Steal up to 3 tokens once.",
    stowaway: "Pay 1 token into missions while off crew.",
    auditor: "Privately check a crew member’s actual deposit.",
    switcher: "Swap objectives with another player once.",
    standard_bearer: "Your team is publicly visible.",
    scout: "Privately learn another player’s team once.",
    recolorer: "Change 1 mission token’s color each attempt.",
    echo: "Pay 2+ of only one color: +1 free token.",
    disabled: "Abilities off.",
  }[id] || "Expand for ability rules.";
}
function privateDetailAttributes(observation, kind) {
  const key = `${observation.viewer}:${kind}`;
  return `data-private-detail="${esc(key)}" ${state.privateDetailsOpen[key] ? "open" : ""}`;
}
function privateHTML(observation) {
  const {objective, ability, team, result} = observation.private;
  const progress = objective.progress;
  const availability = ability.uses_remaining != null ? `<span class="card-availability" aria-label="Once per game · ${ability.uses_remaining ? "Available" : "Used"}">${ability.uses_remaining ? "Available" : "Used"}</span>` : "";
  return `<section class="panel private-panel" aria-label="Your private cards">
    <div class="row spread private-heading"><span class="eyebrow">▧ ${state.mode === "replay" ? `${esc(nameOf(observation.viewer))}'S PERSPECTIVE` : "ONLY YOU CAN SEE THIS"}</span><span class="pill ${team}">${title(team)} team</span></div>
    <details class="card-explanation" ${privateDetailAttributes(observation, `objective:${objective.id}`)}>
      <summary><strong>${esc(objective.name || title(objective.id))}</strong><span class="card-synopsis">${esc(objectiveSummary(observation))}</span></summary>
      <div class="card-full-description"><p>${esc(objective.text)}</p>${progress ? `<div class="objective-progress"><b>${esc(progress.label)}</b><p>${esc(progress.text)}</p>${progress.condition_met !== null ? `<span class="caption">${progress.condition_met ? "Personal condition currently met" : "Personal condition still needed"} · ${result ? "Final position" : "Evaluated at game end"}</span>` : ""}</div>` : ""}${result?.text ? `<p class="private-receipt"><b>${result.won ? "You won." : "You did not win."}</b><br>${esc(result.text)}</p>` : ""}</div>
    </details>
    <details class="card-explanation" ${privateDetailAttributes(observation, `ability:${ability.id}`)}>
      <summary><strong>${esc(ability.name || title(ability.id))}</strong>${availability}<span class="card-synopsis">${esc(abilitySummary(ability.id))}</span></summary>
      <div class="card-full-description"><p>${esc(ability.text)}</p></div>
    </details>${receiptsHTML(observation)}</section>`;
}

function receiptText(receipt) {
  if (receipt.type === "scout") return `${nameOf(receipt.target)} is ${title(receipt.team)}. Their personal objective remains unknown.`;
  if (receipt.type === "audit") return `${nameOf(receipt.target)} originally paid ${tokenText(receipt.tokens)}.`;
  if (receipt.type === "thief") return receipt.source === "wallet" ? `You took ${receipt.amount} uncolored tokens from ${nameOf(receipt.target)}’s wallet.` : `You took ${tokenText(receipt.tokens)} from the mission into your wallet.`;
  if (receipt.type === "echo") return `Your deposit added 1 free ${title(receipt.color)} token.`;
  if (receipt.type === "objective_changed") return `Your objective changed to ${receipt.objective.name}. ${receipt.objective.text} ${receipt.objective.progress?.text || ""}`;
  return "";
}
function receiptsHTML(observation) {
  const receipts = observation.private.receipts || [];
  if (!receipts.length) return "";
  return `<details class="private-receipts" ${privateDetailAttributes(observation, "receipts")}><summary>Private results · ${receipts.length}</summary><div>${receipts.slice().reverse().map(r => `<p><span class="caption">Attempt ${r.attempt} · ${r.type === "objective_changed" ? "Objective changed" : title(r.type)}</span><br>${esc(receiptText(r))}</p>`).join("")}</div></details>`;
}
function abilityControls(spec) {
  if (!spec) return "";
  const d = state.draft.ability;
  const target = `<label>Player<select data-ability="target">${spec.targets?.map(pid => `<option value="${pid}" ${pid === d.target ? "selected" : ""}>${esc(nameOf(pid))}</option>`).join("")}</select></label>`;
  let fields = "";
  if (["scout", "switcher", "auditor"].includes(spec.id)) fields = target;
  if (spec.id === "stowaway") fields = `<p class="caption">Costs 1 wallet token. This is your off-crew deposit.</p><label>Color<select data-ability="color">${colorOptions(d.color)}</select></label>`;
  if (spec.id === "recolorer") fields = `<label>From<select data-ability="from">${colorOptions(d.from)}</select></label><label>To<select data-ability="to">${colorOptions(d.to)}</select></label>`;
  if (spec.id === "thief") fields = `<p class="caption">Request 1–3 tokens. This spends your use even if the source is empty at resolution.</p><label>Source<select data-ability="source"><option value="mission" ${d.source === "mission" ? "selected" : ""}>Mission</option><option value="wallet" ${d.source === "wallet" ? "selected" : ""}>Another wallet</option></select></label>${d.source === "wallet" ? target + `<label>Amount<input type="number" min="1" max="3" step="1" data-ability="amount" value="${esc(d.amount)}"></label>` : colors.map(c => `<label>${title(c)} requested<input type="number" min="0" max="3" step="1" data-ability-token="${c}" value="${esc(d.tokens[c])}"></label>`).join("")}`;
  return `<fieldset class="ability-controls"><legend>${title(spec.id)}</legend><label>Use your ability?<select data-ability="active"><option value="no" ${!d.active ? "selected" : ""}>Pass this time</option><option value="yes" ${d.active ? "selected" : ""}>Use ${title(spec.id)}</option></select></label>${d.active ? fields : '<p class="caption">Passing keeps any unused once-per-game ability available.</p>'}</fieldset>`;
}
function abilityChoice() {
  const spec = state.observation.action_spec.ability, d = state.draft.ability;
  if (!spec || !d?.active) return null;
  if (["scout", "switcher", "auditor"].includes(spec.id)) return {target: d.target};
  if (spec.id === "stowaway") return {color: d.color};
  if (spec.id === "recolorer") return {from: d.from, to: d.to};
  return d.source === "wallet" ? {source: "wallet", target: d.target, amount: d.amount} : {source: "mission", tokens: d.tokens};
}
function legalAbility() {
  const spec = state.observation.action_spec.ability, d = state.draft.ability;
  if (!spec || !d?.active) return true;
  if (["scout", "switcher", "auditor"].includes(spec.id)) return spec.targets.includes(d.target);
  if (spec.id === "stowaway") return colors.includes(d.color);
  if (spec.id === "recolorer") return colors.includes(d.from) && colors.includes(d.to) && d.from !== d.to;
  if (d.source === "wallet") return spec.targets.includes(d.target) && isQuantity(d.amount) && d.amount >= 1 && d.amount <= 3;
  return d.source === "mission" && colors.every(c => isQuantity(d.tokens[c])) && total(d.tokens) >= 1 && total(d.tokens) <= 3;
}

function rowBuilder(kind) {
  const reports = kind === "statements", list = state.draft[kind];
  return `<div class="builder-rows">${list.map((claim, index) => `<div class="claim-row ${reports ? "" : "complaint-row"}" data-kind="${kind}" data-index="${index}">
    ${reports ? `<label>Player<select data-field="player_id" aria-label="Report ${index + 1} player">${personOptions(claim.player_id)}</select></label><label>Claim<select data-field="verb" aria-label="Report ${index + 1} action"><option value="gave" ${claim.verb === "gave" ? "selected" : ""}>gave</option><option value="took" ${claim.verb === "took" ? "selected" : ""}>took</option></select></label><label>Quantity<input type="number" data-field="quantity" aria-label="Report ${index + 1} quantity" min="0" max="2147483647" step="1" value="${esc(claim.quantity)}" required></label>` : `<label>Modifier<select data-field="modifier" aria-label="Complaint ${index + 1} modifier">${[["", "No modifier"], ["more", "More"], ["less", "Less"], ["exact", "Exact"]].map(([v, label]) => `<option value="${v}" ${v === (claim.modifier || "") ? "selected" : ""}>${label}</option>`).join("")}</select></label><label>Player<select data-field="player_id" aria-label="Complaint ${index + 1} player">${personOptions(claim.player_id, true)}</select></label>`}
    <label>Color<select data-field="color" aria-label="${reports ? "Report" : "Complaint"} ${index + 1} color">${colorOptions(claim.color, !reports)}</select></label>${reports ? `<button type="button" class="remove-row" data-command="remove-row" data-kind="${kind}" data-index="${index}" aria-label="Remove ${reports ? "report" : "complaint"} ${index + 1}">Remove ×</button>` : ""}</div>`).join("")}</div>
    ${reports ? `<button type="button" class="text-button" data-command="add-row" data-kind="${kind}" ${list.length >= 3 ? "disabled" : ""}>+ Add a statement</button>` : ""}`;
}

function voteContextHTML(observation) {
  const p = observation.public;
  const yes = p.votes.filter(vote => vote.approve).length, no = p.votes.length - yes;
  return `<ul class="vote-crew" aria-label="Proposed crew and pledges">${p.crew.map(pid => `<li><strong>${esc(nameOf(pid, observation))}</strong><span>${p.pledges[pid] ? esc(tokenText(p.pledges[pid])) : "Not revealed"}</span></li>`).join("")}</ul><p class="current-vote-tally"><span class="vote-yes">${yes} Yes</span> · <span class="vote-no">${no} No</span> · ${p.votes.length}/${p.players.length} voted</p>`;
}

function actionHTML(observation) {
  const spec = observation.action_spec, p = observation.public;
  if (observation.phase === "game_over") {
    const result = p.result, mine = observation.private.result;
    return `<section class="panel action-panel"><span class="eyebrow">THE FINAL RESULT</span><div class="result-medallion" aria-hidden="true">${mine.won ? "✧" : "◎"}</div><h2>${result.winner ? `${title(result.winner)} wins the game.` : "This game is unresolved."}</h2><p class="action-intro">${result.winner ? `${esc(mine.text || (mine.won ? "You won with your team." : "You did not win this game."))} Your final wallet holds ${mine.wallet} tokens.` : "The development attempt limit was reached. No team or player is awarded a win."}</p><button class="button primary full" data-command="open-replay" data-id="${esc(state.game.id)}">Review this game →</button><button class="text-button" data-command="new-game" style="margin-top:15px">Take a new seat</button></section>`;
  }
  if (!spec || (state.mode === "table" && state.canAdvance)) {
    const step = currentStep(observation);
    return `<section class="panel action-panel last-step-panel"><span class="eyebrow">LAST STEP</span><h2>${esc(step.title)}</h2>${step.lines.map(line => `<p class="action-intro">${esc(line)}</p>`).join("")}<button class="button primary full" data-command="live-next" ${state.busy || !state.canAdvance ? "disabled" : ""}>Next step →</button></section>`;
  }
  const copy = {
    prepare: ["Private preparation.", "Choose whether to use your ability before this proposal. Other players do not see your choice.", "Seal my choice"],
    audit: ["Inspect the result.", "The official result is in. Choose an inspection or pass before crew reports are collected.", "Seal my choice"],
    select_crew: ["Choose your crew.", `Select ${spec.crew_size} distinct players from the table. You can include yourself.`, "Propose this crew"],
    pledge: ["You’re on the proposed crew.", `${p.chairman === observation.viewer ? "You included yourself" : `${esc(nameOf(p.chairman, observation))}, the chairman, chose you`} for Mission ${p.mission.number}. Before everyone votes, promise how many tokens you’ll contribute if this crew is approved. Pledges are revealed together; no tokens are spent yet.`, "Seal my pledge"],
    vote: [`Does ${esc(nameOf(p.chairman, observation))}’s crew have your vote?`, "", "Cast my vote"],
    contribute: ["What will you really give?", "Your actual deposit is private. It can differ from your pledge, and costs tokens from your wallet.", "Seal my contribution"],
    report: ["Tell the table.", "You served on the crew. Submit 1–3 statements about this attempt. Crew reports appear together.", "Seal my report"],
  }[spec.type];
  if (spec.type === "contribute" && spec.on_crew === false) {
    copy[0] = "Your hidden action.";
    copy[1] = p.rejections === 8 ? "No crew was approved. Choose your action before the penalty resolves." : "You are off crew. Choose whether to use your ability before the attempt resolves.";
    copy[2] = "Seal my choice";
  }
  let controls = "";
  if (spec.type === "select_crew") controls = `<div class="crew-selection-list">${state.draft.crew.map(pid => `<span>${esc(nameOf(pid))}</span>`).join("")}${Array.from({length: Math.max(0, spec.crew_size - state.draft.crew.length)}, () => '<span class="empty-seat">Open seat</span>').join("")}</div><p class="caption" id="crew-count">${state.draft.crew.length} of ${spec.crew_size} selected. Use Add to crew or Remove from crew below a player. Click their card to inspect their history.</p>`;
  if (["pledge", "contribute"].includes(spec.type) && spec.on_crew !== false) controls = `<div class="token-controls">${colors.map(c => `<div class="token-control"><i class="token-dot ${c}"></i><label for="token-${c}">${title(c)}</label><button type="button" class="stepper" data-command="token" data-color="${c}" data-delta="-1" aria-label="Remove one ${c} token">−</button><input id="token-${c}" type="number" inputmode="numeric" min="0" max="${spec.max_total}" step="1" value="${esc(state.draft.tokens[c])}" data-token="${c}" required><button type="button" class="stepper" data-command="token" data-color="${c}" data-delta="1" aria-label="Add one ${c} token">+</button></div>`).join("")}</div><div class="budget-row" id="budget-row"><span>Your wallet</span><strong id="budget-value"></strong></div>${spec.type === "contribute" && p.pledges[observation.viewer] ? `<button type="button" class="text-button" data-command="copy-pledge">Use my pledge (${esc(tokenText(p.pledges[observation.viewer]))})</button>` : '<p class="caption">Zero is allowed. No tokens are reserved by a pledge.</p>'}`;
  if (spec.type === "vote") controls = `<div class="vote-options">${[["yes", "Yes ✓", "Approve this crew"], ["no", "No ×", "Reject this crew"]].map(([value, label, hint]) => `<button type="button" class="vote-choice ${(value === "yes") === state.draft.approve ? "chosen" : ""}" data-command="vote-choice" data-value="${value}" aria-pressed="${(value === "yes") === state.draft.approve}">${label}<small>${hint}</small></button>`).join("")}</div>${state.draft.approve === false ? `<section class="builder" aria-label="Required complaint"><h3>Why are you voting No?</h3><p class="caption">One complaint is required. Choose a player, a color, or both; add More, Less, or Exact if helpful.</p>${rowBuilder("complaints")}</section>` : ""}`;
  if (spec.type === "report") controls = `<p class="report-help">Reports are player claims and may be false. “Gave” describes an original paid deposit; “took” describes a removal from the mission.</p>${ownReports(observation).length ? '<button type="button" class="text-button" data-command="own-report">Use my actual contribution</button>' : ""}${rowBuilder("statements")}`;
  controls += abilityControls(spec.ability);
  return `<section class="panel action-panel" id="action-panel" aria-labelledby="action-title"><span class="eyebrow">YOUR TURN · ${esc(nameOf(observation.viewer))}</span><h2 id="action-title">${copy[0]}</h2>${spec.type === "vote" ? voteContextHTML(observation) : `<p class="action-intro">${copy[1]}</p>`}<form id="decision-form">${controls}<div id="action-error" class="form-error" role="alert" ${state.error ? "" : "hidden"}>${esc(state.error)}</div><div class="decision-footer"><button id="submit-action" type="submit" class="button primary full">${copy[2]} <span aria-hidden="true">→</span></button><p class="caption">${spec.type === "vote" ? "Your vote is public immediately." : "Your game saves after every decision."}</p></div></form></section>`;
}

function eventHTML(event) {
  const pName = pid => esc(nameOf(pid));
  let tag = "TABLE", cls = "", content = "";
  switch (event.type) {
    case "game_started": case "income": case "vote_income": return "";
    case "mission_drawn": tag = "MISSION"; content = `<b>Mission ${event.mission.number} begins.</b> Target ${event.mission.threshold} tokens · Crew of ${event.mission.crew_size}.`; break;
    case "crew_selected": tag = "CREW"; content = `<b>${pName(event.chairman)}</b> proposed ${event.crew.map(pName).join(", ")}.`; break;
    case "pledges_revealed": tag = "PROMISE"; cls = "claim"; content = `<div class="event-lines">${Object.entries(event.pledges).map(([pid, vector]) => `<span><b>${pName(pid)}</b> ${tokenMini(vector)}</span>`).join("")}</div>`; break;
    case "vote": tag = "VOTE"; content = `<b>${pName(event.player_id)}</b> voted <span class="${event.approve ? "vote-yes" : "vote-no"}">${event.approve ? "Yes" : "No"}</span>.${event.complaints.length ? `<p class="caption">Player complaints: ${event.complaints.map(c => esc(complaintText(c, event.player_id))).join("; ")}</p>` : ""}`; break;
    case "proposal_approved": tag = "VOTE"; content = `<b>Crew approved.</b> ${event.yes_votes} Yes votes. Contributions are now sealed.`; break;
    case "proposal_rejected": tag = "VOTE"; content = `<b>Proposal rejected.</b> ${event.rejections} of 8 rejections.`; break;
    case "attempt_resolved": {
      tag = "RESULT"; cls = "result";
      const m = event.mission;
      content = `<b>${m.winner ? `${title(m.winner)} wins mission ${m.number}.` : "The mission stays open."}</b><p>${esc(tokenText(m.pot))} · ${total(m.pot)}/${m.threshold} funded${event.penalty ? " · Five Red penalty tokens added" : ""}.</p><details class="wallet-details"><summary class="caption">Wallets after resolution</summary><p class="caption">${Object.entries(event.wallets).map(([pid, n]) => `${pName(pid)}: ${n}`).join(" · ")}</p></details>`; break;
    }
    case "reports_revealed": tag = "CLAIM"; cls = "claim"; content = Object.entries(event.reports).filter(([, claims]) => claims.length).map(([speaker, claims]) => `<p><b>${pName(speaker)} says:</b> ${claims.map(c => `“${pName(c.player_id)} ${c.verb} ${c.quantity} ${title(c.color)}”`).join("; ")}</p>`).join("") || "Everyone passed on reporting."; break;
    case "game_over": tag = "FINAL"; cls = "result"; content = `<b>${event.winner ? `${title(event.winner)} wins the game.` : "The game is unresolved."}</b>`; break;
    default: content = esc(title(event.type));
  }
  return `<div class="event ${cls}"><span class="event-tag">${tag}</span><div>${content}</div></div>`;
}

function historyHTML(observation) {
  const groups = new Map();
  for (const event of observation.history) {
    if (["game_started", "income", "vote_income"].includes(event.type)) continue;
    if (state.historyFilter === "results" && !["attempt_resolved", "game_over", "mission_drawn"].includes(event.type)) continue;
    if (state.historyFilter === "claims" && !(event.type === "reports_revealed" || event.type === "pledges_revealed" || (event.type === "vote" && event.complaints.length))) continue;
    if (!groups.has(event.attempt)) groups.set(event.attempt, []);
    groups.get(event.attempt).push(event);
  }
  const latest = Math.max(...groups.keys());
  return `<section class="panel history-panel" id="table-history" aria-labelledby="history-title"><div class="section-head"><div><span class="eyebrow">THE PUBLIC RECORD</span><h2 id="history-title">What happened</h2></div><div class="history-toolbar"><label class="sr-only" for="history-filter">Filter history</label><select id="history-filter">${[["all", "All events"], ["results", "Official results"], ["claims", "Player claims"]].map(([value, label]) => `<option value="${value}" ${state.historyFilter === value ? "selected" : ""}>${label}</option>`).join("")}</select></div></div>
    ${[...groups.entries()].reverse().map(([attempt, events]) => {
      const result = events.find(e => e.type === "attempt_resolved");
      const summary = result ? (result.mission.winner ? `${title(result.mission.winner)} mission win` : "Mission continues") : "In progress";
      const open = state.historyOpen[attempt] ?? attempt === latest;
      return `<details class="history-group" data-attempt="${attempt}" ${open ? "open" : ""}><summary>Attempt ${attempt}<span class="caption">${summary} · ${events.length} events</span></summary><div class="history-events">${events.map(eventHTML).join("")}</div></details>`;
    }).join("") || '<p class="empty-history">No events in this view yet.</p>'}</section>`;
}

function replayStripHTML(replay) {
  const item = replay.timeline[replay.step];
  return `${replay.designer_enabled ? '<div class="designer-banner"><b>Designer inspection is on.</b> All roles and hidden actions are visible in this completed game.</div>' : ""}<section class="replay-strip" aria-label="Replay controls">
    <div class="replay-controls"><button data-command="replay-first" aria-label="Go to start" ${replay.step === 0 ? "disabled" : ""}>|‹</button><button data-command="replay-back" aria-label="Previous step" ${replay.step === 0 ? "disabled" : ""}>‹</button><button class="play-button" data-command="replay-play" aria-label="${state.playing ? "Pause replay" : "Play replay"}" ${replay.step === replay.total_steps - 1 && !state.playing ? "disabled" : ""}>${state.playing ? "Ⅱ" : "▶"}</button><button data-command="replay-next" aria-label="Next step" ${replay.step === replay.total_steps - 1 ? "disabled" : ""}>›</button><button data-command="replay-last" aria-label="Go to latest step" ${replay.step === replay.total_steps - 1 ? "disabled" : ""}>›|</button></div>
    <div class="scrubber"><div class="scrubber-top"><b>${esc(item.label.replace(" · income paid", ""))}</b><span>${replay.step + 1} / ${replay.total_steps}</span></div><input id="replay-scrubber" type="range" min="0" max="${replay.total_steps - 1}" value="${replay.step}" aria-label="Replay position"></div>
    <div class="replay-perspective">${replay.can_inspect ? `<label>View as <select id="replay-seat">${personOptions(replay.viewing_seat)}</select></label><label class="designer-toggle"><input id="designer-toggle" type="checkbox" ${replay.designer_enabled ? "checked" : ""}>Designer view</label>` : `<span class="caption">Viewing ${esc(nameOf(replay.viewing_seat))}</span>`}</div></section>`;
}

function replaySidebarHTML(replay) {
  const observation = replay.observation, mine = observation.private.last_contribution;
  const ownAction = observation.private.submissions.at(-1)?.action;
  let decision = ownAction?.tokens ? tokenText(ownAction.tokens) : ownAction?.approve !== undefined ? (ownAction.approve ? "Yes" : "No") : ownAction?.statements ? ownAction.statements.map(c => `${nameOf(c.player_id)} ${c.verb} ${c.quantity} ${title(c.color)}`).join("; ") || "Passed" : ownAction?.crew?.map(pid => nameOf(pid)).join(", ");
  if (ownAction && "ability" in ownAction) {
    const a = ownAction.ability;
    const choice = !a ? "Ability passed" : a.source === "wallet" ? `Requested ${a.amount} from ${nameOf(a.target)}’s wallet` : a.source === "mission" ? `Requested ${tokenText(a.tokens)} from the mission` : a.from ? `Change 1 ${title(a.from)} to ${title(a.to)}` : a.color ? `Off-crew deposit: 1 ${title(a.color)}` : `Targeted ${nameOf(a.target)}`;
    decision = [decision, choice].filter(Boolean).join(" · ");
  }
  return `${privateHTML(observation)}<section class="panel replay-index"><span class="eyebrow">VERIFIED REPLAY · READ ONLY</span><h3 style="margin-top:9px">Follow the decisions</h3><p class="caption">${replay.designer_enabled ? "Includes each hidden action." : "Only changes visible to this seat appear here."}</p><div class="replay-step-list" aria-label="Replay timeline">${replay.timeline.map((item, i) => `${i === 0 || replay.timeline[i - 1].attempt !== item.attempt ? `<span class="eyebrow" style="padding:12px 10px 4px">ATTEMPT ${item.attempt}</span>` : ""}<button data-command="replay-step" data-step="${item.step}" class="${item.step === replay.step ? "active" : ""}" ${item.step === replay.step ? 'aria-current="step"' : ""}><span>${String(item.step + 1).padStart(2, "0")}</span>${esc(item.label.replace(" · income paid", ""))}</button>`).join("")}</div>${ownAction ? `<p class="private-receipt"><b>Last private decision · ${title(ownAction.type)}</b><br>${esc(decision)}</p>` : ""}${mine ? `<p class="private-receipt"><b>Private receipt · attempt ${mine.attempt}</b><br>${esc(nameOf(observation.viewer))} originally deposited ${esc(tokenText(mine.tokens))}.</p>` : ""}</section>`;
}

function socialInsightsHTML(details) {
  if (!details.traits || !details.beliefs) return "";
  const percent = value => Number.isFinite(value) ? `${Math.round(value * 100)}%` : "—";
  const labels = {selfishness: "Self-interest", caution: "Risk caution", skepticism: "Skepticism"};
  const traits = Object.entries(labels).map(([key, label]) => `<span class="pill">${label} ${percent(details.traits[key])}</span>`).join("");
  const beliefs = Object.entries(details.beliefs);
  const potText = pot => colors.map(c => `${Number(pot[c]).toFixed(1)} ${title(c)}`).join(" · ");
  const covert = details.concealing_red_intent;
  const forecast = details.forecast_pot ? `<p class="inspection-note"><b>${covert ? "Private forecast" : "Expected pot"}:</b> ${potText(details.forecast_pot)}${covert && details.advertised_pot ? `<br><b>Forecast with my public promise:</b> ${potText(details.advertised_pot)}<br><b>Private spending plan:</b> ${esc(tokenText(details.planned_deposit))}` : ""}<br><b>Estimated approval:</b> ${percent(details.approval_likelihood)}</p>` : "";
  const chances = details.outcome_likelihoods;
  const outcomes = chances ? `<p class="inspection-note"><b>Estimated mission outcome:</b> Blue ${percent(chances.blue)} · Red ${percent(chances.red)} · Unfinished ${percent(chances.incomplete)}<br><b>Personal result this attempt:</b> Win ${percent(chances.personal_win)} · Lose ${percent(chances.personal_loss)} · Game continues ${percent(chances.continues)}</p>` : "";
  return `<div class="social-insights"><div class="row wrap">${traits}</div><p class="inspection-note">Pursuing ${esc(title(details.objective))} · Currently favors ${esc(title(details.tactical_side))}.</p>${forecast}${outcomes}
    <h4>This bot’s view of the other players</h4><p class="caption">Estimates at this decision, not revealed roles or calibrated probabilities. Blue preference and honesty are separate judgments.</p>
    <div class="belief-scroll"><table class="belief-table"><thead><tr><th scope="col">Player</th><th scope="col">Blue preference</th><th scope="col">Keeps pledges</th><th scope="col">Report credibility</th><th scope="col">Wants inclusion</th><th scope="col">Expected Yes</th></tr></thead><tbody>${beliefs.map(([pid, b]) => `<tr><th scope="row">${esc(nameOf(pid))}</th>${[b.blue_preference, b.pledge_reliability, b.report_credibility, b.inclusion_demand, details.vote_likelihoods?.[pid]].map(v => `<td>${percent(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
    <details><summary>Evidence behind these estimates</summary>${beliefs.map(([pid, b]) => `<p><b>${esc(nameOf(pid))}</b></p>${b.evidence?.length ? `<ul>${b.evidence.map(e => `<li>Event ${esc(e.event_id)}: ${esc(e.text)}</li>`).join("")}</ul>` : '<p class="caption">No individual evidence yet; using starting assumptions.</p>'}`).join("")}</details></div>`;
}

function agentPredictionsHTML(predictions = [], revealedPlayers = []) {
  if (!predictions.length) return "";
  const players = state.observation.public.players;
  const percent = p => `${Math.round(p * 100)}%`;
  const rows = predictions.map(prediction => {
    const estimates = Object.fromEntries(prediction.estimates.map(e => [e.player_id, e]));
    return `<tr><th scope="row"><button class="button small" data-command="replay-prediction" data-position="${esc(prediction.position)}">Mission ${esc(prediction.mission)}</button></th>${players.map(player => {
      const estimate = estimates[player.id];
      if (!estimate) return '<td>—</td>';
      const p = estimate.p_blue;
      return `<td class="prediction-${p > 0.5 ? "blue" : p < 0.5 ? "red" : "unknown"}" title="${esc(`${player.name}: ${percent(p)} Blue, ${percent(1 - p)} Red. ${estimate.evidence}`)}">${esc(percent(p))}</td>`;
    }).join("")}</tr>`;
  }).join("");
  const teams = Object.fromEntries(revealedPlayers.map(p => [p.id, p.team]));
  const truth = revealedPlayers.length ? `<tfoot><tr><th scope="row">Actual team</th>${players.map(p => `<td>${esc(title(teams[p.id] || "unknown"))}</td>`).join("")}</tr></tfoot>` : "";
  return `<section class="agent-predictions" aria-label="AI team predictions"><h3>AI team predictions</h3><p class="caption">${esc(nameOf(predictions[0].player_id))}'s probability of <b>Blue</b> after each mission. Red is the remaining probability. Recorded from evidence available at that checkpoint, before later observations or designer reveals. Estimates are not calibrated.</p><div class="belief-scroll"><table class="belief-table prediction-table"><thead><tr><th scope="col">Checkpoint</th>${players.map(p => `<th scope="col">${esc(p.name)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody>${truth}</table></div>${predictions.map(p => `<details><summary>Mission ${esc(p.mission)} · Evidence and changes</summary><p>${esc(p.summary)}</p><ul>${p.estimates.map(e => `<li><b>${esc(nameOf(e.player_id))} · ${esc(percent(e.p_blue))} Blue:</b> ${esc(e.evidence)}</li>`).join("")}</ul></details>`).join("")}</section>`;
}

function designerHTML(designer) {
  if (!designer) return "";
  const resolution = designer.last_resolution;
  const last = designer.last_action;
  const decision = designer.bot_decision;
  const baseDescription = action => action.tokens ? tokenText(action.tokens) : action.statements ? `${action.statements.length} report statements` : action.approve !== undefined ? (action.approve ? "Yes" : "No") : action.crew?.map(pid => nameOf(pid)).join(", ") || title(action.type);
  const description = action => {
    const a = action.ability;
    const extra = a ? a.source === "wallet" ? `request ${a.amount} from ${nameOf(a.target)}’s wallet` : a.source === "mission" ? `request ${tokenText(a.tokens)} from mission` : a.from ? `change ${title(a.from)} to ${title(a.to)}` : a.color ? `deposit 1 ${title(a.color)} off crew` : `target ${nameOf(a.target)}` : "";
    return [baseDescription(action), extra].filter(Boolean).join(" · ");
  };
  const effectText = effect => effect.type === "echo" ? `created 1 ${title(effect.color)}` : effect.type === "thief" ? effect.source === "wallet" ? `took ${effect.amount} from ${nameOf(effect.target)}’s wallet` : `took ${tokenText(effect.tokens)} from mission` : `${effect.changed ? "changed 1" : "no token available:"} ${title(effect.from)} → ${title(effect.to)}`;
  return `<section class="designer-panel"><span class="eyebrow">DESIGNER ONLY</span>${agentPredictionsHTML(designer.agent_predictions, designer.players)}<h3>Behind the result</h3>${last ? `<p class="inspection-note">Last action: <b>${esc(nameOf(last.player_id))}</b> · ${title(last.action.type)} · ${esc(description(last.action))}</p>` : '<p class="inspection-note">Roles have been dealt. No actions yet.</p>'}
    ${decision ? `<div class="bot-explanation"><span class="eyebrow">WHY THIS BOT ACTED · ${esc(decision.policy_version)}</span><p>${esc(decision.reason)}</p>${socialInsightsHTML(decision.details)}<details><summary>Forecast and policy limits</summary><pre>${esc(JSON.stringify(decision.details, null, 2))}</pre><ul>${decision.limitations.map(note => `<li>${esc(note)}</li>`).join("")}</ul></details><p class="caption">Saved at the decision. Forecasts are estimates; replay verifies actions and results.</p></div>` : last ? '<p class="inspection-note">No saved bot explanation for this decision.</p>' : ""}
    <h3 style="margin-top:15px">Private cards</h3>${designer.players.map(player => `<div class="inspection-row"><strong>${esc(nameOf(player.id))}</strong><span>${esc(title(player.objective))} · ${esc(title(player.ability || "disabled"))}${player.ability_used ? " (used)" : ""}${player.result ? ` · ${player.result.won ? "Won" : "Did not win"}` : ""}</span></div>`).join("")}
    ${Object.keys(designer.sealed_submissions).length ? `<h3 style="margin-top:15px">Currently sealed</h3>${Object.entries(designer.sealed_submissions).map(([pid, action]) => `<div class="inspection-row"><strong>${esc(nameOf(pid))}</strong><span>${esc(description(action))}</span></div>`).join("")}` : ""}
    ${resolution ? `<h3 style="margin-top:15px">Original deposits · attempt ${resolution.attempt}</h3>${Object.entries(resolution.original_contributions).map(([pid, vector]) => `<div class="inspection-row"><strong>${esc(nameOf(pid))}</strong>${tokenMini(vector)}</div>`).join("") || '<p class="inspection-note">No crew deposits. This attempt used the rejection penalty.</p>'}<p class="inspection-note">${resolution.penalty ? "Penalty attempt" : "Approved crew"} · Final pot: ${esc(tokenText(resolution.mission.pot))}</p>${resolution.effects?.length ? `<h3>Effects in resolution order</h3>${resolution.effects.map(effect => `<div class="inspection-row"><strong>${esc(nameOf(effect.player_id))}</strong><span>${esc(title(effect.type))}: ${esc(effectText(effect))}</span></div>`).join("")}` : ""}` : ""}</section>`;
}

function tableHTML() {
  const observation = state.observation, replay = state.mode === "replay", p = observation.public;
  return `<div class="table-heading"><div><span class="eyebrow">${esc(state.game.title)} · ${replay ? "REPLAY ROOM" : "PRACTICE TABLE"}</span><h1>${replay ? "Every choice, revisited." : `Your seat, ${esc(nameOf(observation.viewer))}.`}</h1></div><div class="heading-tools"><span class="saved"><i></i>${replay ? "Recorded game · verified" : "All decisions saved"}</span>${replay ? (state.game.can_resume ? `<button class="button small" data-command="open-table" data-id="${esc(state.game.id)}">Return to live table ↗</button>` : '<button class="button small" data-command="library">Back to library →</button>') : `<button class="button small" data-command="open-replay" data-id="${esc(state.game.id)}" data-latest="true">${observation.phase === "game_over" ? "Review this game" : "Review so far"} ↗</button>`}</div></div>
    ${replay ? replayStripHTML(state.replay) : pacingHTML()}
    <div class="workspace"><div class="table-column">${missionHTML(observation)}<div id="players-area">${playersHTML(observation)}</div><p class="practice-note">Practice table: computer opponents, ${observation.mode === "development_common_rules" ? "Loyalist objectives (common rules)" : "private objectives"}, abilities ${observation.public.rules.abilities_enabled ? "on" : "off"}.</p>${replay ? designerHTML(state.replay.designer) : ""}</div><aside class="side-column">${replay ? replaySidebarHTML(state.replay) : privateHTML(observation) + `<div id="decision-area">${actionHTML(observation)}</div>`}</aside></div>
    <div id="history-area">${historyHTML(observation)}</div>${!replay && observation.action_spec && !state.canAdvance ? '<button class="mobile-action-jump button primary" data-command="jump-action">Your turn · Go to your controls ↓</button>' : ""}`;
}

function render() {
  document.title = state.mode === "library" ? "Hidden Rules · Game library" : `${state.mode === "replay" ? "Replay" : `Mission ${state.observation.public.mission.number}`} · Hidden Rules`;
  $("#app").innerHTML = state.mode === "library" ? libraryHTML() : tableHTML();
  if (state.mode === "table") { syncAction(); scheduleAdvance(); }
  if (state.mode === "replay") {
    const list = $(".replay-step-list"), active = $(".replay-step-list button.active");
    if (list && active) list.scrollTop = active.offsetTop - list.firstElementChild.offsetTop - list.clientHeight / 2;
  }
}
function renderDecision(focusSelector) {
  $("#decision-area").innerHTML = actionHTML(state.observation);
  syncAction();
  if (focusSelector) $(focusSelector)?.focus({preventScroll: true});
}
function isQuantity(value) { return Number.isSafeInteger(value) && value >= 0 && value <= 2147483647; }
function legalDraft() {
  const spec = state.observation?.action_spec, draft = state.draft;
  if (!spec || state.canAdvance || !legalAbility()) return false;
  if (["prepare", "audit"].includes(spec.type)) return true;
  if (spec.type === "select_crew") return draft.crew.length === spec.crew_size;
  if (["pledge", "contribute"].includes(spec.type)) return colors.every(c => isQuantity(draft.tokens[c])) && total(draft.tokens) <= spec.max_total;
  if (spec.type === "vote") return typeof draft.approve === "boolean" && draft.complaints.length === (draft.approve ? 0 : 1) && draft.complaints.every(c => c.player_id || c.color);
  if (spec.type === "report") return draft.statements.length >= spec.min_statements && draft.statements.length <= 3 && draft.statements.every(c => isQuantity(c.quantity));
  return false;
}
function syncAction() {
  const button = $("#submit-action"), spec = state.observation?.action_spec;
  if (!button || !spec) return;
  button.disabled = state.busy || !legalDraft();
  if (state.busy) button.textContent = "Sealing your decision…";
  else if (spec.type === "report") button.textContent = "Seal my report →";
  if ($("#budget-value")) {
    const remaining = spec.max_total - total(state.draft.tokens);
    $("#budget-value").textContent = `${remaining} of ${spec.max_total} remaining`;
    $("#budget-row").classList.toggle("over", remaining < 0);
    document.querySelectorAll(".stepper").forEach(button => {
      const delta = Number(button.dataset.delta), color = button.dataset.color;
      button.disabled = state.busy || (delta > 0 ? remaining <= 0 : state.draft.tokens[color] <= 0);
    });
  }
}
function draftAction() {
  const type = state.observation.action_spec.type, d = state.draft;
  if (type === "select_crew") return {type, crew: d.crew};
  if (["prepare", "audit"].includes(type)) return {type, ability: abilityChoice()};
  if (["pledge", "contribute"].includes(type)) return {type, tokens: d.tokens,
    ...(type === "contribute" && "ability" in state.observation.action_spec ? {ability: abilityChoice()} : {})};
  if (type === "vote") return {type, approve: d.approve, complaints: d.complaints.map(c => Object.fromEntries(Object.entries(c).filter(([, v]) => v)))};
  return {type, statements: d.statements};
}
async function submitDecision(event) {
  event.preventDefault();
  if (state.busy || !legalDraft()) return;
  const observation = state.observation, gameId = state.game.id, generation = state.generation;
  clearLiveTimer();
  state.busy = true;
  syncAction();
  try {
    const data = await api(`/api/games/${encodeURIComponent(gameId)}/actions`, {request_id: observation.request_id, revision: observation.revision, action: draftAction(), paced: true});
    state.busy = false;
    if (generation !== state.generation || state.mode !== "table" || state.game.id !== gameId) return;
    acceptTable(data);
    state.busy = false;
    render();
    announce(data.observation.phase === "game_over" ? "The game is complete." : `Decision saved. Next: ${title(data.observation.phase)}.`);
  } catch (error) {
    state.busy = false;
    state.error = error.message;
    if (error.status === 409) {
      const data = await api(`/api/games/${encodeURIComponent(gameId)}/state`);
      if (generation !== state.generation) return;
      acceptTable(data);
      toast("The table changed in another window. The latest state is now shown.", true);
      render();
    } else { renderDecision(); toast(error.message, true); }
  }
}

function stopPlayback() { clearTimeout(state.timer); state.timer = null; state.playing = false; }
function route(hash) { stopPlayback(); clearLiveTimer(); if (location.hash === hash) loadRoute(); else location.hash = hash; }
async function loadRoute() {
  stopPlayback(); clearLiveTimer(); state.busy = false; state.transition = ""; state.lastStep = null;
  const generation = ++state.generation;
  const [path, queryText] = location.hash.replace(/^#/, "").split("?");
  const [mode, id] = (path || "library").split("/");
  state.error = "";
  try {
    if (mode === "library" || !id) {
      const data = await api("/api/games");
      if (generation !== state.generation) return;
      state.mode = "library"; state.games = data.games; state.replay = null;
    } else if (mode === "table") {
      const data = await api(`/api/games/${encodeURIComponent(id)}/resume`, {paced: true});
      if (generation !== state.generation) return;
      state.mode = "table"; acceptTable(data); state.replay = null;
    } else if (mode === "replay") {
      const params = new URLSearchParams(queryText || "");
      const data = await api(`/api/games/${encodeURIComponent(id)}/replay?${params.toString()}`);
      if (generation !== state.generation) return;
      state.mode = "replay"; state.game = data.game; state.observation = data.observation; state.replay = data;
    } else throw new Error("That table view does not exist.");
    state.historyOpen = {}; state.historyFilter = "all"; state.playerHistory = null; state.potReference = ""; state.potComparisonOpen = false; state.privateDetailsOpen = {};
    render(); window.scrollTo(0, 0);
  } catch (error) {
    if (generation !== state.generation) return;
    $("#app").innerHTML = `<div class="loading"><span class="eyebrow">COULD NOT OPEN THE TABLE</span><h1>${esc(error.message)}</h1><button class="button primary" data-command="library" style="margin-top:24px">Return to library →</button></div>`;
    toast(error.message, true);
  }
}

async function seek(step, seat = state.replay.viewing_seat, designer = state.replay.designer_enabled, position = null) {
  const generation = ++state.generation, id = state.game.id;
  const params = new URLSearchParams({...(position != null ? {position} : {step}), seat, designer});
  try {
    const data = await api(`/api/games/${encodeURIComponent(id)}/replay?${params}`);
    if (generation !== state.generation) return;
    state.replay = data; state.observation = data.observation;
    history.replaceState(null, "", `#replay/${encodeURIComponent(id)}?${params}`);
    if (data.step === data.total_steps - 1) stopPlayback();
    render();
    if (state.playing) state.timer = setTimeout(() => seek(state.replay.step + 1), 1200);
  } catch (error) { stopPlayback(); toast(error.message, true); render(); }
}

async function command(button) {
  const cmd = button.dataset.command;
  if (cmd === "help") { clearLiveTimer(); $("#help-dialog").showModal(); return; }
  if (cmd === "close-help") { $("#help-dialog").close(); scheduleAdvance(); return; }
  if (cmd === "library") { route("#library"); return; }
  if (cmd === "filter") { state.filter = button.dataset.value; render(); return; }
  if (cmd === "open-table") { route(`#table/${encodeURIComponent(button.dataset.id)}`); return; }
  if (cmd === "open-replay") { route(`#replay/${encodeURIComponent(button.dataset.id)}?step=${button.dataset.latest ? -1 : 0}`); return; }
  if (cmd === "jump-action") { $("#decision-area").scrollIntoView({behavior: "smooth", block: "start"}); return; }
  if (cmd === "new-game" || cmd === "sample") {
    button.disabled = true;
    const label = button.textContent;
    button.textContent = cmd === "sample" ? "Playing a sample game…" : "Dealing your table…";
    try {
      const data = await api("/api/games", {human_seat: Number($("#new-seat")?.value || 0), demo: cmd === "sample", paced: true});
      route(`#${cmd === "sample" ? "replay" : "table"}/${encodeURIComponent(data.game.id)}`);
    } catch (error) { toast(error.message, true); button.disabled = false; button.textContent = label; }
    return;
  }
  if (cmd.startsWith("replay-")) {
    if (cmd === "replay-play") {
      if (state.playing) { stopPlayback(); render(); }
      else { state.playing = true; seek(state.replay.step + 1); }
      return;
    }
    stopPlayback();
    if (cmd === "replay-prediction") {
      await seek(state.replay.step, state.replay.viewing_seat, true, Number(button.dataset.position)); return;
    }
    const target = {"replay-first": 0, "replay-back": state.replay.step - 1, "replay-next": state.replay.step + 1, "replay-last": state.replay.total_steps - 1, "replay-step": Number(button.dataset.step)}[cmd];
    await seek(target); return;
  }
  if (cmd === "live-toggle") { state.livePaused = state.pace ? !state.livePaused : false; if (!state.pace) { state.pace = 1800; savePace(); } render(); return; }
  if (cmd === "live-next") { await advanceTable(); return; }
  if (cmd === "player-history" || cmd === "close-player-history") {
    state.playerHistory = cmd === "close-player-history" || state.playerHistory === button.dataset.id ? null : button.dataset.id;
    if (state.mode === "table" && state.playerHistory) { state.livePaused = true; clearLiveTimer(); }
    render();
    if (state.playerHistory) $("#player-history")?.scrollIntoView({behavior:"smooth",block:"nearest"});
    return;
  }
  if (state.busy) return;
  if (cmd === "continue") { await loadRoute(); return; }
  if (cmd === "select-player") {
    const crew = state.draft.crew, id = button.dataset.id;
    if (crew.includes(id)) crew.splice(crew.indexOf(id), 1);
    else if (crew.length < state.observation.action_spec.crew_size) crew.push(id);
    else { toast("Your crew is full. Remove a player before choosing another."); return; }
    $("#players-area").innerHTML = playersHTML(state.observation); renderDecision(`[data-command="select-player"][data-id="${id}"]`); return;
  }
  if (cmd === "token") {
    const color = button.dataset.color, value = state.draft.tokens[color] + Number(button.dataset.delta);
    if (!isQuantity(value)) return;
    state.draft.tokens[color] = value;
    $(`#token-${color}`).value = value; syncAction(); return;
  }
  if (cmd === "copy-pledge") state.draft.tokens = {...state.observation.public.pledges[state.observation.viewer]};
  if (cmd === "vote-choice") setVoteChoice(button.dataset.value === "yes");
  if (cmd === "own-report") state.draft.statements = ownReports(state.observation);
  if (cmd === "add-row") {
    const kind = button.dataset.kind;
    if (kind === "statements" && state.draft.statements.length < 3) state.draft.statements.push({player_id: state.observation.viewer, verb: "gave", quantity: 0, color: "blue"});
  }
  if (cmd === "remove-row" && button.dataset.kind === "statements") state.draft.statements.splice(Number(button.dataset.index), 1);
  renderDecision(cmd === "vote-choice" ? `[data-command="vote-choice"][data-value="${button.dataset.value}"]` : undefined);
}

document.addEventListener("click", event => {
  const button = event.target.closest("[data-command]");
  if (button && !button.disabled) command(button).catch(error => toast(error.message, true));
});
document.addEventListener("submit", event => { if (event.target.id === "decision-form") submitDecision(event).catch(error => toast(error.message, true)); });
document.addEventListener("input", event => {
  if (event.target.dataset.abilityToken) {
    state.draft.ability.tokens[event.target.dataset.abilityToken] = event.target.value === "" ? NaN : Number(event.target.value);
    syncAction();
  }
  if (event.target.dataset.ability === "amount") {
    state.draft.ability.amount = event.target.value === "" ? NaN : Number(event.target.value);
    syncAction();
  }
  if (event.target.dataset.token) {
    state.draft.tokens[event.target.dataset.token] = event.target.value === "" ? NaN : Number(event.target.value);
    syncAction();
  }
  const row = event.target.closest(".claim-row");
  if (row && event.target.dataset.field) {
    const field = event.target.dataset.field;
    state.draft[row.dataset.kind][Number(row.dataset.index)][field] = field === "quantity" ? (event.target.value === "" ? NaN : Number(event.target.value)) : event.target.value;
    syncAction();
  }
});
document.addEventListener("change", event => {
  if (event.target.id === "table-pace") { updatePace(event.target); return; }
  if (event.target.id === "pot-reference") { state.potReference = event.target.value; render(); return; }
  const abilityField = event.target.dataset.ability;
  if (abilityField && abilityField !== "amount") {
    state.draft.ability[abilityField] = abilityField === "active" ? event.target.value === "yes" : event.target.value;
    if (["active", "source"].includes(abilityField)) renderDecision(`[data-ability="${abilityField}"]`);
    else syncAction();
  }
  if (event.target.id === "history-filter") { state.historyFilter = event.target.value; $("#history-area").innerHTML = historyHTML(state.observation); }
  if (event.target.id === "replay-scrubber") { stopPlayback(); seek(Number(event.target.value)); }
  if (event.target.id === "replay-seat") { stopPlayback(); seek(state.replay.step, event.target.value, state.replay.designer_enabled, state.replay.position); }
  if (event.target.id === "designer-toggle") { stopPlayback(); seek(state.replay.step, state.replay.viewing_seat, event.target.checked, state.replay.position); }
});
document.addEventListener("toggle", event => {
  if (event.target.dataset?.privateDetail && event.target.isConnected) state.privateDetailsOpen[event.target.dataset.privateDetail] = event.target.open;
  if (event.target.id === "pot-comparison" && event.target.isConnected) state.potComparisonOpen = event.target.open;
  if (event.target.matches?.(".history-group")) state.historyOpen[event.target.dataset.attempt] = event.target.open;
}, true);
document.addEventListener("focusin", event => { if (event.target.id === "table-pace") clearLiveTimer(); });
document.addEventListener("focusout", event => { if (event.target.id === "table-pace") scheduleAdvance(); });
document.addEventListener("keydown", event => {
  if (event.target.id === "table-pace" && event.key === "Enter") { event.preventDefault(); updatePace(event.target); event.target.blur(); return; }
  if (state.mode !== "replay" || ["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(event.target.tagName) || $("#help-dialog").open) return;
  if (event.key === "ArrowRight" && state.replay.step < state.replay.total_steps - 1) { event.preventDefault(); stopPlayback(); seek(state.replay.step + 1); }
  if (event.key === "ArrowLeft" && state.replay.step > 0) { event.preventDefault(); stopPlayback(); seek(state.replay.step - 1); }
});
window.addEventListener("hashchange", loadRoute);
window.addEventListener("pagehide", () => { stopPlayback(); clearLiveTimer(); });
document.addEventListener("visibilitychange", scheduleAdvance);
$("#help-dialog")?.addEventListener("close", scheduleAdvance);
async function boot() {
  try {
    const data = await api("/api/bootstrap");
    state.token = data.token; state.games = data.games;
    $("#full-guide").textContent = data.guide;
    if (location.hash && location.hash !== "#library") await loadRoute();
    else { state.mode = "library"; render(); }
  } catch (error) {
    $("#app").innerHTML = `<div class="loading"><h1>The local table is offline.</h1><p class="muted" style="margin:18px 0">Start the Python web server, then refresh this page.</p><button class="button primary" data-command="library">Try again →</button></div>`;
    toast(error.message, true);
  }
}
boot();

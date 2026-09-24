/* Thin player interface. Legal decisions and game outcomes come from Python. */
"use strict";
const $ = (selector, root = document) => root.querySelector(selector);
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[char]));
const colors = ["blue", "red", "green"];
const title = text => String(text || "").replaceAll("_", " ").replace(/\b\w/g, char => char.toUpperCase());
const total = vector => typeof vector === "number" ? vector : colors.reduce((sum, color) => sum + Number(vector?.[color] || 0), 0);
const state = {token: null, games: [], mode: "library", game: null, observation: null, replay: null,
  draft: {}, draftKey: null, error: "", busy: false, filter: "all", historyFilter: "all", historyOpen: {}, historyVisible: false,
  generation: 0, timer: null, playing: false, liveTimer: null, pace: readPace(), livePaused: false,
  canAdvance: false, stepKey: null, lastStep: null, playerHistory: null, potReference: "", potComparisonOpen: false, privateDetailsOpen: {},
  resolutionHold: null, resolutionSeen: null, resolutionAnimated: null};

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
  if (state.mode !== "table" || state.resolutionHold || !state.canAdvance || state.busy || state.livePaused || !state.pace || document.hidden || document.activeElement?.id === "table-pace" || $("#help-dialog")?.open) return;
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
  captureResolution(data.observation);
  resetDraft(data.observation);
}
async function advanceTable() {
  if (state.resolutionHold || state.busy || !state.canAdvance || state.mode !== "table") return;
  clearLiveTimer();
  const restoreFocus = document.activeElement?.dataset?.command === "live-next";
  const id = state.game.id, generation = state.generation;
  state.busy = true; render();
  try {
    const data = await api(`/api/games/${encodeURIComponent(id)}/advance`, {step_key: state.stepKey});
    if (generation !== state.generation || state.mode !== "table") return;
    acceptTable(data); announce(state.resolutionHold ? resolutionAnnouncement(data.observation) : state.lastStep.title);
  } catch (error) {
    if (generation !== state.generation) return;
    state.livePaused = true;
    if (error.status === 409) {
      try { const data = await api(`/api/games/${encodeURIComponent(id)}/state`); if (generation === state.generation) acceptTable(data); }
      catch (_) {}
    }
    toast(error.message, true);
  } finally {
    if (generation === state.generation) {
      state.busy = false; render();
      if (restoreFocus) ($('[data-command="resolution-continue"]') || $('[data-command="live-next"]') || $('[data-command="jump-action"]'))?.focus({preventScroll:true});
    }
  }
}
function pacingHTML() {
  if (state.observation.phase === "game_over") return '<section class="pacing-bar" aria-label="Game complete"><span class="eyebrow">Game complete</span></section>';
  if (state.resolutionHold) return '<section class="pacing-bar" aria-label="Table playback paused"><span class="eyebrow">Paused for the result</span></section>';
  const finished = state.observation.phase === "game_over", waiting = !finished && !state.canAdvance;
  return `<section class="pacing-bar" aria-label="Table playback controls"><span class="eyebrow" id="pace-status">${pacingStatus()}</span><div class="pace-controls"><label>Seconds / step <input id="table-pace" type="number" inputmode="decimal" min="0" max="2147483.647" step="any" value="${state.pace / 1000}" aria-label="Seconds per step (0 for manual)" ${state.busy || finished ? "disabled" : ""}></label><button class="button small" data-command="live-toggle" ${finished ? "disabled" : ""}>${state.livePaused || !state.pace ? "Auto play" : "Pause"}</button>${waiting ? '<button class="button small primary" data-command="jump-action">Your decision ↑</button>' : `<button class="button small primary" data-command="live-next" ${!state.canAdvance || state.busy ? "disabled" : ""}>${state.busy ? "Advancing…" : "Next step →"}</button>`}</div></section>`;
}
// Attach votes and pledges to the proposal visible when they happened.
function contextualEvents(observation) {
  let context = {mission: observation.history.find(e => e.mission)?.mission.number || observation.public.mission.number, attempt: null, proposal: 0, crew: [], chairman: null};
  return observation.history.map((event, index) => {
    if (event.attempt !== context.attempt) context = {...context, attempt: event.attempt, proposal: 0, crew: [], chairman: null};
    if (event.mission) context = {...context, mission: event.mission.number};
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
  if (e.type === "vote") return {title: `${name(e.player_id)} votes ${e.approve ? "Yes" : "No"}${e.influence ? `, spending ${e.influence} tokens` : ""}${e.bonus ? ` (+${e.bonus} bonus influence)` : ""}.${e.complaints?.length ? ` Reason: ${e.complaints.map(c => complaintText(c, e.player_id, observation)).join("; ")}.` : ""}`, lines: context ? [context] : []};
  if (e.type === "crew_selected") return {title: `${name(e.chairman)} proposes a crew.`, lines: [e.crew.map(name).join(", ")]};
  if (e.type === "pledges_revealed") {
    const lines = Object.entries(e.pledges).map(([pid, vector]) => `${name(pid)} pledges ${tokenText(vector)}.`);
    return lines.length === 1 ? {title: lines[0], lines: []} : {title: "The crew reveals its pledges.", lines};
  }
  if (e.type === "proposal_approved") return {title: `Crew approved: ${e.tally ? tallyText(e.tally) : `${e.yes_votes} Yes votes`}.`, lines: context ? [context] : []};
  if (e.type === "proposal_rejected") return {title: `The crew is rejected.${e.tally ? ` ${tallyText(e.tally)}.` : ""}`, lines: context ? [context] : []};
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
  const privateStep = newOwn && own && (own.quantity !== undefined || own.tokens || own.statements || own.ability || previous?.action_spec?.ability)
    ? {title: `Your ${title(own.type).toLowerCase()} is sealed.`, lines: [privateActionText(own)]} : null;
  if (!previous && privateStep) return privateStep;
  const fresh = entries.slice(previous ? previous.history.length : 0).filter(entry => !["game_started", "income", "proposal_income"].includes(entry.event.type));
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
function signed(n) { return n > 0 ? `+${n}` : String(n); }

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
  let text = action.quantity !== undefined ? `Pledged ${action.quantity} tokens` : action.tokens ? `${action.type === "pledge" ? "Pledged" : "Committed"} ${tokenText(action.tokens)}` : action.statements ? `Sealed report: ${action.statements.map(c => `${nameOf(c.player_id)} ${c.verb} ${c.quantity} ${title(c.color)}`).join("; ")}` : title(action.type);
  if ("ability" in action) {
    const a = action.ability;
    text += !a ? " · Ability passed" : a.source === "wallet" ? ` · Requested ${a.amount} from ${nameOf(a.target)}’s wallet` : a.source === "mission" ? ` · Requested ${tokenText(a.tokens)} from the mission` : a.from ? ` · Change ${title(a.from)} to ${title(a.to)}` : a.color ? ` · Off-crew deposit: 1 ${title(a.color)}` : ` · Targeted ${nameOf(a.target)}`;
  }
  return text;
}
function attemptLabel(mission, attempt) { return `Mission ${mission} · Attempt ${attempt}`; }
function attemptOutcome(result) {
  return result.mission.winner ? `${title(result.mission.winner)} wins mission ${result.mission.number}` : "Mission stays open";
}
function attemptResultHTML(result) {
  const m = result.mission, before = result.previous_pot;
  return `<div class="attempt-result-summary"><strong>${attemptOutcome(result)}</strong><span>${total(m.pot)} / ${m.threshold} tokens · ${esc(tokenText(m.pot))}</span>${before ? `<span class="attempt-deltas">This attempt: ${colors.map(c => `<span><i class="token-dot ${c}"></i>${signed(m.pot[c] - before[c])} ${title(c)}</span>`).join("")}</span>` : ""}${result.penalty ? '<span>Eight rejections · five-Red penalty</span>' : ""}${result.reserve_added ? `<span>Includes ${result.reserve_added} Green from reserves</span>` : ""}${result.token_totals ? `<span class="caption">Table totals · Paid: ${esc(tokenText(result.token_totals.paid))} · Green added: ${esc(result.token_totals.green_added)}</span>` : ""}</div>`;
}
function playerHistoryHTML(observation, pid) {
  if (!pid) return "";
  const entries = contextualEvents(observation), groups = new Map(), outcomes = new Map();
  for (const entry of entries) {
    if (!groups.has(entry.attempt)) groups.set(entry.attempt, {mission:entry.mission, result:null, rows:[]});
    if (entry.event.type === "attempt_resolved") groups.get(entry.attempt).result = entry.event;
    if (["proposal_approved", "proposal_rejected"].includes(entry.event.type)) outcomes.set(`${entry.attempt}:${entry.proposal}`, entry.event.type === "proposal_approved" ? "Crew approved" : "Crew rejected");
  }
  const add = (entry, text, withCrew = false) => {
    const status = outcomes.get(`${entry.attempt}:${entry.proposal}`);
    groups.get(entry.attempt).rows.push(`<li>${entry.proposal ? `<span class="caption">Proposal ${entry.proposal}${status ? ` · ${status}` : " · Awaiting vote result"}</span>` : ""}<p>${text}</p>${withCrew && entry.crew.length ? `<p class="history-crew">${esc(crewContext(entry, observation))}</p>` : ""}</li>`);
  };
  for (const entry of entries) {
    const event = entry.event;
    if (event.type === "crew_selected") {
      if (event.chairman === pid) add(entry, `Proposed ${event.crew.map(p => esc(nameOf(p, observation))).join(", ")}.`);
      else if (event.crew.includes(pid)) add(entry, `Selected for ${esc(nameOf(event.chairman, observation))}’s crew.`, true);
    }
    if (event.type === "pledges_revealed" && event.pledges[pid] !== undefined) add(entry, `Pledged ${esc(tokenText(event.pledges[pid]))}.`, true);
    if (event.type === "vote" && event.player_id === pid) add(entry, `<b>Voted ${event.approve ? "Yes" : "No"}.</b>${event.influence ? ` Spent ${event.influence} tokens.` : ""}${event.bonus ? ` +${event.bonus} bonus influence.` : ""}${event.complaints?.length ? ` Reason: ${esc(event.complaints.map(c => complaintText(c,pid,observation)).join("; "))}.` : ""}`, true);
    if (event.type === "reports_revealed" && event.reports[pid]) add(entry, `Reported: ${esc(event.reports[pid].map(c => `${nameOf(c.player_id, observation)} ${c.verb} ${c.quantity} ${title(c.color)}`).join("; "))}. <span class="caption">Player claim</span>`);
  }
  const history = [...groups.entries()].reverse().filter(([,g]) => g.rows.length).map(([attempt,g]) =>
    `<section class="player-history-attempt"><div class="history-attempt-heading"><h4>${attemptLabel(g.mission,attempt)}</h4><button class="text-button" data-command="history-attempt" data-attempt="${attempt}">${g.result ? "View result ↗" : "View attempt ↗"}</button></div>${g.result ? attemptResultHTML(g.result) : '<p class="caption">Attempt in progress</p>'}<ol>${g.rows.join("")}</ol></section>`).join("");
  const own = pid === observation.viewer ? observation.private.submissions.filter(r => !["select_crew","vote"].includes(r.action.type) && (r.action.quantity !== undefined || r.action.tokens || r.action.statements || r.action.ability)) : [];
  return `<section class="player-history panel" id="player-history" aria-label="${esc(nameOf(pid, observation))} action history"><div class="row spread"><h3>${esc(nameOf(pid, observation))} · Action history</h3><button class="icon-button" data-command="close-player-history" aria-label="Close player history">×</button></div><div class="player-history-groups">${history || '<p class="caption">No public actions yet.</p>'}</div>${own.length ? `<h4>Your private decisions</h4><ol>${own.map((r,i) => `<li><span class="caption">Private decision ${i+1} · ${title(r.action.type)}</span><p>${esc(privateActionText(r.action))}</p></li>`).join("")}</ol>` : ""}</section>`;
}

async function api(path, payload) {
  if (window.MissionBrowser) return window.MissionBrowser.request(path, payload);
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
  if (typeof vector === "number") return `${vector} tokens`;
  return colors.filter(c => vector?.[c]).map(c => `${vector[c]} ${title(c)}`).join(" + ") || "0 tokens";
}
function tokenMini(vector) {
  if (typeof vector === "number") return `<span class="mini-tokens">${vector} tokens</span>`;
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
  const lastNo = observation.private.submissions.findLast(r => r.action.type === "vote" && !r.action.approve)?.action.complaints?.[0];
  state.draft = {crew: [], influence: 0, savedComplaint: lastNo ? {...lastNo} : null, tokens: {blue: 0, red: 0, green: 0}, approve: null, complaints: [],
    statements: observation.action_spec?.min_statements ? ownReports(observation) : [],
    ability: {target: "", source: "", amount: 1, color: "", from: "", to: "", tokens: {blue: 0, red: 0, green: 0}}};
}

function libraryHTML() {
  const games = state.games.filter(game => state.filter === "all" || (state.filter === "active" ? game.can_resume : !game.can_resume));
  const cards = games.map(game => {
    const finished = ["FINISHED", "UNRESOLVED"].includes(game.status);
    const date = new Date(game.updated_at * 1000).toLocaleString(undefined, {month: "short", day: "numeric", hour: "numeric", minute: "2-digit"});
    const winner = Object.entries(game.score).find(([, score]) => score === (game.missions_to_win || 3))?.[0];
    return `<article class="panel game-card">
      <div><div class="row spread"><span class="eyebrow">${game.bundled ? "FEATURED REPLAY" : game.sample ? "RECORDED BOT GAME" : "YOUR TABLE"}</span><span class="pill ${game.can_resume ? "live" : ""}">${game.can_resume ? "In progress" : game.status === "UNRESOLVED" ? "Unresolved" : finished ? "Completed" : "Paused recording"}</span></div>
      <h3>${esc(game.title)}</h3><p class="caption">Mission ${game.mission} · Attempt ${game.attempt}<br>${game.mode === "development_abilities" ? "Private objectives & abilities" : game.mode === "development_objectives" ? "Private objectives · Abilities off" : "Common rules · All Loyalists"}</p></div>
      <div class="row spread"><div class="game-score"><span><i class="token-dot blue"></i> Blue <b>${game.score.blue}</b></span><span><i class="token-dot red"></i> Red <b>${game.score.red}</b></span></div>${winner ? `<span class="caption">${title(winner)} wins</span>` : ""}</div>
      <div class="game-card-footer">${game.can_resume ? `<button class="button primary small" data-command="open-table" data-id="${esc(game.id)}">Resume table <span aria-hidden="true">↗</span></button>` : ""}
      <button class="button small ${finished ? "primary" : "subtle"}" data-command="open-replay" data-id="${esc(game.id)}">${finished ? "Watch replay" : "Review so far"} <span aria-hidden="true">→</span></button></div>
      <p class="caption">${game.bundled ? esc(game.description || "Included with the game · Read-only") : `Saved ${esc(date)}`}</p>
    </article>`;
  }).join("");
  return `<section class="welcome"><div><span class="eyebrow">EIGHT PLAYERS. EVERY CHOICE LEAVES A TRACE.</span><h1>A seat at the table.<br>A reason to watch.</h1><p>Propose a crew, make a promise, and decide what to put on the line. Follow the table as each mission unfolds.</p>
    <div class="row"><button class="button primary" data-command="new-game">Take a seat <span aria-hidden="true">↗</span></button><button class="button" data-command="sample">Watch a sample game <span aria-hidden="true">▷</span></button></div>
    <label class="new-game-seat">Your seat <select id="new-seat" aria-label="Your seat for a new game">${Array.from({length:8}, (_, i) => `<option value="${i}">Seat ${i + 1}</option>`).join("")}</select></label>
    <p class="caption">New names at every table<br>5 Blue · 3 Red · Contrarian disabled<br>Private objectives & abilities · Computer opponents</p></div>
    <div class="table-art" aria-hidden="true"><div class="art-table"><div class="art-card"><span><i></i></span></div><div class="art-card"><span><i></i></span></div><div class="art-card"><span><i></i></span></div></div>${["A", "B", "C", "D", "E", "F", "G", "H"].map(n => `<span class="art-seat">${n}</span>`).join("")}</div></section>
    <section aria-labelledby="library-title"><div class="section-head library-head"><div><span class="eyebrow">PICK UP WHERE YOU LEFT OFF</span><h2 id="library-title">Your game library</h2></div><div class="library-filter" aria-label="Filter saved games">${[["all", "All games"], ["active", "In progress"], ["finished", "Replays"]].map(([value, label]) => `<button class="${state.filter === value ? "active" : ""}" data-command="filter" data-value="${value}" aria-pressed="${state.filter === value}">${label}</button>`).join("")}</div></div>
    ${window.MissionBrowser ? '<p class="caption browser-storage-note">Your games save in this browser on this device. Clearing this site’s browser data removes your saves. Featured replays are included with the site.</p>' : ""}<div class="library-grid">${cards || '<div class="panel empty-library">No tables here yet. Take a seat or generate a sample game to explore.</div>'}</div></section>`;
}

// Reconstruct the resolved table from public events: the engine may already have
// drawn the next mission when the final sealed report is revealed.
function resolutionMoment(observation) {
  const history = observation.history, index = history.findLastIndex(e => e.type === "attempt_resolved");
  if (index < 0) return null;
  const event = history[index], after = history.slice(index + 1);
  if (after.some(e => !["reports_revealed", "income", "mission_drawn", "game_over"].includes(e.type))) return null;
  const before = history.slice(0, index), proposalIndex = before.findLastIndex(e => e.type === "crew_selected" && e.attempt === event.attempt);
  const proposal = before[proposalIndex];
  const votes = before.slice(proposalIndex + 1).filter(e => e.type === "vote" && e.attempt === event.attempt);
  const reports = after.find(e => e.type === "reports_revealed" && e.attempt === event.attempt);
  const crew = event.penalty ? [] : proposal?.crew || (observation.public.attempt === event.attempt ? observation.public.crew : []);
  const pledges = before.findLast(e => e.type === "pledges_revealed" && e.attempt === event.attempt)?.pledges || {};
  const previous = event.previous_pot || before.findLast(e => ["attempt_resolved", "mission_drawn"].includes(e.type) && e.mission.number === event.mission.number)?.mission.pot || {blue:0, red:0, green:0};
  return {key:`${observation.game_id}:${index}:${reports ? "reports" : "pot"}`, event, crew, pledges, votes, previous,
    chairman:proposal?.chairman || observation.public.chairman, reports:reports?.reports || null};
}
function captureResolution(observation) {
  const moment = resolutionMoment(observation);
  if (!moment) { state.resolutionHold = null; state.resolutionSeen = null; return; }
  if (moment.key !== state.resolutionSeen) {
    state.resolutionSeen = moment.key; state.resolutionHold = moment.key;
    clearLiveTimer();
    if (state.mode === "replay") stopPlayback();
  }
}
function displayedResolution(observation) {
  const moment = resolutionMoment(observation);
  return moment && (state.resolutionHold === moment.key ||
    (["audit", "report", "game_over"].includes(observation.phase) && observation.public.attempt === moment.event.attempt)) ? moment : null;
}
function resolutionAnnouncement(observation) {
  const moment = resolutionMoment(observation), m = moment.event.mission;
  return `${m.winner ? `Mission ${m.number} complete! ${title(m.winner)} wins.` : `Attempt ${moment.event.attempt} resolved.`} ${total(m.pot)} of ${m.threshold} tokens. ${observation.phase === "game_over" ? "Game complete. Everyone’s final results are available." : `${moment.reports ? "Crew claims revealed." : "Pot revealed."} Paused until you continue.`}`;
}
function resolvedObservation(observation, moment) {
  const e = moment.event;
  return {...observation, public:{...observation.public, mission:e.mission, attempt:e.attempt,
    crew:moment.crew, pledges:moment.pledges, votes:moment.votes, chairman:moment.chairman, score:e.score || observation.public.score}};
}
function potMeterHTML(mission, previous = null, animate = false) {
  const sum = total(mission.pot), scale = Math.max(mission.threshold, sum, total(previous));
  return `<div class="pot-meter ${sum >= mission.threshold ? "filled" : ""} ${animate ? "reveal-pot" : ""}" role="progressbar" aria-label="Mission funding" aria-valuemin="0" aria-valuemax="${mission.threshold}" aria-valuenow="${Math.min(sum, mission.threshold)}" aria-valuetext="${sum} of ${mission.threshold} tokens · ${esc(tokenText(mission.pot))}">${colors.map(c=>`<span class="pot-fill ${c}" style="--from-width:${100*(previous?.[c] || 0)/scale}%;--to-width:${100*mission.pot[c]/scale}%"></span>`).join("")}<i class="pot-target" style="left:${100*mission.threshold/scale}%" aria-hidden="true"></i></div>`;
}
function resolutionHTML(observation, moment) {
  const e = moment.event, m = e.mission, sum = total(m.pot), delta = sum - total(moment.previous);
  const held = state.resolutionHold === moment.key, reveal = held && !moment.reports && state.resolutionAnimated !== moment.key;
  const target = observation.public.rules.missions_to_win || 3, score = e.score || observation.public.score;
  const heading = m.winner ? `Mission ${m.number} complete!` : `Attempt ${e.attempt} resolved`;
  const outcome = m.winner ? `${title(m.winner)} wins` : sum >= m.threshold ? "All Green · mission stays open" : `${m.threshold - sum} more to fill the mission`;
  const finished = observation.phase === "game_over";
  const next = finished ? "Final results" : state.mode === "replay" ? "Continue replay" : observation.phase === "audit" ? observation.action_spec?.ability?.id === "auditor" ? "Inspect reports" : "Continue" : moment.reports || e.penalty ? m.winner ? "Next mission" : "Next attempt" : "Crew reports";
  return `<section class="table-center resolution-center ${m.winner ? `mission-complete winner-${m.winner}` : "attempt-complete"} ${reveal ? "resolution-reveal" : ""}" aria-label="Mission ${m.number}, attempt ${e.attempt} result">
    ${m.winner && reveal ? `<div class="celebration" aria-hidden="true">${Array.from({length:18},(_,i)=>`<i style="--i:${i};--x:${(i*37)%100}%;--drift:${(i%2?1:-1)*(25+i*4)}px"></i>`).join("")}</div>` : ""}
    <div class="table-center-top"><span class="eyebrow">Mission ${m.number} · Attempt ${e.attempt}</span><span class="resolution-score"><span class="blue">Blue ${score.blue}</span><span class="red">Red ${score.red}</span><small>First to ${target}</small></span></div>
    <div class="resolution-heading"><span class="resolution-emblem" aria-hidden="true">${m.winner ? "✦" : "◉"}</span><div><h2>${heading}</h2><p class="resolution-outcome">${outcome}${m.winner ? '<span class="mission-point">+1 mission</span>' : ""}</p></div><strong class="resolution-total">${sum}<small>/ ${m.threshold}</small></strong></div>
    ${potMeterHTML(m, moment.previous, reveal)}
    <div class="resolution-pot-details"><div class="pot-legend">${colors.map(c=>`<span class="color-change"><span><i class="token-dot ${c}"></i>${moment.previous[c]} → <b>${m.pot[c]}</b> ${title(c)}</span><small>${signed(m.pot[c] - moment.previous[c])} this attempt</small></span>`).join("")}</div><span>${total(moment.previous)} → ${sum}<b>${signed(delta)} this attempt</b></span></div>
    <div class="resolution-footer"><span>${finished ? "Game complete" : e.penalty ? "No crew · rejection penalty" : moment.reports ? "Crew claims revealed" : "Pot revealed · crew reports next"}${e.reserve_added ? ` · +${e.reserve_added} Green from reserves` : ""}</span>${held ? `<button class="button resolution-next" data-command="resolution-continue">${next} <span aria-hidden="true">→</span></button>` : ""}</div>
  </section>`;
}

function missionHTML(observation) {
  const moment = displayedResolution(observation);
  if (moment) return resolutionHTML(observation, moment);
  const p = observation.public, m = p.mission, sum = total(m.pot), target = p.rules.missions_to_win || 3;
  const phase = {preparation:"Prepare",select_crew:"Choose a crew",pledge:"Pledges",vote:"Voting",contribute:"Contributions",audit:"Inspections",report:"Reports",game_over:"Final result"}[observation.phase];
  const choosing = state.mode === "table" && !state.canAdvance && observation.action_spec?.type === "select_crew";
  const crew = choosing ? state.draft.crew : p.crew;
  const status = m.winner ? `${title(m.winner)} wins this mission` : observation.phase === "vote" ? `${voteTallyText(p.votes)} · ${p.votes.length}/${p.players.length} voted` : p.rejections === 8 ? "No crew · five-Red penalty" : `${crew.length}/${m.crew_size} crew · ${p.rejections}/8 rejected`;
  return `<section class="table-center" aria-label="Current mission and team score"><div class="table-center-top"><span class="eyebrow">Mission ${m.number} · Attempt ${p.attempt}</span><span class="center-score" aria-label="First team to ${target} missions wins">${["blue","red"].map(c => `<span class="${c}" aria-label="${title(c)}: ${p.score[c]} of ${target} missions">${title(c)} <b>${p.score[c]}</b><span class="score-pips ${c}" aria-hidden="true">${Array.from({length:target},(_,i)=>`<i class="${i<p.score[c]?"on":""}"></i>`).join("")}</span></span>`).join("")}</span></div><div class="table-center-main"><div><h2>${phase}</h2><p class="table-phase-status">${esc(status)}</p></div><div class="center-pot"><strong>${sum}<small> / ${m.threshold} funded</small></strong><div class="pot-legend">${colors.map(c=>`<span><i class="token-dot ${c}"></i>${m.pot[c]} <span class="sr-only">${title(c)}</span></span>`).join("")}</div></div></div>${potMeterHTML(m)}<p class="reserve-status"><i class="token-dot green"></i> ${((p.reserve || 0) * 10 + (p.reserve_credit || 0)) / 10} Green in reserve</p>${crew.length ? `<div class="center-roster" aria-label="${choosing ? "Your selected crew" : "Current crew"}"><span>${choosing ? "Your crew" : ["select_crew","pledge","vote"].includes(observation.phase) ? "Proposed crew" : "Mission crew"}</span><strong>${crew.map(pid=>esc(nameOf(pid,observation))).join(" · ")}</strong></div>` : ""}</section>`;
}

function complaintText(claim, speaker, observation = state.observation) {
  return [claim.modifier ? title(claim.modifier) : "", claim.player_id ? (claim.player_id === speaker ? "me" : nameOf(claim.player_id, observation)) : "", claim.color ? title(claim.color) : ""].filter(Boolean).join(" ");
}
function setVoteChoice(approve) {
  const complaint = state.draft.complaints[0];
  if (complaint && (complaint.player_id || complaint.color)) state.draft.savedComplaint = {...complaint};
  state.draft.approve = approve;
  state.draft.complaints = approve ? [] : [{...(complaint || state.draft.savedComplaint || {modifier: "", player_id: "", color: ""})}];
}
function voteTally(votes) {
  return Object.fromEntries([["yes",true],["no",false]].map(([side,approve]) => {
    const ballots = votes.filter(v => v.approve === approve), influence = ballots.reduce((n,v) => n + (v.influence || 0) + (v.bonus || 0),0);
    return [side, {votes:ballots.length + Math.floor(influence / 10), tokens:influence % 10}];
  }));
}
function tallyText(t) {
  return `${t.yes.votes} Yes + ${t.yes.tokens} tokens · ${t.no.votes} No + ${t.no.tokens} tokens`;
}
function voteTallyText(votes) { return tallyText(voteTally(votes)); }
function voteInfluenceText(vote) {
  return `${vote.influence ? ` · ${vote.influence} tokens` : ""}${vote.bonus ? ` · +${vote.bonus} bonus` : ""}`;
}

function influenceSummary() {
  const n = state.draft.influence, p = state.observation.public, bonus = state.observation.action_spec.vote_bonus || 0;
  if (!isQuantity(n) || n > state.observation.action_spec.max_influence) return "Choose an amount within your wallet.";
  const votes = typeof state.draft.approve === "boolean" ? [...p.votes,{approve:state.draft.approve,influence:n,bonus}] : p.votes;
  return `${bonus ? `+${bonus} free influence. ` : ""}${state.observation.action_spec.max_influence - n} tokens left in your wallet. ${voteTallyText(votes)}${typeof state.draft.approve === "boolean" ? " including your vote" : " so far"}.`;
}

function revealedPlayer(observation, pid) {
  if (state.mode !== "replay" || !state.replay?.designer_enabled || state.replay.observation !== observation) return null;
  return state.replay.designer?.players.find(p => p.id === pid) || null;
}

// Resolve knowledge only from the current seat and replay frame; never cache reveals.
function knownTeam(observation, pid) {
  const badge = observation.public.public_badges?.[pid];
  if (badge) return {team: badge, source: "Official badge"};
  if (pid === observation.viewer) return {team: observation.private.team, source: "Your team"};
  const scout = observation.private.receipts?.findLast(r => r.type === "scout" && r.target === pid);
  if (scout) return {team: scout.team, source: "Scouted · Only you know"};
  const revealed = revealedPlayer(observation,pid);
  if (revealed) return {team: revealed.team, source: "Revealed cards"};
  return null;
}

// Personal notes never become game knowledge or leave this browser.
const allegianceNotes = new Map();
function allegianceNotesKey(observation) {
  return `table-allegiance:${JSON.stringify([observation.game_id, observation.viewer])}`;
}
function notesFor(observation) {
  const key = allegianceNotesKey(observation);
  if (!allegianceNotes.has(key)) {
    let saved;
    try { saved = JSON.parse(localStorage.getItem(key)); } catch (_) {}
    allegianceNotes.set(key, Object.fromEntries(Object.entries(saved && typeof saved === "object" ? saved : {})
      .filter(([pid, team]) => observation.public.players.some(p => p.id === pid) && ["blue", "red"].includes(team))));
  }
  return allegianceNotes.get(key);
}
function canMarkPlayer(observation, pid) {
  return state.mode === "table" && observation.public.players.some(p => p.id === pid) && !knownTeam(observation, pid);
}
function playerGuess(observation, pid) {
  return canMarkPlayer(observation, pid) ? notesFor(observation)[pid] || null : null;
}
function setPlayerGuess(observation, pid, team) {
  if (!canMarkPlayer(observation, pid) || !["blue", "red", ""].includes(team)) return false;
  const notes = notesFor(observation);
  if (team) notes[pid] = team;
  else delete notes[pid];
  try { localStorage.setItem(allegianceNotesKey(observation), JSON.stringify(notes)); }
  catch (_) { toast("Browser storage is unavailable. Your marks will last until you close or refresh this tab.", true); }
  return true;
}
function playerAvatarHTML(observation, player) {
  const known = knownTeam(observation, player.id), guess = playerGuess(observation, player.id);
  const icon = `<span class="avatar ${known?.team || ""} ${guess ? `guess-${guess}` : ""}" aria-hidden="true">${esc(player.name.slice(0,1))}</span>`;
  if (canMarkPlayer(observation, player.id)) {
    const label = `${player.name}: ${guess ? `your guess is ${title(guess)}` : "allegiance unmarked"}. Mark allegiance privately`;
    return `<button class="player-avatar allegiance-toggle" data-command="mark-player" data-id="${player.id}" aria-haspopup="dialog" aria-label="${esc(label)}" title="${esc(label)}">${icon}<span class="player-guess-badge ${guess || ""}" aria-hidden="true">?</span></button>`;
  }
  return `<span class="player-avatar">${icon}${known ? `<span class="player-team-badge ${known.team}" title="${esc(title(known.team)+" · "+known.source)}" aria-label="${esc(title(known.team)+" · "+known.source)}">${title(known.team).slice(0,1)}</span>` : ""}</span>`;
}
function openAllegiancePicker(pid) {
  const observation = state.observation;
  if (!canMarkPlayer(observation, pid)) return;
  pauseForReading();
  const dialog = $("#allegiance-dialog"), guess = playerGuess(observation, pid);
  dialog.dataset.player = pid;
  dialog.dataset.notesKey = allegianceNotesKey(observation);
  dialog.innerHTML = `<div class="dialog-top"><span class="eyebrow">YOUR PRIVATE GUESS</span><button class="icon-button" data-command="close-allegiance" aria-label="Close allegiance marker">×</button></div>
    <h2 id="allegiance-title">${esc(nameOf(pid, observation))}</h2>
    <p id="allegiance-description" class="caption">Which team do you think they're on? Only you see these marks, saved in this browser for this seat and game.</p>
    <div class="allegiance-choices" role="group" aria-label="Allegiance guess">${["blue", "red", ""].map(team => `<button class="button allegiance-choice ${team}" data-command="set-allegiance" data-value="${team}" aria-pressed="${(guess || "") === team}">${team ? `${title(team)} ?` : "Clear mark"}</button>`).join("")}</div>`;
  dialog.showModal();
  $('[aria-pressed="true"]', dialog)?.focus();
}
function closeAllegiancePicker() {
  const dialog = $("#allegiance-dialog"), pid = dialog.dataset.player;
  dialog.close();
  if (dialog.dataset.notesKey === allegianceNotesKey(state.observation)) {
    ($(`[data-command="mark-player"][data-id="${pid}"]`) || $(`.player-card-link[data-id="${pid}"]`))?.focus({preventScroll:true});
  }
}

function playerSignal(observation, pid) {
  const moment = displayedResolution(observation);
  if (moment) {
    if (!moment.crew.includes(pid) || (observation.phase === "game_over" && !moment.reports)) return null;
    const claims = moment.reports?.[pid];
    return {kind:moment.reports ? "Report · claim" : "Report pending", context:"",
      text:claims?.length ? claims.map(c => `${c.player_id === pid ? "I" : nameOf(c.player_id, observation)} ${c.verb} ${c.quantity} ${title(c.color)}`).join("; ") : moment.reports ? "No statement" : ""};
  }
  const entries = contextualEvents(observation);
  const proposal = entries.at(-1)?.proposal;
  for (const entry of entries.reverse()) {
    const e = entry.event;
    const context = entry.attempt !== observation.public.attempt ? `Attempt ${entry.attempt}` : entry.proposal !== proposal ? `Proposal ${entry.proposal}` : "";
    if (e.type === "reports_revealed" && e.reports[pid]?.length) return {kind:"Report · claim", context,
      text:e.reports[pid].map(c => `${nameOf(c.player_id, observation)} ${c.verb} ${c.quantity} ${title(c.color)}`).join("; ")};
    if (e.type === "vote" && e.player_id === pid) return {kind:`Voted ${e.approve ? "Yes" : "No"}${voteInfluenceText(e)}`, context,
      text:e.complaints?.length ? e.complaints.map(c => complaintText(c, pid, observation)).join("; ") : "", no:!e.approve};
    if (e.type === "crew_selected" && e.chairman === pid) return {kind:"Proposed crew",context,text:e.crew.map(p=>nameOf(p,observation)).join(", ")};
  }
  const vote = observation.public.votes.find(v => v.player_id === pid);
  return vote ? {kind:`Voted ${vote.approve ? "Yes" : "No"}${voteInfluenceText(vote)}`, context:"", no:!vote.approve,
    text:(vote.complaints || []).map(c => complaintText(c,pid,observation)).join("; ")} : null;
}

function pledgeTrayHTML(observation, pid) {
  const pledge = observation.public.pledges[pid];
  const revealed = pledge !== undefined;
  const label = `${nameOf(pid,observation)} · ${revealed ? `Pledged ${pledge} tokens` : "Pledge not revealed"}`;
  return `<div class="pledge-tray ${revealed ? "revealed" : "unrevealed"}" role="group" aria-label="${esc(label)}" data-pledge-player="${pid}"><span aria-hidden="true">Pledge</span><strong aria-hidden="true">${revealed ? pledge : "—"}</strong></div>`;
}

function resolvedVoteHTML(vote, observation) {
  if (!vote) return "";
  const complaint = (vote.complaints || []).map(c => complaintText(c, vote.player_id, observation)).join("; ");
  return `<span class="player-signal result-vote ${vote.approve ? "" : "player-complaint"}"><span class="signal-label">Voted ${vote.approve ? "Yes" : "No"}${voteInfluenceText(vote)}</span>${complaint ? `<span class="signal-text">${esc(complaint)}</span>` : ""}</span>`;
}

function playersHTML(observation) {
  const knowledge = observation, moment = displayedResolution(observation);
  if (moment) observation = resolvedObservation(observation, moment);
  const p = observation.public, selecting = !moment && state.mode === "table" && !state.canAdvance && observation.action_spec?.type === "select_crew";
  const selected = selecting ? state.draft.crew : p.crew;
  const showPledges = !moment && ["pledge", "vote", "contribute"].includes(observation.phase);
  const nextVoter = observation.phase === "vote" ? p.players[(p.players.findIndex(x => x.id === p.chairman) + p.votes.length) % p.players.length].id : null;
  const viewerIndex = p.players.findIndex(player => player.id === observation.viewer);
  return `<section class="players-section" aria-label="Players around the table"><div class="player-grid tabletop ${showPledges ? "show-pledges" : ""} ${moment ? "resolving-table" : ""}">${missionHTML(observation)}${p.players.map((player,index) => {
    const chosen = selected.includes(player.id), mine = player.id === observation.viewer, chairman = player.id === p.chairman;
    const known = knownTeam(knowledge,player.id), guess = playerGuess(knowledge,player.id), signal = playerSignal(observation,player.id);
    const revealed = revealedPlayer(knowledge,player.id);
    const result = p.result?.players?.[player.id];
    const resultVote = moment ? resolvedVoteHTML(moment.votes.find(v => v.player_id === player.id), observation) : "";
    const slot = (index - viewerIndex + 5 + p.players.length) % p.players.length;
    const active = !moment && (player.id === nextVoter || (observation.phase === "select_crew" && chairman));
    const full = selecting && !chosen && selected.length >= observation.action_spec.crew_size;
    return `<div class="table-seat ${slot<4 ? "seat-top" : "seat-bottom"} ${chosen ? "crew-seat" : ""}" style="--seat-column:${slot<4?slot+1:8-slot};--seat-row:${slot<4?1:3}"><article class="player-card ${chosen ? "selected" : ""} ${active ? "current" : ""} ${known ? `known-${known.team}` : ""} ${mine ? "own-seat" : ""}" data-player="${player.id}"><div class="player-main"><button class="player-card-link" data-command="${revealed ? "inspect-player" : "player-history"}" data-id="${player.id}" ${revealed ? `aria-current="${mine}"` : `aria-expanded="${state.playerHistory === player.id}"`} aria-label="${esc(player.name)}${chairman ? ", chairman" : ""}${chosen ? ", on crew" : ""}${known ? `, ${esc(title(known.team)+" · "+known.source)}` : ""}${mine ? `, ${observation.private.wallet} tokens` : ", wallet hidden"}. ${revealed ? "View this player’s perspective and player rankings" : "Show action history"}"></button>
      <span class="player-identity">${playerAvatarHTML(knowledge,player)}<span class="player-heading"><span class="player-name">${esc(player.name)}${mine ? state.mode === "replay" ? " · Viewing" : " · You" : ""}</span><span class="player-role">${chairman ? "♜ Chairman" : ""}</span></span>${mine ? `<span class="seat-wallet" title="Your private wallet">${observation.private.wallet} ◉</span>` : '<span class="seat-wallet hidden-wallet" title="Private wallet" aria-label="Wallet hidden">?</span>'}</span>
      <span class="seat-affiliation">${chosen ? '<span class="crew-label">✓ Crew</span>' : ""}${known ? `<span class="seat-team ${known.team}">${title(known.team)}<small>${known.source.startsWith("Scouted") ? "Scouted" : known.source === "Official badge" ? "Public" : known.source === "Revealed cards" ? "Revealed" : "Your team"}</small></span>` : guess ? `<span class="seat-guess ${guess}">${title(guess)} ? <small>Your guess</small></span>` : ""}</span>
      ${result ? `<span class="personal-outcome ${result.won ? "won" : "lost"}">${result.won ? "✦ Won" : "Did not win"}</span>` : ""}
      ${revealed ? `<span class="revealed-player-cards"><span><small>Objective</small><b>${esc(title(revealed.objective))}</b></span><span><small>Ability</small><b>${esc(title(revealed.ability))}${revealed.ability_used ? ' <small>(used)</small>' : ""}</b></span></span>` : ""}
      ${active ? '<b class="up-next">Up next</b>' : ""}
      ${resultVote}
      ${signal ? `<span class="player-signal ${signal.no ? "player-complaint" : ""}"><span class="signal-label">${signal.kind}${signal.context ? ` · ${signal.context}` : ""}</span>${signal.text ? `<span class="signal-text">${esc(signal.text)}</span>` : ""}</span>` : resultVote ? "" : '<span class="player-signal quiet" aria-label="No public actions yet">—</span>'}
      ${revealed ? `<span class="perspective-hint">${mine ? "Viewing this player" : "View perspective →"}</span>` : ""}
    </div>${revealed ? `<button class="text-button player-history-link" data-command="player-history" data-id="${player.id}" aria-label="${esc(player.name)} action history" aria-expanded="${state.playerHistory === player.id}">History</button>` : ""}${selecting ? `<button class="crew-pick button small" data-command="select-player" data-id="${player.id}" aria-pressed="${chosen}" ${full || state.busy ? "disabled" : ""} ${full ? 'title="Crew full"' : ""}>${chosen ? "Remove from crew" : "Add to crew"}</button>` : ""}</article><div class="pledge-position">${chosen && showPledges ? pledgeTrayHTML(observation,player.id) : ""}</div></div>`;
  }).join("")}</div>${playerHistoryHTML(observation,state.playerHistory)}</section>`;
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
    green_machine: `${own} wins; 20+ Green added across the table, from any source.`,
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
    green_thumb: "Automatically adds 5 free influence to every vote.",
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
function objectiveTrackerHTML(objective) {
  const p = objective.progress;
  if (!["opposition_patron", "green_machine"].includes(objective.id) || !Number.isFinite(p?.value) || !(p.target > 0)) return "";
  const met = p.value >= p.target;
  return `<span class="objective-tracker ${met ? "complete" : ""}"><span class="tracker-heading"><span>${esc(p.label)}</span><b>${p.value} / ${p.target}</b></span><progress max="${p.target}" value="${Math.min(p.value, p.target)}" aria-label="${esc(p.label)}: ${p.value} of ${p.target}"></progress><span class="caption">${met ? "Token goal met · team victory also required" : "Table-wide total · updated after each attempt"}</span></span>`;
}
function privateHTML(observation) {
  const {objective, ability, team, result} = observation.private;
  const progress = objective.progress;
  const availability = ability.uses_remaining != null ? `<span class="card-availability" aria-label="Once per game · ${ability.uses_remaining ? "Available" : "Used"}">${ability.uses_remaining ? "Available" : "Used"}</span>` : ["echo", "standard_bearer", "green_thumb"].includes(ability.id) ? '<span class="card-availability">Automatic</span>' : "";
  return `<section class="panel private-panel" id="your-cards" tabindex="-1" aria-label="Your private cards">
    <div class="row spread private-heading"><span class="eyebrow">▧ ${state.mode === "replay" ? `${esc(nameOf(observation.viewer))}'S PERSPECTIVE` : "YOUR PRIVATE CARDS"}</span><span class="pill ${team}">${title(team)} team</span></div>
    <details class="card-explanation" ${privateDetailAttributes(observation, `objective:${objective.id}`)}>
      <summary><strong>${esc(objective.name || title(objective.id))}</strong><span class="card-synopsis">${esc(objectiveSummary(observation))}</span>${objectiveTrackerHTML(objective)}</summary>
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
function abilityControls(spec, standalone = false) {
  if (!spec) return "";
  const d = state.draft.ability;
  const once = ["scout", "switcher", "thief"].includes(spec.id);
  const frequency = once ? '<span class="ability-frequency">Once per game</span>' : "";
  const person = pid => `${esc(nameOf(pid))}${pid === state.observation.viewer ? " (you)" : ""}`;
  let fields = "";
  if (["scout", "switcher", "auditor"].includes(spec.id)) {
    const [label, skip] = {scout:["Learn the team of", "Don’t scout"], switcher:["Swap objectives with", "Keep my objective"], auditor:["Inspect", "Don’t inspect"]}[spec.id];
    fields = `<label>${label}<select data-ability="target"><option value="" ${!d.target ? "selected" : ""}>${skip}</option>${spec.targets.map(pid => {
      const known = spec.id === "scout" && knownTeam(state.observation,pid);
      return `<option value="${pid}" ${pid === d.target ? "selected" : ""}>${person(pid)}${known ? ` · ${title(known.team)} already known` : ""}</option>`;
    }).join("")}</select></label>`;
  }
  if (spec.id === "stowaway") fields = `<label>Off-crew contribution<select data-ability="color"><option value="" ${!d.color ? "selected" : ""}>Don’t contribute</option>${colors.map(c => `<option value="${c}" ${c === d.color ? "selected" : ""}>1 ${title(c)} token</option>`).join("")}</select></label>`;
  if (spec.id === "recolorer") fields = `<label>Change one token<select data-ability="recolor"><option value="" ${!d.from ? "selected" : ""}>Don’t recolor</option>${colors.flatMap(from => colors.filter(to => to !== from).map(to => `<option value="${from}:${to}" ${from === d.from && to === d.to ? "selected" : ""}>${title(from)} → ${title(to)}</option>`)).join("")}</select></label>`;
  if (spec.id === "thief") {
    fields = `<label>Take from<select data-ability="steal"><option value="" ${!d.source ? "selected" : ""}>Don’t steal</option><option value="mission" ${d.source === "mission" ? "selected" : ""}>Mission tokens</option><optgroup label="Player wallet">${spec.targets.map(pid => `<option value="wallet:${pid}" ${d.source === "wallet" && d.target === pid ? "selected" : ""}>${person(pid)}</option>`).join("")}</optgroup></select></label>`;
    if (d.source === "wallet") fields += `<label>Tokens to request<input type="number" inputmode="numeric" min="1" max="${spec.max_total}" step="1" data-ability="amount" value="${esc(d.amount)}"></label>`;
    if (d.source === "mission") fields += `<div class="ability-token-grid">${colors.map(c => `<label><span><i class="token-dot ${c}" aria-hidden="true"></i>${title(c)}</span><input type="number" inputmode="numeric" min="0" max="${spec.max_total}" step="1" data-ability-token="${c}" aria-label="${title(c)} tokens to steal" value="${esc(d.tokens[c])}"></label>`).join("")}</div>`;
  }
  const feedback = abilityFeedback();
  fields += `<p class="caption ability-feedback" id="ability-feedback" aria-live="polite" ${feedback ? "" : "hidden"}>${esc(feedback)}</p>`;
  return standalone ? `<div class="ability-controls standalone" role="group" aria-label="${title(spec.id)}">${frequency}${fields}</div>` : `<fieldset class="ability-controls"><legend>${title(spec.id)}</legend>${frequency}${fields}</fieldset>`;
}
function abilityChoice() {
  const spec = state.observation.action_spec?.ability, d = state.draft.ability;
  if (!spec || !d) return null;
  if (["scout", "switcher", "auditor"].includes(spec.id)) return d.target ? {target:d.target} : null;
  if (spec.id === "stowaway") return d.color ? {color:d.color} : null;
  if (spec.id === "recolorer") return d.from || d.to ? {from:d.from, to:d.to} : null;
  if (spec.id === "thief") return !d.source ? null : d.source === "wallet" ? {source:"wallet", target:d.target, amount:d.amount} : {source:d.source, tokens:d.tokens};
  return null;
}
function legalAbility() {
  const spec = state.observation.action_spec?.ability, choice = abilityChoice();
  if (!choice) return true;
  if (["scout", "switcher", "auditor"].includes(spec.id)) return spec.targets.includes(choice.target);
  if (spec.id === "stowaway") return colors.includes(choice.color) && state.observation.private.wallet >= 1;
  if (spec.id === "recolorer") return colors.includes(choice.from) && colors.includes(choice.to) && choice.from !== choice.to;
  if (choice.source === "wallet") return spec.targets.includes(choice.target) && isQuantity(choice.amount) && choice.amount >= 1 && choice.amount <= spec.max_total;
  return choice.source === "mission" && colors.every(c => isQuantity(choice.tokens[c])) && total(choice.tokens) >= 1 && total(choice.tokens) <= spec.max_total;
}
function abilityFeedback() {
  const spec = state.observation.action_spec?.ability, choice = abilityChoice();
  if (!choice) return "";
  if (spec.id === "stowaway") return state.observation.private.wallet >= 1 ? `Costs 1 token · ${state.observation.private.wallet - 1} left in your wallet.` : "You need 1 token in your wallet to contribute.";
  if (spec.id === "thief") {
    const n = choice.source === "mission" ? total(choice.tokens) : choice.amount;
    if (!isQuantity(n) || n < 1) return `Choose 1–${spec.max_total} tokens.`;
    if (n > spec.max_total) return `${n} requested · maximum ${spec.max_total} total.`;
    return `Requesting ${n} of up to ${spec.max_total} tokens. Uses your one steal, even if the source is empty.`;
  }
  return "";
}
function abilitySubmitLabel(spec) {
  const id = spec.ability.id, choice = abilityChoice();
  if (spec.type === "contribute" && spec.on_crew !== false) return choice ? `Seal contribution + ${id === "thief" ? "steal" : "recolor"}` : "Seal my contribution";
  if (!choice) return {scout:"Keep Scout for later", switcher:"Keep my objective", auditor:"Skip inspection", stowaway:"Skip contribution", recolorer:"Skip recoloring", thief:"Keep my steal"}[id];
  if (["scout", "switcher", "auditor"].includes(id)) return `${{scout:"Scout", switcher:"Swap with", auditor:"Inspect"}[id]} ${nameOf(choice.target)}`;
  if (id === "stowaway") return `Contribute 1 ${title(choice.color)}`;
  if (id === "recolorer") return `Change ${title(choice.from)} → ${title(choice.to)}`;
  const n = choice.source === "mission" ? total(choice.tokens) : choice.amount;
  return isQuantity(n) && n > 0 ? `Request ${n} token${n === 1 ? "" : "s"}` : "Choose tokens to steal";
}
function echoPreview() {
  const paid = state.draft.tokens;
  return state.observation.private.ability.id === "echo" && legalDraft() && total(paid) >= 2 && colors.filter(c => paid[c] > 0).length === 1
    ? `Echo adds +1 ${title(colors.find(c => paid[c] > 0))} automatically.` : "";
}

function rowBuilder(kind) {
  const reports = kind === "statements", list = state.draft[kind];
  return `<div class="builder-rows">${list.map((claim, index) => `<div class="claim-row ${reports ? "" : "complaint-row"}" data-kind="${kind}" data-index="${index}">
    ${reports ? `<label>Player<select data-field="player_id" aria-label="Report ${index + 1} player">${personOptions(claim.player_id)}</select></label><label>Claim<select data-field="verb" aria-label="Report ${index + 1} action"><option value="gave" ${claim.verb === "gave" ? "selected" : ""}>gave</option><option value="took" ${claim.verb === "took" ? "selected" : ""}>took</option></select></label><label>Quantity<input type="number" data-field="quantity" aria-label="Report ${index + 1} quantity" min="0" max="2147483647" step="1" value="${esc(claim.quantity)}" required></label>` : `<label>Modifier<select data-field="modifier" aria-label="Complaint ${index + 1} modifier">${[["", "No modifier"], ["more", "More"], ["less", "Less"], ["exact", "Exact"]].map(([v, label]) => `<option value="${v}" ${v === (claim.modifier || "") ? "selected" : ""}>${label}</option>`).join("")}</select></label><label>Player<select data-field="player_id" aria-label="Complaint ${index + 1} player">${personOptions(claim.player_id, true)}</select></label>`}
    <label>Color<select data-field="color" aria-label="${reports ? "Report" : "Complaint"} ${index + 1} color">${colorOptions(claim.color, !reports)}</select></label>${reports ? `<button type="button" class="remove-row" data-command="remove-row" data-kind="${kind}" data-index="${index}" aria-label="Remove ${reports ? "report" : "complaint"} ${index + 1}">Remove ×</button>` : ""}</div>`).join("")}</div>
    ${reports ? `<button type="button" class="text-button" data-command="add-row" data-kind="${kind}" ${list.length >= 3 ? "disabled" : ""}>+ Add a statement</button>` : ""}`;
}

function finalResultsHTML(observation) {
  if (observation.phase !== "game_over") return "";
  const p = observation.public, result = p.result, mine = observation.private.result;
  return `<section class="panel action-panel final-results" id="final-results" tabindex="-1" aria-label="Final results"><span class="eyebrow">FINAL RESULTS</span><h2>${result.winner ? `${title(result.winner)} wins the game.` : "This game is unresolved."}</h2><p class="action-intro">${result.winner ? esc(mine.text || (mine.won ? "You won." : "You did not win this game.")) : "The development attempt limit was reached. No team or player is awarded a win."}</p>
    <ul class="final-result-list" aria-label="Every player’s result">${p.players.map(player => {
      const won = result.players[player.id].won;
      return `<li><span>${esc(player.name)}${player.id === observation.viewer ? state.mode === "replay" ? " · Viewing" : " · You" : ""}</span><strong class="personal-outcome ${won ? "won" : "lost"}">${won ? "✦ Won" : "Did not win"}</strong></li>`;
    }).join("")}</ul>
    ${state.mode === "table" ? `<button class="button primary full" data-command="open-replay" data-id="${esc(state.game.id)}">Review this game →</button><button class="text-button" data-command="new-game" style="margin-top:15px">Take a new seat</button>` : ""}</section>`;
}

function actionHTML(observation) {
  if (observation.phase === "game_over") return finalResultsHTML(observation);
  if (state.resolutionHold) return "";
  const spec = observation.action_spec, p = observation.public;
  if (!spec || (state.mode === "table" && state.canAdvance)) return "";
  const copy = {
    prepare: ["Private preparation.", "Use your ability or pass.", "Seal my choice"],
    audit: ["Inspect a report.", "Check a crew member’s actual deposit, or skip.", "Confirm choice"],
    select_crew: ["Choose your crew.", `Choose ${spec.crew_size} players at the table.`, "Propose this crew"],
    pledge: ["Make your pledge.", `Promise a quantity. No tokens are spent yet.${p.rules.proposal_income ? " Proposal income is already in your wallet." : ""}`, "Seal my pledge"],
    vote: [`Does ${esc(nameOf(p.chairman, observation))}’s crew have your vote?`, "", "Cast my vote"],
    contribute: ["What will you really give?", "Spend tokens from your wallet. Your deposit is secret.", "Seal my contribution"],
    report: ["Tell the table.", "Make 1–3 claims. Reports are revealed together.", "Seal my report"],
  }[spec.type];
  const standaloneAbility = spec.ability && (["prepare", "audit"].includes(spec.type) || (spec.type === "contribute" && spec.on_crew === false));
  if (standaloneAbility) {
    copy[0] = title(spec.ability.id);
    copy[1] = "";
  }
  if (spec.ability) copy[2] = abilitySubmitLabel(spec);
  let controls = "";
  if (spec.type === "select_crew") controls = `<div class="crew-selection-list">${state.draft.crew.map(pid => `<span>${esc(nameOf(pid))}</span>`).join("")}${Array.from({length: Math.max(0, spec.crew_size - state.draft.crew.length)}, () => '<span class="empty-seat">Open seat</span>').join("")}</div><p class="caption" id="crew-count">${state.draft.crew.length} of ${spec.crew_size} selected.</p>`;
  if (["pledge", "contribute"].includes(spec.type) && spec.on_crew !== false) controls = `<div class="token-controls">${(spec.type === "pledge" ? ["blue"] : colors).map(c => `<div class="token-control"><i class="token-dot ${c}"></i><label for="token-${c}">${spec.type === "pledge" ? "Tokens" : title(c)}</label><button type="button" class="stepper" data-command="token" data-color="${c}" data-delta="-1" aria-label="Remove one ${c} token">−</button><input id="token-${c}" type="number" inputmode="numeric" min="0" max="${spec.max_total}" step="1" value="${esc(state.draft.tokens[c])}" data-token="${c}" required><button type="button" class="stepper" data-command="token" data-color="${c}" data-delta="1" aria-label="Add one ${c} token">+</button></div>`).join("")}</div><div class="budget-row" id="budget-row"><span>Your wallet</span><strong id="budget-value"></strong></div>${spec.type === "contribute" && p.pledges[observation.viewer] ? `<button type="button" class="text-button" data-command="copy-pledge">Use my pledge (${esc(tokenText(p.pledges[observation.viewer]))})</button>` : '<p class="caption">Zero is allowed. No tokens are reserved by a pledge.</p>'}`;
  if (spec.type === "vote") controls = `<div class="vote-options">${[["yes", "Yes ✓", "Approve this crew"], ["no", "No ×", "Reject this crew"]].map(([value, label, hint]) => `<button type="button" class="vote-choice ${(value === "yes") === state.draft.approve ? "chosen" : ""}" data-command="vote-choice" data-value="${value}" aria-pressed="${(value === "yes") === state.draft.approve}">${label}<small>${hint}</small></button>`).join("")}</div><label class="influence-control">Tokens to spend<input id="vote-influence" type="number" min="0" max="${spec.max_influence}" step="1" inputmode="numeric" value="${esc(state.draft.influence)}" required></label><p class="caption" id="vote-influence-summary">${esc(influenceSummary())}</p>${state.draft.approve === false ? `<section class="builder" aria-label="Required complaint"><h3>Why are you voting No?</h3><p class="caption">Choose a player, a color, or both.</p>${rowBuilder("complaints")}</section>` : ""}`;
  if (spec.type === "report") controls = `<p class="report-help">Reports are player claims and may be false. “Gave” describes an original paid deposit; “took” describes a removal from the mission.</p>${ownReports(observation).length ? '<button type="button" class="text-button" data-command="own-report">Use my actual contribution</button>' : ""}${rowBuilder("statements")}`;
  if (spec.type === "contribute" && spec.on_crew !== false && observation.private.ability.id === "echo") controls += `<p class="caption ability-feedback" id="echo-bonus-preview" aria-live="polite" ${echoPreview() ? "" : "hidden"}>${esc(echoPreview())}</p>`;
  controls += abilityControls(spec.ability, standaloneAbility);
  return `<section class="panel action-panel" id="action-panel" aria-labelledby="action-title"><span class="eyebrow">YOUR TURN · ${esc(nameOf(observation.viewer))}</span><h2 id="action-title">${copy[0]}</h2>${copy[1] ? `<p class="action-intro">${copy[1]}</p>` : ""}<form id="decision-form">${controls}<div id="action-error" class="form-error" role="alert" ${state.error ? "" : "hidden"}>${esc(state.error)}</div><div class="decision-footer"><button id="submit-action" type="submit" class="button primary full" ${state.busy || !legalDraft() ? "disabled" : ""}>${esc(copy[2])} <span aria-hidden="true">→</span></button></div></form></section>`;
}

function eventHTML(event) {
  const pName = pid => esc(nameOf(pid));
  let tag = "TABLE", cls = "", content = "";
  switch (event.type) {
    case "game_started": case "income": case "proposal_income": return "";
    case "mission_drawn": tag = "MISSION"; content = `<b>Mission ${event.mission.number} begins.</b> Target ${event.mission.threshold} tokens · Crew of ${event.mission.crew_size}.`; break;
    case "crew_selected": tag = "CREW"; content = `<b>${pName(event.chairman)}</b> proposed ${event.crew.map(pName).join(", ")}.`; break;
    case "pledges_revealed": tag = "PROMISE"; cls = "claim"; content = `<div class="event-lines">${Object.entries(event.pledges).map(([pid, vector]) => `<span><b>${pName(pid)}</b> ${tokenMini(vector)}</span>`).join("")}</div>`; break;
    case "vote": tag = "VOTE"; content = `<b>${pName(event.player_id)}</b> voted <span class="${event.approve ? "vote-yes" : "vote-no"}">${event.approve ? "Yes" : "No"}</span>${event.influence ? `, spending ${event.influence} tokens` : ""}${event.bonus ? ` (+${event.bonus} bonus influence)` : ""}.${event.complaints.length ? `<p class="caption">Player complaints: ${event.complaints.map(c => esc(complaintText(c, event.player_id))).join("; ")}</p>` : ""}`; break;
    case "proposal_approved": tag = "VOTE"; content = `<b>Crew approved.</b> ${event.tally ? tallyText(event.tally) : `${event.yes_votes} Yes votes`}. Contributions are now sealed.`; break;
    case "proposal_rejected": tag = "VOTE"; content = `<b>Proposal rejected.</b> ${event.rejections} of 8 rejections.${event.tally ? ` ${tallyText(event.tally)}.` : ""}`; break;
    case "attempt_resolved": tag = "RESULT"; cls = "result"; content = attemptResultHTML(event); break;
    case "reports_revealed": tag = "CLAIM"; cls = "claim"; content = Object.entries(event.reports).filter(([, claims]) => claims.length).map(([speaker, claims]) => `<p><b>${pName(speaker)} says:</b> ${claims.map(c => `“${pName(c.player_id)} ${c.verb} ${c.quantity} ${title(c.color)}”`).join("; ")}</p>`).join("") || "Everyone passed on reporting."; break;
    case "game_over": tag = "FINAL"; cls = "result"; content = `<b>${event.winner ? `${title(event.winner)} wins the game.` : "The game is unresolved."}</b>`; break;
    default: content = esc(title(event.type));
  }
  return `<div class="event ${cls}"${event.type === "attempt_resolved" ? ` id="attempt-result-${event.attempt}" tabindex="-1"` : ""}><span class="event-tag">${tag}</span><div>${content}</div></div>`;
}

function visibleHistoryEntries(observation) {
  return contextualEvents(observation).filter(({event}) => !["game_started", "income", "proposal_income"].includes(event.type));
}

function matchesHistoryFilter(event) {
  if (state.historyFilter === "results") return ["attempt_resolved", "game_over", "mission_drawn"].includes(event.type);
  if (state.historyFilter === "votes") return ["crew_selected", "vote", "proposal_approved", "proposal_rejected"].includes(event.type);
  if (state.historyFilter === "claims") return ["reports_revealed", "pledges_revealed"].includes(event.type) || (event.type === "vote" && event.complaints?.length > 0);
  return true;
}

function historyHTML(observation) {
  const groups = new Map();
  for (const entry of visibleHistoryEntries(observation)) {
    const {event} = entry;
    if (!groups.has(event.attempt)) groups.set(event.attempt, []);
    groups.get(event.attempt).push(entry);
  }
  const latest = Math.max(...[...groups].filter(([, entries]) => entries.some(({event}) => matchesHistoryFilter(event))).map(([attempt]) => attempt));
  return `<section class="panel history-panel" id="table-history" tabindex="-1" aria-labelledby="history-title"><div class="section-head"><div><span class="eyebrow">THE PUBLIC RECORD</span><h2 id="history-title">What happened</h2></div><div class="history-toolbar"><label class="sr-only" for="history-filter">Filter history</label><select id="history-filter">${[["all", "All events"], ["results", "Official results"], ["votes", "Votes & crews"], ["claims", "Player claims"]].map(([value, label]) => `<option value="${value}" ${state.historyFilter === value ? "selected" : ""}>${label}</option>`).join("")}</select></div></div><div class="history-guide"><p class="caption">Newest attempts first · Events in play order</p><div class="row"><button class="text-button" data-command="history-expand">Expand all</button><button class="text-button" data-command="history-collapse">Collapse all</button></div></div>
    ${[...groups.entries()].reverse().map(([attempt, entries]) => {
      const events = entries.filter(({event}) => matchesHistoryFilter(event));
      if (!events.length) return "";
      const result = entries.find(({event}) => event.type === "attempt_resolved")?.event;
      const summary = result ? attemptOutcome(result) : entries.some(({event}) => event.type === "game_over") ? "Game ended" : "In progress";
      const open = state.historyOpen[attempt] ?? attempt === latest;
      return `<details class="history-group" id="history-attempt-${attempt}" tabindex="-1" data-attempt="${attempt}" ${open ? "open" : ""}><summary><span>${attemptLabel(entries[0].mission,attempt)}</span><span class="caption">${summary} · ${events.length} ${events.length === 1 ? "event" : "events"}</span></summary><div class="history-events">${events.map(entry => `${entry.event.type === "crew_selected" ? `<p class="proposal-divider">Proposal ${entry.proposal} · ${esc(nameOf(entry.chairman, observation))} is chairman</p>` : ""}${eventHTML(entry.event)}`).join("")}</div></details>`;
    }).join("") || '<p class="empty-history">No events in this view yet.</p>'}</section>`;
}

function replayStripHTML(replay) {
  const item = replay.timeline[replay.step];
  return `${replay.designer_enabled ? '<div class="designer-banner"><b>All cards revealed.</b> Click a player to view their perspective and recorded player rankings at this moment.</div>' : ""}<section class="replay-strip" aria-label="Replay controls">
    <div class="replay-controls"><button data-command="replay-first" aria-label="Go to start" ${replay.step === 0 ? "disabled" : ""}>|‹</button><button data-command="replay-back" aria-label="Previous step" ${replay.step === 0 ? "disabled" : ""}>‹</button><button class="play-button" data-command="replay-play" aria-label="${state.playing ? "Pause replay" : "Play replay"}" ${replay.step === replay.total_steps - 1 && !state.playing ? "disabled" : ""}>${state.playing ? "Ⅱ" : "▶"}</button><button data-command="replay-next" aria-label="Next step" ${replay.step === replay.total_steps - 1 ? "disabled" : ""}>›</button><button data-command="replay-last" aria-label="Go to latest step" ${replay.step === replay.total_steps - 1 ? "disabled" : ""}>›|</button></div>
    <div class="scrubber"><div class="scrubber-top"><b>${esc(item.label.replace(" · income paid", ""))}</b><span>${replay.step + 1} / ${replay.total_steps}</span></div><input id="replay-scrubber" type="range" min="0" max="${replay.total_steps - 1}" value="${replay.step}" aria-label="Replay position"></div>
    <div class="replay-perspective">${replay.can_inspect ? `<label>View as <select id="replay-seat">${personOptions(replay.viewing_seat)}</select></label><label class="designer-toggle"><input id="designer-toggle" type="checkbox" ${replay.designer_enabled ? "checked" : ""}>Reveal all</label>` : `<span class="caption">Viewing ${esc(nameOf(replay.viewing_seat))}</span>`}</div></section>`;
}

function replaySidebarHTML(replay) {
  const observation = replay.observation, mine = observation.private.last_contribution;
  const ownAction = observation.private.submissions.at(-1)?.action;
  let decision = ownAction?.quantity !== undefined ? `${ownAction.quantity} tokens` : ownAction?.tokens ? tokenText(ownAction.tokens) : ownAction?.approve !== undefined ? (ownAction.approve ? "Yes" : "No") : ownAction?.statements ? ownAction.statements.map(c => `${nameOf(c.player_id)} ${c.verb} ${c.quantity} ${title(c.color)}`).join("; ") || "Passed" : ownAction?.crew?.map(pid => nameOf(pid)).join(", ");
  if (ownAction && "ability" in ownAction) {
    const a = ownAction.ability;
    const choice = !a ? "Ability passed" : a.source === "wallet" ? `Requested ${a.amount} from ${nameOf(a.target)}’s wallet` : a.source === "mission" ? `Requested ${tokenText(a.tokens)} from the mission` : a.from ? `Change 1 ${title(a.from)} to ${title(a.to)}` : a.color ? `Off-crew deposit: 1 ${title(a.color)}` : `Targeted ${nameOf(a.target)}`;
    decision = [decision, choice].filter(Boolean).join(" · ");
  }
  return `${finalResultsHTML(observation)}${privateHTML(observation)}<section class="panel replay-index"><span class="eyebrow">VERIFIED REPLAY · READ ONLY</span><h3 style="margin-top:9px">Follow the decisions</h3><p class="caption">${replay.designer_enabled ? "Includes each hidden action." : "Only changes visible to this seat appear here."}</p><div class="replay-step-list" aria-label="Replay timeline">${replay.timeline.map((item, i) => `${i === 0 || replay.timeline[i - 1].attempt !== item.attempt ? `<span class="eyebrow" style="padding:12px 10px 4px">${attemptLabel(item.mission,item.attempt)}</span>` : ""}<button data-command="replay-step" data-step="${item.step}" class="${item.step === replay.step ? "active" : ""}" ${item.step === replay.step ? 'aria-current="step"' : ""}><span>${String(item.step + 1).padStart(2, "0")}</span>${esc(item.label.replace(" · income paid", ""))}</button>`).join("")}</div>${ownAction ? `<p class="private-receipt"><b>Last private decision · ${title(ownAction.type)}</b><br>${esc(decision)}</p>` : ""}${mine ? `<p class="private-receipt"><b>Private receipt · attempt ${mine.attempt}</b><br>${esc(nameOf(observation.viewer))} originally deposited ${esc(tokenText(mine.tokens))}.</p>` : ""}</section>`;
}

function playerRankingsHTML(details) {
  const percent = value => Number.isFinite(value) ? `${Math.round(value * 100)}%` : "—";
  const beliefs = Object.entries(details.beliefs || {}).sort(([, a], [, b]) => (b.blue_preference ?? -1) - (a.blue_preference ?? -1));
  return `<p class="caption">Ranked from highest to lowest Blue preference. These are the bot’s estimates, not revealed roles or calibrated probabilities. Blue preference and honesty are separate judgments.</p>
    <div class="belief-scroll"><table class="belief-table"><thead><tr><th scope="col">Player</th><th scope="col">Blue preference</th><th scope="col">Keeps pledges</th><th scope="col">Report credibility</th><th scope="col">Wants inclusion</th><th scope="col">Expected Yes</th></tr></thead><tbody>${beliefs.map(([pid, b]) => `<tr><th scope="row">${esc(nameOf(pid))}${b.known_team ? `<span class="known-team-note">Known ${esc(title(b.known_team))}</span>` : ""}</th>${[b.blue_preference, b.pledge_reliability, b.report_credibility, b.inclusion_demand, details.vote_likelihoods?.[pid]].map(v => `<td>${percent(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
    <details><summary>Evidence behind these estimates</summary>${beliefs.map(([pid, b]) => `<p><b>${esc(nameOf(pid))}</b></p>${b.evidence?.length ? `<ul>${b.evidence.map(e => `<li>Event ${esc(e.event_id)}: ${esc(e.text)}</li>`).join("")}</ul>` : '<p class="caption">No individual evidence yet; using starting assumptions.</p>'}`).join("")}</details>`;
}

function replayPlayerAssessmentHTML(replay) {
  if (state.mode !== "replay" || !replay?.designer_enabled || replay.observation !== state.observation) return "";
  const pid = replay.viewing_seat, saved = replay.designer?.player_assessment;
  const assessment = saved?.player_id === pid && saved.details?.beliefs ? saved : null;
  return `<section class="panel replay-assessment" id="replay-player-assessment" tabindex="-1" aria-labelledby="player-assessment-title"><span class="eyebrow">SELECTED PLAYER · RECORDED ASSESSMENT</span><h3 id="player-assessment-title">${esc(nameOf(pid))}’s player rankings</h3>${assessment ? `<p class="caption">Latest assessment recorded at decision ${assessment.position} · ${esc(title(assessment.action_type))}. Carried forward until this player records another assessment.</p><button class="text-button" data-command="replay-assessment" data-position="${assessment.position}">View that decision ↗</button><div class="social-insights">${playerRankingsHTML(assessment.details)}</div>` : '<p class="caption">No player rankings recorded for this seat at this point in the replay.</p>'}</section>`;
}

function socialInsightsHTML(details) {
  if (!details.traits || !details.beliefs) return "";
  const percent = value => Number.isFinite(value) ? `${Math.round(value * 100)}%` : "—";
  const labels = {selfishness: "Self-interest", caution: "Risk caution", skepticism: "Skepticism"};
  const traits = Object.entries(labels).map(([key, label]) => `<span class="pill">${label} ${percent(details.traits[key])}</span>`).join("");
  const potText = pot => colors.map(c => `${Number(pot[c]).toFixed(1)} ${title(c)}`).join(" · ");
  const covert = details.concealing_red_intent;
  const forecast = details.forecast_pot ? `<p class="inspection-note"><b>${covert ? "Private forecast" : "Expected pot"}:</b> ${potText(details.forecast_pot)}${covert && details.advertised_pot ? `<br><b>Forecast with my public promise:</b> ${potText(details.advertised_pot)}<br><b>Private spending plan:</b> ${esc(tokenText(details.planned_deposit))}` : ""}<br><b>Estimated approval:</b> ${percent(details.approval_likelihood)}</p>` : "";
  const chances = details.outcome_likelihoods;
  const outcomes = chances ? `<p class="inspection-note"><b>Estimated mission outcome:</b> Blue ${percent(chances.blue)} · Red ${percent(chances.red)} · Unfinished ${percent(chances.incomplete)}<br><b>Personal result this attempt:</b> Win ${percent(chances.personal_win)} · Lose ${percent(chances.personal_loss)} · Game continues ${percent(chances.continues)}</p>` : "";
  return `<div class="social-insights"><div class="row wrap">${traits}</div><p class="inspection-note">Pursuing ${esc(title(details.objective))} · Currently favors ${esc(title(details.tactical_side))}.</p>${forecast}${outcomes}
    <h4>This bot’s view of the other players</h4>${playerRankingsHTML(details)}</div>`;
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
  const baseDescription = action => action.quantity !== undefined ? `${action.quantity} tokens` : action.tokens ? tokenText(action.tokens) : action.statements ? `${action.statements.length} report statements` : action.approve !== undefined ? (action.approve ? "Yes" : "No") : action.crew?.map(pid => nameOf(pid)).join(", ") || title(action.type);
  const description = action => {
    const a = action.ability;
    const extra = a ? a.source === "wallet" ? `request ${a.amount} from ${nameOf(a.target)}’s wallet` : a.source === "mission" ? `request ${tokenText(a.tokens)} from mission` : a.from ? `change ${title(a.from)} to ${title(a.to)}` : a.color ? `deposit 1 ${title(a.color)} off crew` : `target ${nameOf(a.target)}` : "";
    return [baseDescription(action), extra].filter(Boolean).join(" · ");
  };
  const effectText = effect => effect.type === "echo" ? `created 1 ${title(effect.color)}` : effect.type === "thief" ? effect.source === "wallet" ? `took ${effect.amount} from ${nameOf(effect.target)}’s wallet` : `took ${tokenText(effect.tokens)} from mission` : `${effect.changed ? "changed 1" : "no token available:"} ${title(effect.from)} → ${title(effect.to)}`;
  return `<section class="designer-panel"><span class="eyebrow">REVEALED INFORMATION</span>${agentPredictionsHTML(designer.agent_predictions, designer.players)}<h3>Behind the result</h3>${last ? `<p class="inspection-note">Last action: <b>${esc(nameOf(last.player_id))}</b> · ${title(last.action.type)} · ${esc(description(last.action))}</p>` : '<p class="inspection-note">Roles have been dealt. No actions yet.</p>'}
    ${decision ? `<div class="bot-explanation"><span class="eyebrow">WHY THIS BOT ACTED · ${esc(decision.policy_version)}</span><p>${esc(decision.reason)}</p>${socialInsightsHTML(decision.details)}<details><summary>Forecast and policy limits</summary><pre>${esc(JSON.stringify(decision.details, null, 2))}</pre><ul>${decision.limitations.map(note => `<li>${esc(note)}</li>`).join("")}</ul></details><p class="caption">Saved at the decision. Forecasts are estimates; replay verifies actions and results.</p></div>` : last ? '<p class="inspection-note">No saved bot explanation for this decision.</p>' : ""}
    <h3 style="margin-top:15px">Private cards</h3>${designer.players.map(player => `<div class="inspection-row"><strong>${esc(nameOf(player.id))}</strong><span>${esc(title(player.objective))} · ${esc(title(player.ability || "disabled"))}${player.ability_used ? " (used)" : ""}${player.result ? ` · ${player.result.won ? "Won" : "Did not win"}` : ""}</span></div>`).join("")}
    ${Object.keys(designer.sealed_submissions).length ? `<h3 style="margin-top:15px">Currently sealed</h3>${Object.entries(designer.sealed_submissions).map(([pid, action]) => `<div class="inspection-row"><strong>${esc(nameOf(pid))}</strong><span>${esc(description(action))}</span></div>`).join("")}` : ""}
    ${resolution ? `<h3 style="margin-top:15px">Original deposits · attempt ${resolution.attempt}</h3>${Object.entries(resolution.original_contributions).map(([pid, vector]) => `<div class="inspection-row"><strong>${esc(nameOf(pid))}</strong>${tokenMini(vector)}</div>`).join("") || '<p class="inspection-note">No crew deposits. This attempt used the rejection penalty.</p>'}<p class="inspection-note">${resolution.penalty ? "Penalty attempt" : "Approved crew"} · Final pot: ${esc(tokenText(resolution.mission.pot))}</p>${resolution.effects?.length ? `<h3>Effects in resolution order</h3>${resolution.effects.map(effect => `<div class="inspection-row"><strong>${esc(nameOf(effect.player_id))}</strong><span>${esc(title(effect.type))}: ${esc(effectText(effect))}</span></div>`).join("")}` : ""}` : ""}</section>`;
}

function tableHTML() {
  const observation = state.observation, replay = state.mode === "replay";
  const moment = displayedResolution(observation), tableObservation = moment ? resolvedObservation(observation, moment) : observation;
  return `<div class="table-heading"><h1>${esc(state.game.title)}${replay ? '<small>Replay</small>' : ""}</h1><div class="heading-tools"><button class="button small subtle" data-command="toggle-history" aria-expanded="${state.historyVisible}" aria-controls="history-area">History</button>${replay ? (state.game.can_resume ? `<button class="button small" data-command="open-table" data-id="${esc(state.game.id)}">Return to table</button>` : '<button class="button small" data-command="library">Library</button>') : `<button class="button small subtle" data-command="open-replay" data-id="${esc(state.game.id)}" data-latest="true">Replay ↗</button>`}</div></div>
    ${replay ? replayStripHTML(state.replay) : ""}<div class="workspace"><div class="table-column" id="table-board" tabindex="-1"><div id="players-area" tabindex="-1">${playersHTML(observation)}</div>${replay ? replayPlayerAssessmentHTML(state.replay) : pacingHTML()}<div class="table-accounting">${potComparisonHTML(tableObservation)}</div>${replay ? designerHTML(state.replay.designer) : ""}</div><aside class="side-column ${replay ? "replay-side" : "live-side"}">${replay ? replaySidebarHTML(state.replay) : `<div id="decision-area" tabindex="-1">${actionHTML(observation)}</div>${privateHTML(observation)}`}</aside></div>
    <div id="history-area" ${state.historyVisible ? "" : "hidden"}>${state.historyVisible ? historyHTML(observation) : ""}</div>${!replay && !state.resolutionHold && observation.action_spec && !state.canAdvance ? '<button class="mobile-action-jump button primary" data-command="jump-action">Your decision ↑</button>' : ""}`;
}

function render() {
  document.title = state.mode === "library" ? "Hidden Rules · Game library" : `${state.mode === "replay" ? "Replay" : `Mission ${state.observation.public.mission.number}`} · Hidden Rules`;
  $("#app").innerHTML = state.mode === "library" ? libraryHTML() : tableHTML();
  state.resolutionAnimated = state.resolutionHold;
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
  if (state.resolutionHold || !spec || state.canAdvance || !legalAbility()) return false;
  if (["prepare", "audit"].includes(spec.type)) return true;
  if (spec.type === "select_crew") return draft.crew.length === spec.crew_size;
  if (spec.type === "pledge") return isQuantity(draft.tokens.blue) && draft.tokens.blue <= spec.max_total;
  if (spec.type === "contribute") return colors.every(c => isQuantity(draft.tokens[c])) && total(draft.tokens) <= spec.max_total;
  if (spec.type === "vote") return isQuantity(draft.influence) && draft.influence <= spec.max_influence && typeof draft.approve === "boolean" && draft.complaints.length === (draft.approve ? 0 : 1) && draft.complaints.every(c => c.player_id || c.color);
  if (spec.type === "report") return draft.statements.length >= spec.min_statements && draft.statements.length <= 3 && draft.statements.every(c => isQuantity(c.quantity));
  return false;
}
function syncAction() {
  const button = $("#submit-action"), spec = state.observation?.action_spec;
  if (!button || !spec) return;
  button.disabled = state.busy || !legalDraft();
  if (state.busy) button.textContent = "Sealing your decision…";
  else if (spec.type === "report") button.textContent = "Seal my report →";
  else if (spec.ability) button.textContent = `${abilitySubmitLabel(spec)} →`;
  for (const [selector, preview] of [["#ability-feedback", abilityFeedback], ["#echo-bonus-preview", echoPreview]]) {
    const element = $(selector);
    if (element) { element.textContent = preview(); element.hidden = !element.textContent; }
  }
  if ($("#vote-influence-summary")) $("#vote-influence-summary").textContent = influenceSummary();
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
  if (type === "pledge") return {type, quantity: d.tokens.blue};
  if (type === "contribute") return {type, tokens: d.tokens,
    ...(type === "contribute" && "ability" in state.observation.action_spec ? {ability: abilityChoice()} : {})};
  if (type === "vote") return {type, approve: d.approve, influence:d.influence, complaints: d.complaints.map(c => Object.fromEntries(Object.entries(c).filter(([, v]) => v)))};
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
    announce(state.resolutionHold ? resolutionAnnouncement(data.observation) : data.observation.phase === "game_over" ? "The game is complete." : `Decision saved. Next: ${title(data.observation.phase)}.`);
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
  $("#allegiance-dialog")?.close();
  stopPlayback(); clearLiveTimer(); state.busy = false; state.lastStep = null; state.resolutionHold = null; state.resolutionSeen = null;
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
      captureResolution(data.observation);
    } else throw new Error("That table view does not exist.");
    state.historyVisible = false; state.historyOpen = {}; state.historyFilter = "all"; state.playerHistory = null; state.potReference = ""; state.potComparisonOpen = false; state.privateDetailsOpen = {};
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
    captureResolution(data.observation);
    history.replaceState(null, "", `#replay/${encodeURIComponent(id)}?${params}`);
    if (data.step === data.total_steps - 1) stopPlayback();
    render();
    if (state.resolutionHold) announce(resolutionAnnouncement(data.observation));
    if (state.playing) state.timer = setTimeout(() => seek(state.replay.step + 1), 1200);
  } catch (error) { stopPlayback(); toast(error.message, true); render(); }
}

function pauseForReading() {
  if (state.mode === "replay") {
    stopPlayback();
    const button = $('[data-command="replay-play"]');
    if (button) { button.textContent = "▶"; button.setAttribute("aria-label", "Play replay"); }
    return;
  }
  if (state.mode !== "table") return;
  state.livePaused = true; clearLiveTimer();
  const status = $("#pace-status"), toggle = $('[data-command="live-toggle"]');
  if (status) status.textContent = pacingStatus();
  if (toggle) toggle.textContent = "Auto play";
}

function jumpToSection(id) {
  const target = $(`#${id}`);
  if (!target) return;
  if (id !== "table-board" && id !== "decision-area" && id !== "players-area") pauseForReading();
  target.scrollIntoView({behavior: "smooth", block: "start"});
  target.focus({preventScroll: true});
}

async function command(button) {
  const cmd = button.dataset.command;
  if (cmd === "reload") { window.location.reload(); return; }
  if (cmd === "mark-player") { openAllegiancePicker(button.dataset.id); return; }
  if (cmd === "close-allegiance") { closeAllegiancePicker(); return; }
  if (cmd === "set-allegiance") {
    const dialog = $("#allegiance-dialog");
    if (dialog.open && dialog.dataset.notesKey === allegianceNotesKey(state.observation) &&
        setPlayerGuess(state.observation, dialog.dataset.player, button.dataset.value)) {
      $("#players-area").innerHTML = playersHTML(state.observation);
      announce(button.dataset.value ? `${nameOf(dialog.dataset.player)} marked as possibly ${title(button.dataset.value)}. Only you see this guess.` : `Your guess for ${nameOf(dialog.dataset.player)} cleared.`);
    }
    closeAllegiancePicker();
    return;
  }
  if (cmd === "resolution-continue") {
    state.resolutionHold = null;
    if (state.observation.phase === "game_over") {
      render(); jumpToSection("final-results");
      return;
    }
    if (state.mode === "replay") {
      if (state.replay.step < state.replay.total_steps - 1) await seek(state.replay.step + 1);
      else render();
      return;
    }
    render();
    ($('[data-command="live-next"]') || $('[data-command="jump-action"]'))?.focus({preventScroll:true});
    return;
  }
  if (cmd === "help") { clearLiveTimer(); $("#help-dialog").showModal(); return; }
  if (cmd === "close-help") { $("#help-dialog").close(); scheduleAdvance(); return; }
  if (cmd === "library") { route("#library"); return; }
  if (cmd === "filter") { state.filter = button.dataset.value; render(); return; }
  if (cmd === "open-table") { route(`#table/${encodeURIComponent(button.dataset.id)}`); return; }
  if (cmd === "open-replay") { route(`#replay/${encodeURIComponent(button.dataset.id)}?step=${button.dataset.latest ? -1 : 0}`); return; }
  if (cmd === "toggle-history") {
    pauseForReading(); state.historyVisible = !state.historyVisible; render();
    if (state.historyVisible) jumpToSection("table-history");
    else $('[data-command="toggle-history"]')?.focus({preventScroll:true});
    return;
  }
  if (cmd === "history-attempt") {
    const attempt = Number(button.dataset.attempt);
    if (!state.observation.history.some(e => e.attempt === attempt)) return;
    pauseForReading(); state.historyVisible = true; state.historyFilter = "all"; state.historyOpen[attempt] = true;
    render();
    jumpToSection(state.observation.history.some(e => e.type === "attempt_resolved" && e.attempt === attempt) ? `attempt-result-${attempt}` : `history-attempt-${attempt}`);
    return;
  }
  if (cmd === "inspect-player") {
    if (!revealedPlayer(state.observation,button.dataset.id)) return;
    stopPlayback(); state.playerHistory = null;
    await seek(state.replay.step, button.dataset.id, true, state.replay.position);
    if (state.replay.viewing_seat === button.dataset.id) jumpToSection("replay-player-assessment");
    return;
  }
  if (cmd === "jump-action") { jumpToSection(state.observation.action_spec?.type === "select_crew" ? "players-area" : "decision-area"); return; }
  if (cmd === "history-expand" || cmd === "history-collapse") {
    pauseForReading();
    for (const {event} of visibleHistoryEntries(state.observation)) state.historyOpen[event.attempt] = cmd === "history-expand";
    $("#history-area").innerHTML = historyHTML(state.observation);
    $(`[data-command="${cmd}"]`)?.focus({preventScroll: true});
    return;
  }
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
    if (cmd === "replay-prediction" || cmd === "replay-assessment") {
      await seek(state.replay.step, state.replay.viewing_seat, true, Number(button.dataset.position)); return;
    }
    const target = {"replay-first": 0, "replay-back": state.replay.step - 1, "replay-next": state.replay.step + 1, "replay-last": state.replay.total_steps - 1, "replay-step": Number(button.dataset.step)}[cmd];
    await seek(target); return;
  }
  if (cmd === "live-toggle") { state.livePaused = state.pace ? !state.livePaused : false; if (!state.pace) { state.pace = 1800; savePace(); } render(); $('[data-command="live-toggle"]')?.focus({preventScroll:true}); return; }
  if (cmd === "live-next") { await advanceTable(); return; }
  if (cmd === "player-history" || cmd === "close-player-history") {
    state.playerHistory = cmd === "close-player-history" || state.playerHistory === button.dataset.id ? null : button.dataset.id;
    if (state.playerHistory) pauseForReading();
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
    const color = button.dataset.color, current = state.draft.tokens[color];
    const value = (isQuantity(current) ? current : 0) + Number(button.dataset.delta);
    if (!isQuantity(value)) return;
    if (Number(button.dataset.delta) > 0 && total({...state.draft.tokens,[color]:value}) > state.observation.action_spec.max_total) return;
    state.draft.tokens[color] = value;
    $(`#token-${color}`).value = value; syncAction(); return;
  }
  if (cmd === "copy-pledge") state.draft.tokens = {blue:Math.min(state.observation.public.pledges[state.observation.viewer], state.observation.action_spec.max_total),red:0,green:0};
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
  if (event.target.closest("summary")?.closest("#your-cards, .pot-comparison, .history-group")) pauseForReading();
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
  if (event.target.id === "vote-influence") {
    state.draft.influence = event.target.value === "" ? NaN : Number(event.target.value);
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
    const d = state.draft.ability, value = event.target.value;
    if (abilityField === "steal") {
      const [source, target = ""] = value.split(":");
      d.source = source;
      d.target = target;
      renderDecision('[data-ability="steal"]');
    } else {
      if (abilityField === "recolor") [d.from, d.to] = value ? value.split(":") : ["", ""];
      else d[abilityField] = value;
      syncAction();
    }
  }
  if (event.target.id === "history-filter") { pauseForReading(); state.historyFilter = event.target.value; $("#history-area").innerHTML = historyHTML(state.observation); $("#history-filter")?.focus({preventScroll: true}); }
  if (event.target.id === "replay-scrubber") { stopPlayback(); seek(Number(event.target.value)); }
  if (event.target.id === "replay-seat") { stopPlayback(); seek(state.replay.step, event.target.value, state.replay.designer_enabled, state.replay.position); }
  if (event.target.id === "designer-toggle") { stopPlayback(); seek(state.replay.step, state.replay.viewing_seat, event.target.checked, state.replay.position); }
});
document.addEventListener("toggle", event => {
  if (event.target.dataset?.privateDetail && event.target.isConnected) state.privateDetailsOpen[event.target.dataset.privateDetail] = event.target.open;
  if (event.target.id === "pot-comparison" && event.target.isConnected) state.potComparisonOpen = event.target.open;
  if (event.target.matches?.(".history-group") && event.target.isConnected) state.historyOpen[event.target.dataset.attempt] = event.target.open;
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
$("#allegiance-dialog")?.addEventListener("cancel", event => { event.preventDefault(); closeAllegiancePicker(); });
async function boot() {
  try {
    const data = await api("/api/bootstrap");
    state.token = data.token; state.games = data.games;
    $("#full-guide").textContent = data.guide;
    if (location.hash && location.hash !== "#library") await loadRoute();
    else { state.mode = "library"; render(); }
  } catch (error) {
    $("#app").innerHTML = `<div class="loading"><h1>${window.MissionBrowser ? "The game could not start." : "The local table is offline."}</h1><p class="muted" style="margin:18px 0">${window.MissionBrowser ? esc(error.message) : "Start the Python web server, then refresh this page."}</p><button class="button primary" data-command="reload">Reload →</button></div>`;
    toast(error.message, true);
  }
}
boot();

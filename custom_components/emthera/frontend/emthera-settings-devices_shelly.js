/* Devices, part Shelly devices (1.4.5 HA-PANEL-145: split from emthera-settings-devices.js, the module budget):
   the screens #devices/shelly and #devices/shelly/<id> (a device's health, The Pill's probes, a BLU Gateway's valves and
   the pump by hand), with their texts. Loaded by the panel with the other section modules (settings.SECTION_MODULES);
   it hands its screens to its section through window.OpenThermostatSettingsParts, and the section registers once it
   is here. */
const TEXTS = {
 nl: {
  'Saving…': 'Opslaan…',
  'Shelly devices': 'Shelly-apparaten',
  '1 valve': '1 kraan',
  '{n} valves': '{n} kranen',
  'No reading': 'Geen meting',
  'Shelly device': 'Shelly-apparaat',
  'Add a Shelly device': 'Shelly-apparaat toevoegen',
  'No Shelly devices yet.': 'Nog geen Shelly-apparaten.',
  'IP address': 'IP-adres',
  'Remove device': 'Apparaat verwijderen',
  'Remove {name}?': '{name} verwijderen?',
  'The Hub stops reading and switching the device. The valves of a BLU Gateway stay in their rooms until you remove them under Rooms.': 'De Hub leest en schakelt het apparaat niet meer. De kranen van een BLU Gateway blijven in hun ruimtes tot je ze onder Ruimtes verwijdert.',
  'Probe roles': 'Sonderollen',
  'Choose the place of each probe.': 'Kies de plek van elke sonde.',
  'To keep the water at the manifold below its limit, a probe must sit on the manifold. A probe on the supply only measures.': 'Om het water op de verdeler onder de grens te houden, moet een sonde op de verdeler zitten. Een sonde op de aanvoer meet alleen.',
  'Probe {n}': 'Sonde {n}',
  'Back from floor loop {n}': 'Terug van vloergroep {n}',
  'Other probe {n}': 'Andere sonde {n}',
  'Not used': 'Niet gebruikt',
  'A heating circuit measures with this probe. Change the circuit first (on the Hub: Home → Heating settings).': 'Een verwarmingscircuit meet met deze sonde. Pas eerst het circuit aan (op de Hub: Huis → Verwarming).',
  'Save probe roles': 'Sonderollen opslaan',
  'Probe roles saved.': 'Sonderollen opgeslagen.',
  'The Pill reports no probes yet.': 'The Pill meldt nog geen sondes.',
  'Try again': 'Opnieuw proberen',
  'Valves': 'Kranen',
  'Valve {id}': 'Kraan {id}',
  'room: {room}': 'ruimte: {room}',
  'No valves yet.': 'Nog geen kranen.',
  'Add a valve': 'Kraan toevoegen',
  'Remove': 'Verwijderen',
  'Remove {valve}': '{valve} verwijderen',
  'The Hub stops reading and driving these valves. A valve in a room stays there until you remove it under Rooms → the room → Radiator valves.': 'De Hub leest en stuurt deze kranen niet meer. Een kraan in een ruimte blijft daar tot je hem verwijdert onder Ruimtes → de ruimte → Radiatorkranen.',
  'Look for valves at the gateway': 'Kranen zoeken bij de gateway',
  'Search again': 'Opnieuw zoeken',
  'Searching…': 'Zoeken…',
  'Tap a valve to add it.': 'Tik op een kraan om hem toe te voegen.',
  'Valves found so far can be added when the search is over.': 'Gevonden kranen kun je toevoegen als het zoeken klaar is.',
  'Already in the list': 'Staat al in de lijst',
  'Already in the list as “{name}”': 'Staat al in de lijst als “{name}”',
  'The gateway reports no paired valves. Pair them in the Shelly app first.': 'De gateway meldt geen gekoppelde kranen. Koppel ze eerst in de Shelly-app.',
  "Looking at the gateway's list of valves…": 'Kijken in de lijst met kranen van de gateway…',
  'Asking the gateway for each valve number (200 to 209)…': 'De gateway per kraannummer (200 tot en met 209) vragen…',
  'Reading the names of the valves…': 'De namen van de kranen lezen…',
  'Found {n} valve so far.': 'Tot nu toe {n} kraan gevonden.',
  'Found {n} valves so far.': 'Tot nu toe {n} kranen gevonden.',
  'Found {n} valve.': '{n} kraan gevonden.',
  'Found {n} valves.': '{n} kranen gevonden.',
  'Found {n} valve, but the search could not be finished:': '{n} kraan gevonden, maar het zoeken is niet helemaal gelukt:',
  'Found {n} valves, but the search could not be finished:': '{n} kranen gevonden, maar het zoeken is niet helemaal gelukt:',
  'No valves found:': 'Geen kranen gevonden:',
  "The gateway's list is too long for the Hub. The valve numbers 200 to 209 were asked one by one instead.": 'De lijst van de gateway is te lang voor de Hub. In plaats daarvan zijn de kraannummers 200 tot en met 209 een voor een gevraagd.',
  'This gateway cannot give a list of its valves (older firmware?). The numbers 200 to 209 were asked one by one instead.': 'Deze gateway kan geen lijst van zijn kranen geven (oudere firmware?). In plaats daarvan zijn de nummers 200 tot en met 209 een voor een gevraagd.',
  "The gateway's list could not be read. The numbers 200 to 209 were asked one by one instead.": 'De lijst van de gateway kon niet gelezen worden. In plaats daarvan zijn de nummers 200 tot en met 209 een voor een gevraagd.',
  'The gateway has more components than the Hub looks at. Valves far down its list may be missing.': 'De gateway heeft meer onderdelen dan de Hub bekijkt. Kranen ver onderaan de lijst kunnen ontbreken.',
  'The gateway did not answer (tried twice).': 'De gateway antwoordde niet (twee keer geprobeerd).',
  "Another device answers at the gateway's address. Check the address.": 'Op het adres van de gateway antwoordt een ander apparaat. Controleer het adres.',
  'The gateway wants a password that the Hub does not have or cannot use.': 'De gateway wil een wachtwoord dat de Hub niet heeft of niet kan gebruiken.',
  'The Hub was busy with the gateway. Try again.': 'De Hub was bezig met de gateway. Probeer het opnieuw.',
  'The search was interrupted because the settings were saved. Search again.': 'Het zoeken is onderbroken doordat de instellingen zijn opgeslagen. Zoek opnieuw.',
  "The gateway's answer for valve {n} could not be read.": 'Het antwoord van de gateway over kraan {n} kon niet gelezen worden.',
  'The name of valve {n} could not be read. It is listed without a name; you can still add it.': 'De naam van kraan {n} kon niet gelezen worden. Hij staat zonder naam in de lijst; je kunt hem toch toevoegen.',
  'The search did not work.': 'Het zoeken is niet gelukt.',
  "The gateway's list did not show these valves, but they answered when asked by number.": 'De lijst van de gateway toonde deze kranen niet, maar ze antwoordden wel toen om het nummer werd gevraagd.',
  'The gateway has a valve with number {n} that the Hub cannot use (it supports 200 to 299).': 'De gateway heeft een kraan met nummer {n} die de Hub niet kan gebruiken (hij ondersteunt 200 tot en met 299).',
  'You can still add a valve by its number: use “Add a valve”.': 'Je kunt een kraan ook met zijn nummer toevoegen: gebruik “Kraan toevoegen”.',
  'The search is taking longer than expected. Search again in a moment.': 'Het zoeken duurt langer dan verwacht. Zoek over een moment opnieuw.',
  'The gateway calls this valve “{name}”. Use this name?': 'De gateway noemt deze kraan “{name}”. Deze naam gebruiken?',
  'The device calls itself “{name}”. Use this name?': 'Het apparaat noemt zichzelf “{name}”. Deze naam gebruiken?',
  'Use this name': 'Deze naam gebruiken',
  'The name was longer than 32 bytes and was shortened.': 'De naam was langer dan 32 bytes en is ingekort.',
  'Some characters in the name are not allowed here and were replaced.': 'Sommige tekens in de naam zijn hier niet toegestaan en zijn vervangen.',
  'Cancel': 'Annuleren',
  'Name': 'Naam',
  'Rename': 'Hernoemen',
  'Rename {name}': '{name} hernoemen',
  'New name': 'Nieuwe naam',
  'Standard name': 'Standaardnaam',
  'Leave the field empty to use the standard name.': 'Laat het veld leeg voor de standaardnaam.',
  '{n} of 32 bytes': '{n} van 32 bytes',
  'Name saved.': 'Naam opgeslagen.',
  'A gateway takes at most 5 valves.': 'Een gateway neemt hoogstens 5 kranen.',
  'waiting for the first answer': 'wacht op het eerste antwoord',
  'connected': 'verbonden',
  'not reachable': 'niet bereikbaar',
  'another device answers at this address': 'op dit adres antwoordt een ander apparaat',
  'the password is not accepted': 'het wachtwoord wordt niet geaccepteerd',
  'the device reports an error': 'het apparaat meldt een fout',
  'waiting for a report': 'wacht op een melding',
  'reporting': 'meldt zich',
  'silent for 15 minutes': 'al 15 minuten stil',
  'not reporting': 'meldt zich niet',
  'not found at the gateway': 'niet gevonden bij de gateway',
  'not paired with the gateway': 'niet gekoppeld aan de gateway',
  'gateway not reachable': 'gateway niet bereikbaar',
  'On the manifold': 'Op de verdeler',
  'On the supply': 'Op de aanvoer',
  'On the return': 'Op de retour',
  'Waiting for a reading': 'Wacht op een meting',
  'Not found on The Pill': 'Niet gevonden op The Pill'}};
const ERRORS = {
};

// What the section shares with this part (its screens' state and helpers) comes in once, when the section registers.
const build = ({ERRORS, SCREENS, JOBS, deviceName, valveName, standardName, sleep, icon, card, button, item, problem, state, routeTo, show, redraw, head, saved, flash, errorLine, POLL_GATEWAY_MS, GATEWAY_MS}) => {
const HEALTH = {waiting: 'waiting for the first answer', ok: 'connected', unreachable: 'not reachable', wrong_device: 'another device answers at this address',
 auth_failed: 'the password is not accepted', error: 'the device reports an error'};
const VALVE_HEALTH = {waiting: 'waiting for a report', ok: 'reporting', silent: 'silent for 15 minutes', offline: 'not reporting',
 missing: 'not found at the gateway', unpaired: 'not paired with the gateway', gateway: 'gateway not reachable'};
// The places of The Pill's probes (heating_link.PROBE_ROLES; the E32 page's three plain words: on the manifold, on the supply,
// on the return); loop_return_<n> and other_<n> are numbered.
const PIPES = {floor_supply: 'On the manifold', boiler_supply: 'On the supply', floor_return: 'On the return'};
const PROBE_HEALTH = {waiting: 'Waiting for a reading', no_reading: 'No reading', missing: 'Not found on The Pill'};
// The steps of a search and the Hub page's sentence for each (gateway_scan_result ``step``).
const STEPS = {list: 'Looking at the gateway\'s list of valves…', ids: 'Asking the gateway for each valve number (200 to 209)…', names: 'Reading the names of the valves…'};
// What went wrong in the list step (problems: step "list"), in the Hub page's words.
const LIST_WORDS = {too_large: 'The gateway\'s list is too long for the Hub. The valve numbers 200 to 209 were asked one by one instead.',
 rpc_error: 'This gateway cannot give a list of its valves (older firmware?). The numbers 200 to 209 were asked one by one instead.',
 malformed: 'The gateway\'s list could not be read. The numbers 200 to 209 were asked one by one instead.',
 cut: 'The gateway has more components than the Hub looks at. Valves far down its list may be missing.'};
// One plain sentence for one problem the search reports ({step, error, id?}); one for a code it does not know.
function problemWord(t, {step, error, id}) {
 if (/^(timeout|closed|connect_failed|http_error)$/.test(error)) return t('The gateway did not answer (tried twice).');
 if (error === 'wrong_device') return t('Another device answers at the gateway\'s address. Check the address.');
 if (/^(password_required|realm_mismatch|wrong_password|unsupported_auth)$/.test(error)) return t('The gateway wants a password that the Hub does not have or cannot use.');
 if (error === 'busy') return t('The Hub was busy with the gateway. Try again.');
 if (error === 'interrupted') return t('The search was interrupted because the settings were saved. Search again.');
 if (step === 'list' && LIST_WORDS[error]) return t(LIST_WORDS[error]);
 if (step === 'ids' && /^(too_large|malformed)$/.test(error)) return t('The gateway\'s answer for valve {n} could not be read.', {n: id});
 if (step === 'names') return t('The name of valve {n} could not be read. It is listed without a name; you can still add it.', {n: id});
 return t('The search did not work.');
}
// The rule the Hub applies to a name, said before anything is sent: 32 BYTES (a letter with an accent is two), no control
// characters, a valve's name no quote or backslash. "" is fine: it means the standard name.
const bytes = text => new TextEncoder().encode(text).length;
const nameRefused = (text, valve) => bytes(text) > 32 || /[\u0000-\u001f\u007f]/.test(text) || (valve && /["\\]/.test(text));
const KIND_ICON = Object.freeze({switch: 'plug', probes: 'probe', gateway: 'gateway'});
const pipeOf = (role, t) => {
 if (PIPES[role]) return t(PIPES[role]);
 const m = /^(loop_return|other)_(\d+)$/.exec(role || '');
 return m ? t(m[1] === 'loop_return' ? 'Back from floor loop {n}' : 'Other probe {n}', {n: m[2]}) : role;
};
/* ---- Shelly devices ---- */
function healthChip(t, health) {
 if (!HEALTH[health]) return null;
 const bad = !['ok', 'waiting'].includes(health);
 return [t(HEALTH[health]), problem(bad), bad ? 'alert' : health === 'ok' ? 'check' : null];
}
function shellyScreen(ctx) {
 const {kit, t, model: m} = ctx, {h} = kit, sh = m.shelly, live = m.live?.shelly || {};
 const out = [head(ctx, t('Shelly devices'), t(SCREENS.shelly[1]))];
 out.push(flash(ctx, 'shelly') || saved(ctx, ['removed']));
 if (!sh) return [...out, kit.notice(t(ERRORS.shelly_unsupported), 'info')];
 const full = sh.devices.length >= sh.max_devices;
 const add = button(kit, t('Shelly device'), () => ctx.navigate('#devices/shelly-add'), 'filled', 'plus',
  {disabled: ctx.readOnly || full, 'aria-label': t('Add a Shelly device'), 'data-add-device': ''});
 if (!sh.devices.length) return [...out, h('div', {class: 'ot-card'}, kit.empty({icon: 'devices', text: t('No Shelly devices yet.'), action: add}))];
 out.push(kit.h('div', {class: 'dv-toolbar end'}, add));
 if (full) out.push(h('p', {class: 'help dv-full', text: t(ERRORS.shelly_full)}));
 const list = h('div', {class: 'card list', 'data-list': 'shelly'});
 for (const d of sh.devices) {
  const valves = d.kind === 'gateway' ? (d.valves || []).length : null;
  list.append(item(kit, {name: KIND_ICON[d.kind] || 'devices', label: deviceName(d, live, t), data: {device: d.id},
   lines: [[t(JOBS[d.kind]), d.ip].join(' · '), valves == null ? '' : valves === 1 ? t('1 valve') : t('{n} valves', {n: valves})],
   chips: [healthChip(t, live[String(d.n)])], route: routeTo('device/' + d.id), onClick: () => show('device/' + d.id)}));
 }
 out.push(list);
 return out;
}
function deviceScreen(ctx, id) {
 const {kit, t, model: m} = ctx, {h} = kit, d = m.device, live = m.live?.shelly || {};
 if (m.supported === false) return [head(ctx, t('Shelly device'), null), kit.notice(t(ERRORS.shelly_unsupported), 'info')];
 if (!d) {  // a link to a device that was removed
  return [head(ctx, t('Shelly device'), null), kit.notice(t('No Shelly devices yet.'), 'info',
   kit.button(t('Shelly devices'), () => show('shelly'), 'outlined', {'data-to-list': ''}))];
 }
 const out = [head(ctx, deviceName(d, live, t), t(JOBS[d.kind]))];
 const chip = healthChip(t, live[String(d.n)]);
 out.push(h('div', {class: 'ot-card dv-facts'}, h('span', {class: 'row-icon'}, icon(kit, KIND_ICON[d.kind] || 'devices')),
  h('div', {class: 'dv-fact'}, h('span', {class: 'label', text: t('IP address')}), h('span', {class: 'dv-ip', text: d.ip})),
  chip ? kit.chip(...chip) : null));
 out.push(flash(ctx, 'rename'), nameCard(ctx, d, live));
 if (d.kind === 'probes') out.push(pillCard(ctx, d));
 if (d.kind === 'gateway') out.push(flash(ctx, 'valve') || saved(ctx, ['valves_removed']), ...gatewayCards(ctx, d));
 if (d.pump) out.push(h('p', {class: 'help dv-why', 'data-pump': '', text: t(ERRORS.shelly_pump_in_use)}));
 else if (!ctx.readOnly) out.push(h('div', {class: 'dv-remove'}, button(kit, t('Remove device'), () => ctx.act({action: 'shelly_remove', device: d.id}, {
  title: t('Remove {name}?', {name: deviceName(d, live, t)}),
  text: t('The Hub stops reading and switching the device. The valves of a BLU Gateway stay in their rooms until you remove them under Rooms.'),
  confirm: t('Remove device'), danger: true}), 'danger', 'trash', {'data-remove-device': d.id})));
 return out;
}

/* The Pill: each probe's pipe, read with pill_roles and saved whole with set_pill_roles. */
async function loadPill(id) {
 const run = state.pill = {id, loading: true, answer: null, chosen: {}, error: null, errors: {}, busy: false, done: false};
 redraw();
 try {
  const answer = await state.ctx.action('pill_roles', {device: id});
  if (state.pill !== run) return;
  run.answer = answer;
  for (const p of answer.probes || []) run.chosen[p.c] = p.role || '';
 } catch (e) { if (state.pill === run) run.error = e.text; }
 if (state.pill === run) { run.loading = false; redraw(); }
}
/* A probe's component number is 100..299 (a real Pill's probe is temperature:200): "Probe 1" for 100 and 200, "Probe 2"
   for 101 and 201, never "Probe 101". The same rule as the E32 page (data/html/shelly.js). */
const probeNumber = c => (c - 100) % 100 + 1;
function pillCard(ctx, d) {
 const {kit, t, lang} = ctx, {h} = kit, p = state.pill;
 const head = {title: t('Probe roles'), icon: 'probe', summary: t('Choose the place of each probe.'), data: {card: 'roles'}};
 const more = kit.more(t('To keep the water at the manifold below its limit, a probe must sit on the manifold. A probe on the supply only measures.'), ctx.lang);
 // Reading the probes is an action, and actions are for administrators (CONTRACT-1.4.1 §3).
 if (ctx.readOnly) return card(kit, head, more);
 if (!p || p.id !== d.id) queueMicrotask(() => { if (state.screen === 'device/' + d.id && state.pill?.id !== d.id) loadPill(d.id); });
 const body = [];
 if (!p || p.id !== d.id || p.loading) body.push(h('div', {role: 'status', 'aria-label': t('Probe roles')}, kit.skeleton('rows', 2)));
 else if (p.error && !p.answer) body.push(kit.inlineError(p.error), kit.button(t('Try again'), () => loadPill(d.id), 'text', {'data-retry': ''}));
 else {
  const a = p.answer, used = a.in_use || {}, probes = a.probes || [];
  if (p.done) body.push(h('div', {class: 'dv-done', 'data-done': 'roles'}, kit.notice(t('Probe roles saved.'), 'success')));
  body.push(errorLine(kit, p.error));
  if (!probes.length) body.push(h('p', {class: 'help', text: t('The Pill reports no probes yet.')}));
  const fields = h('div', {class: 'fields'});
  for (const probe of probes) {
   const mine = p.chosen[probe.c] || '', held = probe.role && used[probe.role] && mine === probe.role && (a.roles || {})[probe.c] === probe.role;
   const now = probe.health === 'ok' && typeof probe.t_c === 'number' ? kit.degrees(probe.t_c, '°C', lang) : t(PROBE_HEALTH[probe.health] || PROBE_HEALTH.waiting);
   const taken = new Set(Object.entries(p.chosen).filter(([c, r]) => r && Number(c) !== probe.c).map(([, r]) => r));
   const api = kit.fields.select({key: `role:${probe.c}`, label: t('Probe {n}', {n: probeNumber(probe.c)}), value: mine, hass: ctx.hass, disabled: ctx.readOnly || held || p.busy,
    help: held ? `${kit.together(now)} · ${t('A heating circuit measures with this probe. Change the circuit first (on the Hub: Home → Heating settings).')}` : kit.together(now),
    options: [{value: '', label: t('Not used')}, ...(a.choices || []).map(role => ({value: role, label: pipeOf(role, t)}))],
    onChange: v => { p.chosen[probe.c] = v; p.done = false; delete p.errors[probe.c]; redraw(); }});
   for (const option of api.el.querySelectorAll('option')) if (option.value && taken.has(option.value)) option.disabled = true;
   if (p.errors[probe.c]) api.setError(p.errors[probe.c]);
   api.el.dataset.probe = String(probe.c);
   fields.append(api.el);
  }
  body.push(fields);
  const changed = probes.some(x => (p.chosen[x.c] || '') !== ((a.roles || {})[x.c] || ''));
  if (probes.length) body.push(h('div', {class: 'dv-actions'}, kit.button(p.busy ? t('Saving…') : t('Save probe roles'), () => saveRoles(d.id), 'filled',
   {disabled: ctx.readOnly || p.busy || !changed, 'data-save-roles': ''})));
 }
 return card(kit, head, more, ...body);
}
async function saveRoles(id) {
 const p = state.pill;
 if (!p?.answer || p.busy) return;
 const roles = Object.fromEntries((p.answer.probes || []).map(x => [String(x.c), p.chosen[x.c] || null]));
 p.busy = true; p.error = null; p.errors = {}; p.done = false; redraw();
 try {
  const r = await state.ctx.action('set_pill_roles', {device: id, roles});
  if (state.pill !== p) return;
  p.answer = {...p.answer, roles: r.roles || {}, probes: p.answer.probes.map(x => ({...x, role: (r.roles || {})[x.c] || null}))};
  for (const x of p.answer.probes) p.chosen[x.c] = x.role || '';
  p.done = true;
 } catch (e) {
  if (state.pill !== p) return;
  const m = /^role:(\d+)$/.exec(e.field || '');
  if (m) p.errors[m[1]] = e.text; else p.error = e.text;
 }
 p.busy = false; redraw();
}

/* One name, one Rename (SH-NAME-3): a device's `label`, a valve's `name`; an empty field means the standard name. The pencil opens
   one field with Save and Cancel; the 32 bytes are counted and said before anything is sent; the Hub's refusal shows in the row.
   A save never changes an id, a key, a unique id or an entity id: only the name the screens show. */
const nameKey = (d, v) => (v ? `valve:${d.n}:${v.id}` : `device:${d.id}`);
const closeRename = () => { state.rename = null; redraw(); };
function openRename(key, own) {
 state.rename = {key, value: own, busy: false, error: null};
 redraw();
 queueMicrotask(() => state.root?.querySelector('[data-fk="rename"]')?.focus());
}
async function renameTo(d, v, name) {
 const ctx = state.ctx;
 if (!ctx || ctx.readOnly) return;
 const key = nameKey(d, v), run = state.rename = {value: name, ...(state.rename?.key === key ? state.rename : {}), key, busy: true, error: null};
 redraw();
 try {
  await ctx.action(v ? 'valve_rename' : 'shelly_rename', v ? {gateway: d.n, valve: v.id, name} : {device: d.id, name});
 } catch (e) { if (state.rename === run) { run.busy = false; run.error = e.text; redraw(); } return; }
 state.rename = null;
 state.flash = {kind: 'rename', done: 'renamed', make: t => t('Name saved.')};
 ctx.reload();  // the screen reads the Hub again: the new name, and the standard text when the name was emptied
}
// The pencil of a row: opens or closes the field of that row.
function renameButton(ctx, d, v, name, own) {
 const key = nameKey(d, v), open = state.rename?.key === key;
 return ctx.kit.h('button', {type: 'button', class: 'btn icon', 'aria-label': ctx.t('Rename {name}', {name}), title: ctx.t('Rename'), 'aria-expanded': String(open),
  'data-rename-open': key, on: {click: () => (open ? closeRename() : openRename(key, own))}}, icon(ctx.kit, 'pencil', 22));
}
// The open field: the standard name as placeholder, the bytes counted in words, Save (only for a name the Hub takes), Cancel.
function renameBox(ctx, d, v, own, standard) {
 const {kit, t} = ctx, {h} = kit, r = state.rename, valve = !!v;
 const field = kit.fields.text({key: 'rename', label: t('New name'), value: r.value, hass: ctx.hass, placeholder: own ? '' : standard, disabled: r.busy,
  help: t('Leave the field empty to use the standard name.'), onChange: x => { r.value = x; r.error = null; check(); }});
 const count = h('p', {class: 'help dv-bytes', 'data-bytes': '', role: 'status'});
 const save = kit.button(t(r.busy ? 'Saving…' : 'Save'), () => submit(), 'filled', {'data-rename-save': ''});
 const submit = () => { if (!r.busy && !nameRefused(r.value.trim(), valve)) renameTo(d, v, r.value.trim()); };
 const check = () => {
  const text = r.value.trim(), bad = nameRefused(text, valve);
  count.textContent = t('{n} of 32 bytes', {n: bytes(text)});
  count.dataset.tone = bad ? 'bad' : '';
  field.setError(bad ? t(ERRORS[valve ? 'shelly_valve_name_invalid' : 'shelly_label_invalid']) : '');
  save.disabled = bad || r.busy;
 };
 check();
 return h('form', {class: 'dv-rename', 'data-rename': r.key, on: {submit: e => { e.preventDefault(); submit(); }}}, field.el, count,
  r.error ? kit.inlineError(r.error) : null,
  h('div', {class: 'dv-actions'}, save, kit.button(t('Cancel'), closeRename, 'text', {'data-rename-cancel': '', disabled: r.busy})));
}
// What the gateway or the device calls itself, offered with one button; nothing is stored until it is pressed.
function suggestionBox(ctx, d, v, s) {
 const {kit, t} = ctx, {h} = kit;
 const notes = [s.cut ? t('The name was longer than 32 bytes and was shortened.') : '', s.cleaned ? t('Some characters in the name are not allowed here and were replaced.') : ''].filter(Boolean);
 return h('div', {class: 'dv-suggest', 'data-suggestion': nameKey(d, v)},
  h('p', {class: 'help', text: t(v ? 'The gateway calls this valve “{name}”. Use this name?' : 'The device calls itself “{name}”. Use this name?', {name: s.name})}),
  ...notes.map(text => h('p', {class: 'help', text})),
  ctx.readOnly ? null : kit.button(t('Use this name'), () => renameTo(d, v, s.name), 'outlined', {'data-suggestion-use': nameKey(d, v), disabled: !!state.rename?.busy}));
}
// The device's own name on its screen: the name shown everywhere, a pencil, the field and what the device calls itself.
function nameCard(ctx, d, live) {
 const {kit, t} = ctx, {h} = kit, shown = deviceName(d, live, t), own = d.label || '', key = nameKey(d), s = !own ? live['suggest:' + d.n] : null;
 const top = h('div', {class: 'dv-namerow'}, h('strong', {class: 'dv-name', 'data-name': '', text: shown}), own ? null : kit.chip(t('Standard name'), 'rest'),
  ctx.readOnly ? null : renameButton(ctx, d, null, shown, own));
 return card(kit, {title: t('Name'), icon: KIND_ICON[d.kind] || 'devices', data: {card: 'name'}}, top,
  state.rename?.key === key ? renameBox(ctx, d, null, own, shown) : null, s && state.rename?.key !== key ? suggestionBox(ctx, d, null, s) : null);
}

/* The BLU Gateway: its valves, and the search for the valves paired with it in the Shelly app (SH-FIND-3): the same flow as the
   Hub's own page. It starts with the button (and on "Search again"), shows the Hub's step and the count so far while it runs,
   waits for its real end (at most about three minutes), shows the result by state with one plain sentence per reason, and a new
   search clears the old result at once. */
async function startGatewayScan(d) {
 const ctx = state.ctx;
 if (!ctx || ctx.readOnly) return;
 const run = state.gateway = {id: d.id, n: d.n, running: true, result: null, error: null, timeout: false, lost: 0, until: Date.now() + GATEWAY_MS};
 redraw();
 const alive = () => state.gateway === run && run.running && state.root?.isConnected && state.screen === 'device/' + d.id;
 try { await ctx.action('gateway_scan', {gateway: d.n}); } catch (e) { if (state.gateway === run) { run.running = false; run.error = e.text; redraw(); } return; }
 while (alive()) {
  await sleep(POLL_GATEWAY_MS);
  if (!alive()) break;
  try {
   const r = await state.ctx.action('gateway_scan_result', {gateway: d.n});
   if (state.gateway !== run) return;
   // "none": the Hub knows no search of this gateway (not started yet, expired); five answers in a row end the wait.
   run.lost = r.state === 'none' ? run.lost + 1 : 0;
   if (r.state !== 'none') run.result = r;
   if (r.done) run.running = false;
   else if (run.lost >= 5 || Date.now() >= run.until) { run.running = false; run.timeout = true; }
  } catch (e) { if (state.gateway !== run) return; run.running = false; run.error = e.text; }
  if (state.screen === 'device/' + d.id) redraw();
 }
 if (state.gateway === run) run.running = false;
}
// The sentences under a finished or partly finished search: one per reason (and per valve where it is about one valve).
function searchNotes(t, r, rowIds) {
 const out = new Set();
 for (const p of r.problems || []) if (!(p.id != null && rowIds.has(p.id) && (p.step === 'ids' || p.step === 'names'))) out.add(problemWord(t, p));
 if (!(r.problems || []).length && (r.state === 'partial' || r.state === 'failed')) out.add(problemWord(t, {step: '', error: r.error || 'timeout'}));
 if (r.list_missed) out.add(t('The gateway\'s list did not show these valves, but they answered when asked by number.'));
 for (const n of (r.unsupported_ids || []).slice(0, 4)) out.add(t('The gateway has a valve with number {n} that the Hub cannot use (it supports 200 to 299).', {n}));
 return [...out];
}
// What a found valve says about its name (shortened, replaced, unread) and about its own problem.
function foundNotes(t, v, r) {
 const out = [];
 if (v.name_cut) out.push(t('The name was longer than 32 bytes and was shortened.'));
 if (v.name_cleaned) out.push(t('Some characters in the name are not allowed here and were replaced.'));
 if (v.name_unread) out.push(t('The name of valve {n} could not be read. It is listed without a name; you can still add it.', {n: v.id}));
 for (const p of r?.problems || []) if (p.id === v.id && (p.step === 'ids' || p.step === 'names')) out.push(problemWord(t, p));
 return [...new Set(out)];
}
function gatewayCards(ctx, d) {
 const {kit, t, model: m} = ctx, {h} = kit, live = m.live?.shelly || {}, max = m.max_valves, valves = d.valves || [];
 const full = valves.length >= max;
 const list = h('div', {class: 'card list dv-inner', 'data-list': 'valves'});
 for (const v of valves) {
  const key = `${d.n}:${v.id}`, health = live[key], name = valveName(d, v, live, t), own = v.name || '', s = !own ? live['suggest:' + key] : null;
  const bad = health && !['ok', 'waiting'].includes(health), open = state.rename?.key === nameKey(d, v);
  list.append(item(kit, {name: 'valve', label: name, data: {valve: key}, lines: [live['room:' + key] ? t('room: {room}', {room: live['room:' + key]}) : ''],
   chips: [VALVE_HEALTH[health] ? [t(VALVE_HEALTH[health]), problem(bad), bad ? 'alert' : null] : null],
   trailing: ctx.readOnly ? null : h('span', {class: 'dv-acts'}, renameButton(ctx, d, v, name, own), kit.iconButton('close', t('Remove {valve}', {valve: name}), () => ctx.act({action: 'valves_remove', valves: [key]}, {
    title: t('Remove {name}?', {name}),
    text: t('The Hub stops reading and driving these valves. A valve in a room stays there until you remove it under Rooms → the room → Radiator valves.'),
    confirm: t('Remove'), danger: true}), {'data-remove-valve': key}))}));
  if (open) list.append(renameBox(ctx, d, v, own, name));
  else if (s) list.append(suggestionBox(ctx, d, v, s));
 }
 if (!valves.length) list.append(h('p', {class: 'help dv-none', text: t('No valves yet.')}));
 const from = {id: d.id, name: deviceName(d, live, t)};
 const byNumber = kit.button(t('Add a valve'), () => { state.prefill = {gateway: String(d.n)}; state.valveFrom = from; ctx.navigate('#devices/valve-add'); }, 'text',
  {disabled: ctx.readOnly || full, 'data-add-valve': d.id});
 const valvesCard = card(kit, {title: t('Valves'), icon: 'valve', data: {card: 'valves'}}, list,
  full ? h('p', {class: 'help dv-full', text: t('A gateway takes at most 5 valves.')}) : null, h('div', {class: 'dv-actions'}, byNumber));
 // A valve just added by its number: the Hub asks the gateway for its name; read the screen once more to offer it.
 const w = state.nameWatch;
 if (w && w.id === d.id) {
  state.nameWatch = null;
  const added = valves.find(v => v.id === w.valve);
  if (added && !added.name && !live[`suggest:${d.n}:${added.id}`]) setTimeout(() => { if (state.screen === 'device/' + d.id && state.root?.isConnected) state.ctx?.reload(); }, 6000);
 }
 // The search.
 const g = state.gateway?.id === d.id ? state.gateway : null, r = g?.result, running = !!g?.running, body = [];
 const look = button(kit, t(running ? 'Searching…' : g ? 'Search again' : 'Look for valves at the gateway'), () => startGatewayScan(d), 'filled', 'magnify',
  {disabled: ctx.readOnly || full || running, 'data-gateway-scan': d.id});
 const found = r ? (r.valves || []) : [], count = found.length, rowIds = new Set(found.map(v => v.id));
 body.push(h('div', {class: 'dv-actions'}, look));
 if (g?.error) body.push(kit.inlineError(g.error));
 else if (running) body.push(h('div', {class: 'dv-status', 'data-status': 'looking'}, kit.statusLine(!r ? t('Searching…')
  : t(STEPS[r.step] || STEPS.list) + (count ? ' ' + t(count === 1 ? 'Found {n} valve so far.' : 'Found {n} valves so far.', {n: count}) : ''), 'accent')));
 else if (g?.timeout) body.push(h('div', {'data-status': 'slow'}, kit.statusLine(t('The search is taking longer than expected. Search again in a moment.'), 'attention')));
 else if (r) {
  const word = r.state === 'ok' ? (count ? t(count === 1 ? 'Found {n} valve.' : 'Found {n} valves.', {n: count}) : t('The gateway reports no paired valves. Pair them in the Shelly app first.'))
   : r.state === 'partial' && count ? t(count === 1 ? 'Found {n} valve, but the search could not be finished:' : 'Found {n} valves, but the search could not be finished:', {n: count})
   : t('No valves found:');
  body.push(h('div', {'data-status': r.state === 'ok' && !count ? 'none' : r.state}, kit.statusLine(word, r.state === 'ok' ? 'rest' : 'attention')));
  for (const text of searchNotes(t, r, rowIds)) body.push(h('div', {'data-problem': ''}, kit.statusLine(text, 'attention')));
  if (r.state !== 'ok' || !count) body.push(h('p', {class: 'help', 'data-hint': 'by-number', text: t('You can still add a valve by its number: use “Add a valve”.')}));
 }
 if (count && (r || running)) {
  const room = !full && !r.full && !running;
  body.push(h('p', {class: 'help', text: running ? t('Valves found so far can be added when the search is over.') : room ? t('Tap a valve to add it.') : t('A gateway takes at most 5 valves.')}));
  const rows = h('div', {class: 'card list dv-inner', 'data-list': 'found-valves'});
  for (const v of found) {
   const shown = v.display ? (v.name ? v.display : standardName(v.display, t)) : t('Valve {id}', {id: v.id}) + (v.name ? ` · ${v.name}` : '');
   rows.append(item(kit, {name: 'valve', label: shown, data: {'found-valve': v.id}, lines: foundNotes(t, v, r),
    chips: [v.known ? [v.known_as ? t('Already in the list as “{name}”', {name: v.known_as}) : t('Already in the list'), 'rest', 'check'] : null],
    disabled: v.known || !room || ctx.readOnly,
    onClick: () => { state.prefill = {gateway: String(d.n), valve: v.id, name: v.name || '', flags: {cut: !!v.name_cut, cleaned: !!v.name_cleaned, unread: !!v.name_unread}}; state.valveFrom = from; ctx.navigate('#devices/valve-add'); }}));
  }
  body.push(rows);
 } else if (running && !count) body.push(kit.skeleton('rows', 2));
 return [valvesCard, kit.h('section', {class: 'ot-card dv-search', 'data-card': 'search'}, ...body)];
}
// What the add form says about a valve the search found: the gateway's name is offered in the field (saving is the owner's OK).
function valveNotes(ctx, fill) {
 const {kit, t} = ctx, {h} = kit;
 if (!fill?.name && !fill?.flags?.unread) return null;
 const lines = fill.name ? [t('The gateway calls this valve “{name}”. Use this name?', {name: fill.name})] : [];
 if (fill.flags?.cut) lines.push(t('The name was longer than 32 bytes and was shortened.'));
 if (fill.flags?.cleaned) lines.push(t('Some characters in the name are not allowed here and were replaced.'));
 if (fill.flags?.unread) lines.push(t('The name of valve {n} could not be read. It is listed without a name; you can still add it.', {n: fill.valve}));
 return h('div', {class: 'dv-suggest', 'data-found-name': ''}, ...lines.map(text => h('p', {class: 'help', text})));
}

 return {shellyScreen, deviceScreen, valveNotes};
};
// Hand this part to its section (emthera-settings-devices.js), which registers once every part of it is here.
(window.OpenThermostatSettingsParts ||= {})["devices_shelly"] = {build, texts: TEXTS, errors: ERRORS};
window.dispatchEvent(new CustomEvent('openthermostat-settings-part', {detail: "devices_shelly"}));

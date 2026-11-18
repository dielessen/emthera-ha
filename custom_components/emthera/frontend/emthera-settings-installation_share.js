/* Installation, part Share data with Emthera (TESTER-AUTO-5): the block that shows what the Hub does with the boiler's data in plain words, asks the one
   question again when the permission is off, switches it off and changes the pick. Home Assistant sends nothing: the Hub does, and this block only
   talks to the Hub's routes through the actions share_state, share_permission and share_pick (settings_share.py). It is shown only for a Hub that
   answers with a sharing document: the old gateway, a Hub without the routes, a boiler link without a collector and a Hub that cannot be reached
   show nothing. The permission text is the model's own (settings_share.py reads share_format/consent_auto.json); the sentences below are the same words as
   the Hub's own pages (data/html/ui-messages-share.js). Loaded by the panel with the other section modules (settings.SECTION_MODULES); it hands its
   block to its section through window.OpenThermostatSettingsParts, and the section registers once it is here. */
const TEXTS = {
 nl: {
  'Waiting': 'Wacht',
  'Choose your boiler yourself': 'Kies zelf je ketel',
  'The Hub does not know this boiler yet.': 'De Hub kent deze ketel nog niet.',
  'The boiler only passes on numbers, not a name. Choose your boiler below.': 'De ketel geeft alleen nummers door, geen naam. Kies hieronder je ketel.',
  'Boiler brand': 'Merk',
  'Boiler type': 'Type',
  'Choose a brand': 'Kies een merk',
  'Choose a type': 'Kies een type',
  'Brand and type of your boiler': 'Merk en type van je ketel',
  'Use at most 40 characters: letters, digits, spaces and - / .': 'Gebruik hooguit 40 tekens: letters, cijfers, spaties en - / .',
  'My boiler is not in the list': 'Mijn ketel staat er niet bij',
  'Choose from the list instead': 'Kies toch uit de lijst',
  'Choose the type of your boiler too, or leave the brand empty.': 'Kies ook het type van je ketel, of laat het merk leeg.',
  'The Hub did not accept this choice.': 'De Hub nam deze keuze niet aan.',
  'The Hub could not save this. Try again.': 'De Hub kon dit niet bewaren. Probeer het opnieuw.',
  'What is sent?': 'Wat wordt er gestuurd?',
  'This version of the Hub does not send anything yet: nothing leaves your home. Your choice is remembered.': 'Deze versie van de Hub verstuurt nog niets: er verlaat niets je huis. Je keuze wordt wel onthouden.',
  'Share data with Emthera': 'Gegevens delen met Emthera',
  'Sharing on': 'Delen aan',
  'Sharing off': 'Delen uit',
  'Nothing is recorded and nothing is sent.': 'Er wordt niets opgenomen en niets verstuurd.',
  'You do not share anything. You can switch this on whenever you like.': 'Je deelt niets. Je kunt dit aanzetten wanneer je wilt.',
  'Brand and type': 'Merk en type',
  'Read by the Hub': 'Gelezen',
  'Seen by the Hub': 'Gezien',
  'You chose: {boiler}': 'Jij koos: {boiler}',
  'Not read yet. The Hub reads them as soon as the boiler passes them on.': 'Nog niet gelezen. De Hub leest ze zodra de ketel ze doorgeeft.',
  'The boiler heats': 'De ketel verwarmt',
  'Not seen yet. This comes by itself as soon as the boiler heats.': 'Nog niet gezien. Dat komt vanzelf zodra de ketel verwarmt.',
  'The boiler makes hot water': 'De ketel maakt warm water',
  'Not seen yet. This comes by itself as soon as someone uses hot water.': 'Nog niet gezien. Dat komt vanzelf zodra iemand warm water gebruikt.',
  'Sending': 'Versturen',
  'Not sent yet': 'Nog niet',
  'Soon': 'Straks',
  'Busy': 'Bezig',
  'Sent': 'Verstuurd',
  'Not accepted': 'Niet aangenomen',
  'Given up': 'Opgegeven',
  'This version of the Hub does not send anything yet.': 'Deze versie van de Hub verstuurt nog niets.',
  'Nothing leaves your home.': 'Er verlaat niets je huis.',
  'This starts by itself as soon as everything has been seen.': 'Dat gaat vanzelf zodra alles gezien is.',
  'The Hub has a good half hour and sends it by itself.': 'De Hub heeft een goed half uur en verstuurt het vanzelf.',
  'The Hub is sending the data now.': 'De Hub verstuurt de gegevens nu.',
  'Sent on {date}.': 'Verstuurd op {date}.',
  'Emthera did not accept the data of {date}.': 'Emthera heeft de gegevens van {date} niet aangenomen.',
  'Emthera did not accept the data.': 'Emthera heeft de gegevens niet aangenomen.',
  'The Hub gave up sending the data.': 'De Hub heeft het versturen opgegeven.',
  'Sent on {date}. The Hub is waiting for a better half hour.': 'Verstuurd op {date}. De Hub wacht op een beter half uur.',
  'The data was sent on {date}. The Hub still waits for one half hour in which it sees the boiler heat and make hot water. It then sends once more by itself.': 'De gegevens zijn verstuurd op {date}. De Hub wacht nog op één half uur waarin hij de ketel ziet verwarmen en warm water maken. Daarna verstuurt hij ze nog één keer vanzelf.',
  'Sharing is off. Switch it on to choose your boiler.': 'Delen staat uit. Zet het aan om je ketel te kiezen.',
  'The Hub waits at most {n} more days for a better half hour.': 'De Hub wacht hooguit nog {n} dagen op een beter half uur.',
  'The Hub waits at most 1 more day for a better half hour.': 'De Hub wacht hooguit nog 1 dag op een beter half uur.',
  'This boiler connection cannot share data yet.': 'Deze ketelaansluiting kan nog geen gegevens delen.',
  'The Hub is busy. Try again in a moment.': 'De Hub is bezig. Probeer het zo opnieuw.',
  'The Hub records by itself. You do not have to do anything. This can take a few days.': 'De Hub neemt zelf op. Jij hoeft niets te doen. Dit kan een paar dagen duren.',
  'In {n} days at the latest the Hub sends the best half hour it has by then.': 'Uiterlijk over {n} dagen verstuurt de Hub het beste half uur dat hij dan heeft.',
  'Tomorrow at the latest the Hub sends the best half hour it has by then.': 'Uiterlijk morgen verstuurt de Hub het beste half uur dat hij dan heeft.',
  'Today at the latest the Hub sends the best half hour it has.': 'Uiterlijk vandaag verstuurt de Hub het beste half uur dat hij heeft.',
  'The Hub has not recorded a full half hour yet.': 'De Hub heeft nog geen vol half uur opgenomen.',
  'The Hub is waiting for a connection to the internet.': 'De Hub wacht op een verbinding met internet.',
  'Sending did not work on {date}. The Hub tries again later.': 'Versturen lukte niet op {date}. De Hub probeert het later opnieuw.',
  'Sending did not work. The Hub tries again later.': 'Versturen lukte niet. De Hub probeert het later opnieuw.',
  'Thank you. You do not have to do anything more.': 'Dank je wel. Je hoeft verder niets te doen.',
  'There is nothing you can do about this yourself. If you want us to look into it, send us the reference below.': 'Hier kun je zelf niets aan doen. Wil je dat wij ernaar kijken, stuur ons dan de verwijzing hieronder.',
  'There is nothing you can do about this yourself.': 'Hier kun je zelf niets aan doen.',
  'Extra functions for your boiler come with a later update, after we have looked at the data.': 'Extra functies voor jouw ketel komen met een latere update, nadat wij de gegevens hebben bekeken.',
  'Delete what I shared': 'Wis wat ik heb gedeeld',
  'Everything your Hub shared with Emthera is deleted. Sharing is also switched off.': 'Alles wat je Hub met Emthera heeft gedeeld wordt gewist. Het delen gaat ook uit.',
  'Yes, delete': 'Ja, wissen',
  'Try sending again': 'Opnieuw proberen',
  'Your request to delete is ready. The Hub sends it by itself.': 'Je verzoek om te wissen staat klaar. De Hub verstuurt het vanzelf.',
  'This version of the Hub does not send anything yet. Your request stays.': 'Deze versie van de Hub verstuurt nog niets. Je verzoek blijft staan.',
  'The Hub is sending your request now.': 'De Hub verstuurt je verzoek nu.',
  'Your request to delete was sent on {date}. We delete your data as soon as we process it.': 'Je verzoek om te wissen is verstuurd op {date}. Wij wissen je gegevens zodra we het verwerken.',
  'Your request to delete was sent. We delete your data as soon as we process it.': 'Je verzoek om te wissen is verstuurd. Wij wissen je gegevens zodra we het verwerken.',
  'Emthera did not accept your request to delete. Try again.': 'Emthera heeft je verzoek om te wissen niet aangenomen. Probeer het opnieuw.',
  'Your request to delete could not be sent. Try again.': 'Je verzoek om te wissen kon niet worden verstuurd. Probeer het opnieuw.',
  'Nothing is recorded any more.': 'Er wordt niets meer opgenomen.',
  'Once it has been sent, you can switch sharing on again.': 'Zodra het verstuurd is, kun je het delen weer aanzetten.',
  'Your request to delete has not been sent yet. After that you can switch sharing on again.': 'Je verzoek om te wissen is nog niet verstuurd. Daarna kun je het delen weer aanzetten.',
  'There is nothing to delete: your Hub has not sent anything.': 'Er is niets om te wissen: je Hub heeft niets verstuurd.',
  'Reference:': 'Verwijzing:',
  'The Hub could not store your request. Sharing is off. Try deleting again.': 'De Hub kon je verzoek niet bewaren. Het delen staat wel uit. Probeer het wissen opnieuw.',
  'Cancel': 'Annuleren',
  'Choose your boiler': 'Kies je ketel',
  'Save choice': 'Keuze bewaren',
  'Your choice was saved.': 'Je keuze is bewaard.',
 }};
const ERRORS = {};
const OTHER = /^[A-Za-z0-9 \-/.]{1,40}$/;
// The Hub keeps the brand and the model as the words sent: at most 40 characters of letters, digits, space, - / and . (else invalid_pick). A list entry with
// other characters (a few Buderus names carry an asterisk) goes as the same words with a space in their place.
const sendable = text => String(text).replace(/[^A-Za-z0-9 \-/.]/g, ' ').replace(/ +/g, ' ').trim().slice(0, 40).trim();
const REFRESH_MS = 30000;
const STYLE = `.sh{display:grid;gap:var(--ot-s2)}.sh p{margin:0;overflow-wrap:anywhere}.sh-head{display:flex;align-items:center;justify-content:space-between;gap:var(--ot-s3)}
.sh-rows{margin:0;padding:0;list-style:none;border:1px solid var(--ot-divider);border-radius:var(--ot-radius-s)}
.sh-rows li{display:flex;justify-content:space-between;align-items:flex-start;gap:var(--ot-s3);padding:var(--ot-s3);border-top:1px solid var(--ot-divider)}.sh-rows li:first-child{border-top:0}
.sh-label{min-width:0;font-weight:500}.sh-sub{display:block;margin-top:2px;font-weight:400;font-size:var(--ot-text-s);color:var(--ot-muted)}
.sh-val{flex:none;display:inline-flex;align-items:center;gap:6px;white-space:nowrap}.sh-dot{width:8px;height:8px;border-radius:50%;background:var(--ot-tone-ink,var(--ot-muted))}
.sh-quiet{color:var(--ot-muted)}.sh-ref{display:block;font-family:ui-monospace,Consolas,monospace;overflow-wrap:anywhere;user-select:all;color:var(--ot-fg)}
.sh-pick{display:grid;gap:var(--ot-s2)}.sh-fold dl{margin:0;display:grid;gap:var(--ot-s2)}.sh-fold dt{font-weight:500}.sh-fold dd{margin:2px 0 0;color:var(--ot-fg-2)}
.sh-actions{display:flex;flex-wrap:wrap;gap:var(--ot-s2);align-items:center}.sh .btn{max-width:100%;white-space:normal;text-align:left}.sh-link{justify-self:start;height:auto}
@media(max-width:420px){.sh-actions .btn{flex:1 1 auto}}`;

// What the section shares with this part comes in once, when the section registers.
const build = ({notice}) => {
 // Per installation: the last answer, the pick being made, whether the permission is being sent. It outlives a redraw of the page.
 const memos = new Map();
 const memoOf = ctx => {
  if (!memos.has(ctx.entry_id)) memos.set(ctx.entry_id, {view: null, pick: null, picked: '', timer: null, working: false, error: '', saved: false, declined: false, wrongOpen: false, foldOpen: false, confirming: false});
  return memos.get(ctx.entry_id);
 };
 const dateOf = (ctx, seconds) => (Number.isFinite(seconds) && seconds > 0 ? new Date(seconds * 1000).toLocaleDateString(ctx.hass?.locale?.language || ctx.lang || 'en', {day: 'numeric', month: 'long', year: 'numeric'}) : '');
 const daysSentence = (t, n) => (n > 1 ? t('In {n} days at the latest the Hub sends the best half hour it has by then.', {n}) : n === 1
  ? t('Tomorrow at the latest the Hub sends the best half hour it has by then.') : t('Today at the latest the Hub sends the best half hour it has.'));

 // The rows and sentences of a Hub that shares. Every sentence is true for the state it is shown in: with configured false nothing leaves the house,
 // so nothing says that something is sent, waits to be sent or was sent.
 function status(ctx, doc, h) {
  const {t} = ctx, waits = Array.isArray(doc.waiting_for) ? doc.waiting_for : [], seen = doc.seen || {}, sending = doc.configured === true;
  const pick = doc.boiler.pick || {};
  const chose = pick.other || (pick.brand && pick.model ? pick.brand + ' ' + pick.model : '');
  const row = (label, tone, value, sub) => h('li', null, h('span', {class: 'sh-label'}, label, sub ? h('span', {class: 'sh-sub', text: sub}) : null),
   h('span', {class: 'sh-val', 'data-tone': tone}, h('span', {class: 'sh-dot'}), value));
  const gone = name => !waits.includes(name);
  const identity = seen.identity === true && gone('identity'), heat = seen.heating_s > 0 && gone('heating'), water = seen.hot_water_s > 0 && gone('hot_water');
  const state = sending ? doc.state : 'collecting', date = dateOf(ctx, doc.sent_at), tried = doc.last_try ? dateOf(ctx, doc.last_try.at) : '';
  const rows = [
   row(t('Brand and type'), identity ? 'ok' : 'accent', identity ? t('Read by the Hub') : t('Waiting'),
    chose ? t('You chose: {boiler}', {boiler: chose}) : (identity ? null : t('Not read yet. The Hub reads them as soon as the boiler passes them on.'))),
   row(t('The boiler heats'), heat ? 'ok' : 'accent', heat ? t('Seen by the Hub') : t('Waiting'), heat ? null : t('Not seen yet. This comes by itself as soon as the boiler heats.')),
   row(t('The boiler makes hot water'), water ? 'ok' : 'accent', water ? t('Seen by the Hub') : t('Waiting'), water ? null : t('Not seen yet. This comes by itself as soon as someone uses hot water.'))];
  const again = sending && state === 'collecting' && Number.isFinite(doc.sent_at);
  rows.push(!sending ? row(t('Sending'), 'rest', t('Not sent yet'), t('This version of the Hub does not send anything yet.'))
   : state === 'sent' ? row(t('Sending'), 'ok', t('Sent'), date ? t('Sent on {date}.', {date}) : null)
   : state === 'sending' ? row(t('Sending'), 'accent', t('Busy'), t('The Hub is sending the data now.'))
   : state === 'refused' ? row(t('Sending'), 'error', t('Not accepted'), tried ? t('Emthera did not accept the data of {date}.', {date: tried}) : t('Emthera did not accept the data.'))
   : state === 'given_up' ? row(t('Sending'), 'error', t('Given up'), t('The Hub gave up sending the data.'))
   : again ? row(t('Sending'), 'ok', t('Sent'), t('Sent on {date}. The Hub is waiting for a better half hour.', {date}))
   : state === 'ready' ? row(t('Sending'), 'accent', t('Soon'), t('The Hub has a good half hour and sends it by itself.'))
   : row(t('Sending'), 'rest', t('Not sent yet'), t('This starts by itself as soon as everything has been seen.')));
  const lines = [];
  if (!sending) lines.push(notice(ctx, t('This version of the Hub does not send anything yet.') + ' ' + t('Nothing leaves your home.'), 'warning'));
  else if (state === 'collecting' || state === 'ready') {
   if (state === 'collecting' && again) lines.push(h('p', {class: 'sh-quiet', 'data-part': 'share-again', text: t('The data was sent on {date}. The Hub still waits for one half hour in which it sees the boiler heat and make hot water. It then sends once more by itself.', {date})}));
   else lines.push(h('p', {class: 'sh-quiet', text: t('The Hub records by itself. You do not have to do anything. This can take a few days.')}));
   if (state === 'collecting' && Number.isInteger(doc.days_left)) lines.push(h('p', {class: 'sh-quiet', text: again ? (doc.days_left > 1 ? t('The Hub waits at most {n} more days for a better half hour.', {n: doc.days_left}) : t('The Hub waits at most 1 more day for a better half hour.')) : daysSentence(t, doc.days_left)}));
   if (waits.includes('length')) lines.push(h('p', {class: 'sh-quiet', text: t('The Hub has not recorded a full half hour yet.')}));
   if (waits.includes('network')) lines.push(h('p', {class: 'sh-quiet', text: t('The Hub is waiting for a connection to the internet.')}));
   const last = doc.last_try && doc.last_try.result === 'try_later' ? doc.last_try : null;
   if (last) lines.push(h('p', {class: 'sh-quiet', text: Number.isFinite(last.at) ? t('Sending did not work on {date}. The Hub tries again later.', {date: dateOf(ctx, last.at)}) : t('Sending did not work. The Hub tries again later.')}));
  } else if (state === 'sent') lines.push(h('p', {class: 'sh-quiet', text: t('Thank you. You do not have to do anything more.')}));
  else if (state === 'refused') lines.push(h('p', {class: 'sh-quiet', text: t('There is nothing you can do about this yourself. If you want us to look into it, send us the reference below.')}));
  else if (state === 'given_up') lines.push(h('p', {class: 'sh-quiet', text: t('There is nothing you can do about this yourself.')}));
  if (sending) lines.push(notice(ctx, t('Extra functions for your boiler come with a later update, after we have looked at the data.'), 'info'));
  return {rows: h('ul', {class: 'sh-rows', 'data-part': 'share-rows'}, rows), lines};
 }

 // The pick: brand, then type, from the catalogue the model carries; or a boiler that is not in the list, with a free text of at most 40 characters.
 function pickBox(ctx, m, view, redraw) {
  const {t, kit} = ctx, {h} = kit, stored = view.doc.boiler.pick || {}, boilers = view.boilers || [];
  const key = JSON.stringify(stored);
  if (!m.pick || m.picked !== key) { m.picked = key; m.pick = {brand: stored.brand || '', model: stored.model || '', other: stored.other || '', useOther: !!stored.other || boilers.length === 0, error: ''}; }
  const p = m.pick, types = (boilers.find(b => b.brand === p.brand) || {types: []}).types;
  const error = h('p', {class: 'error', role: 'alert', 'data-share-error': '', hidden: !p.error, text: p.error});
  const parts = [];
  if (!p.useOther) {
   parts.push(kit.fields.select({key: 'share-brand', hass: ctx.hass, label: t('Boiler brand'), value: p.brand, disabled: ctx.readOnly,
    options: [{value: '', label: t('Choose a brand')}, ...boilers.map(b => ({value: b.brand, label: b.brand}))], onChange: v => { p.brand = v; p.model = ''; p.error = ''; redraw(); }}).el,
    kit.fields.select({key: 'share-type', hass: ctx.hass, label: t('Boiler type'), value: types.find(x => x === p.model || sendable(x) === p.model) || '', disabled: ctx.readOnly || !p.brand,
     options: [{value: '', label: t('Choose a type')}, ...types.map(x => ({value: x, label: x}))], onChange: v => { p.model = v; p.error = ''; }}).el);
  } else {
   parts.push(kit.fields.text({key: 'share-other', hass: ctx.hass, label: t('Brand and type of your boiler'), value: p.other, maxlength: 40, disabled: ctx.readOnly,
    help: t('Use at most 40 characters: letters, digits, spaces and - / .'), onChange: v => { p.other = v; p.error = ''; }}).el);
  }
  if (boilers.length && !ctx.readOnly) parts.push(kit.button(p.useOther ? t('Choose from the list instead') : t('My boiler is not in the list'), () => { p.useOther = !p.useOther; p.error = ''; redraw(); }, 'text', {'data-action': 'share-other-toggle', class: 'btn text sh-link'}));
  parts.push(error);
  // true when nothing is wrong (sent, or unchanged); false when the person has to look (the reason is shown)
  const body = () => (p.useOther ? (p.other.trim() ? {other: p.other.trim()} : {}) : (p.brand && p.model ? {brand: sendable(p.brand), model: sendable(p.model)} : {}));
  const same = b => (b.other || null) === (stored.other || null) && (b.brand || null) === (stored.brand || null) && (b.model || null) === (stored.model || null);
  // what is wrong in the panel itself, said in words, before anything is sent
  const check = () => {
   if (!p.useOther && p.brand && !p.model) { p.error = t('Choose the type of your boiler too, or leave the brand empty.'); redraw(); return false; }
   if (p.useOther && p.other.trim() && !OTHER.test(p.other.trim())) { p.error = t('Use at most 40 characters: letters, digits, spaces and - / .'); redraw(); return false; }
   return true;
  };
  const commit = async () => {
   if (!check()) return false;
   const b = body();
   if (same(b)) return true;
   try {
    const answer = await ctx.action('share_pick', {...b, language: ctx.lang});
    m.view = answer?.share || null; m.pick = null; m.answeredAt = Date.now();
    return true;
   } catch (e) { p.error = e?.code === 'share_busy' ? t('The Hub is busy. Try again in a moment.') : e?.code === 'share_permission_off' ? t('Sharing is off. Switch it on to choose your boiler.') : t('The Hub did not accept this choice.'); redraw(); return false; }
  };
  return {el: h('div', {class: 'sh-pick', 'data-part': 'share-pick'}, ...parts), check, commit};
 }

 // "Delete what I shared" (AUTO-4B): the sentence of the Hub's `forget` member, the button (or "Try sending again"), and the question in the panel itself.
 function forgetParts(ctx, m, doc, send, paint) {
  const {kit, t} = ctx, {h} = kit, f = doc.forget && typeof doc.forget === 'object' ? doc.forget : null, state = f ? f.state : null;
  const say = (part, text) => h('p', {class: 'sh-quiet', 'data-part': part, text}), status = [];
  if (state === 'waiting') {
   status.push(say('share-forget-state', doc.configured === true ? t('Your request to delete is ready. The Hub sends it by itself.') : t('This version of the Hub does not send anything yet. Your request stays.')));
   if (doc.configured === true && f.last_try && f.last_try.result === 'try_later') status.push(say('share-forget-later', Number.isFinite(f.last_try.at) ? t('Sending did not work on {date}. The Hub tries again later.', {date: dateOf(ctx, f.last_try.at)}) : t('Sending did not work. The Hub tries again later.')));
  } else if (state === 'sending') status.push(say('share-forget-state', t('The Hub is sending your request now.')));
  else if (state === 'sent') {
   const at = [f.sent_at, f.last_try && f.last_try.at, f.asked_at].find(x => Number.isFinite(x) && x > 0);   // 0 is "unknown" (no clock yet): never a date
   status.push(say('share-forget-state', Number.isFinite(at) ? t('Your request to delete was sent on {date}. We delete your data as soon as we process it.', {date: dateOf(ctx, at)}) : t('Your request to delete was sent. We delete your data as soon as we process it.')));
  } else if (state === 'refused') status.push(say('share-forget-state', t('Emthera did not accept your request to delete. Try again.')));
  else if (state === 'given_up') status.push(say('share-forget-state', t('Your request to delete could not be sent. Try again.')));
  const buttons = [], pending = state === 'waiting' || state === 'sending';
  if (state === 'refused' || state === 'given_up') buttons.push(kit.button(t('Try sending again'), () => send('share_forget', {}), 'outlined', {'data-action': 'share-forget-again', disabled: m.working}));
  else if (doc.reference && !f && (doc.sent_at !== null && doc.sent_at !== undefined || doc.state === 'sending' || doc.permission.on === false)) buttons.push(kit.button(t('Delete what I shared'), () => { m.confirming = true; m.error = ''; paint(); }, 'outlined', {'data-action': 'share-forget', disabled: m.working}));
  const confirm = [notice(ctx, t('Everything your Hub shared with Emthera is deleted. Sharing is also switched off.'), 'warning'),
   h('div', {class: 'sh-actions'}, kit.button(t('Yes, delete'), async () => { m.confirming = false; await send('share_forget', {}); }, 'filled', {'data-action': 'share-forget-yes', disabled: m.working}),
    kit.button(t('Cancel'), () => { m.confirming = false; paint(); }, 'outlined', {'data-action': 'share-forget-cancel'}))];
  return {status, buttons, confirm, pending};
 }

 // The block. `host` is its card; it stays out of the page (hidden, empty) until the Hub answers with a document.
 function shareCard(ctx) {
  // The actions are the administrator's (settings/action): a reader's panel never asks, so it shows no block and makes no request.
  if (ctx.readOnly) return null;
  const {kit, t} = ctx, {h} = kit, m = memoOf(ctx);
  const host = h('section', {class: 'ot-card form sh', 'data-group': 'share', hidden: true});
   const set = view => { m.view = view; paint(); };
  const send = async (name, values) => {
   m.working = true; m.error = ''; paint();
   try { const answer = await ctx.action(name, {...values, language: ctx.lang}); m.view = answer?.share || null; m.answeredAt = Date.now(); return true; }
   catch (e) {
    m.error = e?.code === 'share_not_supported' ? t('This boiler connection cannot share data yet.') : e?.code === 'share_busy' ? t('The Hub is busy. Try again in a moment.')
     : e?.code === 'share_nothing_sent' ? t('There is nothing to delete: your Hub has not sent anything.')
     : e?.code === 'share_forget_pending' ? t('Your request to delete has not been sent yet. After that you can switch sharing on again.') : t('The Hub could not save this. Try again.');
    if (name === 'share_forget' && e?.code === 'share_no_storage') m.error = t('The Hub could not store your request. Sharing is off. Try deleting again.');
    if (name === 'share_forget') {
     // whatever the answer was the Hub may have changed (a 503 has switched sharing off already): read what it says and draw that
     try { const again = await ctx.action('share_state', {language: ctx.lang}); m.view = again?.share || m.view; m.answeredAt = Date.now(); } catch (_) { /* the next look does it */ }
    }
    return false;
   }
   finally { m.working = false; paint(); }
  };
  function paint() {
   const view = m.view;
   if (!view || !view.doc) { host.hidden = true; host.replaceChildren(); return; }
   host.hidden = false;
   const doc = view.doc, on = doc.permission.on === true, words = view.text || {};
   const kids = [h('style', {text: STYLE}), h('header', {class: 'ot-card-head'}, h('div', {class: 'ot-card-titles'}, h('h3', {class: 'ot-card-title', text: t('Share data with Emthera')}))),
    h('div', {class: 'sh-head'}, kit.chip(on ? t('Sharing on') : t('Sharing off'), on ? 'ok' : 'rest'))];
   const pick = pickBox(ctx, m, view, paint);
   // The reference is shown once, where the block asks for it: a refusal of a bundle ("if you want us to look into it, send us the reference below").
   const reference = doc.reference && on && doc.state === 'refused' ? h('p', {class: 'sh-quiet', 'data-part': 'share-reference'}, t('Reference:') + ' ', h('span', {class: 'sh-ref', text: doc.reference})) : null;
   const problem = m.error ? notice(ctx, m.error, 'error') : null;
   const forget = forgetParts(ctx, m, doc, send, paint);
   if (on) {
    const s = status(ctx, doc, h);
    kids.push(s.rows, ...s.lines, reference);
    kids.push(kit.fold({key: 'share-pick', title: doc.boiler.recognised === true ? t('Choose your boiler yourself') : t('Choose your boiler'), icon: 'info', open: m.foldOpen || doc.boiler.recognised !== true || !!(doc.boiler.pick && (doc.boiler.pick.other || doc.boiler.pick.brand)),
     onToggle: o => { m.foldOpen = o; }, data: {section: 'share-pick'}}, pick.el,
     ctx.readOnly ? null : h('div', {class: 'sh-actions'}, kit.button(t('Save choice'), async () => { if (await pick.commit()) { m.saved = true; paint(); setTimeout(() => { m.saved = false; paint(); }, 4000); } }, 'outlined', {'data-action': 'share-save-pick'})),
     m.saved ? h('p', {class: 'sh-quiet', role: 'status', text: t('Your choice was saved.')}) : null));
    kids.push(problem);
    kids.push(...forget.status);
    if (m.confirming) kids.push(...forget.confirm);
    else kids.push(h('div', {class: 'sh-actions'}, kit.button(words.off, () => send('share_permission', {on: false}), 'outlined', {'data-action': 'share-off', disabled: m.working}), ...forget.buttons));
   } else {
    const known = doc.boiler.recognised === true;
    kids.push(h('p', {class: 'sh-quiet', text: m.declined ? t('You do not share anything. You can switch this on whenever you like.') : forget.pending ? t('Nothing is recorded any more.') : t('Nothing is recorded and nothing is sent.')}));
    if (!known) kids.push(notice(ctx, t('The Hub does not know this boiler yet.') + ' ' + t('The boiler only passes on numbers, not a name. Choose your boiler below.'), 'warning'));
    if (known) kids.push(kit.button(t('Choose your boiler yourself'), () => { m.wrongOpen = true; paint(); }, 'text', {'data-action': 'share-wrong', hidden: m.wrongOpen || !!(doc.boiler.pick && (doc.boiler.pick.other || doc.boiler.pick.brand)), class: 'btn text sh-link'}));
    if (!known || m.wrongOpen || (doc.boiler.pick && (doc.boiler.pick.other || doc.boiler.pick.brand))) kids.push(pick.el);
    kids.push(...forget.status);
    if (m.confirming) kids.push(...forget.confirm);
    else if (forget.buttons.length) kids.push(h('div', {class: 'sh-actions'}, ...forget.buttons));
    // While the request to delete is still on its way the question is not offered (the Hub would refuse it): the sentence takes its place.
    if (forget.pending) {
     kids.push(h('p', {class: 'sh-quiet', 'data-part': 'share-forget-pending', text: t('Once it has been sent, you can switch sharing on again.')}), problem);
     host.replaceChildren(...kids.filter(Boolean));
     return;
    }
    kids.push(h('h4', {class: 'ot-card-title', text: words.title}), h('p', {text: words.intro}));
    if (doc.configured !== true) kids.push(h('p', {class: 'sh-quiet', 'data-part': 'share-not-configured', text: t('This version of the Hub does not send anything yet: nothing leaves your home. Your choice is remembered.')}));
    kids.push(kit.fold({key: 'share-sent', title: t('What is sent?'), icon: 'info', open: false, data: {section: 'share-sent'}}, h('dl', null, (words.paragraphs || []).flatMap(p => [h('dt', {text: p.title}), h('dd', {text: p.text})]))));
    kids.push(problem);
    if (!ctx.readOnly) kids.push(h('div', {class: 'sh-actions'},
     kit.button(words.yes, async () => { if (pick.check()) { m.declined = false; /* the Hub keeps a pick only while the permission is on: the permission first, the pick after it */ if (await send('share_permission', {on: true})) await pick.commit(); } paint(); }, 'filled', {'data-action': 'share-yes', disabled: m.working}),
     kit.button(words.no, () => { m.declined = true; paint(); }, 'outlined', {'data-action': 'share-no'})));
   }
   host.replaceChildren(...kids.filter(Boolean));
  }
  // One look when the card is drawn, then every 30 s while it is on the page (and not while a control inside it is in use).
  // The card is made before the page puts it in: a look that comes first waits for it (a card that never comes in is given up after 10 s), and a newer draw of the
  // card takes the loop over, so there is never more than one.
  const mine = m.gen = (m.gen || 0) + 1;
  let waited = 0;
  const look = async () => {
   if (m.gen !== mine) return;
   if (!host.isConnected) { if (++waited < 100) m.timer = setTimeout(look, 100); return; }
   if (!m.working && !m.confirming && !host.contains(host.getRootNode().activeElement)) {
    try { const answer = await ctx.action('share_state', {language: ctx.lang}); if (m.gen === mine) { m.answeredAt = Date.now(); set(answer?.share || null); } } catch (e) { if (!m.view && m.gen === mine) set(null); }
   }
   if (m.gen === mine) m.timer = setTimeout(look, REFRESH_MS);
  };
  paint();
  clearTimeout(m.timer);
  // a new draw looks at once only when there is no answer yet; else when 30 s since the last answer are over (a redraw that changes nothing asks the Hub nothing)
  m.timer = setTimeout(look, Number.isFinite(m.answeredAt) ? Math.max(0, REFRESH_MS - (Date.now() - m.answeredAt)) : 0);
  return host;
 }
 return {shareCard};
};

(window.OpenThermostatSettingsParts ||= {})["installation_share"] = {build, texts: TEXTS, errors: ERRORS};
window.dispatchEvent(new CustomEvent('openthermostat-settings-part', {detail: "installation_share"}));

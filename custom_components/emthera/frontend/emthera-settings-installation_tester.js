/* Installation, part Tester program (TESTER-P2, a wizard since TESTER-P2c): the one run in Home Assistant for today's boilers, as ten
   steps on a phone, one screen and one main action at the bottom each: take part (the consent with the recording's own tick), before
   you start (the readiness check), heating, hot water, the boiler's display, the type-plate photo, the boiler test, set back and
   wait (what is still open, everything the Hub has seen), what will be sent (the whole file on request) and saved. The run itself is tester_run.py; this module only draws its model (live.run) and calls its actions
   (settings_tester.py). Loaded by the panel with the other section modules (settings.SECTION_MODULES); it hands its screen to
   its section through window.OpenThermostatSettingsParts, and the section registers once it is here. */
const TEXTS = {
 nl: {
  'Take part in the tester program': 'Meedoen met het testerprogramma',
  'Take part': 'Meedoen',
  'It takes about half an hour. Read what you agree to first.': 'Het duurt ongeveer een half uur. Lees eerst waar je mee instemt.',
  'It takes about half an hour. Read what you agree to first. Then you choose whether the recording is part of it.': 'Het duurt ongeveer een half uur. Lees eerst waar je mee instemt. Daarna kies je of de opname erbij hoort.',
  'It takes about half an hour. Have these at hand:': 'Het duurt ongeveer een half uur. Leg dit klaar:',
  'The boiler within reach, to read its display and type plate': 'De ketel binnen handbereik, om zijn display en typeplaatje te lezen',
  'A hot water tap you can open': 'Een warmwaterkraan die je kunt openen',
  'Your phone, for one photo of the type plate': 'Je telefoon, voor één foto van het typeplaatje',
  'Start': 'Begin',
  'Tap "{button}": it starts the recording. Do the next steps while it runs.': 'Tik op "{button}": dat start de opname. Doe de volgende stappen terwijl die loopt.',
  'Tap "{button}" to begin your run. Do the next steps while it goes on.': 'Tik op "{button}" om je run te beginnen. Doe de volgende stappen terwijl hij loopt.',
  'The Hub is ready': 'De Hub is klaar',
  'This must be right first': 'Dit moet eerst kloppen',
  'Your run has started. This is what you needed.': 'Je run is gestart. Dit had je nodig.',
  'Next': 'Volgende',
  'Previous step': 'Vorige stap',
  'Step {n} of {total}': 'Stap {n} van {total}',
  'Heating': 'Verwarmen',
  'Turn the thermostat up so the boiler starts heating.': 'Zet de thermostaat omhoog zodat de ketel gaat verwarmen.',
  'Hot water': 'Warm water',
  'Open a hot tap for two minutes.': 'Open twee minuten een warmwaterkraan.',
  'The Hub has not read the boiler yet.': 'De Hub heeft de ketel nog niet gelezen.',
  'Save and go on': 'Bewaar en ga verder',
  'Go on without answering': 'Ga verder zonder antwoord',
  'The type plate': 'Het typeplaatje',
  'Go on without a photo': 'Ga verder zonder foto',
  'Take one photo of your boiler\'s type plate.': 'Maak één foto van het typeplaatje van je ketel.',
  'Go on without the test': 'Ga verder zonder de test',
  'Only waiting helps': 'Alleen wachten helpt',
  'The Hub has seen the boiler heat.': 'De Hub heeft de ketel zien verwarmen.',
  'The Hub has seen the boiler make hot water.': 'De Hub heeft de ketel warm water zien maken.',
  'You turned the thermostat up, {when}.': 'Je hebt de thermostaat omhoog gezet, {when}.',
  'You opened a hot water tap, {when}.': 'Je hebt een warmwaterkraan opengezet, {when}.',
  'You set everything back, {when}.': 'Je hebt alles teruggezet, {when}.',
  'after {n} minutes': 'na {n} minuten', 'after 1 minute': 'na 1 minuut', 'within the first minute': 'binnen de eerste minuut',
  'Without a photo your report cannot count as tested. You can still send it.': 'Zonder foto kan je melding niet als getest meetellen. Je kunt hem wel nog versturen.',
  'The photo you chose': 'De foto die je koos',
  'Set back and wait': 'Terugzetten en wachten',
  'Set everything back as it was, and close the tap.': 'Zet alles terug zoals het was en sluit de kraan.',
  'You may close this screen. The recording goes on without it.': 'Je mag dit scherm sluiten. De opname loopt ook zonder dit scherm door.',
  'Go to step {n}': 'Ga naar stap {n}',
  'Your report will lack:': 'Je melding mist dan:',
  'Finishing cannot be undone: the recording stops.': 'Afronden kun je niet terugdraaien: de opname stopt.',
  'Finish anyway': 'Toch afronden',
  'Go back': 'Ga terug',
  'What will be sent': 'Wat er verstuurd wordt',
  'Saved': 'Bewaard',
  'Back to Installation': 'Terug naar Installatie',
  'This stops the recording and deletes this run and its files. You start again from step 1.': 'Dit stopt de opname en verwijdert deze run en zijn bestanden. Je begint weer bij stap 1.',
  'Stop and delete': 'Stoppen en wissen',
  'Yes, stop and delete': 'Ja, stop en wis',
  'No, go on': 'Nee, ga verder',
  'You can switch it off here at any time.': 'Je kunt het hier altijd weer uitzetten.',
  'Switching it off removes the run and its files from Home Assistant.': 'Uitzetten verwijdert de run en zijn bestanden uit Home Assistant.',
  'The tester program is on.': 'Het testerprogramma staat aan.',
  'The tester program is off. Its run and its files are removed from Home Assistant.': 'Het testerprogramma staat uit. De run en zijn bestanden zijn uit Home Assistant verwijderd.',
  'The run could not be read just now. Check that the Hub is on, then open this page again.': 'De run kon nu niet gelezen worden. Controleer of de Hub aan staat en open deze pagina dan opnieuw.',
  'Yes, I take part': 'Ja, ik doe mee', 'No, never mind': 'Nee, laat maar',
  'Before you start': 'Voor je begint',
  'Seen: {seen} of {total}': 'Gezien: {seen} van {total}',
  'What helps now': 'Wat nu helpt',
  'What the Hub has seen': 'Wat de Hub heeft gezien',
  'Seen': 'Gezien', 'Still open': 'Nog open', 'Seen, but not believable': 'Gezien maar niet geloofwaardig',
  'Recording: {minutes} {minutes:minute|minutes} recorded; {needed} are needed.': 'Opname loopt: {minutes} {minutes:minuut|minuten} opgenomen; er zijn er {needed} nodig.',
  'Recording: {minutes} {minutes:minute|minutes} recorded, which is enough.': 'Opname loopt: {minutes} {minutes:minuut|minuten} opgenomen, dat is genoeg.',
  'No recording on this run: your report will be marked incomplete.': 'Geen opname in deze run: je melding wordt als onvolledig gemarkeerd.',
  'The Hub could not be reached just now. The run waits; it continues when the Hub answers.': 'De Hub was nu niet te bereiken. De run wacht en gaat door zodra de Hub antwoordt.',
  'I turned the thermostat up': 'Ik heb de thermostaat omhoog gezet',
  'A hot water tap is open': 'Een warmwaterkraan staat open',
  'I set everything back': 'Ik heb alles teruggezet',
  'The boiler display': 'Het display van de ketel',
  'Is there a code on the boiler\'s display now? Never cause a fault for this: just tell us what it shows.': 'Staat er nu een code op het display van de ketel? Veroorzaak hier nooit een storing voor: vertel alleen wat het toont.',
  'What does the display show?': 'Wat toont het display?',
  'A code': 'Een code', 'A temperature': 'Een temperatuur', 'A code and a temperature': 'Een code en een temperatuur',
  'Nothing, it is dark': 'Niets, het is donker', 'This boiler has no display': 'Deze ketel heeft geen display',
  'The code (one to three characters)': 'De code (één tot drie tekens)',
  'The temperature in degrees': 'De temperatuur in graden',
  'Your country (optional)': 'Je land (niet verplicht)', 'Not telling': 'Zeg ik niet',
  'Answer saved.': 'Antwoord bewaard.',
  'Needed to count as tested, not needed to send. You may cover the serial number. What a phone adds to a photo (where, when, which camera) is removed before it is kept, and the original is never kept.': 'Nodig om als getest te tellen, niet om te versturen. Het serienummer mag je afdekken. Wat een telefoon aan een foto toevoegt (waar, wanneer, welke camera) wordt verwijderd voordat hij bewaard wordt, en het origineel wordt nooit bewaard.',
  'Take or choose a photo': 'Maak of kies een foto', 'Choose another photo': 'Kies een andere foto', 'Remove the photo': 'Haal de foto weg',
  'Photo kept: {kb} KB, without its hidden data.': 'Foto bewaard: {kb} KB, zonder verborgen gegevens.',
  'No photo yet.': 'Nog geen foto.',
  'The boiler test': 'De keteltest',
  'Start the boiler test': 'Start de keteltest',
  'The run does not make its own test: it reads the one the Hub keeps. The test opens on the Hub\'s own page.': 'De run maakt geen eigen test: hij leest de test die de Hub bewaart. De test opent op de eigen pagina van de Hub.',
  'Finish': 'Afronden',
  'Finish stops the recording and shows everything that will be sent. Nothing is sent yet.': 'Afronden stopt de opname en toont alles wat er verstuurd wordt. Er wordt nog niets verstuurd.',
  'This run ends by itself in about {h} hours if it is not finished.': 'Deze run stopt vanzelf over ongeveer {h} uur als hij niet is afgerond.',
  'Not complete yet. What is missing:': 'Nog niet compleet. Wat er mist:',
  'Show the whole file': 'Toon het hele bestand',
  'Hide the file': 'Verberg het bestand',
  'Save the file': 'Bewaar het bestand',
  'Open the public form': 'Open het openbare formulier',
  'Save it as incomplete': 'Bewaar het als onvolledig',
  'Saving keeps the files in Home Assistant for {days} days. You send the file yourself; Home Assistant sends nothing.': 'Als je bewaart, blijven de bestanden {days} dagen in Home Assistant staan. Jij stuurt het bestand zelf; Home Assistant verstuurt niets.',
  'Your report is saved': 'Je melding is bewaard',
  'Your report is saved as incomplete': 'Je melding is bewaard als onvolledig',
  'The file is private: send it by hand as you agreed. These links need your sign-in and stop working after {min} minutes (reopen this page for new ones). The files are removed from Home Assistant after {days} days; {left} days are left.': 'Het bestand is privé: stuur het met de hand zoals afgesproken. Deze links vragen je aanmelding en werken {min} minuten (open deze pagina opnieuw voor nieuwe). De bestanden worden na {days} dagen uit Home Assistant verwijderd; ze blijven nog {left} dagen staan.',
  'One thing would complete it: {action}': 'Eén ding maakt hem compleet: {action}',
  'All in one file': 'Alles in één bestand', 'The report': 'De melding', 'The recording': 'De opname', 'The photo': 'De foto',
  'Your report id is {id}. Quote it if you ever want your report deleted.': 'Het id van je melding is {id}. Noem het als je je melding ooit wilt laten wissen.',
  'Your tester code is {code}. It stays the same for this installation.': 'Je testercode is {code}. Hij blijft gelijk voor deze installatie.',
  'New tester code': 'Nieuwe testercode',
  'Remove the files now': 'Verwijder de bestanden nu',
  'Start a new run': 'Start een nieuwe run',
  'The run ended by itself': 'De run is vanzelf gestopt',
  'The tester program is off. Switch it on first.': 'Het testerprogramma staat uit. Zet het eerst aan.',
  'That is not possible at this step of the run. Open this page again.': 'Dat kan niet in deze stap van de run. Open deze pagina opnieuw.',
  'Tick that you understand and take part first.': 'Vink eerst aan dat je het begrijpt en meedoet.',
  'The Hub is not ready for a run yet. Read the list at the top, fix the first thing and try again.': 'De Hub is nog niet klaar voor een run. Lees de lijst bovenaan, los het eerste op en probeer het opnieuw.',
  'That answer is not valid. Try again.': 'Dat antwoord is niet geldig. Probeer het opnieuw.',
  'Type the one to three characters the display shows (letters, digits, - or similar).': 'Typ de één tot drie tekens die het display toont (letters, cijfers, - of iets dergelijks).',
  'Type the temperature in whole degrees, from 0 to 100.': 'Typ de temperatuur in hele graden, van 0 tot 100.',
  'That file is not a photo Home Assistant can use. Choose a photo (JPEG) of the type plate.': 'Dat bestand is geen foto die Home Assistant kan gebruiken. Kies een foto (JPEG) van het typeplaatje.',
  'That photo is too large. Take it again at a lower quality or choose another.': 'Die foto is te groot. Maak hem opnieuw in lagere kwaliteit of kies een andere.',
  'The summary could not be read from the Hub. Check that the Hub is on and try again.': 'De samenvatting kon niet van de Hub gelezen worden. Controleer of de Hub aan staat en probeer het opnieuw.',
  'Home Assistant could not write the files. Check that its configuration folder has free space, then try again.': 'Home Assistant kon de bestanden niet schrijven. Controleer of de configuratiemap ruimte vrij heeft en probeer het opnieuw.',
  'Only an administrator can run this.': 'Alleen een beheerder kan dit uitvoeren.',
  'The Hub\'s own page has a tester run going. Finish or delete it there first, then start here.': 'De eigen pagina van de Hub heeft een testerrun lopen. Rond die daar eerst af of verwijder hem en begin dan hier.',
  'The Hub is already recording a run. Finish or delete it first, or wait until it ends by itself, then try again.': 'De Hub neemt al een run op. Rond die eerst af of verwijder hem, of wacht tot hij vanzelf stopt, en probeer het dan opnieuw.',
  'The Hub was busy for a moment. Try again.': 'De Hub was even bezig. Probeer het opnieuw.',
  'The Hub has no connection to your boiler to read. Check the boiler cable, then open this page again.': 'De Hub heeft geen verbinding met je ketel om te lezen. Controleer de ketelkabel en open deze pagina dan opnieuw.'
 }
};
const ERRORS = {
 tester_off: 'The tester program is off. Switch it on first.',
 tester_run_state: 'That is not possible at this step of the run. Open this page again.',
 tester_consent_needed: 'Tick that you understand and take part first.',
 tester_not_ready: 'The Hub is not ready for a run yet. Read the list at the top, fix the first thing and try again.',
 tester_input_invalid: 'That answer is not valid. Try again.',
 tester_display_code: 'Type the one to three characters the display shows (letters, digits, - or similar).',
 tester_display_temp: 'Type the temperature in whole degrees, from 0 to 100.',
 tester_photo_unreadable: 'That file is not a photo Home Assistant can use. Choose a photo (JPEG) of the type plate.',
 tester_photo_too_large: 'That photo is too large. Take it again at a lower quality or choose another.',
 tester_summary_unreadable: 'The summary could not be read from the Hub. Check that the Hub is on and try again.',
 tester_share_not_written: 'Home Assistant could not write the files. Check that its configuration folder has free space, then try again.',
 tester_hub_run_owns: 'The Hub\'s own page has a tester run going. Finish or delete it there first, then start here.',
 tester_run_elsewhere: 'The Hub is already recording a run. Finish or delete it first, or wait until it ends by itself, then try again.',
 tester_hub_busy: 'The Hub was busy for a moment. Try again.',
 tester_no_link: 'The Hub has no connection to your boiler to read. Check the boiler cable, then open this page again.'
};


/* The wizard's table: which step shows what the Hub has seen (rule id -> step). Every rule of the format has exactly ONE step
   (a test fails otherwise: ha/tests_native/test_tester_wizard_steps.py). Step 3 heating, 4 hot water, 5 the display, 6 the photo,
   7 the boiler test, 8 everything else (the recording, the boiler's values, plausibility, the messages), where all of them show together. */
const RULE_STEP = {
 phase_heating: 3, ot_heating_values: 3,
 phase_hot_water: 4, ot_hot_water_values: 4,
 display_typed: 5, display_matches_ems: 5, display_matches_ot: 5,
 photo_declared: 6, photo_clean: 6,
 tested_run_classic: 7, tested_run_plus: 7, tested_run_ot: 7,
 consent: 8, link_known: 8, software_versions: 8, software_versions_ot: 8, identity_ems: 8, identity_ot: 8,
 recording_chosen: 8, recording_length: 8, telegrams_classic: 8, telegrams_plus_reports: 8, settings_answered: 8, frames_clean: 8,
 plausible_ems: 8, phase_rest: 8, devices_listed: 8, fields_read: 8, extra_telegrams: 8, limit_read_ems: 8, active_days: 8,
 marks_plausible: 8, claims_consistent: 8, files_match: 8,
 ot_config: 8, ot_support: 8, ot_values: 8, ot_rest_values: 8, ot_fault_recorded: 8, ot_limit: 8, ot_line: 8, ot_log: 8
};
const STEPS_TOTAL = 10;

// What the section shares with this part comes in once, when the section registers.
const build = ({ERRORS: errors, notice, actions, bar, upload, errorText}) => {
 const COUNTRIES = ['NL', 'BE', 'DE', 'LU', 'FR', 'GB', 'IE', 'AT', 'CH', 'IT', 'ES', 'PL', 'DK', 'SE', 'NO', 'FI', 'CZ'];
 const DISPLAY = [['code', 'A code'], ['temperature', 'A temperature'], ['code_and_temperature', 'A code and a temperature'],
  ['dark', 'Nothing, it is dark'], ['no_display', 'This boiler has no display']];
 const MARKS = {heat_up: 'I turned the thermostat up', hot_water: 'A hot water tap is open', restored: 'I set everything back'};
 const TONE = {seen: 'ok', open: 'rest', untrusted: 'attention'};
 const STATE = {seen: 'Seen', open: 'Still open', untrusted: 'Seen, but not believable'};
 const TITLES = {1: 'Take part', 2: 'Before you start', 3: 'Heating', 4: 'Hot water', 5: 'The boiler display', 6: 'The type plate',
  7: 'The boiler test', 8: 'Set back and wait', 9: 'What will be sent', 10: 'Saved'};
 // The screen's own state outlives a redraw of the page; it is per page view (one entry, one tester).
 const local = {consent: false, recording: true, display: null, code: '', temp: '', country: '', file: false, working: false, error: null, run: null, timer: null, note: null,
  intro: 1, view: null, serverStep: undefined, navBusy: 0, navSeq: 0, shown: null, focus: false, confirm: null, preview: null};

 const mmss = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
 const stepOf = id => RULE_STEP[id] ?? 8;

 function tester(ctx) {
  const {kit, t, model: m} = ctx, {h} = kit;
  const live = m.live || {};
  if (live.run !== local.model) { local.model = live.run; local.run = live.run; local.error = null; if (live.run?.state !== 'intro') { local.consent = false; } }
  const root = h('div', {class: 'it', 'data-part': 'tester'}, h('style', {text: STYLE}));
  const switchCard = kit.card({cls: 'form'}, h('div', {class: 'fields'}, ctx.field('toggle', 'tester_enabled', {label: t('Take part in the tester program'),
   help: t('You can switch it off here at any time.'), more: t('Switching it off removes the run and its files from Home Assistant.')})));
  const body = h('div', {class: 'it-body', 'data-run': local.run?.state || 'none'});
  root.append(switchCard, body);
  if (live.done === 'switched_on') root.insertBefore(h('div', {class: 'iv-done', 'data-done': 'switched_on'}, notice(ctx, t('The tester program is on.'), 'info')), switchCard);
  if (live.done === 'tester_switched_off') root.insertBefore(h('div', {class: 'iv-done', 'data-done': 'tester_switched_off'},
   notice(ctx, t('The tester program is off. Its run and its files are removed from Home Assistant.'), 'info')), switchCard);
  if (!m.tester_enabled) return root;
  const redraw = () => {
   body.setAttribute('data-run', local.run?.state || 'none');
   body.replaceChildren(...draw(ctx));
   // The switch stands only where there is no run: before the run (step 1), when it ended, or when it could not be read.
   const r = local.run;
   switchCard.style.display = !r || r.state === 'ended' || (r.state === 'intro' && local.intro === 1) ? '' : 'none';
   if (local.focus) {
    local.focus = false;
    root.scrollIntoView?.({block: 'start'});
    body.querySelector('[data-step-title]')?.focus({preventScroll: true});
   }
  };
  local.redraw = redraw;
  local.body = body;
  redraw();
  follow(ctx, body);
  return root;
 }

 // The run answers every action with its model; the page draws from that. A poll keeps the live list moving.
 async function call(ctx, name, values = {}) {
  local.working = true; local.error = null; local.redraw?.();
  try {
   const answer = await ctx.action(name, {...values, language: ctx.lang});
   if (answer?.run) { local.run = answer.run; }
  } catch (e) { local.error = e?.text || errorText(ctx, e); }
  local.working = false; local.redraw?.();
  return local.error === null;
 }
 function follow(ctx, body) {
  if (local.timer) return;
  const step = async () => {
   local.timer = null;
   if (!body.isConnected) return;
   const state = local.run?.state;
   if (state === 'recording' || state === 'summary' || state === 'saved' || state === 'intro') {
    if (!local.working && !busyField(body)) {
     const seq = local.navSeq;
     try {
      const answer = await ctx.action('tester_state', {language: ctx.lang});
      if (answer?.run && !local.working && seq === local.navSeq) { local.run = answer.run; local.redraw?.(); }
     } catch (e) { /* the next look tries again */ }
    }
    local.timer = setTimeout(step, state === 'recording' ? 15000 : 30000);
   }
  };
  local.timer = setTimeout(step, 15000);
 }
 // A control the tester is using is never redrawn under his fingers.
 const busyField = body => body.contains(body.getRootNode().activeElement) && ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON', 'A'].includes(body.getRootNode().activeElement?.tagName);

 // Going to another step: shown at once, remembered with the run (a running recording) so any device lands on it.
 function go(ctx, n) {
  local.confirm = null; local.error = null; local.navSeq++;
  if (local.run?.state === 'intro') { local.intro = n; local.redraw(); return; }
  local.view = n;
  if (local.run?.state !== 'recording') { local.redraw(); return; }
  local.navBusy++;  // while a move is on its way the page keeps the step the tester chose, not the one the run still holds
  local.redraw();
  ctx.action('tester_step', {step: n, language: ctx.lang}).then(a => { if (a?.run && local.navBusy === 1) local.run = a.run; }).catch(() => {})
   .finally(() => { local.navBusy--; });
 }
 // The step on show: the page's own before the run starts; the run's step while it records (or the one the tester went to); then the state's.
 function stepNow(run) {
  if (run.state === 'intro') return local.intro;
  if (run.state === 'summary') return 9;
  if (run.state === 'saved') return 10;
  if (!local.navBusy && run.step !== local.serverStep) { local.serverStep = run.step; local.view = run.step; }
  return Math.min(8, Math.max(2, local.view ?? run.step ?? 3));
 }

 function draw(ctx) {
  const {kit, t} = ctx, {h} = kit, run = local.run, out = [];
  if (!run) return [notice(ctx, t('The run could not be read just now. Check that the Hub is on, then open this page again.'), 'warning')];
  if (local.error) out.push(notice(ctx, local.error, 'error'));
  if (ctx.readOnly) out.push(h('p', {class: 'help', text: ctx.t('Only an administrator can run this.')}));
  if (run.state === 'ended') return [...out, ...ended(ctx, run)];
  if (run.state !== local.lastState) { local.lastState = run.state; local.confirm = null; if (run.state === 'intro') { local.intro = 1; local.view = null; local.serverStep = undefined; } }
  const n = stepNow(run);
  if (n !== local.shown) { local.shown = n; local.focus = true; }
  const step = STEP[n](ctx, run, n);
  out.push(header(ctx, run, n));
  out.push(h('h2', {class: 'it-step-title', tabindex: '-1', 'data-step-title': String(n), text: t(TITLES[n])}));
  const stopping = local.confirm === 'restart';
  if (step.intro && !stopping) out.push(h('p', {class: 'it-step-intro', text: step.intro}));
  const finishing = local.confirm === 'finish' && n === 8 && lacking(run).length > 0;
  if (stopping) out.push(restartRow(ctx));   // the stop question stands alone, as the finish question does
  else if (finishing) out.push(lackingCard(ctx, run));   // what the report will lack, then two buttons
  else out.push(...step.content);
  if (!finishing && !stopping && (run.state === 'recording' || run.state === 'summary')) out.push(restartRow(ctx));
  out.push(finishing ? bottom(ctx, kit.button(t('Finish anyway'), () => call(ctx, 'tester_finish'), 'filled', {'data-action': 'finish-anyway', disabled: ctx.readOnly || local.working}),
    kit.button(t('Go back'), () => { local.confirm = null; local.redraw(); }, 'text', {'data-action': 'finish-back'}))
   : local.confirm === 'restart' ? bottom(ctx) : bottom(ctx, step.main, ...(step.quiet || [])));
  return out;
 }

 /* ---- the frame every step shares: where you are, the way back, the recording's clock, the way to stop ---- */
 function header(ctx, run, n) {
  const {kit, t} = ctx, {h} = kit;
  const back = (n >= 3 && n <= 8) || (n === 2 && run.state === 'intro')
   ? kit.button(t('Previous step'), () => go(ctx, n - 1), 'text', {'data-action': 'back', class: 'btn text it-back'}) : null;
  const counter = t('Step {n} of {total}', {n, total: STEPS_TOTAL});
  const out = [h('div', {class: 'it-head'}, back, h('span', {class: 'it-count', 'data-step': String(n), text: counter})),
   h('div', {class: 'it-progress', role: 'progressbar', 'aria-valuemin': '1', 'aria-valuemax': String(STEPS_TOTAL), 'aria-valuenow': String(n), 'aria-label': counter},
    h('span', {style: `width:${n * 100 / STEPS_TOTAL}%`}))];
  if (run.state === 'recording' && n >= 3 && n !== 8) out.push(clock(ctx, run));
  return h('div', {class: 'it-top'}, ...out);
 }
 function clock(ctx, run) {
  const {kit, t} = ctx, rec = run.recording || {};
  const line = !rec.chosen ? t('No recording on this run: your report will be marked incomplete.') : recordingLine(t, rec);
  const enough = rec.chosen && Math.floor((rec.seconds || 0) / 60) >= (rec.needed_min || 25);
  return kit.statusLine(line, enough ? 'ok' : rec.chosen && rec.state === 'recording' ? 'heat' : 'rest');
 }
 function recordingLine(t, rec) {
  const minutes = Math.floor((rec.seconds || 0) / 60), needed = rec.needed_min || 25;
  const say = (text, vars) => t(text, vars).replace(/\{(\w+):([^{}|:]*)\|([^{}|:]*)\}/g, (m, k, one, other) => (vars[k] === 1 ? one : other));   // `{minutes:minute|minutes}`: the first word at exactly 1
  return minutes >= needed ? say('Recording: {minutes} {minutes:minute|minutes} recorded, which is enough.', {minutes})
   : say('Recording: {minutes} {minutes:minute|minutes} recorded; {needed} are needed.', {minutes, needed});
 }
 // The quiet way to stop and delete the run, with its question inside the page.
 function restartRow(ctx) {
  const {kit, t} = ctx, {h} = kit;
  if (local.confirm === 'restart') return kit.card({cls: 'it-confirm', data: {part: 'confirm-restart'}},
   h('p', {class: 'it-confirm-text', role: 'alert', text: t('This stops the recording and deletes this run and its files. You start again from step 1.')}));
  return h('div', {class: 'it-stop'}, kit.button(t('Stop and delete'), () => { local.confirm = 'restart'; local.redraw(); }, 'text', {'data-action': 'restart-ask', disabled: ctx.readOnly || local.working}));
 }
 // The bar at the bottom: the one main action and at most one quiet one; the question of "Start over" takes its place while it is asked.
 function bottom(ctx, main, ...quiet) {
  const {kit, t} = ctx, {h} = kit;
  if (local.confirm === 'restart') return h('div', {class: 'it-bar', 'data-part': 'bar'}, kit.button(t('No, go on'), () => { local.confirm = null; local.redraw(); }, 'filled', {'data-action': 'restart-no'}),
   kit.button(t('Yes, stop and delete'), () => call(ctx, 'tester_restart'), 'text', {'data-action': 'restart', disabled: ctx.readOnly || local.working}));
  return h('div', {class: 'it-bar', 'data-part': 'bar'}, main, ...quiet.filter(Boolean));
 }
 const next = (ctx, to, label) => ctx.kit.button(label || ctx.t('Next'), () => go(ctx, to), 'filled', {'data-action': 'next', disabled: ctx.readOnly});

 /* ---- the evidence: one thing the Hub has seen, drawn on the step it belongs to ---- */
 function item(ctx, i, jump, plain) {
  const {kit, t} = ctx, {h} = kit;
  return h('li', {class: 'it-item', 'data-state': i.state, 'data-rule': i.id}, kit.chip(t(STATE[i.state]), TONE[i.state], i.state === 'seen' ? 'check' : i.state === 'untrusted' ? 'alert' : 'clock'),
   h('div', {class: 'it-item-body'}, plain ? null : h('strong', {text: i.title}), h('span', {class: 'it-text', text: i.text}), i.action ? h('span', {class: 'it-do', text: i.action}) : null,
    jump ? kit.button(t('Go to step {n}', {n: jump}), () => go(ctx, jump), 'text', {'data-action': 'jump', 'data-jump': String(jump)}) : null));
 }
 // What is still open, grouped by the step it belongs to: one entry and one jump per step; what only waiting brings (step 8's own rules)
 // is one entry without a jump.
 function openGroups(open) {
  const groups = [];
  for (const i of open) {
   const key = i.step < 8 ? i.step : 'wait';
   let g = groups.find(x => x.key === key);
   if (!g) { g = {key, items: []}; groups.push(g); }
   g.items.push(i);
  }
  return groups.sort((a, b) => (a.key === 'wait' ? 99 : a.key) - (b.key === 'wait' ? 99 : b.key));
 }
 function openEntry(ctx, g) {
  const {kit, t} = ctx, {h} = kit, jump = g.key === 'wait' ? null : g.key;
  const lines = [...new Set(g.items.map(i => i.action || i.text))];
  const firstLine = jump ? [lines[0]] : lines;   // a step's own entry says its one action; the waiting entry says each thing it waits for
  const untrusted = g.items.every(i => i.state === 'untrusted');
  return h('li', {class: 'it-item it-open-item', 'data-step': String(g.key), 'data-rules': g.items.map(i => i.id).join(' '), 'data-jumpable': jump ? '1' : null},
   h('div', {class: 'it-item-body'}, h('strong', {text: jump ? t(TITLES[jump]) : t('Only waiting helps')}),
    ...firstLine.map(x => h('span', {class: untrusted ? 'it-text' : 'it-do', text: x}))),
   jump ? kit.button(t('Go to step {n}', {n: jump}), () => go(ctx, jump), 'text', {'data-action': 'jump', 'data-jump': String(jump)}) : null);
 }
 // What the Hub has seen on this step. `after`: the step's own thing is done (an answer, a photo, a test); before it a step shows no open item,
 // only its question. `said`: the Hub's own sentence for a rule that is seen (steps 3 and 4), instead of the rule's.
 function seenHere(ctx, run, n, {after = true, said = null} = {}) {
  const {kit, t} = ctx, {h} = kit, ev = run.evidence;
  if (!after) return null;
  if (!ev) return kit.statusLine(t('The Hub has not read the boiler yet.'), 'rest');
  const items = ev.items.filter(i => stepOf(i.id) === n);
  const seen = said && items.find(i => i.id === said[0] && i.state === 'seen');
  const rest = items.filter(i => i !== seen);
  const out = [];
  if (seen) out.push(kit.statusLine(t(said[1]), 'ok'));
  if (rest.length) out.push(h('ul', {class: 'it-items', 'data-part': 'seen-here'}, ...rest.map(i => item(ctx, i, null, true))));
  return out.length ? h('div', {class: 'it-seen'}, ...out) : null;
 }
 // The moment, as a button until it is tapped; afterwards a plain line with a tick that says when.
 const DONE = {heat_up: 'You turned the thermostat up, {when}.', hot_water: 'You opened a hot water tap, {when}.', restored: 'You set everything back, {when}.'};
 function markCard(ctx, run, kind) {
  const {kit, t} = ctx, {h} = kit, label = MARKS[kind], at = run.marks?.[kind];
  if (at != null) {
   const minutes = Math.floor(at / 60);
   const when = minutes < 1 ? t('within the first minute') : minutes === 1 ? t('after 1 minute') : t('after {n} minutes', {n: minutes});
   return kit.card({cls: 'it-moments', data: {part: 'moments'}}, h('p', {class: 'it-done', 'data-tone': 'ok', 'data-mark': kind, 'data-done': String(at)}, kit.icon('check', {size: 22}), h('span', {text: t(DONE[kind], {when})})));
  }
  return kit.card({cls: 'it-moments', data: {part: 'moments'}}, kit.button(t(label), () => call(ctx, 'tester_mark', {kind}), 'outlined',
   {class: 'btn outlined it-mark', 'data-mark': kind, disabled: ctx.readOnly || local.working}));
 }

 /* ---- step 1 and 2: take part, then what you need and the readiness ---- */
 function step1(ctx, run) {
  const {kit, t} = ctx, {h} = kit, c = run.consent, ot = run.link === 'opentherm';   // an OpenTherm run always has its log: no tick of its own
  const text = kit.card({title: c.title, cls: 'it-consent', data: {part: 'consent', version: c.version}}, h('p', {text: c.intro}),
   ...c.paragraphs.map(p => h('div', {class: 'it-para', 'data-para': p.id}, h('strong', {text: p.title}), h('p', {text: p.text}))));
  const consent = kit.fields.toggle({key: 'it-consent', hass: ctx.hass, label: c.tick, value: local.consent, disabled: ctx.readOnly || local.working,
   onChange: v => { local.consent = v; local.redraw(); }});
  // What happens without the recording is told BEFORE its tick is asked.
  const recording = kit.card({cls: 'it-recording', data: {part: 'recording-choice'}}, h('p', {class: 'it-without', text: c.recording_without}),
   kit.fields.toggle({key: 'it-recording', hass: ctx.hass, label: c.recording_tick, value: local.recording && run.recording_available !== false,
    disabled: ctx.readOnly || local.working || run.recording_available === false, onChange: v => { local.recording = v; }}).el);
  const content = [text, kit.card({cls: 'form'}, h('div', {class: 'fields'}, consent.el))];
  if (!ot) content.push(recording);
  if (!local.consent) content.push(h('p', {class: 'help it-why', 'data-part': 'why', text: t('Tick that you understand and take part first.')}));
  return {intro: ot ? t('It takes about half an hour. Read what you agree to first.') : t('It takes about half an hour. Read what you agree to first. Then you choose whether the recording is part of it.'), content,
   main: kit.button(t('Yes, I take part'), () => go(ctx, 2), 'filled', {'data-action': 'agree', disabled: ctx.readOnly || !local.consent || local.working}),
   quiet: [kit.button(t('No, never mind'), () => ctx.act({tester_enabled: false}), 'text', {'data-action': 'no', disabled: ctx.readOnly})]};
 }
 function step2(ctx, run) {
  const {kit, t} = ctx, {h} = kit, started = run.state !== 'intro';
  const needs = kit.card({cls: 'it-needs', data: {part: 'needs'}}, h('ul', {class: 'it-lines'}, ...['The boiler within reach, to read its display and type plate', 'A hot water tap you can open', 'Your phone, for one photo of the type plate'].map(x => h('li', {text: t(x)}))));
  if (started) return {intro: t('Your run has started. This is what you needed.'), content: [needs], main: next(ctx, 3)};
  const ready = kit.card({title: run.readiness.blocking ? t('This must be right first') : t('The Hub is ready'), cls: 'it-ready', data: {part: 'readiness'}},
   ...run.readiness.items.map(i => kit.statusLine(i.text, i.ok ? 'ok' : (i.id === 'hub' || run.readiness.blocking && i.id === 'boiler') ? 'error' : 'attention')));
  const content = [needs, ready];
  if (run.readiness.blocking) content.push(h('p', {class: 'help it-why', 'data-part': 'why', text: t('The Hub is not ready for a run yet. Read the list at the top, fix the first thing and try again.')}));
  else content.push(h('p', {class: 'help', 'data-part': 'start-hint'}, run.link !== 'opentherm' && local.recording && run.recording_available !== false
   ? t('Tap "{button}": it starts the recording. Do the next steps while it runs.', {button: t('Start')}) : t('Tap "{button}" to begin your run. Do the next steps while it goes on.', {button: t('Start')})));
  return {intro: t('It takes about half an hour. Have these at hand:'), content,
   main: kit.button(t('Start'), () => call(ctx, 'tester_start', {recording: run.link === 'opentherm' || (local.recording && run.recording_available !== false), consent: true}), 'filled',
    {'data-action': 'start', disabled: ctx.readOnly || !local.consent || local.working || run.readiness.blocking})};
 }

 /* ---- steps 3 and 4: heating and hot water, each with its moment and what the Hub saw ---- */
 const step3 = (ctx, run) => ({intro: ctx.t('Turn the thermostat up so the boiler starts heating.'), content: [markCard(ctx, run, 'heat_up'), seenHere(ctx, run, 3, {said: ['phase_heating', 'The Hub has seen the boiler heat.']})].filter(Boolean), main: next(ctx, 4)});
 const step4 = (ctx, run) => ({intro: ctx.t('Open a hot tap for two minutes.'), content: [markCard(ctx, run, 'hot_water'), seenHere(ctx, run, 4, {said: ['phase_hot_water', 'The Hub has seen the boiler make hot water.']})].filter(Boolean), main: next(ctx, 5)});

 /* ---- step 5: what the boiler's display shows ---- */
 function step5(ctx, run) {
  const {kit, t} = ctx, {h} = kit, d = run.display || {};
  if (local.display === null) { local.display = d.state && d.state !== 'not_asked' ? d.state : 'code'; local.code = d.code || ''; local.temp = d.temp == null ? '' : String(d.temp); local.country = run.country || ''; }
  const answered = !!(d.state && d.state !== 'not_asked');
  const needsCode = ['code', 'code_and_temperature'].includes(local.display), needsTemp = ['temperature', 'code_and_temperature'].includes(local.display);
  const fields = [kit.fields.radio({key: 'it-display', hass: ctx.hass, label: t('What does the display show?'), value: local.display, disabled: ctx.readOnly,
   options: DISPLAY.map(([value, label]) => ({value, label: t(label)})), onChange: v => { local.display = v; local.redraw(); }}).el];
  if (needsCode) fields.push(kit.fields.text({key: 'it-code', hass: ctx.hass, label: t('The code (one to three characters)'), value: local.code, maxlength: 3, disabled: ctx.readOnly,
   onChange: v => { local.code = v; }}).el);
  if (needsTemp) fields.push(kit.fields.number({key: 'it-temp', hass: ctx.hass, label: t('The temperature in degrees'), value: local.temp, min: 0, max: 100, step: 1, unit: '°C', disabled: ctx.readOnly,
   onChange: v => { local.temp = v == null ? '' : String(v); }}).el);
  fields.push(kit.fields.select({key: 'it-country', hass: ctx.hass, label: t('Your country (optional)'), value: local.country, disabled: ctx.readOnly,
   options: [{value: '', label: t('Not telling')}, ...COUNTRIES.map(c => ({value: c, label: c}))], onChange: v => { local.country = v; }}).el);
  const save = async () => { if (await call(ctx, 'tester_display', {state: local.display, code: needsCode ? local.code : null, temp: needsTemp && local.temp !== '' ? Number(local.temp) : null,
   country: local.country || null})) go(ctx, 6); };
  return {intro: t('Is there a code on the boiler\'s display now? Never cause a fault for this: just tell us what it shows.'),
   content: [kit.card({cls: 'form it-display', data: {part: 'display'}}, h('div', {class: 'fields'}, ...fields),
    answered ? h('p', {class: 'it-saved', text: t('Answer saved.')}) : null), seenHere(ctx, run, 5, {after: answered})].filter(Boolean),
   main: kit.button(t('Save and go on'), save, 'filled', {'data-action': 'display', disabled: ctx.readOnly || local.working}),
   quiet: [kit.button(t('Go on without answering'), () => go(ctx, 6), 'text', {'data-action': 'skip', disabled: ctx.readOnly})]};
 }

 /* ---- step 6: the photo of the type plate ---- */
 // The phone's photo, written again in the browser (a canvas keeps none of its hidden data and turns it upright); the server
 // writes it again once more and checks it. A browser that cannot do it sends the original: the server still cleans it.
 async function recode(file) {
  try {
   const bitmap = await createImageBitmap(file, {imageOrientation: 'from-image'});
   const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height)), canvas = document.createElement('canvas');
   canvas.width = Math.max(1, Math.round(bitmap.width * scale)); canvas.height = Math.max(1, Math.round(bitmap.height * scale));
   canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
   const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.85));
   return blob ? new File([blob], 'plate.jpg', {type: 'image/jpeg'}) : file;
  } catch (e) { return file; }
 }
 const forget = () => { if (local.preview) { try { URL.revokeObjectURL(local.preview); } catch (e) { /* none */ } local.preview = null; } };
 function step6(ctx, run) {
  const {kit, t} = ctx, {h} = kit, p = run.photo;
  const input = h('input', {type: 'file', accept: 'image/jpeg,image/png,image/webp,image/heic,image/heif', hidden: true, 'data-file': 'photo', capture: 'environment'});
  input.addEventListener('change', async () => {
   const file = input.files?.[0];
   if (!file) return;
   local.working = true; local.error = null; local.redraw();
   try {
    const clean = await recode(file);
    const id = await upload(ctx.hass, clean);
    const answer = await ctx.action('tester_photo', {upload_id: id, language: ctx.lang});
    if (answer?.run) { local.run = answer.run; forget(); try { local.preview = URL.createObjectURL(clean); } catch (e) { local.preview = null; } }
   } catch (e) { local.error = e?.text || errorText(ctx, e); }
   local.working = false; local.redraw();
  });
  const pick = () => input.click();
  const card = kit.card({cls: 'it-photo', data: {part: 'photo'}},
   h('p', {class: 'help', text: t('Needed to count as tested, not needed to send. You may cover the serial number. What a phone adds to a photo (where, when, which camera) is removed before it is kept, and the original is never kept.')}),
   p && local.preview ? h('img', {class: 'it-preview', src: local.preview, alt: t('The photo you chose')}) : null,
   p ? h('p', {class: 'it-saved', text: t('Photo kept: {kb} KB, without its hidden data.', {kb: Math.max(1, Math.round(p.bytes / 1024))})}) : h('p', {class: 'it-saved', text: t('No photo yet.')}),
   !p ? h('p', {class: 'help', 'data-part': 'photo-cost', text: t('Without a photo your report cannot count as tested. You can still send it.')}) : null,
   p ? actions(ctx, kit.button(t('Choose another photo'), pick, 'outlined', {'data-action': 'photo-again', disabled: ctx.readOnly || local.working}),
    kit.button(t('Remove the photo'), async () => { forget(); await call(ctx, 'tester_photo_remove'); }, 'text', {'data-action': 'photo-remove', disabled: ctx.readOnly || local.working})) : null, input);
  // Without a photo the thing we want is the main action; going on without one is the quiet second action.
  return {intro: t('Take one photo of your boiler\'s type plate.'), content: [card, seenHere(ctx, run, 6, {after: !!p})].filter(Boolean),
   main: p ? next(ctx, 7) : kit.button(t('Take or choose a photo'), pick, 'filled', {'data-action': 'photo', disabled: ctx.readOnly || local.working}),
   quiet: p ? [] : [kit.button(t('Go on without a photo'), () => go(ctx, 7), 'text', {'data-action': 'next', disabled: ctx.readOnly})]};
 }

 /* ---- step 7: the boiler test ---- */
 function step7(ctx, run) {
  const {kit, t} = ctx, {h} = kit, tested = !!run.test && run.test.state !== 'none';
  const openTest = async () => {
   try { const answer = await ctx.action('tester_test_page', {}); if (answer?.url) window.open(answer.url, '_blank', 'noopener'); } catch (e) { local.error = e?.text || ''; local.redraw(); }
  };
  return {content: [kit.card({cls: 'it-test', data: {part: 'test', test: run.test?.state || 'none'}}, h('p', {text: run.test?.text || ''}),
   h('p', {class: 'help', text: t('The run does not make its own test: it reads the one the Hub keeps. The test opens on the Hub\'s own page.')})), seenHere(ctx, run, 7, {after: tested})].filter(Boolean),
   main: tested ? next(ctx, 8) : kit.button(t('Start the boiler test'), openTest, 'filled', {'data-action': 'test', disabled: ctx.readOnly}),
   quiet: tested ? [] : [kit.button(t('Go on without the test'), () => go(ctx, 8), 'text', {'data-action': 'next', disabled: ctx.readOnly})]};
 }

 /* ---- step 8: set back, wait, what is still open, everything the Hub has seen ---- */
 // What the report will lack if it is finished now: every thing on the Hub's list that is still open or not believable.
 function lacking(run) {
  return (run.evidence?.items || []).filter(i => i.state !== 'seen').map(i => ({id: i.id, title: i.title, text: i.text, action: i.action, step: stepOf(i.id), state: i.state}));
 }
 function lackingCard(ctx, run) {
  const {kit, t} = ctx, {h} = kit;
  return kit.card({title: t('Your report will lack:'), cls: 'it-lacking', data: {part: 'lacking'}}, h('ul', {class: 'it-items'}, ...lacking(run).map(i =>
   h('li', {class: 'it-item', 'data-rule': i.id}, h('div', {class: 'it-item-body'}, h('strong', {text: i.title}), h('span', {class: 'it-text', text: i.text}))))),
   h('p', {class: 'help', text: t('Finishing cannot be undone: the recording stops.')}));
 }
 function step8(ctx, run) {
  const {kit, t} = ctx, {h} = kit, ev = run.evidence, rec = run.recording || {};
  const minutes = Math.floor((rec.seconds || 0) / 60), needed = rec.needed_min || 25;
  const progress = kit.card({cls: 'it-wait', data: {part: 'wait'}}, clock(ctx, run),
   rec.chosen ? h('div', {class: 'it-progress it-rec', role: 'progressbar', 'aria-valuemin': '0', 'aria-valuemax': String(needed), 'aria-valuenow': String(Math.min(minutes, needed)),
    'aria-label': t('The recording')}, h('span', {style: `width:${Math.min(100, minutes * 100 / needed)}%`})) : null,
   h('p', {class: 'help', text: t('You may close this screen. The recording goes on without it.')}),
   h('p', {class: 'help', text: t('Finish stops the recording and shows everything that will be sent. Nothing is sent yet.')}),
   h('p', {class: 'help', text: t('This run ends by itself in about {h} hours if it is not finished.', {h: run.abandon_in_h ?? 24})}));
  const open = lacking(run), groups = openGroups(open);
  const lead = open.some(i => i.action === run.next) ? null : h('p', {class: 'it-next-text', text: run.next || ''});
  const todo = kit.card({title: t('What helps now'), cls: 'it-next', data: {part: 'next'}}, lead,
   groups.length ? h('ul', {class: 'it-items it-open', 'data-open': groups.length}, ...groups.map(g => openEntry(ctx, g))) : null);
  const all = ev ? kit.fold({key: 'it-all', title: t('What the Hub has seen'), summary: t('Seen: {seen} of {total}', {seen: ev.seen, total: ev.total}), open: local.allOpen === true, onToggle: on => { local.allOpen = on; }},
   h('ul', {class: 'it-items', 'data-part': 'all'}, ...ev.items.map(i => item(ctx, i)))) : kit.card({title: t('What the Hub has seen'), cls: 'it-list', data: {part: 'evidence'}}, kit.statusLine(t('The Hub has not read the boiler yet.'), 'rest'));
  const finish = () => { if (lacking(run).length) { local.confirm = 'finish'; local.redraw(); } else call(ctx, 'tester_finish'); };
  const notices = run.sample_failed ? [notice(ctx, t('The Hub could not be reached just now. The run waits; it continues when the Hub answers.'), 'warning')] : [];
  return {intro: t('Set everything back as it was, and close the tap.'), content: [markCard(ctx, run, 'restored'), progress, ...notices, todo, all],
   main: kit.button(t('Finish'), finish, 'filled', {'data-action': 'finish', disabled: ctx.readOnly || local.working})};
 }

 /* ---- step 9: everything that will be sent ---- */
 function step9(ctx, run) {
  const {kit, t} = ctx, {h} = kit, s = run.summary, content = [];
  if (!s) return {content: [notice(ctx, errorText(ctx, {code: 'tester_summary_unreadable'}), 'warning')], main: null};
  content.push(notice(ctx, s.headline, s.complete ? 'success' : 'warning'));
  if (s.missing.length) content.push(kit.card({title: t('Not complete yet. What is missing:'), cls: 'it-missing', data: {part: 'missing'}},
   h('ul', {class: 'it-items'}, ...s.missing.map(i => h('li', {class: 'it-item', 'data-rule': i.id, 'data-state': 'open'}, kit.chip(t('Still open'), 'rest', 'clock'),
    h('div', {class: 'it-item-body'}, h('strong', {text: i.title}), h('span', {class: 'it-text', text: i.text}), h('span', {class: 'it-do', text: i.action})))))));
  content.push(kit.card({cls: 'it-sent', data: {part: 'sent'}}, h('ul', {class: 'it-lines'}, ...s.lines.map(l => h('li', {text: l}))),
   h('ul', {class: 'it-files'}, ...s.files.map(f => h('li', {'data-file-kind': f.kind, text: `${f.name} (${Math.max(1, Math.round(f.bytes / 1024))} KB)`}))),
   local.file ? h('pre', {class: 'it-file', 'data-part': 'file', text: s.file_text}) : null,
   kit.button(local.file ? t('Hide the file') : t('Show the whole file'), () => { local.file = !local.file; local.redraw(); }, 'text', {'data-action': 'file'})));
  content.push(h('p', {class: 'help', text: t('Saving keeps the files in Home Assistant for {days} days. You send the file yourself; Home Assistant sends nothing.', {days: run.bounds.keep_days})}));
  content.push(h('p', {class: 'help it-form-note', text: s.form_note}));
  return {content, main: kit.button(s.complete ? t('Save the file') : t('Save it as incomplete'), () => call(ctx, 'tester_save'), 'filled', {'data-action': 'save', disabled: ctx.readOnly || local.working}),
   quiet: [kit.button(t('Open the public form'), () => window.open(s.form_url, '_blank', 'noopener'), 'outlined', {'data-action': 'form', disabled: local.working})]};
 }

 /* ---- step 10: saved: the links (signed, short-lived), what stays and for how long ---- */
 function step10(ctx, run) {
  const {kit, t} = ctx, {h} = kit, s = run.saved, content = [];
  content.push(notice(ctx, s.complete ? t('Your report is saved') : t('Your report is saved as incomplete'), s.complete ? 'success' : 'warning'));
  if (!s.complete && s.first_action) content.push(h('p', {class: 'it-next-text', text: t('One thing would complete it: {action}', {action: s.first_action})}));
  const names = {all: 'All in one file', report: 'The report', recording: 'The recording', photo: 'The photo'};
  content.push(kit.card({title: t('Save the file'), cls: 'it-files-card', data: {part: 'files'}},
   s.files.length ? h('div', {class: 'it-links'}, ...s.files.map(f => h('a', {class: 'btn ' + (f.kind === 'all' ? 'filled' : 'outlined'), href: f.url || '#', download: f.name, 'data-file-kind': f.kind,
    text: `${t(names[f.kind])} (${f.name.replace(/^boiler-share-/, '')})`}))) : null,
   h('p', {class: 'help', text: t('The file is private: send it by hand as you agreed. These links need your sign-in and stop working after {min} minutes (reopen this page for new ones). The files are removed from Home Assistant after {days} days; {left} days are left.',
    {min: run.bounds.link_min, days: run.bounds.keep_days, left: s.days_left})}),
   h('p', {class: 'help', text: t('Your report id is {id}. Quote it if you ever want your report deleted.', {id: s.report_id})}),
   run.tester_code ? h('p', {class: 'help', text: t('Your tester code is {code}. It stays the same for this installation.', {code: run.tester_code})}) : null));
  content.push(h('p', {class: 'help it-form-note', text: s.form_note}));
  content.push(h('div', {class: 'it-quiet'}, kit.button(t('Remove the files now'), () => call(ctx, 'tester_restart'), 'text', {'data-action': 'remove', disabled: ctx.readOnly || local.working}),
   kit.button(t('New tester code'), () => call(ctx, 'tester_new_code'), 'text', {'data-action': 'new-code', disabled: ctx.readOnly || local.working})));
  return {content, main: kit.button(t('Back to Installation'), () => ctx.navigate('#installation'), 'outlined', {'data-action': 'done'})};
 }
 const STEP = {1: step1, 2: step2, 3: step3, 4: step4, 5: step5, 6: step6, 7: step7, 8: step8, 9: step9, 10: step10};

 function ended(ctx, run) {
  const {kit, t} = ctx;
  return [notice(ctx, run.ended?.text || t('The run ended by itself'), 'info'), actions(ctx, kit.button(t('Start a new run'), () => call(ctx, 'tester_restart'), 'filled', {'data-action': 'again', disabled: ctx.readOnly || local.working}))];
 }

 const STYLE = `.it{display:grid;gap:var(--ot-s3);max-width:640px;width:100%;margin-inline:auto}.it-body{display:grid;gap:var(--ot-s3);align-content:start}.it .help{margin:0}
.it-top{display:grid;gap:var(--ot-s2)}.it-head{display:flex;align-items:center;gap:var(--ot-s2);min-height:var(--ot-touch)}.it-count{margin-left:auto;color:var(--ot-muted);font-size:var(--ot-text-s)}
.it-progress{height:4px;border-radius:2px;overflow:hidden;background:color-mix(in srgb,var(--ot-accent) 18%,var(--ot-surface))}.it-progress>span{display:block;height:100%;border-radius:2px;background:var(--ot-fill)}
.it-rec{margin-top:var(--ot-s2)}.ot-card.it-photo,.ot-card.it-test,.ot-card.it-wait,.ot-card.it-moments,.ot-card.it-needs,.ot-card.it-next,.ot-card.it-files-card,.ot-card.it-sent,.ot-card.it-display,.ot-card.it-missing{display:grid;gap:var(--ot-s2);align-content:start}
.it-open-item{grid-template-columns:1fr auto;align-items:center;justify-items:stretch;gap:var(--ot-s2)}.it-open-item .btn{min-height:var(--ot-touch)}.it-open-item .it-item-body{gap:var(--ot-s1)}
.it-step-title{margin:var(--ot-s2) 0 0;font-size:var(--ot-text-xl);line-height:var(--ot-line-xl);font-weight:500;outline:0}.it-step-intro{margin:0;font-size:var(--ot-text-l);line-height:var(--ot-line-l);overflow-wrap:anywhere}
.it-quiet{display:flex;justify-content:flex-start}.it-confirm-text{margin:0;overflow-wrap:anywhere}
.it-bar{position:sticky;bottom:0;z-index:3;display:grid;gap:var(--ot-s2);padding:var(--ot-s3) 0 calc(var(--ot-s3) + env(safe-area-inset-bottom,0px));background:var(--ot-bg);border-top:1px solid var(--ot-divider)}.it-bar .btn{width:100%}
.it-preview{display:block;max-width:100%;max-height:220px;margin:0 auto var(--ot-s2);border-radius:var(--ot-radius-s);object-fit:contain}
.it-para{display:grid;gap:2px;margin-top:var(--ot-s3)}.it-para p{margin:0;overflow-wrap:anywhere}.it-without{margin:0 0 var(--ot-s2);font-weight:500}
.it-next-text{margin:0;font-size:var(--ot-text-l);line-height:var(--ot-line-l);overflow-wrap:anywhere}
.it-items{display:grid;gap:var(--ot-s2);margin:0;padding:0;list-style:none}
.it-item{display:grid;grid-template-columns:1fr;justify-items:start;gap:var(--ot-s2);padding:var(--ot-s2) 0;border-top:1px solid var(--ot-divider)}.it-item:first-child{border-top:0}
.it-item-body{display:grid;gap:2px;min-width:0;justify-self:stretch;justify-items:start}.it-item-body strong{font-weight:500}.it-text,.it-do{overflow-wrap:anywhere}.it-do{color:var(--ot-muted)}
.it-mark{min-height:56px;width:100%;justify-content:flex-start;text-align:left}
.it-done{display:flex;align-items:center;gap:var(--ot-s2);margin:0}.it-done .ot-icon{flex:none;color:var(--ot-tone-ink)}.it-seen{display:grid;gap:var(--ot-s2)}
.it-stop{display:flex;justify-content:flex-start;margin-top:var(--ot-s5)}.it-stop .btn{padding-left:0;font-size:var(--ot-text-s);color:var(--ot-muted)}
.it-lines{display:grid;gap:var(--ot-s2);margin:0;padding-left:20px}.it-lines li{overflow-wrap:anywhere}.it-files{margin:var(--ot-s3) 0 0;padding-left:20px;color:var(--ot-muted);font-size:var(--ot-text-s)}
.it-file{margin:var(--ot-s3) 0 0;padding:var(--ot-s3);max-height:360px;overflow:auto;border:1px solid var(--ot-divider);border-radius:var(--ot-radius-s);background:var(--ot-surface);font-size:var(--ot-text-s);white-space:pre-wrap;overflow-wrap:anywhere}
.it-links{display:grid;gap:var(--ot-s2)}.it-links .btn{width:100%;justify-content:flex-start;text-decoration:none;overflow-wrap:anywhere;text-align:left}
.it-saved{margin:var(--ot-s2) 0 0;color:var(--ot-muted);font-size:var(--ot-text-s)}.it-form-note{margin:0}
.it input[type=text],.it input[type=number],.it select{font-size:16px}`;

 return {tester};
};

(window.OpenThermostatSettingsParts ||= {})["installation_tester"] = {build, texts: TEXTS, errors: ERRORS, ruleStep: RULE_STEP};
window.dispatchEvent(new CustomEvent('openthermostat-settings-part', {detail: "installation_tester"}));

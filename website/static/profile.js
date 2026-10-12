(() => {
  const get = id => document.getElementById(id);
  let account = null;
  let sessionLoading = null;
  const modButton = document.createElement('button');
  modButton.type = 'button'; modButton.textContent = 'Moderator'; modButton.hidden = true;
  document.getElementById('nav-links').append(modButton);
  const modDialog = document.createElement('main');
  modDialog.id = 'moderator-page'; modDialog.hidden = true;
  modDialog.className = 'mod-dashboard mod-page';
  const make = (tag, text) => {const el = document.createElement(tag); if (text) el.textContent = text; return el;};
  const modHeader = make('div'); modHeader.className = 'profile-heading';
  const modClose = make('button', 'Back to home'); modClose.type = 'button';
  modHeader.append(make('h2','Moderator dashboard'), modClose);
  modClose.addEventListener('click',()=>{location.hash = 'home';});
  const modStatus = make('p'); modStatus.setAttribute('role','status');
  const modActions = make('div'); modActions.className = 'mod-actions';
  const searchLabel = make('label','Find player'); searchLabel.className = 'profile-field';
  const search = make('input'); search.type = 'search'; searchLabel.append(search);
  const playerLabel = make('label','Player'); playerLabel.className = 'profile-field';
  const playerSelect = make('select'); playerLabel.append(playerSelect);
  const ratingForm = make('form');
  const ratingFields = make('div'); ratingFields.className = 'mod-ratings';
  const inputs = {};
  const fineRatings = {};
  ['Top','Jungle','Mid','ADC','Support'].forEach(role=>{
    const label = make('label',role === 'ADC' ? 'Bot' : role); label.className = 'profile-field';
    const input = make('select'); input.required = true;
    const fine = make('input'); fine.type = 'number'; fine.min = '0'; fine.max = '10000'; fine.step = '1'; fine.required = true;
    fine.setAttribute('aria-label', (role === 'ADC' ? 'Bot' : role) + ' exact rating');
    input.addEventListener('change',()=>{fine.value = input.value;});
    fine.addEventListener('input',()=>{input.value = [...input.options].some(option=>option.value === fine.value) ? fine.value : '';});
    input.required = false;
    fineRatings[role] = fine;
    inputs[role] = input; label.append(input, fine); ratingFields.append(label);
  });
  const saveRatings = make('button','Save ratings'); saveRatings.type = 'submit'; saveRatings.className = 'button button--primary';
  ratingForm.append(ratingFields, saveRatings);
  const queueSection = make('section');
  queueSection.append(make('h3','Active queue'), modActions);
  const modQueueList = make('div'); queueSection.append(modQueueList);
  const playerSection = make('section');
  playerSection.append(make('h3','Signup player ratings'), searchLabel, playerLabel, ratingForm);
  const modLayout = make('div'); modLayout.className = 'mod-layout'; modLayout.append(queueSection, playerSection);
  const accountSection = make('section'); accountSection.className = 'mod-accounts';
  const accountHeading = make('h3','Website accounts');
  const accountSearchLabel = make('label','Find website account'); accountSearchLabel.className = 'profile-field';
  const accountSearch = make('input'); accountSearch.type = 'search'; accountSearchLabel.append(accountSearch);
  const accountList = make('div');
  accountSection.append(accountHeading, accountSearchLabel, accountList); modLayout.append(accountSection);
  function renderAccounts() {
    const accounts = modData?.accounts || [];
    accountHeading.textContent = 'Website accounts (' + accounts.length + ')';
    accountList.replaceChildren();
    const query = accountSearch.value.trim().toLowerCase();
    const matches = accounts.filter(a=>[a.name,a.id,a.signup_name || ''].some(value=>value.toLowerCase().includes(query)));
    matches.forEach(account=>{
      const row = make('div'); row.className = 'mod-account-row';
      const identity = make('div'); identity.append(make('strong',account.name),make('small',account.id));
      row.append(identity,make('span',account.signup_completed ? 'Signup complete / ' + account.signup_name : 'Website only / Signup pending'));
      accountList.append(row);
    });
    if (!matches.length) accountList.append(make('p',accounts.length ? 'No matching accounts.' : 'No website accounts yet.'));
  }
  accountSearch.addEventListener('input',renderAccounts);
  modDialog.append(modHeader, modStatus, modLayout);
  document.getElementById('homepage').before(modDialog);
  let modData = null;
  let modBusy = false;
  function renderModQueue() {
    modQueueList.replaceChildren();
    const queue = modData?.queue;
    if (!queue) return;
    [['players','Queued players'],['waitlist','Waitlist']].forEach(([key,title])=>{
      modQueueList.append(make('h4',title + ' (' + queue[key].length + ')'));
      queue[key].forEach(player=>{
        const row = make('div'); row.className = 'mod-queue-row';
        row.append(make('span',player.name + ' / ' + player.rank + (queue.deadline && key === 'players' ? player.ready ? ' / Ready' : ' / Waiting' : '')));
        const remove = make('button','Remove'); remove.type = 'button'; remove.className = 'button';
        remove.disabled = key === 'players' && queue.locked;
        remove.addEventListener('click',()=>{if (confirm('Remove ' + player.name + ' from the queue?')) modRequest({action:'remove',player_id:player.id});});
        row.append(remove); modQueueList.append(row);
      });
    });
  }
  function showPlayer() {
    const player = modData?.players.find(p=>p.id === playerSelect.value);
    Object.entries(inputs).forEach(([role,input])=>{
      input.replaceChildren();
      const current = player?.ratings[role];
      const options = modData?.rating_options || [];
      if (current != null && !options.some(option=>option.value === current)) {
        const option = make('option','Current rating - ' + current); option.value = current; input.append(option);
      }
      options.forEach(item=>{const option = make('option',item.label + ' - ' + item.value); option.value = item.value; input.append(option);});
      input.value = current ?? ''; input.disabled = !player;
      fineRatings[role].value = current ?? ''; fineRatings[role].disabled = !player;
    });
    saveRatings.disabled = !player;
  }
  function filterPlayers() {
    const previous = playerSelect.value;
    playerSelect.replaceChildren();
    (modData?.players || []).filter(p=>p.name.toLowerCase().includes(search.value.toLowerCase()) || p.id.includes(search.value)).forEach(p=>{
      const option = make('option', p.name + ' / ' + p.rank + ' / ' + p.rating); option.value = p.id; playerSelect.append(option);
    });
    if ([...playerSelect.options].some(o=>o.value === previous)) playerSelect.value = previous;
    showPlayer();
  }
  search.addEventListener('input',filterPlayers); playerSelect.addEventListener('change',showPlayer);
  async function modRequest(body) {
    if (modBusy) return;
    modBusy = true;
    modDialog.querySelectorAll('button').forEach(b=>{if (b !== modClose) b.disabled = true;});
    try {
      const response = await fetch('/api/mod', body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:AbortSignal.timeout(20000)} : {cache:'no-store',signal:AbortSignal.timeout(20000)});
      if (!response.ok) throw Error(await response.text());
      modData = await response.json(); filterPlayers(); renderModQueue(); renderAccounts();
      modStatus.textContent = (body ? 'Saved. ' : '') + (modData.queue.locked ? 'Game in progress.' : modData.queue.active ? 'Queue active.' : 'No active queue.');
      modButton.hidden = false;
      if (body) await refreshQueue();
    } catch(error) {modStatus.textContent = error.message || 'Dashboard unavailable.'; if (!body) {modData = null; modButton.hidden = true; modLayout.hidden = true;}}
    finally {modBusy = false; modActions.querySelectorAll('button').forEach(b=>b.disabled = false); showPlayer();}
  }
  [['start','Start queue'],['cancel','Cancel queue']].forEach(([action,title])=>{
    const button = make('button',title); button.type = 'button'; button.className = 'button';
    button.addEventListener('click',()=>{
      if (action === 'cancel' && !confirm('Cancel the queue and clear every queued and waitlisted player?')) return;
      modRequest({action});
    }); modActions.append(button);
  });
  ratingForm.addEventListener('submit',event=>{
    event.preventDefault();
    if (!playerSelect.value || modBusy) return;
    modRequest({action:'rating',player_id:playerSelect.value,ratings:Object.fromEntries(Object.entries(fineRatings).map(([role,input])=>[role,Number(input.value)]))});
  });
  function routeModerator() {
    modDialog.hidden = location.hash !== '#moderator';
    if (!modDialog.hidden) {
      get('homepage').hidden = true; get('standings-page').hidden = true;
      modLayout.hidden = !modData;
      if (account?.authenticated) modRequest().then(()=>{modLayout.hidden = !modData;});
      else modStatus.textContent = 'Sign in with your moderator Discord account to access this page.';
    }
  }
  modButton.addEventListener('click',()=>{location.hash = 'moderator';});
  window.addEventListener('hashchange',routeModerator);
  setInterval(()=>{if (!modDialog.hidden && modData && !modDialog.contains(document.activeElement)) modRequest();},15000);
  const avoidedField = document.createElement('label');
  avoidedField.className = 'profile-field';
  avoidedField.textContent = 'Avoided role (optional)';
  const avoidedSelect = document.createElement('select');
  avoidedSelect.id = 'profile-avoided';
  ['None','Top','Jungle','Mid','Bot','Support'].forEach(role => {
    const option = document.createElement('option');
    option.value = role; option.textContent = role;
    avoidedSelect.append(option);
  });
  avoidedField.append(avoidedSelect);
  document.querySelector('.profile-role-fields').after(avoidedField);
  let queueState = null;
  let statusBusy = false;
  let actionBusy = false;
  let shownReadyDeadline = null;
  const readySound = new Audio('/static/ready-check.mp3');
  readySound.preload = 'auto';
  let pendingReadySound = false;
  async function playReadySound() {
    try {
      readySound.currentTime = 0;
      await readySound.play();
      pendingReadySound = false;
    } catch {pendingReadySound = true;}
  }
  function unlockReadySound() {
    if (pendingReadySound && queueState?.ready_check && !queueState.confirmed) {
      playReadySound();
    } else {
      pendingReadySound = false;
      readySound.muted = true;
      const playback = readySound.play();
      if (playback) playback.then(()=>{
        readySound.pause(); readySound.currentTime = 0; readySound.muted = false;
      }).catch(()=>{readySound.muted = false;});
    }
  }
  document.addEventListener('pointerdown', unlockReadySound, {once:true});
  document.addEventListener('keydown', unlockReadySound, {once:true});
  const readyDialog = document.createElement('dialog');
  readyDialog.className = 'queue-ready-dialog';
  const readyTitle = document.createElement('h2');
  readyTitle.textContent = 'Your lobby is ready';
  const readyCopy = document.createElement('p');
  readyCopy.textContent = 'All 10 players must confirm within 5 minutes or the queue is canceled.';
  const readyTimer = document.createElement('p');
  const popupReady = document.createElement('button');
  popupReady.type = 'button'; popupReady.className = 'button button--primary'; popupReady.textContent = "I'm ready";
  const dismissReady = document.createElement('button');
  dismissReady.type = 'button'; dismissReady.className = 'button'; dismissReady.textContent = 'Close';
  readyDialog.append(readyTitle, readyCopy, readyTimer, popupReady, dismissReady);
  document.body.append(readyDialog);
  popupReady.addEventListener('click', () => readyButton.click());
  dismissReady.addEventListener('click', () => readyDialog.close());
  const statusLine = document.createElement('p');
  statusLine.className = 'queue-personal-status';
  document.querySelector('.queue-panel').append(statusLine);
  const readyButton = document.createElement('button');
  readyButton.type = 'button'; readyButton.className = 'button button--primary';
  readyButton.textContent = "I'm ready"; readyButton.hidden = true;
  const queueButton = document.createElement('button');
  queueButton.type = 'button';
  queueButton.className = 'button button--primary';
  queueButton.textContent = 'Join queue';
  const queueFooter = document.querySelector('.queue-panel .panel-foot');
  queueFooter.querySelector('a').replaceWith(queueButton);
  const leaveButton = document.createElement('button');
  leaveButton.type = 'button';
  leaveButton.className = 'button';
  leaveButton.textContent = 'Leave queue';
  queueFooter.append(leaveButton);
  queueFooter.append(readyButton);
  function notify(message) {
    if ('Notification' in window && Notification.permission === 'granted') {
      try {new Notification('PCL queue', {body:message, icon:'/pcl-logo.png'});} catch {}
    }
  }
  function paintStatus() {
    const s = queueState;
    queueButton.hidden = !!(s?.queued || s?.waitlist_position);
    leaveButton.hidden = !(s?.queued || s?.waitlist_position);
    queueButton.disabled = actionBusy || (!!account?.authenticated && (!s || !s.signed_up || !s.active));
    leaveButton.disabled = actionBusy || !!(s?.queued && s.locked);
    readyButton.hidden = !s?.ready_check;
    readyButton.disabled = actionBusy || !!s?.confirmed;
    readyButton.textContent = s?.confirmed ? 'Ready confirmed' : "I'm ready";
    const deadline = s?.ready_check ? s.deadline : s?.expires;
    const seconds = deadline ? Math.max(0, Math.ceil(deadline - Date.now()/1000)) : null;
    const timer = seconds === null ? '' : ' / ' + Math.floor(seconds/60) + ':' + String(seconds%60).padStart(2,'0') + (s.ready_check ? ' to confirm' : ' until expiry');
    popupReady.disabled = actionBusy;
    readyTimer.textContent = s?.ready_check ? timer.replace(' / ', '') : '';
    if (!s?.ready_check || s.confirmed) {
      pendingReadySound = false;
      if (readyDialog.open) readyDialog.close();
    } else if (shownReadyDeadline !== s.deadline) {
      shownReadyDeadline = s.deadline;
      readyDialog.showModal();
      playReadySound();
    }
    statusLine.textContent = !account?.authenticated ? 'Sign in to join the queue.' : !s ? 'Queue connection unavailable. Retrying...' : !s.signed_up ? 'Complete /signup in Discord to join.' : s.ready_check ? (s.confirmed ? 'You are ready.' : 'Your lobby is ready. Confirm below.') + timer : s.queued ? (s.locked ? 'You are in the game.' : "You're queued.") + timer : s.waitlist_position ? 'Waitlist position: ' + s.waitlist_position + timer : !s.active ? 'No active queue. Start one in Discord.' : 'You can join the queue.' + timer;
    document.querySelectorAll('.queue-user').forEach(row => row.classList.remove('is-current-player'));
    const lists = document.querySelectorAll('#queue-display .queue-list');
    const row = s?.queued ? lists[0]?.children[s.player_index] : s?.waitlist_position ? lists[1]?.children[s.waitlist_position-1] : null;
    row?.classList.add('is-current-player');
  }
  async function refreshStatus() {
    if (statusBusy) return;
    if (!account?.authenticated) {queueState = null; paintStatus(); return;}
    statusBusy = true;
    try {
      const response = await fetch('/api/queue/me', {cache:'no-store', signal:AbortSignal.timeout(10000)});
      if (!response.ok) throw Error();
      const next = await response.json();
      if (queueState && !queueState.ready_check && next.ready_check) notify('Your lobby is ready. Confirm your ready check.');
      if (queueState?.waitlist_position && next.queued) notify('You have been promoted from the waitlist.');
      queueState = next;
    } catch {queueState = null;}
    finally {statusBusy = false; paintStatus();}
  }
  readyButton.addEventListener('click', async () => {
    actionBusy = true; paintStatus();
    try {
      const response = await fetch('/api/queue/ready', {method:'POST', signal:AbortSignal.timeout(10000)});
      if (!response.ok) throw Error(await response.text());
      await refreshStatus();
    } catch(error) {statusLine.textContent = error.message || 'Could not confirm. Please retry.';}
    finally {actionBusy = false; paintStatus();}
  });
  window.addEventListener('beforeunload', event => {
    if (queueState?.ready_check && !queueState.confirmed) {event.preventDefault();event.returnValue = '';}
  });
  setInterval(refreshStatus, 5000);
  setInterval(paintStatus, 1000);
  document.addEventListener('visibilitychange', () => {if (!document.hidden) refreshStatus();});
  leaveButton.addEventListener('click', async () => {
    await load();
    if (!account?.authenticated) {await open(); return;}
    actionBusy = true;
    queueButton.disabled = leaveButton.disabled = true;
    try {
      const response = await fetch('/api/queue/leave', {method:'POST'});
      if (!response.ok) throw new Error(await response.text());
      get('queue-updated').textContent = 'You have left the queue.';
      await refreshQueue();
    } catch (error) {
      get('queue-updated').textContent = error.message || 'Could not leave. Please retry.';
    } finally {actionBusy = false; paintStatus();}
  });
  async function refreshQueue() {
    try {
      const response = await fetch('/api/voice', {cache:'no-store'});
      if (response.ok && typeof renderVoice === 'function') renderVoice(await response.json());
    } catch {}
    await refreshStatus();
  }
  queueButton.addEventListener('click', async () => {
    await load();
    if (!account?.authenticated) {await open(); return;}
    actionBusy = true;
    queueButton.disabled = leaveButton.disabled = true;
    try {
      const response = await fetch('/api/queue/join', {method:'POST'});
      if (!response.ok) throw new Error(await response.text());
      const result = await response.json();
      get('queue-updated').textContent = result.position.startsWith('waitlist') ? 'You are on the waitlist.' : 'You are in the queue.';
      await refreshQueue();
    } catch (error) {
      get('queue-updated').textContent = error.message || 'Could not join. Please retry.';
    } finally {actionBusy = false; paintStatus();}
  });
  const note = document.querySelector('.profile-draft-note');
  const authLink = document.createElement('a');
  authLink.href = '/auth/discord'; authLink.className = 'button button--primary';
  authLink.textContent = 'Sign in with Discord';
  note.after(authLink);
  get('profile-reset').textContent = 'Sign out';
  const connections = document.querySelectorAll('.profile-connections span');
  function display() {
    const signedIn = !!account?.authenticated;
    const synced = !!account?.signup_completed;
    note.textContent = synced ? 'Synced with Discord. Role changes here update your signup and primary Discord role.' : signedIn ? 'Signed in with Discord. Complete /signup in Discord to join the league.' : 'Sign in with Discord to create your PCL website profile.';
    authLink.hidden = signedIn;
    authLink.textContent = account?.login_available ? 'Sign in with Discord' : 'Discord sign-in awaiting setup';
    authLink.setAttribute('aria-disabled', String(!account?.login_available));
    ['profile-primary','profile-secondary','profile-avoided'].forEach(id => {get(id).disabled = !signedIn;});
    get('profile-name').disabled = !signedIn || synced;
    get('profile-reset').disabled = !signedIn;
    get('profile-form').querySelector('[type="submit"]').disabled = !signedIn;
    connections[0].textContent = signedIn ? 'Linked: ' + account.identity.name : 'Not linked';
    connections[1].textContent = 'Not linked';
    const saved = account?.preferences || {};
    get('profile-name').value = saved.name || account?.identity?.name || '';
    get('profile-primary').value = saved.primary || '';
    get('profile-secondary').value = saved.secondary || '';
    get('profile-avoided').value = saved.avoided || 'None';
    get('saved-role-summary').textContent = signedIn
      ? (saved.primary ? 'Primary: ' + saved.primary + ' / Secondary: ' + saved.secondary + (account.player ? ' / ' + account.player.rank + ' / ' + account.player.rating + ' MMR' : '') : 'Choose your roles in My profile.')
      : 'Sign in with Discord to save your role preferences.';
    document.querySelectorAll('.role-choice').forEach(button => button.classList.toggle('is-selected', button.dataset.role === saved.primary));
    document.querySelectorAll('.profile-open').forEach(button => {if (button.closest('nav')) button.textContent = signedIn ? 'My profile' : 'Sign in';});
  }
  async function loadSession() {
    try {
      const response = await fetch('/api/profile', {cache:'no-store', credentials:'same-origin', signal:AbortSignal.timeout(10000)});
      if (!response.ok) throw Error();
      account = await response.json();
    } catch {
      // A temporary connection failure should not erase a known session.
      return;
    }
    display();
    await refreshStatus();
    if (account?.authenticated && !modData) await modRequest();
    if (!account?.authenticated) {modData = null; modButton.hidden = true; modLayout.hidden = true;}
    routeModerator();
  }
  function load() {
    if (!sessionLoading) sessionLoading = loadSession().finally(()=>{sessionLoading = null;});
    return sessionLoading;
  }
  setInterval(()=>{
    if (!document.hidden && !get('profile-dialog').open) load();
  },15000);
  window.addEventListener('focus',()=>{if (!get('profile-dialog').open) load();});
  window.addEventListener('online',()=>{if (!get('profile-dialog').open) load();});
  document.addEventListener('visibilitychange',()=>{
    if (!document.hidden && !get('profile-dialog').open) load();
  });
  authLink.addEventListener('click', event => {if (!account?.login_available) {event.preventDefault();get('profile-feedback').textContent = 'Discord sign-in needs to be configured on the server.';}});
  async function open(role) {
    await load(); get('profile-feedback').textContent = '';
    if (role && account?.authenticated) get('profile-primary').value = role;
    get('profile-dialog').showModal();
  }
  document.querySelectorAll('.profile-open').forEach(button => button.addEventListener('click', () => open()));
  document.querySelectorAll('.role-choice').forEach(button => button.addEventListener('click', () => open(button.dataset.role)));
  get('profile-close').addEventListener('click', () => get('profile-dialog').close());
  get('profile-form').addEventListener('submit', async event => {
    event.preventDefault();
    const preferences = {name:get('profile-name').value.trim(), primary:get('profile-primary').value, secondary:get('profile-secondary').value, avoided:get('profile-avoided').value};
    if (!preferences.name || preferences.primary === preferences.secondary) {get('profile-feedback').textContent = 'Enter a name and choose different primary and secondary roles.';return;}
    try {
      const response = await fetch('/api/profile', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(preferences)});
      if (!response.ok) throw Error();
      const result = await response.json();
      await load();
      get('profile-feedback').textContent = result.discord_role_synced === false
        ? 'Roles saved, but Discord role assignment failed. Ask staff to check bot permissions.'
        : account?.signup_completed ? 'Roles saved and synced to Discord.' : 'Profile saved. Complete /signup in Discord to join games.';
      if (result.discord_role_synced !== false) get('profile-dialog').close();
    } catch {get('profile-feedback').textContent = 'Could not save. Please sign in again and retry.';}
  });
  get('profile-reset').addEventListener('click', async () => {
    try {
      const response = await fetch('/auth/logout', {method:'POST'});
      if (!response.ok) throw Error();
      await load();get('profile-feedback').textContent = 'Signed out.';
    } catch {get('profile-feedback').textContent = 'Could not sign out. Please retry.';}
  });
  load().then(() => {if (location.hash === '#profile') open();});
})();

(() => {
  const get = id => document.getElementById(id);
  let account = null;
  let queueState = null;
  let statusBusy = false;
  let actionBusy = false;
  let shownReadyDeadline = null;
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
      if (readyDialog.open) readyDialog.close();
    } else if (shownReadyDeadline !== s.deadline) {
      shownReadyDeadline = s.deadline;
      readyDialog.showModal();
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
    ['profile-primary','profile-secondary'].forEach(id => {get(id).disabled = !signedIn;});
    get('profile-name').disabled = !signedIn || synced;
    get('profile-reset').disabled = !signedIn;
    get('profile-form').querySelector('[type="submit"]').disabled = !signedIn;
    connections[0].textContent = signedIn ? 'Linked: ' + account.identity.name : 'Not linked';
    connections[1].textContent = 'Not linked';
    const saved = account?.preferences || {};
    get('profile-name').value = saved.name || account?.identity?.name || '';
    get('profile-primary').value = saved.primary || '';
    get('profile-secondary').value = saved.secondary || '';
    get('saved-role-summary').textContent = signedIn
      ? (saved.primary ? 'Primary: ' + saved.primary + ' / Secondary: ' + saved.secondary + (account.player ? ' / ' + account.player.rank + ' / ' + account.player.rating + ' MMR' : '') : 'Choose your roles in My profile.')
      : 'Sign in with Discord to save your role preferences.';
    document.querySelectorAll('.role-choice').forEach(button => button.classList.toggle('is-selected', button.dataset.role === saved.primary));
    document.querySelectorAll('.profile-open').forEach(button => {if (button.closest('nav')) button.textContent = signedIn ? 'My profile' : 'Sign in';});
  }
  async function load() {
    try {
      const response = await fetch('/api/profile', {cache:'no-store'});
      if (!response.ok) throw Error();
      account = await response.json();
    } catch {account = null;}
    display();
    await refreshStatus();
  }
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
    const preferences = {name:get('profile-name').value.trim(), primary:get('profile-primary').value, secondary:get('profile-secondary').value};
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

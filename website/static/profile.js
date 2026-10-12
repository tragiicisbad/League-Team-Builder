(() => {
  const get = id => document.getElementById(id);
  let account = null;
  const note = document.querySelector('.profile-draft-note');
  const authLink = document.createElement('a');
  authLink.href = '/auth/discord'; authLink.className = 'button button--primary';
  authLink.textContent = 'Sign in with Discord';
  note.after(authLink);
  get('profile-reset').textContent = 'Sign out';
  const connections = document.querySelectorAll('.profile-connections span');
  function display() {
    const signedIn = !!account?.authenticated;
    note.textContent = signedIn ? 'Signed in with Discord. Website preferences are saved to your account.' : 'Sign in with Discord to create your PCL website profile.';
    authLink.hidden = signedIn;
    authLink.textContent = account?.login_available ? 'Sign in with Discord' : 'Discord sign-in awaiting setup';
    authLink.setAttribute('aria-disabled', String(!account?.login_available));
    ['profile-name','profile-primary','profile-secondary','profile-reset'].forEach(id => {get(id).disabled = !signedIn;});
    get('profile-form').querySelector('[type="submit"]').disabled = !signedIn;
    connections[0].textContent = signedIn ? 'Linked: ' + account.identity.name : 'Not linked';
    connections[1].textContent = 'Not linked';
    const saved = account?.preferences || {};
    get('profile-name').value = saved.name || account?.identity?.name || '';
    get('profile-primary').value = saved.primary || '';
    get('profile-secondary').value = saved.secondary || '';
    get('saved-role-summary').textContent = signedIn
      ? (saved.primary ? 'Primary: ' + saved.primary + ' / Secondary: ' + saved.secondary : 'Choose your roles in My profile.')
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
  }
  authLink.addEventListener('click', event => {if (!account?.login_available) {event.preventDefault();get('profile-feedback').textContent = 'Discord sign-in needs to be configured on the server.';}});
  function open(role) {
    display(); get('profile-feedback').textContent = '';
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
      await load();
      get('profile-feedback').textContent = 'Profile saved. Complete /signup in Discord to join games.';
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

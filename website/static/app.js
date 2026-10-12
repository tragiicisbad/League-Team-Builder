const $ = id => document.getElementById(id);
const node = (tag, text, className) => {
  const result = document.createElement(tag);
  if (text != null) result.textContent = text;
  if (className) result.className = className;
  return result;
};
const art = name => 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/' + name + '_0.jpg';
let standings = {leaderboard: [], matches: [], stats_hidden: true};
let standingsLoaded = false;
let voiceBusy = false;
let standingsBusy = false;
function avatar(member) {
  const wrap = node('div', null, 'avatar-wrap');
  const fallback = () => wrap.replaceChildren(node('span', (member.name || 'Player').slice(0, 2).toUpperCase(), 'avatar avatar-initials'));
  if (member.avatar_url) {
    const image = node('img', null, 'avatar');
    image.src = member.avatar_url; image.alt = ''; image.width = 32; image.height = 32;
    image.addEventListener('error', fallback, {once: true});
    wrap.append(image);
  } else fallback();
  return wrap;
}
function playerRow(member, queue = false) {
  const row = node('div', null, queue ? 'queue-user' : 'voice-user');
  row.append(avatar(member), node('strong', member.name || 'Player'));
  if (queue && member.rank) row.append(node('span', member.rank, 'rank rank--cyan'));
  return row;
}
function message(container, title, body) {
  const box = node('div', null, 'queue-message');
  box.append(node('strong', title), node('p', body));
  container.replaceChildren(box);
}
function renderVoice(payload) {
  const channels = Array.isArray(payload.channels) ? payload.channels : [];
  $('voice-channels').replaceChildren();
  let count = 0;
  [...channels].sort((a,b) => (a.position || 0) - (b.position || 0)).forEach(channel => {
    const members = Array.isArray(channel.members) ? channel.members : [];
    count += members.length;
    const title = node('div', null, 'channel-title');
    title.append(node('span', '\u266b', 'channel-symbol'), node('strong', channel.name), node('span', members.length));
    const list = node('div', null, 'voice-list');
    members.forEach(member => list.append(playerRow(typeof member === 'string' ? {name: member} : member)));
    if (!members.length) list.append(node('p', 'No one in voice', 'channel-empty'));
    $('voice-channels').append(title, list);
  });
  if (!channels.length) message($('voice-channels'), 'Voice is quiet', 'No channels are available to display.');
  $('voice-status').textContent = 'Live';
  $('voice-count').textContent = count + ' in voice';
  const queue = payload.queue;
  if (!queue) {
    message($('queue-display'), 'Queue unavailable', 'Check Discord for the current lobby.');
    $('queue-state').textContent = 'Unavailable';
    return;
  }
  const players = Array.isArray(queue.players) ? queue.players : [];
  const waitlist = Array.isArray(queue.waitlist) ? queue.waitlist : [];
  const capacity = Number(queue.capacity) || 10;
  $('queue-state').textContent = queue.state;
  const meta = node('div', null, 'queue-meta');
  meta.append(node('span', players.length + '/' + capacity + ' players'),
    node('small', queue.state === 'Queue open' ? Math.max(0, capacity - players.length) + ' spots open' : queue.state));
  const list = node('div', null, 'queue-list');
  players.forEach(member => list.append(playerRow(member, true)));
  if (!players.length) list.append(node('p', queue.state === 'No active queue' ? 'No active queue. Start one in Discord.' : 'Be the first one in.', 'channel-empty'));
  $('queue-display').replaceChildren(meta, list);
  const wait = node('div', null, 'waitlist-heading');
  wait.append(node('strong', 'Waitlist'), node('span', waitlist.length));
  $('queue-display').append(wait);
  const waiting = node('div', null, 'queue-list');
  waitlist.forEach(member => waiting.append(playerRow(member, true)));
  if (!waitlist.length) waiting.append(node('p', 'No players waiting', 'channel-empty'));
  $('queue-display').append(waiting);
  $('queue-updated').textContent = 'Updated ' + new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
}
async function refreshVoice() {
  if (voiceBusy || document.hidden) return;
  voiceBusy = true;
  try {
    const response = await fetch('/api/voice', {cache: 'no-store', signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw Error();
    renderVoice(await response.json());
  } catch {
    $('voice-status').textContent = 'Unavailable'; $('queue-state').textContent = 'Unavailable';
    message($('voice-channels'), 'Discord is temporarily unavailable', 'Open Discord to see who is in voice.');
    message($('queue-display'), 'Queue unavailable', 'Check Discord for the latest lineup.');
    $('queue-updated').textContent = 'Retrying connection...';
  } finally {voiceBusy = false;}
}
const roleName = value => value === 'ADC' ? 'Bot' : value;
function historyTab() {return location.hash === '#matches';}
function renderStandings() {
  const history = historyTab();
  const paused = standings.stats_hidden !== false;
  $('filters').hidden = paused || history || !standingsLoaded;
  $('leader-table').hidden = paused || !standingsLoaded;
  $('rows').replaceChildren(); $('matches').replaceChildren();
  $('standings-notice').hidden = false; $('no-players').hidden = true;
  if (!standingsLoaded) return;
  if (paused) {
    $('notice-title').textContent = history ? 'Match history coming soon' : 'Standings coming soon';
    $('notice-body').textContent = 'Public player records are paused while we prepare account linking and sharing preferences. Games continue in Discord.';
    return;
  }
  const players = standings.leaderboard || [];
  players.forEach((player, index) => {
    if (!player.name.toLowerCase().includes($('search').value.toLowerCase())) return;
    if ($('role-filter').value && roleName(player.role) !== $('role-filter').value) return;
    const games = player.wins + player.losses;
    const row = node('tr');
    [index + 1, player.name, player.rank, player.rating, roleName(player.role), player.wins + ' / ' + player.losses,
      games ? Math.round(player.wins / games * 100) + '%' : '--'].forEach(value => row.append(node('td', value)));
    $('rows').append(row);
  });
  $('no-players').hidden = $('rows').children.length > 0 || history;
  const matches = standings.matches || [];
  matches.forEach(match => {
    const article = node('article', null, 'match-card live-match');
    article.append(node('h3', (match.winner === 'blue' ? 'Blue' : 'Red') + ' team wins'),
      node('time', new Date(match.date).toLocaleString()));
    const teams = node('div', null, 'live-teams');
    ['blue', 'red'].forEach(side => {
      const team = node('div');
      team.append(node('strong', side === 'blue' ? 'Blue team' : 'Red team'));
      (match[side] || []).forEach(player => team.append(node('p', player.name + ' / ' + roleName(player.role))));
      teams.append(team);
    });
    article.append(teams); $('matches').append(article);
  });
  $('standings-notice').hidden = history ? matches.length > 0 : players.length > 0;
  $('notice-title').textContent = history ? 'A new chapter awaits' : 'The ladder awaits';
  $('notice-body').textContent = history ? 'Completed public matches will appear here.' : 'Public standings will appear here.';
}
async function refreshStandings() {
  if (standingsBusy || document.hidden) return;
  standingsBusy = true;
  try {
    const response = await fetch('/api/standings', {cache: 'no-store', signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw Error();
    standings = await response.json(); standingsLoaded = true; renderStandings();
    $('standings-updated').textContent = 'Updated ' + new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
  } catch {
    standingsLoaded = false; renderStandings();
    $('notice-title').textContent = 'Records temporarily unavailable';
    $('notice-body').textContent = 'We are reconnecting to the league. Games continue in Discord.';
    $('standings-updated').textContent = 'Retrying connection...';
  } finally {standingsBusy = false;}
}
function route() {
  const hash = location.hash;
  const home = !['#leaderboard', '#matches', '#standings'].includes(hash) && !(location.pathname.startsWith('/standings') && !hash);
  const history = historyTab();
  $('homepage').hidden = !home; $('standings-page').hidden = home;
  $('home-link').classList.toggle('is-active', home); $('standings-link').classList.toggle('is-active', !home);
  $('home-link').setAttribute('aria-current', home ? 'page' : 'false');
  $('standings-link').setAttribute('aria-current', home ? 'false' : 'page');
  $('leader-tab').classList.toggle('is-active', !history); $('matches-tab').classList.toggle('is-active', history);
  $('leader-tab').setAttribute('aria-selected', String(!history)); $('matches-tab').setAttribute('aria-selected', String(history));
  $('leaders').hidden = history; $('matches').hidden = !history;
  $('standings-hero').style.backgroundImage = 'url("' + art(history ? 'Thresh' : 'Ahri') + '")';
  $('page-title').textContent = history ? 'Match history' : 'Standings';
  $('nav-links').classList.remove('is-open'); $('menu-button').setAttribute('aria-expanded', 'false');
  renderStandings();
  if (hash !== '#how-it-works') window.scrollTo({top: 0, behavior: 'instant'});
}
$('menu-button').addEventListener('click', () => {
  const open = $('nav-links').classList.toggle('is-open');
  $('menu-button').setAttribute('aria-expanded', String(open));
});
$('leader-tab').addEventListener('click', () => {location.hash = 'leaderboard';});
$('matches-tab').addEventListener('click', () => {location.hash = 'matches';});
$('search').addEventListener('input', renderStandings);
$('role-filter').addEventListener('change', renderStandings);
window.addEventListener('hashchange', route);
document.addEventListener('visibilitychange', () => {if (!document.hidden) {refreshVoice(); refreshStandings();}});
const video = $('hero-video');
video.addEventListener('error', () => {video.hidden = true;});
video.querySelector('source').addEventListener('error', () => {video.hidden = true;});
const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
if (reduced.matches) {video.pause(); video.hidden = true;}
route(); refreshVoice(); refreshStandings();
setInterval(refreshVoice, 15000); setInterval(refreshStandings, 30000);
const targets = document.querySelectorAll('.section-heading,.server-cards article,.feature-copy,.role-card,.faq-list details');
if ('IntersectionObserver' in window && !reduced.matches) {
  const observer = new IntersectionObserver(entries => entries.forEach(entry => {
    if (entry.isIntersecting) {entry.target.classList.add('is-visible'); observer.unobserve(entry.target);}
  }), {threshold: 0.1});
  targets.forEach(target => {target.classList.add('cinematic-reveal'); observer.observe(target);});
}
window.addEventListener('scroll', () => {
  const max = document.documentElement.scrollHeight - innerHeight;
  document.documentElement.style.setProperty('--scroll-progress', String(max > 0 ? scrollY / max : 0));
}, {passive: true});

export const site = {
  name: "Prim Customs League",
  shortName: "PCL",
  tagline: "North American customs",
  discordUrl: "https://discord.gg/dNxqzmzsND",
  year: 2026,
  logo: "/pcl-logo.png",
};

export const art = {
  jax: "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Jax_0.jpg",
  lulu: "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Lulu_0.jpg",
  annie: "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Annie_0.jpg",
  sylas: "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Sylas_0.jpg",
  ahri: "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Ahri_0.jpg",
  thresh: "https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Thresh_0.jpg",
};

export const avatars = [
  "https://ddragon.leagueoflegends.com/cdn/14.24.1/img/champion/Jax.png",
  "https://ddragon.leagueoflegends.com/cdn/14.24.1/img/champion/Lulu.png",
  "https://ddragon.leagueoflegends.com/cdn/14.24.1/img/champion/Annie.png",
  "https://ddragon.leagueoflegends.com/cdn/14.24.1/img/champion/Sylas.png",
  "https://ddragon.leagueoflegends.com/cdn/14.24.1/img/champion/Ahri.png",
  "https://ddragon.leagueoflegends.com/cdn/14.24.1/img/champion/Thresh.png",
];

/** Swap `src` for any new Higgsfield render. The Jax splash is the still fallback. */
export const cinematic = {
  src: "/opening.mp4",
  poster: art.jax,
  eyebrow: "PRIM CUSTOMS LEAGUE",
  skipLabel: "Skip opening",
};

export const hero = {
  eyebrow: "FREE • NORTH AMERICA • ALL SKILL LEVELS",
  title: "Good games.",
  accent: "Better lobbies.",
  body: "PCL is a welcoming League of Legends custom-game community built around balanced 5v5s, friendly voices, and the simple joy of queueing together.",
  primary: "Join the next game",
  secondary: "See how it works",
  scroll: "Scroll to enter",
};

export const voice = {
  eyebrow: "PCL GAMES",
  title: "Saturday customs",
  live: "Live",
  channel: "Lobby • Game 2",
  count: "5",
  online: "11 online tonight",
  note: "Good games, better company.",
};

export const queueCopy = {
  eyebrow: "ACTIVE QUEUE",
  openTitle: "Summoner's Rift",
  readyTitle: "Ready check!",
  openMeta: "5/10 players",
  openSpots: "5 spots open",
  readyMeta: "10/10 readying up",
  readySpots: "00:24 remaining",
  waitlist: "Waitlist",
  waitlistNote: "+2 ready to sub",
  loadingTitle: "Checking the queue",
  loadingBody: "Asking the poros for the latest lineup…",
  emptyTitle: "Be the first one in",
  emptyBody: "The queue is open and waiting for players.",
  unavailableTitle: "Queue is resting",
  unavailableBody: "Check Discord for the next customs night.",
};

export const players = [
  { name: "Locke", rank: "Vanguard", role: "Top", avatar: 0, voice: "Host" },
  { name: "PoroSnax", rank: "Artisan", role: "Jungle", avatar: 1, voice: "In voice" },
  { name: "Primrose", rank: "Vanguard", role: "Mid", avatar: 2, voice: "In voice" },
  { name: "Moonbyte", rank: "Artisan", role: "Bottom", avatar: 3, voice: "In voice" },
  { name: "Sundew", rank: "Scout", role: "Support", avatar: 4, voice: "In voice" },
];

export const waitlist = [
  { name: "Nightjar", avatar: 5 },
  { name: "Moss", avatar: 1 },
];

export const servers = {
  eyebrow: "TWO SERVERS, ONE COMMUNITY",
  title: "A place to play. A place to stay.",
  body: "We keep game-night logistics tidy without turning the whole community into a signup sheet.",
  cards: [
    {
      icon: "shield",
      label: "PCL GAMES",
      title: "Queue up & play",
      body: "Sign up, join voice, complete ready checks, and find your match lobby.",
      soft: false,
    },
    {
      icon: "discord",
      label: "COMMUNITY DISCORD",
      title: "Hang out awhile",
      body: "Share clips, find duos, talk patches, or just enjoy the post-game chatter.",
      soft: true,
    },
  ],
};

export const balanced = {
  eyebrow: "MATCHES THAT FEEL FAIR",
  title: "Balanced 5v5s, not mystery stomps.",
  body: "Community ratings help captains build competitive teams while keeping the mood light. Your history helps us make the next lobby even better.",
  stats: [
    { value: "5v5", label: "Draft customs" },
    { value: "Free", label: "Always" },
    { value: "NA", label: "Server region" },
  ],
};

export const roles = {
  eyebrow: "PLAY YOUR WAY",
  title: "Your roles, in your order.",
  body: "Tell the queue where you shine. We use your preferences to make lobbies faster and fairer.",
  items: [
    { name: "Top", note: "Preferred" },
    { name: "Jungle", note: "Preferred" },
    { name: "Mid", note: "Available" },
    { name: "Bottom", note: "Available" },
    { name: "Support", note: "Available" },
  ],
};

export const ready = {
  eyebrow: "NO MORE HERDING CATS",
  title: "Ready checks keep everyone on beat.",
  body: "When the lobby fills, one clear prompt gets ten players moving together. Accept, jump into voice, and meet your team.",
  label: "READY CHECK",
  headline: "You're in for Game 3",
  status: "9 of 10 players ready",
  action: "I'm ready",
};

export const ratings = {
  eyebrow: "RATINGS WITH A HUMAN TOUCH",
  title: "A rank made for customs.",
  body: "PCL ranks reflect how you play here—not your solo queue badge. They're a practical tool for team balance, shaped by match results and community context.",
  scale: ["Scout", "Artisan", "Vanguard", "Paragon"],
};

export const faq = {
  eyebrow: "QUICK ANSWERS",
  title: "New to PCL?",
  body: "You only need a North American League account, Discord, and a little time for a full game.",
  items: [
    { q: "Does it cost anything?", a: "No. PCL is completely free to join and play." },
    { q: "What ranks can join?", a: "All of them. Our balancing system is designed for mixed-skill communities." },
    { q: "How do I sign up?", a: "Join PCL Games, choose your roles, and add yourself when a queue opens." },
    { q: "Do I need a team?", a: "Nope. Sign up solo and we'll place you in a balanced lobby." },
  ],
};

export const join = {
  eyebrow: "YOUR NEXT LOBBY IS WAITING",
  title: "Come play one.",
  body: "No team required. No entry fee. Just ten people and a good game.",
  action: "Join PCL on Discord",
};

export const footer = {
  explore: "Explore",
  community: "Community",
  links: [
    { label: "PCL Discord", href: site.discordUrl },
    { label: "Community Discord", href: site.discordUrl },
  ],
  legal:
    "Prim Customs League is a community-run project. PCL is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone officially involved in producing or managing League of Legends. League of Legends and Riot Games are trademarks or registered trademarks of Riot Games, Inc.",
};

export const standings = {
  eyebrow: "PCL COMPETITIVE RECORDS",
  title: "Standings",
  body: "Follow the climb, celebrate good runs, and see how the community is growing.",
  leaderboard: "Leaderboard",
  history: "Match history",
  soonEyebrow: "THE RECORD BOOK IS OPENING SOON",
  leaderboardSoon: "Standings coming soon",
  leaderboardSoonBody: "We're tuning the first season's rating system before the climb begins.",
  historySoon: "Match history coming soon",
  historySoonBody: "Completed lobbies will appear here once official tracking goes live.",
  updates: "Get season updates",
  sample: "SAMPLE DATA",
  leaderboardPreview: "Leaderboard preview",
  historyPreview: "Recent match preview",
  sampleNote: "Example layout for future PCL records.",
  search: "Search players",
  empty: "No sample players match those filters.",
  roles: ["All roles", "Top", "Jungle", "Mid", "Bottom", "Support"],
};

export const standingRows = [
  { name: "Primrose", rank: "Paragon", mmr: 1842, role: "Mid", wins: 31, losses: 16, avatar: 4 },
  { name: "Locke", rank: "Vanguard", mmr: 1776, role: "Top", wins: 27, losses: 17, avatar: 0 },
  { name: "Moonbyte", rank: "Vanguard", mmr: 1698, role: "Bottom", wins: 22, losses: 15, avatar: 3 },
  { name: "PoroSnax", rank: "Artisan", mmr: 1584, role: "Jungle", wins: 19, losses: 16, avatar: 1 },
  { name: "Sundew", rank: "Scout", mmr: 1421, role: "Support", wins: 14, losses: 15, avatar: 2 },
];

export const matches = [
  { game: "Game 24", result: "Blue side victory", duration: "38:12", date: "Yesterday", red: false },
  { game: "Game 23", result: "Red side victory", duration: "31:48", date: "Saturday", red: true },
  { game: "Game 22", result: "Blue side victory", duration: "42:05", date: "Last Friday", red: false },
];

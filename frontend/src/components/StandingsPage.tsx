import { useMemo, useState } from "react";
import { art, matches, site, standingRows, standings } from "../content";
import { Avatar, Button, Icon } from "./ui";

export function StandingsPage() {
  const [tab, setTab] = useState<"leaderboard" | "history">("leaderboard");
  const [search, setSearch] = useState("");
  const [role, setRole] = useState(standings.roles[0]);
  const filtered = useMemo(
    () =>
      standingRows.filter(
        (player) =>
          player.name.toLowerCase().includes(search.toLowerCase()) &&
          (role === "All roles" || player.role === role),
      ),
    [search, role],
  );

  return (
    <main className="standings-page">
      <section
        className="standings-hero"
        style={{ backgroundImage: `url("${tab === "leaderboard" ? art.ahri : art.thresh}")` }}
      >
        <div className="standings-shade" />
        <div className="section-inner standings-title">
          <span className="eyebrow">{standings.eyebrow}</span>
          <h1>{standings.title}</h1>
          <p>{standings.body}</p>
        </div>
      </section>
      <section className="standings-content">
        <div className="section-inner">
          <div className="tabs" role="tablist">
            <button className={tab === "leaderboard" ? "is-active" : ""} onClick={() => setTab("leaderboard")} role="tab">
              {standings.leaderboard}
            </button>
            <button className={tab === "history" ? "is-active" : ""} onClick={() => setTab("history")} role="tab">
              {standings.history}
            </button>
          </div>
          <div className="coming-card">
            <div className="coming-orb">
              <Icon name={tab === "leaderboard" ? "shield" : "clock"} size={26} />
            </div>
            <div>
              <span className="eyebrow">{standings.soonEyebrow}</span>
              <h2>{tab === "leaderboard" ? standings.leaderboardSoon : standings.historySoon}</h2>
              <p>{tab === "leaderboard" ? standings.leaderboardSoonBody : standings.historySoonBody}</p>
            </div>
            <Button href={site.discordUrl} kind="secondary">
              {standings.updates} <Icon name="arrow" />
            </Button>
          </div>
          <div className="sample-bar">
            <div>
              <span className="sample-pill">{standings.sample}</span>
              <strong>{tab === "leaderboard" ? standings.leaderboardPreview : standings.historyPreview}</strong>
            </div>
            <p>{standings.sampleNote}</p>
          </div>
          {tab === "leaderboard" ? (
            <>
              <div className="filters">
                <label className="search-box">
                  <Icon name="search" />
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder={standings.search}
                    aria-label={standings.search}
                  />
                </label>
                <label className="select-box">
                  <span className="sr-only">Filter by role</span>
                  <select value={role} onChange={(event) => setRole(event.target.value)}>
                    {standings.roles.map((item) => (
                      <option key={item}>{item}</option>
                    ))}
                  </select>
                  <Icon name="chevron" size={15} />
                </label>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Player</th>
                      <th>PCL rank</th>
                      <th>MMR</th>
                      <th>Role</th>
                      <th>W / L</th>
                      <th>Win rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((player, index) => (
                      <tr key={player.name}>
                        <td>{index + 1}</td>
                        <td>
                          <div className="player-cell">
                            <Avatar index={player.avatar} name={player.name} status={false} />
                            <strong>{player.name}</strong>
                          </div>
                        </td>
                        <td>
                          <span className="rank rank--cyan">{player.rank}</span>
                        </td>
                        <td>
                          <strong>{player.mmr.toLocaleString()}</strong>
                        </td>
                        <td>{player.role}</td>
                        <td>
                          {player.wins} / {player.losses}
                        </td>
                        <td>
                          <strong>{Math.round((player.wins / (player.wins + player.losses)) * 100)}%</strong>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {filtered.length === 0 && <div className="no-results">{standings.empty}</div>}
              </div>
            </>
          ) : (
            <div className="match-list">
              {matches.map((match, index) => (
                <article className="match-card" key={match.game}>
                  <div className={`match-result ${match.red ? "is-red" : ""}`}>
                    <Icon name={match.red ? "x" : "check"} />
                    <span>{match.result}</span>
                  </div>
                  <div>
                    <small>MATCH</small>
                    <strong>{match.game}</strong>
                  </div>
                  <div>
                    <small>DURATION</small>
                    <strong>{match.duration}</strong>
                  </div>
                  <div>
                    <small>PLAYED</small>
                    <strong>{match.date}</strong>
                  </div>
                  <div className="match-avatars">
                    {[0, 1, 2, 3, 4].map((avatar) => (
                      <Avatar key={avatar} index={avatar + index} name="Sample player" status={false} />
                    ))}
                  </div>
                  <Icon name="chevron" />
                </article>
              ))}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

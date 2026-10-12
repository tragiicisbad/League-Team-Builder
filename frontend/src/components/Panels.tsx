import { useState } from "react";
import { players, queueCopy, voice, waitlist } from "../content";
import type { QueueState } from "../types";
import { Avatar, Icon } from "./ui";

const states: QueueState[] = ["queue-open", "ready-check", "loading", "empty", "unavailable"];

export function VoicePanel() {
  return (
    <article className="discord-panel">
      <div className="panel-top">
        <div>
          <span className="eyebrow">{voice.eyebrow}</span>
          <h3>{voice.title}</h3>
        </div>
        <span className="live-pill">
          <i /> {voice.live}
        </span>
      </div>
      <div className="channel-title">
        <Icon name="headset" /> {voice.channel} <span>{voice.count}</span>
      </div>
      <div className="voice-list">
        {players.slice(0, 4).map((player) => (
          <div className="voice-user" key={player.name}>
            <Avatar index={player.avatar} name={player.name} />
            <span>{player.name}</span>
            <span className="muted">{player.voice}</span>
          </div>
        ))}
      </div>
      <div className="panel-foot">
        <span>
          <Icon name="users" /> {voice.online}
        </span>
        <span>{voice.note}</span>
      </div>
    </article>
  );
}

export function QueuePanel() {
  const [state, setState] = useState<QueueState>("queue-open");
  const nextState = () => setState(states[(states.indexOf(state) + 1) % states.length]);
  const populated = state === "queue-open" || state === "ready-check";

  return (
    <article className="discord-panel queue-panel">
      <div className="panel-top">
        <div>
          <span className="eyebrow">{queueCopy.eyebrow}</span>
          <h3>{state === "ready-check" ? queueCopy.readyTitle : queueCopy.openTitle}</h3>
        </div>
        <button className="state-toggle" onClick={nextState} title="Preview next queue state">
          {state.replace("-", " ")} <Icon name="chevron" size={14} />
        </button>
      </div>
      {state === "loading" && (
        <div className="queue-message">
          <span className="spinner" />
          <strong>{queueCopy.loadingTitle}</strong>
          <p>{queueCopy.loadingBody}</p>
        </div>
      )}
      {state === "empty" && (
        <div className="queue-message">
          <Icon name="users" size={28} />
          <strong>{queueCopy.emptyTitle}</strong>
          <p>{queueCopy.emptyBody}</p>
        </div>
      )}
      {state === "unavailable" && (
        <div className="queue-message">
          <Icon name="clock" size={28} />
          <strong>{queueCopy.unavailableTitle}</strong>
          <p>{queueCopy.unavailableBody}</p>
        </div>
      )}
      {populated && (
        <>
          <div className="queue-meta">
            <span>
              <i /> {state === "ready-check" ? queueCopy.readyMeta : queueCopy.openMeta}
            </span>
            <small>{state === "ready-check" ? queueCopy.readySpots : queueCopy.openSpots}</small>
          </div>
          <div className="queue-list">
            {players.map((player) => (
              <div className="queue-user" key={player.name}>
                <Avatar index={player.avatar} name={player.name} />
                <div>
                  <strong>{player.name}</strong>
                  <span>{player.role}</span>
                </div>
                <span className={`rank rank--${player.rank === "Scout" ? "scout" : "cyan"}`}>{player.rank}</span>
                {state === "ready-check" && (
                  <span className="ready">
                    <Icon name="check" size={14} />
                  </span>
                )}
              </div>
            ))}
          </div>
          <div className="waitlist">
            <span>{queueCopy.waitlist}</span>
            <div className="avatar-stack">
              {waitlist.map((person) => (
                <Avatar key={person.name} index={person.avatar} name={person.name} />
              ))}
            </div>
            <small>{queueCopy.waitlistNote}</small>
          </div>
        </>
      )}
    </article>
  );
}

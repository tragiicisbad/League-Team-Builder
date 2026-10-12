import { Fragment, useState } from "react";
import { art, avatars, balanced, cinematic, faq, hero, ratings, ready, roles, servers, site } from "../content";
import { ArtSection, Button, Icon, SectionHeading } from "./ui";
import { QueuePanel, VoicePanel } from "./Panels";

export function HomePage() {
  const [film, setFilm] = useState(true);

  return (
    <main>
      <section className="hero">
        <div className="hero-art" style={{ backgroundImage: `url("${art.jax}")` }} />
        {film && (
          <video
            className="hero-video"
            autoPlay
            muted
            loop
            playsInline
            poster={cinematic.poster}
            onError={() => setFilm(false)}
          >
            <source src={cinematic.src} type="video/mp4" />
          </video>
        )}
        <div className="hero-shade" />
        <div className="cinematic-beam" />
        <div className="hero-particles" aria-hidden="true">
          {Array.from({ length: 12 }, (_, index) => (
            <i key={index} />
          ))}
        </div>
        <div className="hero-inner">
          <div className="hero-copy reveal">
            <span className="eyebrow">{hero.eyebrow}</span>
            <h1>
              <span>{hero.title}</span>
              <br />
              <em>{hero.accent}</em>
            </h1>
            <p>{hero.body}</p>
            <div className="hero-actions">
              <Button href={site.discordUrl}>
                <Icon name="discord" /> {hero.primary}
              </Button>
              <a className="text-link" href="#how-it-works">
                {hero.secondary} <Icon name="arrow" />
              </a>
            </div>
          </div>
          <div className="panel-grid reveal reveal--late">
            <VoicePanel />
            <QueuePanel />
          </div>
          <a className="scroll-cue" href="#how-it-works">
            <span>{hero.scroll}</span>
            <i />
          </a>
        </div>
      </section>

      <section className="discord-explainer" id="how-it-works">
        <div className="section-inner two-column">
          <SectionHeading eyebrow={servers.eyebrow} title={servers.title}>
            {servers.body}
          </SectionHeading>
          <div className="server-cards">
            {servers.cards.map((card) => (
              <article key={card.title}>
                <span className={`server-icon ${card.soft ? "server-icon--soft" : ""}`}>
                  <Icon name={card.icon} />
                </span>
                <div>
                  <small>{card.label}</small>
                  <h3>{card.title}</h3>
                  <p>{card.body}</p>
                </div>
                <Icon name="arrow" />
              </article>
            ))}
          </div>
        </div>
      </section>

      <ArtSection art={art.lulu} side="right" className="balanced-section">
        <div className="feature-copy">
          <SectionHeading eyebrow={balanced.eyebrow} title={balanced.title}>
            {balanced.body}
          </SectionHeading>
          <div className="stat-row">
            {balanced.stats.map((stat) => (
              <div key={stat.label}>
                <strong>{stat.value}</strong>
                <span>{stat.label}</span>
              </div>
            ))}
          </div>
        </div>
      </ArtSection>

      <section className="role-section">
        <div className="section-inner">
          <SectionHeading eyebrow={roles.eyebrow} title={roles.title}>
            {roles.body}
          </SectionHeading>
          <div className="roles-row">
            {roles.items.map((role, index) => (
              <div className="role-card" key={role.name}>
                <span>0{index + 1}</span>
                <img src={avatars[index]} alt="" />
                <strong>{role.name}</strong>
                <small>{role.note}</small>
              </div>
            ))}
          </div>
        </div>
      </section>

      <ArtSection art={art.annie} side="left" className="ready-section">
        <div className="feature-copy feature-copy--right">
          <SectionHeading eyebrow={ready.eyebrow} title={ready.title}>
            {ready.body}
          </SectionHeading>
          <div className="ready-demo">
            <div className="ready-ring">
              <Icon name="check" size={26} />
            </div>
            <div>
              <small>{ready.label}</small>
              <strong>{ready.headline}</strong>
              <span>{ready.status}</span>
            </div>
            <Button kind="secondary">{ready.action}</Button>
          </div>
        </div>
      </ArtSection>

      <ArtSection art={art.sylas} side="right" className="rating-section">
        <div className="feature-copy">
          <SectionHeading eyebrow={ratings.eyebrow} title={ratings.title}>
            {ratings.body}
          </SectionHeading>
          <div className="rank-scale">
            {ratings.scale.map((rank, index) => (
              <Fragment key={rank}>
                {index > 0 && <i />}
                <span>{rank}</span>
              </Fragment>
            ))}
          </div>
        </div>
      </ArtSection>

      <section className="faq-section">
        <div className="section-inner faq-layout">
          <SectionHeading eyebrow={faq.eyebrow} title={faq.title}>
            {faq.body}
          </SectionHeading>
          <div className="faq-list">
            {faq.items.map((item, index) => (
              <details key={item.q} open={index === 0}>
                <summary>
                  {item.q}
                  <span>+</span>
                </summary>
                <p>{item.a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

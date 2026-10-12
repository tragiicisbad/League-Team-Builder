import { footer, join, site } from "../content";
import type { Route } from "../types";
import { Brand, Button, Icon } from "./ui";

export function JoinBanner() {
  return (
    <section className="join-banner">
      <div className="join-glow" />
      <div className="section-inner">
        <div>
          <span className="eyebrow">{join.eyebrow}</span>
          <h2>{join.title}</h2>
          <p>{join.body}</p>
        </div>
        <Button href={site.discordUrl}>
          <Icon name="discord" /> {join.action}
        </Button>
      </div>
    </section>
  );
}

export function Footer({ navigate }: { navigate: (route: Route) => void }) {
  return (
    <footer>
      <div className="section-inner footer-main">
        <Brand />
        <div className="footer-links">
          <div>
            <strong>{footer.explore}</strong>
            <button onClick={() => navigate("home")}>Home</button>
            <button onClick={() => navigate("standings")}>Standings</button>
          </div>
          <div>
            <strong>{footer.community}</strong>
            {footer.links.map((link) => (
              <a key={link.label} href={link.href} target="_blank" rel="noreferrer">
                {link.label}
              </a>
            ))}
          </div>
        </div>
      </div>
      <div className="section-inner legal">
        <p>{footer.legal}</p>
        <span>
          © {site.year} {site.name}
        </span>
      </div>
    </footer>
  );
}

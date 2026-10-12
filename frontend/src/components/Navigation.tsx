import { useState } from "react";
import { site } from "../content";
import type { Route } from "../types";
import { Brand, Button, Icon } from "./ui";

export function Navigation({ route, navigate }: { route: Route; navigate: (route: Route) => void }) {
  const [open, setOpen] = useState(false);

  return (
    <header className="nav-shell">
      <nav className="nav">
        <button className="brand-button" onClick={() => navigate("home")} aria-label="PCL home">
          <Brand />
        </button>
        <div className={`nav-links ${open ? "is-open" : ""}`}>
          <button
            className={route === "home" ? "is-active" : ""}
            onClick={() => {
              navigate("home");
              setOpen(false);
            }}
          >
            Home
          </button>
          <button
            className={route === "standings" ? "is-active" : ""}
            onClick={() => {
              navigate("standings");
              setOpen(false);
            }}
          >
            Standings
          </button>
          <Button href={site.discordUrl}>
            <Icon name="discord" /> Join Discord
          </Button>
        </div>
        <button className="menu-button" aria-expanded={open} aria-label="Toggle navigation" onClick={() => setOpen(!open)}>
          <Icon name={open ? "x" : "menu"} size={22} />
        </button>
      </nav>
    </header>
  );
}

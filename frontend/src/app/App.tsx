import { useEffect, useState } from "react";
import { HomePage } from "../components/HomePage";
import { Navigation } from "../components/Navigation";
import { Opening } from "../components/Opening";
import { Footer, JoinBanner } from "../components/Footer";
import { StandingsPage } from "../components/StandingsPage";
import type { Route } from "../types";

function routeFromPath(): Route {
  return window.location.pathname.includes("standings") ? "standings" : "home";
}

export default function App() {
  const [route, setRoute] = useState<Route>(routeFromPath);
  const [opening, setOpening] = useState(routeFromPath() === "home");

  const navigate = (next: Route) => {
    setRoute(next);
    setOpening(false);
    window.history.pushState({}, "", next === "home" ? "/" : "/standings");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  useEffect(() => {
    const handle = () => setRoute(routeFromPath());
    window.addEventListener("popstate", handle);
    return () => window.removeEventListener("popstate", handle);
  }, []);

  useEffect(() => {
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const revealTargets = document.querySelectorAll(
      ".section-heading, .server-cards article, .feature-copy, .role-card, .ready-demo, .faq-list details, .coming-card, .sample-bar, .filters, .table-wrap, .match-card, .join-banner .section-inner",
    );
    revealTargets.forEach((element, index) => {
      element.classList.add("cinematic-reveal");
      (element as HTMLElement).style.setProperty("--reveal-order", String(index % 5));
    });
    if (reducedMotion) {
      revealTargets.forEach((element) => element.classList.add("is-visible"));
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.14, rootMargin: "0px 0px -7% 0px" },
    );
    revealTargets.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [route, opening]);

  useEffect(() => {
    let frame = 0;
    const updateScroll = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const max = document.documentElement.scrollHeight - window.innerHeight;
        document.documentElement.style.setProperty("--scroll-progress", String(max > 0 ? window.scrollY / max : 0));
        document.documentElement.style.setProperty("--page-scroll", `${window.scrollY}px`);
      });
    };
    updateScroll();
    window.addEventListener("scroll", updateScroll, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", updateScroll);
    };
  }, []);

  return (
    <div className="app">
      <div className="scroll-progress" />
      <Navigation route={route} navigate={navigate} />
      {route === "home" ? <HomePage /> : <StandingsPage />}
      <JoinBanner />
      <Footer navigate={navigate} />
      {opening && route === "home" && <Opening onDone={() => setOpening(false)} />}
    </div>
  );
}

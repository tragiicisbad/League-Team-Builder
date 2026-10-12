import type { ReactNode } from "react";
import { avatars, site } from "../content";

export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    arrow: (
      <>
        <path d="M5 12h14" />
        <path d="m13 6 6 6-6 6" />
      </>
    ),
    chevron: <path d="m9 18 6-6-6-6" />,
    discord: (
      <>
        <path d="M8.5 8.2a12 12 0 0 1 7 0" />
        <path d="M7 17c-2-1-3-3-3-3 .4-4 2-7 2-7 1-1 3-1 3-1l.8 1.4" />
        <path d="M17 17c2-1 3-3 3-3-.4-4-2-7-2-7-1-1-3-1-3-1l-.8 1.4" />
        <circle cx="9" cy="12" r="1" fill="currentColor" />
        <circle cx="15" cy="12" r="1" fill="currentColor" />
        <path d="M8 17c2.5 1.3 5.5 1.3 8 0" />
      </>
    ),
    headset: (
      <>
        <path d="M4 13a8 8 0 0 1 16 0" />
        <path d="M4 13v5a2 2 0 0 0 2 2h2v-7H4Z" />
        <path d="M20 13v5a2 2 0 0 1-2 2h-2v-7h4Z" />
      </>
    ),
    search: (
      <>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-4-4" />
      </>
    ),
    users: (
      <>
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M22 21v-2a4 4 0 0 0-3-3.9" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    shield: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />,
    menu: (
      <>
        <path d="M4 7h16" />
        <path d="M4 12h16" />
        <path d="M4 17h16" />
      </>
    ),
    x: (
      <>
        <path d="m6 6 12 12" />
        <path d="m18 6-12 12" />
      </>
    ),
  };

  return (
    <svg
      aria-hidden="true"
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths[name]}
    </svg>
  );
}

export function Brand() {
  return (
    <div className="brand">
      <img src={site.logo} alt="" />
      <div>
        <strong>{site.name}</strong>
        <span>{site.tagline}</span>
      </div>
    </div>
  );
}

export function Button({
  children,
  href,
  kind = "primary",
  onClick,
  type = "button",
}: {
  children: ReactNode;
  href?: string;
  kind?: "primary" | "ghost" | "secondary";
  onClick?: () => void;
  type?: "button" | "submit";
}) {
  const className = `button button--${kind}`;
  if (href) {
    return (
      <a className={className} href={href} target={href.startsWith("http") ? "_blank" : undefined} rel="noreferrer">
        {children}
      </a>
    );
  }
  return (
    <button className={className} onClick={onClick} type={type}>
      {children}
    </button>
  );
}

export function Avatar({ index, name, status = true }: { index: number; name: string; status?: boolean }) {
  return (
    <div className="avatar-wrap">
      <img className="avatar" src={avatars[index % avatars.length]} alt={`${name} avatar`} />
      {status && <i />}
    </div>
  );
}

export function SectionHeading({ eyebrow, title, children }: { eyebrow: string; title: string; children: ReactNode }) {
  return (
    <div className="section-heading">
      <span className="eyebrow">{eyebrow}</span>
      <h2>{title}</h2>
      <p>{children}</p>
    </div>
  );
}

export function ArtSection({
  art,
  side = "left",
  className = "",
  children,
}: {
  art: string;
  side?: "left" | "right";
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={`art-section art-section--${side} ${className}`} style={{ backgroundImage: `url("${art}")` }}>
      <div className="art-shade" />
      <div className="section-inner">{children}</div>
    </section>
  );
}

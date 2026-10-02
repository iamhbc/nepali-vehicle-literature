import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../api/client";
import type { Meta, Theme } from "../api/types";
import { readStore, writeStore } from "../lib/storage";
import { ChevronBand, Jhalar, Wordmark } from "./ornaments";

interface MetaCtx {
  meta: Meta | null;
  themes: Record<string, Theme>;
  error: string | null;
}

const MetaContext = createContext<MetaCtx>({ meta: null, themes: {}, error: null });
export const useMeta = () => useContext(MetaContext);

export function MetaProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.meta().then(setMeta).catch((e: Error) => setError(e.message));
  }, []);
  const themes = useMemo(() => Object.fromEntries((meta?.themes ?? []).map((t) => [t.code, t])), [meta]);
  return <MetaContext.Provider value={{ meta, themes, error }}>{children}</MetaContext.Provider>;
}

type ThemePref = "system" | "light" | "dark";

function ThemeToggle() {
  const [pref, setPref] = useState<ThemePref>(() => readStore<ThemePref>("nvl.theme", "system"));
  useEffect(() => {
    const root = document.documentElement;
    if (pref === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", pref);
    writeStore("nvl.theme", pref);
  }, [pref]);
  const next: Record<ThemePref, ThemePref> = { system: "light", light: "dark", dark: "system" };
  const label = { system: "Auto", light: "Day", dark: "Night" }[pref];
  return (
    <button className="btn btn-ghost btn-sm theme-toggle" onClick={() => setPref(next[pref])} aria-label={`Colour theme: ${label}. Change theme`}>
      <span aria-hidden="true">{pref === "dark" ? "☾" : pref === "light" ? "☀" : "◐"}</span> {label}
    </button>
  );
}

const NAV = [
  { to: "/analyze", en: "Analyse", ne: "विश्लेषण" },
  { to: "/scan", en: "Photograph", ne: "फोटो" },
  { to: "/corpus", en: "Corpus", ne: "संग्रह" },
  { to: "/explore", en: "Explore", ne: "अन्वेषण" },
  { to: "/method", en: "Method", ne: "विधि" },
];

function Icon({ name }: { name: string }) {
  const paths: Record<string, ReactNode> = {
    analyze: <path d="M4 6h16M4 12h10M4 18h7M17 14l4 4-4 4" />,
    scan: (
      <>
        <rect x="3" y="6" width="18" height="14" rx="3" />
        <circle cx="12" cy="13" r="4" />
        <path d="M8 6l2-3h4l2 3" />
      </>
    ),
    corpus: <path d="M4 4h6v16H4zM10 4h4v16h-4zM15 5l4-1 2 15-4 1z" />,
    explore: (
      <>
        <circle cx="6" cy="6" r="2.5" />
        <circle cx="18" cy="8" r="2.5" />
        <circle cx="10" cy="18" r="2.5" />
        <path d="M8 7l8 1M7 8l2 8M16 10l-5 6" />
      </>
    ),
    method: <path d="M12 3a9 9 0 100 18 9 9 0 000-18zm0 5v.5M12 11v6" />,
  };
  return (
    <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

export function Layout() {
  const location = useLocation();
  const { error } = useMeta();
  useEffect(() => {
    window.scrollTo({ top: 0 });
    document.getElementById("main")?.focus({ preventScroll: true });
  }, [location.pathname]);

  return (
    <div className="app">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <header className="site-header">
        <div className="container header-inner">
          <Link to="/" className="brand" aria-label="Nepali Vehicle Literature — home">
            <Wordmark />
          </Link>
          <nav className="top-nav" aria-label="Main">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} className={({ isActive }) => `top-link ${isActive ? "is-active" : ""}`}>
                {n.en}
                <span lang="ne">{n.ne}</span>
              </NavLink>
            ))}
          </nav>
          <ThemeToggle />
        </div>
        <Jhalar />
      </header>
      {error && (
        <div className="container">
          <p className="notice notice-error" role="alert">
            The analysis server is not responding ({error}). Browsing may be limited.
          </p>
        </div>
      )}
      <main id="main" tabIndex={-1}>
        <Outlet />
      </main>
      <footer className="site-footer">
        <ChevronBand />
        <div className="container footer-inner">
          <p className="footer-sign" lang="ne">
            फेरि भेटौंला
          </p>
          <p className="subtle">
            “See you again” — the farewell painted on the back of countless Nepali buses and trucks.
          </p>
          <nav className="footer-links" aria-label="Footer">
            <Link to="/method">How analysis works</Link>
            <Link to="/method#privacy">Privacy</Link>
            <Link to="/admin">Researcher area</Link>
          </nav>
          <p className="subtle">
            AI interpretations are analytical readings, not statements of any author's intention.
          </p>
        </div>
      </footer>
      <nav className="bottom-nav" aria-label="Main (mobile)">
        {[
          { to: "/analyze", label: "Analyse", icon: "analyze" },
          { to: "/corpus", label: "Corpus", icon: "corpus" },
          { to: "/scan", label: "Photo", icon: "scan", primary: true },
          { to: "/explore", label: "Explore", icon: "explore" },
          { to: "/method", label: "Method", icon: "method" },
        ].map((n) => (
          <NavLink key={n.to} to={n.to} className={({ isActive }) => `bottom-link ${n.primary ? "is-primary" : ""} ${isActive ? "is-active" : ""}`}>
            <Icon name={n.icon} />
            <span>{n.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import Dashboard from "./Dashboard";
import "./style.css";

const API = import.meta.env.VITE_API_URL;

function App() {
  const [user, setUser] = useState(null);
  const [mode, setMode] = useState("signin");
  const [form, setForm] = useState({ name: "", email: "", password: "", otp: "" });
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [activePage, setActivePage] = useState("overview");
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  const [fullscreen, setFullscreen] = useState(false);
  const searchRef = useRef(null);
  const windowRef = useRef(null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    const changed = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", changed);
    return () => document.removeEventListener("fullscreenchange", changed);
  }, []);

  useEffect(() => {
    localStorage.removeItem("token");
    fetch(`${API}/api/me`, { credentials: "include" })
      .then((response) => response.ok && response.json())
      .then((data) => data && setUser(data));
  }, []);

  useEffect(() => {
    function shortcuts(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
      if (event.key === "Escape" && document.activeElement === searchRef.current) {
        setQuery("");
        searchRef.current.blur();
      }
    }
    window.addEventListener("keydown", shortcuts);
    return () => window.removeEventListener("keydown", shortcuts);
  }, []);

  useEffect(() => {
    if (!user) return;
    const panels = document.querySelectorAll(".dashboard-content .panel, .dashboard-content .student-class-card");
    panels.forEach((panel) => {
      const matches = !query || panel.textContent.toLowerCase().includes(query.toLowerCase());
      panel.classList.toggle("search-hidden", !matches);
    });
  }, [query, user]);

  function update(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    const endpoint = mode === "forgot" ? "forgot-password" : mode === "reset" ? "reset-password" : mode === "verify" ? "verify-email" : mode;
    const body = mode === "signup"
      ? { name: form.name, email: form.email, password: form.password }
      : mode === "reset"
        ? { email: form.email, otp: form.otp, password: form.password }
        : mode === "verify"
          ? { email: form.email, otp: form.otp }
        : mode === "forgot"
          ? { email: form.email }
          : { email: form.email, password: form.password };
    try {
      const response = await fetch(`${API}/api/auth/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        credentials: "include",
      });
      const data = await response.json();
      if (!response.ok) {
        if (data.detail === "Email is not verified") setMode("verify");
        return setMessage(typeof data.detail === "string" ? data.detail : "Please check your details.");
      }
      if (mode === "forgot") {
        setMode("reset");
        return setMessage(data.message);
      }
      if (mode === "reset") {
        setMode("signin");
        setForm({ ...form, password: "", otp: "" });
        return setMessage(data.message);
      }
      if (mode === "signup") {
        setMode("verify");
        return setMessage("Enter the verification code sent to your email.");
      }
      if (data.status !== "ACTIVE") return setMessage("Teacher account submitted for admin approval.");
      setUser(data.user);
    } catch {
      setMessage("Cannot reach the server.");
    } finally {
      setBusy(false);
    }
  }

  function show(nextMode) {
    setMode(nextMode);
    setMessage("");
    setForm({ ...form, password: "", otp: "" });
  }

  async function resend() {
    setBusy(true);
    try {
      const response = await fetch(`${API}/api/auth/resend-verification`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: form.email }),
      });
      const data = await response.json();
      setMessage(response.ok ? data.message : data.detail || "Could not send a new code.");
    } catch {
      setMessage("Cannot reach the server.");
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    await fetch(`${API}/api/auth/logout`, { method: "POST", credentials: "include" });
    setUser(null);
    setActivePage("overview");
  }

  function navigate(id) {
    setActivePage(id);
    setQuery("");
  }

  function updateUser(patch) {
    setUser((current) => ({ ...current, ...patch }));
  }

  async function toggleFullscreen() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await windowRef.current?.requestFullscreen();
    } catch { setMessage("Fullscreen is not available in this browser."); }
  }

  async function enablePush() {
    const publicKey = import.meta.env.VITE_VAPID_PUBLIC_KEY;
    if (!publicKey) return setMessage("Push notifications need a VAPID public key in the deployment settings.");
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return setMessage("Push notifications are not supported by this browser.");
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") return setMessage("Notification permission was not granted.");
      const registration = await navigator.serviceWorker.register("/sw.js");
      const padding = "=".repeat((4 - publicKey.length % 4) % 4);
      const bytes = Uint8Array.from(atob((publicKey + padding).replace(/-/g, "+").replace(/_/g, "/")), (char) => char.charCodeAt(0));
      const subscription = await registration.pushManager.getSubscription() || await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: bytes });
      const json = subscription.toJSON();
      const response = await fetch(`${API}/api/push/subscribe`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ endpoint: json.endpoint, p256dh: json.keys.p256dh, auth: json.keys.auth }) });
      if (!response.ok) throw new Error();
      setMessage("Push notifications enabled.");
    } catch { setMessage("Could not enable push notifications."); }
  }

  const initials = user?.name?.split(" ").map((part) => part[0]).slice(0, 2).join("").toUpperCase();
  const navigation = user?.role === "STUDENT"
    ? [["overview", "Overview", "grid"], ["student-hub", "Student hub", "folder"], ["classes", "Classes", "book"], ["others", "Others", "more"], ["notifications", "Notifications", "bell"]]
    : [["overview", "Overview", "grid"], [user?.role === "TEACHER" ? "classes" : "administration", user?.role === "TEACHER" ? "Classes" : "Administration", "folder"], ["notifications", "Notifications", "bell"]];
  const pageTitle = navigation.find(([id]) => id === activePage)?.[1] || "Overview";

  return (
    <main className="app-stage">
      <section ref={windowRef} className={`mac-window ${user ? "dashboard-window" : "auth-window"}`}>
        <header className="titlebar">
          <div />
          <div className="window-title"><Icon name="campus" /> IIT Management</div>
          <div className="titlebar-actions">{!user && <button className="icon-button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="Toggle dark mode" title="Toggle dark mode"><Icon name={theme === "dark" ? "sun" : "moon"} /></button>}</div>
        </header>
        {user ? (
          <div className="app-layout">
            <aside className="sidebar">
              <div className="brand"><span className="brand-mark"><Icon name="campus" /></span><span><strong>IIT Management</strong><small>University of Dhaka</small></span></div>
              <nav aria-label="Main navigation">
                {navigation.map(([id, label, icon]) => <button className={activePage === id ? "nav-item selected" : "nav-item"} key={id} onClick={() => navigate(id)}><Icon name={icon} />{label}</button>)}
              </nav>
              <div className="sidebar-profile">
                <span className="avatar">{user.profile_picture ? <img src={user.profile_picture} alt="" /> : initials}</span>
                <span><strong>{user.name}</strong><small>{user.role.replaceAll("_", " ").toLowerCase()}</small></span>
                <button className="icon-button" onClick={logout} aria-label="Sign out" title="Sign out"><Icon name="logout" /></button>
              </div>
            </aside>
            <div className="content-column">
              <div className="toolbar">
                <div><p className="toolbar-kicker">{new Intl.DateTimeFormat("en", { weekday: "long", month: "long", day: "numeric" }).format(new Date())}</p><h1>{pageTitle}</h1></div>
                <div className="toolbar-actions"><label className="search-field"><Icon name="search" /><input ref={searchRef} value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${pageTitle.toLowerCase()}`} aria-label="Search current page" /><kbd>⌘ K</kbd></label><button className="icon-button toolbar-button" onClick={enablePush} aria-label="Enable push notifications" title="Enable push notifications"><Icon name="bell" /></button><button className="icon-button toolbar-button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label="Toggle dark mode" title="Toggle dark mode"><Icon name={theme === "dark" ? "sun" : "moon"} /></button><button className="icon-button toolbar-button" onClick={toggleFullscreen} aria-label="Toggle fullscreen" title="Toggle fullscreen"><Icon name="fullscreen" /></button></div>
              </div>
              <div className="dashboard-content"><Dashboard user={user} page={activePage} notify={setMessage} onUserUpdate={updateUser} /></div>
            </div>
            <nav className="mobile-dock" aria-label="Mobile navigation">
              {navigation.map(([id, label, icon]) => <button className={activePage === id ? "selected" : ""} key={id} onClick={() => navigate(id)}><Icon name={icon} /><span>{label}</span></button>)}
            </nav>
          </div>
        ) : (
          <div className="auth-content">
            <div className="auth-brand"><span className="brand-mark large"><Icon name="campus" /></span><p className="eyebrow">University of Dhaka</p><h1>IIT Management</h1><p className="auth-intro">Everything you need for campus, in one place.</p></div>
            <div className="auth-card">
              <div className="tabs" role="tablist">
                <button className={mode === "signin" ? "active" : "link"} onClick={() => show("signin")}>Sign in</button>
                <button className={mode === "signup" ? "active" : "link"} onClick={() => show("signup")}>Create account</button>
              </div>
              <form onSubmit={submit}>
                {mode === "signup" && <label>Name<input name="name" value={form.name} onChange={update} autoComplete="name" placeholder="Your full name" required /></label>}
                <label>Email<input name="email" type="email" value={form.email} onChange={update} autoComplete="email" placeholder="name@du.ac.bd" required /></label>
                {(mode === "reset" || mode === "verify") && <label>6-digit code<input name="otp" inputMode="numeric" pattern="[0-9]{6}" value={form.otp} onChange={update} placeholder="000000" required /></label>}
                {mode !== "forgot" && mode !== "verify" && <label>{mode === "reset" ? "New password" : "Password"}<input name="password" type="password" minLength="8" maxLength="128" value={form.password} onChange={update} autoComplete={mode === "signin" ? "current-password" : "new-password"} placeholder="At least 8 characters" required /></label>}
                <button className="primary-button" type="submit" disabled={busy}>{busy ? "Please wait…" : mode === "forgot" ? "Send code" : mode === "reset" ? "Reset password" : mode === "verify" ? "Verify email" : mode === "signup" ? "Create account" : "Sign in"}</button>
              </form>
              {mode === "signin" && <button className="link forgot" onClick={() => show("forgot")}>Forgot password?</button>}
              {mode === "verify" && <button className="link forgot" onClick={resend} disabled={busy}>Send a new code</button>}
              {(mode === "forgot" || mode === "reset" || mode === "verify") && <button className="link forgot" onClick={() => show("signin")}><span aria-hidden="true">←</span> Back to sign in</button>}
            </div>
          </div>
        )}
        {message && <p role="status"><Icon name="info" />{message}<button onClick={() => setMessage("")} aria-label="Dismiss">×</button></p>}
      </section>
    </main>
  );
}

function Icon({ name }) {
  const paths = {
    campus: <><path d="M3 10 12 4l9 6"/><path d="M5 10h14v9H5zM9 10v9m6-9v9M3 19h18"/></>,
    grid: <><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></>,
    folder: <path d="M3 7.5A1.5 1.5 0 0 1 4.5 6H9l2 2h8.5A1.5 1.5 0 0 1 21 9.5v8a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5z"/>,
    book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v17H6.5A2.5 2.5 0 0 0 4 22z"/><path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H13v17h4.5A2.5 2.5 0 0 1 20 22z"/></>,
    more: <><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></>,
    bell: <><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 7h18s-3 0-3-7"/><path d="M10 20h4"/></>,
    logout: <><path d="M10 5H5v14h5M14 8l4 4-4 4m4-4H9"/></>,
    search: <><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/></>,
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/></>,
    moon: <path d="M20 15.5A8 8 0 0 1 8.5 4 8.5 8.5 0 1 0 20 15.5z"/>,
    sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M19 5l-1.5 1.5m-11 11L5 19"/></>,
    fullscreen: <><path d="M8 3H3v5m13-5h5v5M8 21H3v-5m13 5h5v-5"/></>,
  };
  return <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

createRoot(document.getElementById("root")).render(<App />);

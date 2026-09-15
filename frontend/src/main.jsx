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
  const searchRef = useRef(null);

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
    const panels = document.querySelectorAll(".dashboard-content .panel");
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
  }

  function jumpTo(id) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const initials = user?.name?.split(" ").map((part) => part[0]).slice(0, 2).join("").toUpperCase();
  const navigation = [
    ["overview", "Overview", "grid"],
    ["workspace", user?.role === "STUDENT" ? "Student hub" : user?.role === "TEACHER" ? "Classes" : "Administration", "folder"],
    ["notifications", "Notifications", "bell"],
  ];

  return (
    <main className="app-stage">
      <section className={`mac-window ${user ? "dashboard-window" : "auth-window"}`}>
        <header className="titlebar">
          <div className="traffic-lights" aria-label="Window controls">
            <span className="traffic-close" /><span className="traffic-minimize" /><span className="traffic-expand" />
          </div>
          <div className="window-title"><Icon name="campus" /> IIT Management</div>
          <div className="titlebar-spacer" />
        </header>
        {user ? (
          <div className="app-layout">
            <aside className="sidebar">
              <div className="brand"><span className="brand-mark"><Icon name="campus" /></span><span><strong>IIT Management</strong><small>University of Dhaka</small></span></div>
              <nav aria-label="Main navigation">
                {navigation.map(([id, label, icon], index) => <button className={index === 0 ? "nav-item selected" : "nav-item"} key={id} onClick={() => jumpTo(id)}><Icon name={icon} />{label}</button>)}
              </nav>
              <div className="sidebar-profile">
                <span className="avatar">{initials}</span>
                <span><strong>{user.name}</strong><small>{user.role.replaceAll("_", " ").toLowerCase()}</small></span>
                <button className="icon-button" onClick={logout} aria-label="Sign out" title="Sign out"><Icon name="logout" /></button>
              </div>
            </aside>
            <div className="content-column">
              <div className="toolbar">
                <div><p className="toolbar-kicker">{new Intl.DateTimeFormat("en", { weekday: "long", month: "long", day: "numeric" }).format(new Date())}</p><h1>Welcome back, {user.name.split(" ")[0]}</h1></div>
                <label className="search-field"><Icon name="search" /><input ref={searchRef} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search dashboard" aria-label="Search dashboard" /><kbd>⌘ K</kbd></label>
              </div>
              <div className="dashboard-content"><Dashboard user={user} notify={setMessage} /></div>
            </div>
            <nav className="mobile-dock" aria-label="Mobile navigation">
              {navigation.map(([id, label, icon]) => <button key={id} onClick={() => jumpTo(id)}><Icon name={icon} /><span>{label}</span></button>)}
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
    bell: <><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 7h18s-3 0-3-7"/><path d="M10 20h4"/></>,
    logout: <><path d="M10 5H5v14h5M14 8l4 4-4 4m4-4H9"/></>,
    search: <><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/></>,
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/></>,
  };
  return <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

createRoot(document.getElementById("root")).render(<App />);

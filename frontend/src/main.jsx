import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const API = import.meta.env.VITE_API_URL;

function App() {
  const [user, setUser] = useState(null);
  const [mode, setMode] = useState("signin");
  const [form, setForm] = useState({ name: "", email: "", password: "", otp: "" });
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [teachers, setTeachers] = useState([]);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token)
      fetch(`${API}/api/me`, { headers: { Authorization: `Bearer ${token}` } })
        .then((response) => response.ok && response.json())
        .then((data) => data && setUser(data));
  }, []);

  useEffect(() => {
    if (user && ["SUPER_ADMIN", "DEPARTMENT_ADMIN"].includes(user.role))
      fetch(`${API}/api/admin/teachers`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
      })
        .then((response) => response.ok && response.json())
        .then((data) => data && setTeachers(data));
  }, [user]);

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
      if (!data.token) return setMessage("Teacher account submitted for admin approval.");
      localStorage.setItem("token", data.token);
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

  function logout() {
    localStorage.removeItem("token");
    setUser(null);
  }

  async function decide(teacherId, action) {
    const response = await fetch(`${API}/api/admin/teachers/${teacherId}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${localStorage.getItem("token")}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ action }),
    });
    if (response.ok) setTeachers(teachers.filter(({ id }) => id !== teacherId));
    else setMessage("Could not update the teacher account.");
  }

  return (
    <main>
      <section>
        <p className="eyebrow">University of Dhaka</p>
        <h1>IIT Management</h1>
        {user ? (
          <>
            <h2>Welcome, {user.name}</h2>
            <p>{user.email} · {user.role}</p>
            {["SUPER_ADMIN", "DEPARTMENT_ADMIN"].includes(user.role) && (
              <div className="requests">
                <h3>Pending teachers</h3>
                {teachers.length ? teachers.map((teacher) => (
                  <article key={teacher.id}>
                    <span><strong>{teacher.name}</strong><small>{teacher.email}</small></span>
                    <button onClick={() => decide(teacher.id, "APPROVE")}>Approve</button>
                    <button className="reject" onClick={() => decide(teacher.id, "REJECT")}>Reject</button>
                  </article>
                )) : <p>No pending requests.</p>}
              </div>
            )}
            <button onClick={logout}>Sign out</button>
          </>
        ) : (
          <>
            <div className="tabs">
              <button className={mode === "signin" ? "active" : "link"} onClick={() => show("signin")}>Sign in</button>
              <button className={mode === "signup" ? "active" : "link"} onClick={() => show("signup")}>Sign up</button>
            </div>
            <form onSubmit={submit}>
              {mode === "signup" && <label>Name<input name="name" value={form.name} onChange={update} autoComplete="name" required /></label>}
              <label>Email<input name="email" type="email" value={form.email} onChange={update} autoComplete="email" required /></label>
              {(mode === "reset" || mode === "verify") && <label>6-digit code<input name="otp" inputMode="numeric" pattern="[0-9]{6}" value={form.otp} onChange={update} required /></label>}
              {mode !== "forgot" && mode !== "verify" && <label>{mode === "reset" ? "New password" : "Password"}<input name="password" type="password" minLength="8" maxLength="128" value={form.password} onChange={update} autoComplete={mode === "signin" ? "current-password" : "new-password"} required /></label>}
              <button type="submit" disabled={busy}>{busy ? "Please wait…" : mode === "forgot" ? "Send code" : mode === "reset" ? "Reset password" : mode === "verify" ? "Verify email" : mode === "signup" ? "Create account" : "Sign in"}</button>
            </form>
            {mode === "signin" && <button className="link forgot" onClick={() => show("forgot")}>Forgot password?</button>}
            {mode === "verify" && <button className="link forgot" onClick={resend} disabled={busy}>Send a new code</button>}
            {(mode === "forgot" || mode === "reset" || mode === "verify") && <button className="link forgot" onClick={() => show("signin")}>Back to sign in</button>}
          </>
        )}
        {message && <p role="status">{message}</p>}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);

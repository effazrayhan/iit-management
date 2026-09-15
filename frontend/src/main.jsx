import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";
import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const API = import.meta.env.VITE_API_URL;

function App() {
  const [user, setUser] = useState(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token)
      fetch(`${API}/api/me`, { headers: { Authorization: `Bearer ${token}` } })
        .then((response) => response.ok && response.json())
        .then((data) => data && setUser(data));
  }, []);

  async function login(credential) {
    setMessage("");
    const response = await fetch(`${API}/api/auth/google`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential }),
    });
    const data = await response.json();
    if (!response.ok) return setMessage(data.detail || "Sign-in failed");
    if (!data.token) return setMessage("Teacher account submitted for admin approval.");
    localStorage.setItem("token", data.token);
    setUser(data.user);
  }

  function logout() {
    localStorage.removeItem("token");
    setUser(null);
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
            <button onClick={logout}>Sign out</button>
          </>
        ) : (
          <>
            <p>Use your IIT account to continue.</p>
            <GoogleLogin onSuccess={({ credential }) => login(credential)} onError={() => setMessage("Sign-in failed")} />
          </>
        )}
        {message && <p role="alert">{message}</p>}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(
  <GoogleOAuthProvider clientId={import.meta.env.VITE_GOOGLE_CLIENT_ID}>
    <App />
  </GoogleOAuthProvider>
);

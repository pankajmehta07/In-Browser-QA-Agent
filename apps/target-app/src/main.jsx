import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

function getInitialVariant() {
  const params = new URLSearchParams(window.location.search);
  const variant = params.get("variant");

  if (["original", "changed", "flaky"].includes(variant)) {
    return variant;
  }

  return "original";
}
function App() {
  const [page, setPage] = useState("login");
  const [variant, setVariant] = useState(getInitialVariant);
  const [flakyButtonName] = useState(() =>
    Math.random() > 0.5 ? "Login" : "Delete",
  );
  const [email, setEmail] = useState("user@example.com");
  const [password, setPassword] = useState("");

  function handleLogin(event) {
    event.preventDefault();

    if (email && password) {
      setPage("dashboard");
    }
  }

  function renderLoginButton() {
    if (variant === "changed") {
      return (
        <div className="button-row moved">
          <button id="sign-in-button" type="submit">
            Sign In
          </button>
        </div>
      );
    }

    if (variant === "flaky") {
      return (
        <div className="button-row">
          <button
            id={flakyButtonName === "Login" ? "login-button" : "delete-button"}
            type={flakyButtonName === "Login" ? "submit" : "button"}
          >
            {flakyButtonName}
          </button>
        </div>
      );
    }

    return (
      <div className="button-row">
        <button id="login-button" type="submit">
          Login
        </button>
      </div>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Demo website</p>
          <h1>Acme Settings Portal</h1>
        </div>

        <button
          className="variant-button"
          type="button"
          onClick={() =>
            setVariant((current) => {
              if (current === "original") {
                return "changed";
              }

              if (current === "changed") {
                return "flaky";
              }

              return "original";
            })
          }
        >
          DOM Variant: {variant}
        </button>
      </header>

      {page === "login" && (
        <section className="panel">
          <h2>Login</h2>

          <form onSubmit={handleLogin}>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              aria-label="Email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />

            <label htmlFor="password">Password</label>
            <input
              id="password"
              aria-label="Password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />

            {renderLoginButton()}
          </form>
        </section>
      )}

      {page === "dashboard" && (
        <section className="panel">
          <h2>Dashboard</h2>
          <p>Welcome back.</p>

          <nav className="nav-actions">
            <button type="button" onClick={() => setPage("settings")}>
              Settings
            </button>

            <button type="button" onClick={() => setPage("login")}>
              Log out
            </button>
          </nav>
        </section>
      )}

      {page === "settings" && (
        <section className="panel">
          <h2>Settings</h2>

          <label htmlFor="settings-email">Email</label>
          <input
            id="settings-email"
            aria-label="Email"
            value="user@example.com"
            readOnly
          />

          <button type="button" onClick={() => setPage("dashboard")}>
            Back to Dashboard
          </button>
        </section>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);

import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css"

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
    Math.random() > 0.5 ? "Login" : "Delete"
  );

  const [email, setEmail] = useState("user@example.com");
  const [password, setPassword] = useState("");

  const [users, setUsers] = useState([
    { name: "Alice Johnson", email: "alice@example.com" },
    { name: "Ramesh Thapa", email: "ramesh@example.com" }
  ]);
  const [newUserName, setNewUserName] = useState("");
  const [newUserEmail, setNewUserEmail] = useState("");

  const [projects, setProjects] = useState([
    "QA Agent MVP",
    "Accessibility Review"
  ]);
  const [newProjectName, setNewProjectName] = useState("");

  function handleLogin(event) {
    event.preventDefault();

    if (email && password) {
      setPage("dashboard");
    }
  }

  function addUser(event) {
    event.preventDefault();

    if (!newUserName || !newUserEmail) {
      return;
    }

    setUsers((current) => [
      ...current,
      { name: newUserName, email: newUserEmail }
    ]);
    setNewUserName("");
    setNewUserEmail("");
  }

  function addProject(event) {
    event.preventDefault();

    if (!newProjectName) {
      return;
    }

    setProjects((current) => [...current, newProjectName]);
    setNewProjectName("");
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

  function getVariantLabel(original, changed) {
    return variant === "changed" ? changed : original;
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Demo website</p>
          <h1>Acme Operations Portal</h1>
        </div>

        <button
          id="dom-variant-toggle"
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
        <section className="panel wide-panel">
          <h2>Dashboard</h2>
          <p>Welcome back. Choose an area to manage.</p>

          <nav className="nav-grid" aria-label="Main navigation">
            <button type="button" onClick={() => setPage("settings")}>
              Settings
            </button>

            <button type="button" onClick={() => setPage("users")}>
              Users
            </button>

            <button type="button" onClick={() => setPage("projects")}>
              Projects
            </button>

            <button type="button" onClick={() => setPage("billing")}>
              Billing
            </button>

            <button type="button" onClick={() => setPage("profile")}>
              Profile
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

          <button
            id="back-to-dashboard-button"
            type="button"
            onClick={() => setPage("dashboard")}
          >
            Back to Dashboard
          </button>
        </section>
      )}

      {page === "users" && (
        <section className="panel wide-panel">
          <div className="section-heading">
            <div>
              <h2>Users</h2>
              <p>Manage workspace members.</p>
            </div>
          </div>

          <div className="content-grid">
            <section className="subpanel">
              <h3>Team Members</h3>
              <ul className="item-list">
                {users.map((user) => (
                  <li key={`${user.name}-${user.email}`}>
                    <strong>{user.name}</strong>
                    <span>{user.email}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="subpanel">
              <h3>{getVariantLabel("Add User", "New User")}</h3>

              <form onSubmit={addUser}>
                <label htmlFor="new-user-name">Name</label>
                <input
                  id="new-user-name"
                  aria-label="Name"
                  value={newUserName}
                  onChange={(event) => setNewUserName(event.target.value)}
                />

                <label htmlFor="new-user-email">User Email</label>
                <input
                  id="new-user-email"
                  aria-label="User Email"
                  value={newUserEmail}
                  onChange={(event) => setNewUserEmail(event.target.value)}
                />

                <button
                  id={
                    variant === "changed"
                      ? "new-user-button"
                      : "add-user-button"
                  }
                  type="submit"
                >
                  {getVariantLabel("Add User", "New User")}
                </button>
              </form>
            </section>
          </div>

          <button type="button" onClick={() => setPage("dashboard")}>
            Back to Dashboard
          </button>
        </section>
      )}

      {page === "projects" && (
        <section className="panel wide-panel">
          <h2>Projects</h2>
          <p>Track active product work.</p>

          <div className="content-grid">
            <section className="subpanel">
              <h3>Active Projects</h3>
              <ul className="item-list">
                {projects.map((project) => (
                  <li key={project}>
                    <strong>{project}</strong>
                    <span>Active</span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="subpanel">
              <h3>{getVariantLabel("Create Project", "New Project")}</h3>

              <form onSubmit={addProject}>
                <label htmlFor="project-name">Project Name</label>
                <input
                  id="project-name"
                  aria-label="Project Name"
                  value={newProjectName}
                  onChange={(event) => setNewProjectName(event.target.value)}
                />

                <button
                  id={
                    variant === "changed"
                      ? "new-project-button"
                      : "create-project-button"
                  }
                  type="submit"
                >
                  {getVariantLabel("Create Project", "New Project")}
                </button>
              </form>
            </section>
          </div>

          <button type="button" onClick={() => setPage("dashboard")}>
            Back to Dashboard
          </button>
        </section>
      )}

      {page === "billing" && (
        <section className="panel">
          <h2>Billing</h2>

          <label htmlFor="current-plan">Current Plan</label>
          <input
            id="current-plan"
            aria-label="Current Plan"
            value="Pro"
            readOnly
          />

          <div className="info-block">
            <h3>Payment Method</h3>
            <p>Visa ending in 4242</p>
          </div>

          <button type="button">Update Plan</button>

          <button type="button" onClick={() => setPage("dashboard")}>
            Back to Dashboard
          </button>
        </section>
      )}

      {page === "profile" && (
        <section className="panel">
          <h2>Profile</h2>

          <label htmlFor="profile-name">Name</label>
          <input
            id="profile-name"
            aria-label="Name"
            value="Neev Badu"
            readOnly
          />

          <label htmlFor="profile-email">Profile Email</label>
          <input
            id="profile-email"
            aria-label="Profile Email"
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
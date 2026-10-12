import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity, Bell, BriefcaseBusiness, Building2, Check, ChevronDown,
  CircleDollarSign, FolderKanban, LayoutDashboard, LogOut, Menu,
  MoreHorizontal, Plus, Search, Settings, ShieldCheck, Sparkles,
  UserRound, Users, X,
} from "lucide-react";
import "./style.css";

function getInitialVariant() {
  const variant = new URLSearchParams(window.location.search).get("variant");
  return ["original", "changed", "flaky"].includes(variant) ? variant : "original";
}

const navigation = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "projects", label: "Projects", icon: FolderKanban },
  { id: "users", label: "Users", icon: Users },
  { id: "billing", label: "Billing", icon: CircleDollarSign },
  { id: "playground", label: "QA Playground", icon: Sparkles },
];

const initialUsers = [
  { name: "Alice Johnson", email: "alice@example.com", role: "Admin", status: "Active" },
  { name: "Ramesh Thapa", email: "ramesh@example.com", role: "Developer", status: "Active" },
  { name: "Maya Chen", email: "maya@example.com", role: "QA Engineer", status: "Invited" },
  { name: "Jordan Lee", email: "jordan@example.com", role: "Designer", status: "Active" },
];

const initialProjects = [
  { name: "QA Agent MVP", owner: "Neev Badu", progress: 78, status: "In progress", updated: "Today" },
  { name: "Accessibility Review", owner: "Maya Chen", progress: 46, status: "At risk", updated: "Yesterday" },
  { name: "Checkout Redesign", owner: "Jordan Lee", progress: 100, status: "Complete", updated: "Aug 28" },
];

function App() {
  const [page, setPage] = useState("login");
  const [variant, setVariant] = useState(getInitialVariant);
  const [flakyButtonName] = useState(() => (Math.random() > 0.5 ? "Login" : "Delete"));
  const [email, setEmail] = useState("user@example.com");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const [search, setSearch] = useState("");
  const [users, setUsers] = useState(initialUsers);
  const [newUserName, setNewUserName] = useState("");
  const [newUserEmail, setNewUserEmail] = useState("");
  const [newUserRole, setNewUserRole] = useState("Developer");
  const [projects, setProjects] = useState(initialProjects);
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectOwner, setNewProjectOwner] = useState("Neev Badu");
  const [profile, setProfile] = useState({ name: "Neev Badu", email: "user@example.com", title: "QA Lead" });
  const [settings, setSettings] = useState({ emailReports: true, failedRunAlerts: true, weeklyDigest: false });
  const [plan, setPlan] = useState("Pro");
  const [playground, setPlayground] = useState({
    name: "Smoke test",
    notes: "",
    priority: "Medium",
    requiresApproval: false,
    counter: 0,
    hoverDetected: false,
  });

  const filteredUsers = useMemo(() => {
    const query = search.toLowerCase();
    return users.filter((user) => `${user.name} ${user.email} ${user.role}`.toLowerCase().includes(query));
  }, [search, users]);

  function showNotice(message) {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 2600);
  }

  function navigate(nextPage) {
    setPage(nextPage);
    setMobileNavOpen(false);
    setSearch("");
  }

  function handleLogin(event) {
    event.preventDefault();
    if (email && password) navigate("dashboard");
  }

  function addUser(event) {
    event.preventDefault();
    if (!newUserName || !newUserEmail) return;
    setUsers((current) => [...current, {
      name: newUserName, email: newUserEmail, role: newUserRole, status: "Invited",
    }]);
    showNotice(`${newUserName} was invited to the workspace.`);
    setNewUserName("");
    setNewUserEmail("");
  }

  function addProject(event) {
    event.preventDefault();
    if (!newProjectName) return;
    setProjects((current) => [...current, {
      name: newProjectName, owner: newProjectOwner, progress: 0,
      status: "In progress", updated: "Just now",
    }]);
    showNotice(`${newProjectName} was created.`);
    setNewProjectName("");
  }

  function getVariantLabel(original, changed) {
    return variant === "changed" ? changed : original;
  }

  function renderLoginButton() {
    if (variant === "changed") return <button id="sign-in-button" type="submit">Sign In</button>;
    if (variant === "flaky") {
      return <button id={flakyButtonName === "Login" ? "login-button" : "delete-button"} type={flakyButtonName === "Login" ? "submit" : "button"}>{flakyButtonName}</button>;
    }
    return <button id="login-button" type="submit">Login</button>;
  }

  if (page === "login") {
    return (
      <main className="login-page">
        <section className="login-story" aria-label="Product introduction">
          <Brand light />
          <div className="story-content">
            <p className="story-kicker">Operations, without the overhead</p>
            <h1>Keep every project moving in the same direction.</h1>
            <p>Plan work, manage your team, and understand progress from one calm workspace.</p>
            <div className="story-proof"><div className="avatar-stack"><span>NB</span><span>MC</span><span>JL</span></div><span>Trusted by growing product teams</span></div>
          </div>
          <p className="story-footnote">Acme Operations Portal</p>
        </section>
        <section className="login-workspace">
          <div className="login-toolbar"><span className={`variant-dot ${variant}`} /><button id="dom-variant-toggle" className="variant-button" type="button" onClick={() => setVariant((current) => current === "original" ? "changed" : current === "changed" ? "flaky" : "original")}>DOM Variant: {variant}</button></div>
          <div className="login-card">
            <div className="mobile-brand"><Brand /></div>
            <p className="eyebrow">Welcome back</p><h2>Login</h2>
            <p className="subtle">Enter your workspace credentials to continue.</p>
            <form onSubmit={handleLogin}>
              <label htmlFor="email">Email</label>
              <input id="email" aria-label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
              <div className="label-row"><label htmlFor="password">Password</label><button className="text-button" type="button" onClick={() => showNotice("Password reset link sent.")}>Forgot password?</button></div>
              <div className="password-field"><input id="password" aria-label="Password" type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter password123" /><button type="button" className="show-password" onClick={() => setShowPassword((current) => !current)}>{showPassword ? "Hide" : "Show"}</button></div>
              <div className={`button-row ${variant === "changed" ? "moved" : ""}`}>{renderLoginButton()}</div>
            </form>
            <p className="login-hint">Demo password: <code>password123</code></p>
          </div>
        </section>
        {notice && <Toast message={notice} />}
      </main>
    );
  }

  return (
    <main className="product-shell">
      <aside className={`sidebar ${mobileNavOpen ? "open" : ""}`}>
        <Brand />
        <button className="close-nav icon-button" type="button" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)}><X size={20} /></button>
        <nav aria-label="Main navigation">
          <p className="nav-label">Workspace</p>
          {navigation.map(({ id, label, icon: Icon }) => <button key={id} className={page === id ? "active" : ""} type="button" onClick={() => navigate(id)}><Icon size={18} />{label}</button>)}
          <p className="nav-label">Account</p>
          <button className={page === "settings" ? "active" : ""} type="button" onClick={() => navigate("settings")}><Settings size={18} />Settings</button>
          <button className={page === "profile" ? "active" : ""} type="button" onClick={() => navigate("profile")}><UserRound size={18} />Profile</button>
        </nav>
        <div className="sidebar-footer">
          <div className="workspace-switcher"><span className="company-avatar">A</span><div><strong>Acme Inc.</strong><small>Pro workspace</small></div><ChevronDown size={16} /></div>
          <button type="button" onClick={() => navigate("login")}><LogOut size={18} />Log out</button>
        </div>
      </aside>
      {mobileNavOpen && <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)} />}
      <section className="app-main">
        <header className="app-header">
          <div className="header-left"><button className="menu-button icon-button" type="button" aria-label="Open navigation" onClick={() => setMobileNavOpen(true)}><Menu size={20} /></button><div className="global-search"><Search size={17} /><input aria-label="Search workspace" placeholder="Search workspace" /></div></div>
          <div className="header-actions">
            <div className="variant-control"><span className={`variant-dot ${variant}`} /><select aria-label="DOM Variant" value={variant} onChange={(event) => setVariant(event.target.value)}><option value="original">Original DOM</option><option value="changed">Changed DOM</option><option value="flaky">Flaky DOM</option></select></div>
            <button className="icon-button notification-button" type="button" aria-label="Notifications" onClick={() => showNotice("You are all caught up.")}><Bell size={19} /><span /></button>
            <button className="profile-button" type="button" onClick={() => navigate("profile")}><span>NB</span><div><strong>Neev Badu</strong><small>QA Lead</small></div></button>
          </div>
        </header>
        <div className="page-content">
          {page === "dashboard" && <DashboardPage projects={projects} users={users} navigate={navigate} />}
          {page === "users" && <UsersPage users={filteredUsers} search={search} setSearch={setSearch} newUserName={newUserName} setNewUserName={setNewUserName} newUserEmail={newUserEmail} setNewUserEmail={setNewUserEmail} newUserRole={newUserRole} setNewUserRole={setNewUserRole} addUser={addUser} variant={variant} getVariantLabel={getVariantLabel} />}
          {page === "projects" && <ProjectsPage projects={projects} newProjectName={newProjectName} setNewProjectName={setNewProjectName} newProjectOwner={newProjectOwner} setNewProjectOwner={setNewProjectOwner} addProject={addProject} variant={variant} getVariantLabel={getVariantLabel} />}
          {page === "billing" && <BillingPage plan={plan} setPlan={setPlan} showNotice={showNotice} />}
          {page === "playground" && <PlaygroundPage state={playground} setState={setPlayground} />}
          {page === "settings" && <SettingsPage settings={settings} setSettings={setSettings} showNotice={showNotice} />}
          {page === "profile" && <ProfilePage profile={profile} setProfile={setProfile} showNotice={showNotice} />}
        </div>
      </section>
      {notice && <Toast message={notice} />}
    </main>
  );
}

function Brand({ light = false }) {
  return <div className={`brand ${light ? "brand-light" : ""}`}><span className="brand-mark"><Sparkles size={18} /></span>Northstar</div>;
}

function PageHeading({ eyebrow, title, description, action }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p>{description}</p></div>{action}</div>;
}

function DashboardPage({ projects, users, navigate }) {
  return <><PageHeading eyebrow="Monday, September 22" title="Dashboard" description="Here is what is happening across your workspace." action={<button type="button" onClick={() => navigate("projects")}><Plus size={17} />Create Project</button>} /><section className="metric-grid" aria-label="Workspace overview"><Metric icon={FolderKanban} label="Active projects" value={projects.filter((project) => project.status !== "Complete").length} trend="2 due this week" tone="blue" /><Metric icon={Users} label="Team members" value={users.length} trend="1 invitation pending" tone="green" /><Metric icon={Activity} label="Test pass rate" value="96.4%" trend="+3.2% this month" tone="violet" /><Metric icon={ShieldCheck} label="Open issues" value="7" trend="3 need attention" tone="amber" /></section><section className="dashboard-grid"><article className="surface project-overview"><div className="surface-heading"><div><h2>Project overview</h2><p>Progress across active initiatives</p></div><button className="text-button" type="button" onClick={() => navigate("projects")}>View all</button></div><div className="project-list">{projects.slice(0, 3).map((project) => <ProjectRow key={project.name} project={project} />)}</div></article><article className="surface activity-feed"><div className="surface-heading"><div><h2>Recent activity</h2><p>Latest workspace updates</p></div><MoreHorizontal size={19} /></div><ul><ActivityItem initials="MC" title="Maya completed an accessibility review" meta="QA Agent MVP · 18 minutes ago" /><ActivityItem initials="RT" title="Ramesh invited two collaborators" meta="Workspace · 1 hour ago" /><ActivityItem initials="JL" title="Jordan updated the checkout flow" meta="Checkout Redesign · 3 hours ago" /><ActivityItem initials="NB" title="You created a regression suite" meta="QA Agent MVP · Yesterday" /></ul></article></section></>;
}

function Metric({ icon: Icon, label, value, trend, tone }) {
  return <article className="metric"><span className={`metric-icon ${tone}`}><Icon size={19} /></span><div><p>{label}</p><strong>{value}</strong><small>{trend}</small></div></article>;
}

function ProjectRow({ project }) {
  return <div className="project-row"><span className="project-icon"><BriefcaseBusiness size={18} /></span><div className="project-copy"><div><strong>{project.name}</strong><span className={`status-tag ${project.status.toLowerCase().replaceAll(" ", "-")}`}>{project.status}</span></div><small>{project.owner} · Updated {project.updated}</small><div className="progress-track"><span style={{ width: `${project.progress}%` }} /></div></div><b>{project.progress}%</b></div>;
}

function ActivityItem({ initials, title, meta }) {
  return <li><span className="activity-avatar">{initials}</span><div><strong>{title}</strong><small>{meta}</small></div></li>;
}

function UsersPage(props) {
  const [showForm, setShowForm] = useState(false);
  return <><PageHeading eyebrow="Workspace" title="Users" description="Manage access, roles, and invitations for your team." action={!showForm && <button type="button" onClick={() => setShowForm(true)}><Plus size={17} />{props.getVariantLabel("Add User", "New User")}</button>} /><section className="surface table-surface"><div className="section-title"><div><h2>Team Members</h2><p>{props.users.length} people in this workspace</p></div></div><div className="table-toolbar"><div className="search-field"><Search size={17} /><input aria-label="Search users" placeholder="Search members" value={props.search} onChange={(event) => props.setSearch(event.target.value)} /></div><select aria-label="Filter by role"><option>All roles</option><option>Admin</option><option>Developer</option><option>QA Engineer</option></select></div><div className="data-table"><div className="table-row table-head"><span>Member</span><span>Role</span><span>Status</span><span>Actions</span></div>{props.users.map((user) => <div className="table-row" key={user.email}><div className="member-cell"><span className="user-avatar">{user.name.split(" ").map((part) => part[0]).join("")}</span><div><strong>{user.name}</strong><small>{user.email}</small></div></div><span>{user.role}</span><span><i className={`status-dot ${user.status.toLowerCase()}`} />{user.status}</span><MoreHorizontal size={18} /></div>)}</div></section>{showForm && <Modal title={props.getVariantLabel("Add User", "New User")} description="Invite a teammate to your workspace." onClose={() => setShowForm(false)}><form onSubmit={(event) => { props.addUser(event); setShowForm(false); }}><label htmlFor="new-user-name">Name</label><input id="new-user-name" aria-label="Name" value={props.newUserName} onChange={(event) => props.setNewUserName(event.target.value)} placeholder="Full name" required /><label htmlFor="new-user-email">User Email</label><input id="new-user-email" aria-label="User Email" type="email" value={props.newUserEmail} onChange={(event) => props.setNewUserEmail(event.target.value)} placeholder="name@company.com" required /><label htmlFor="new-user-role">Role</label><select id="new-user-role" value={props.newUserRole} onChange={(event) => props.setNewUserRole(event.target.value)}><option>Developer</option><option>QA Engineer</option><option>Designer</option><option>Admin</option></select><div className="modal-actions"><button className="secondary-button" type="button" onClick={() => setShowForm(false)}>Cancel</button><button id={props.variant === "changed" ? "new-user-button" : "add-user-button"} type="submit">{props.getVariantLabel("Add User", "New User")}</button></div></form></Modal>}</>;
}

function ProjectsPage(props) {
  const [showForm, setShowForm] = useState(false);
  return <><PageHeading eyebrow="Delivery" title="Projects" description="Track milestones, ownership, and delivery health." action={!showForm && <button type="button" onClick={() => setShowForm(true)}><Plus size={17} />{props.getVariantLabel("Create Project", "New Project")}</button>} /><div className="section-title standalone"><div><h2>Active Projects</h2><p>{props.projects.length} projects across the workspace</p></div></div><section className="project-grid" aria-label="Active Projects">{props.projects.map((project) => <article className="project-card" key={project.name}><div className="project-card-top"><span className="project-icon large"><FolderKanban size={20} /></span><MoreHorizontal size={19} /></div><h2>{project.name}</h2><p>Owned by {project.owner}</p><div className="project-meta"><span className={`status-tag ${project.status.toLowerCase().replaceAll(" ", "-")}`}>{project.status}</span><small>Updated {project.updated}</small></div><div className="progress-label"><span>Progress</span><strong>{project.progress}%</strong></div><div className="progress-track"><span style={{ width: `${project.progress}%` }} /></div></article>)}</section>{showForm && <Modal title={props.getVariantLabel("Create Project", "New Project")} description="Set up a new project for your team." onClose={() => setShowForm(false)}><form onSubmit={(event) => { props.addProject(event); setShowForm(false); }}><label htmlFor="project-name">Project Name</label><input id="project-name" aria-label="Project Name" value={props.newProjectName} onChange={(event) => props.setNewProjectName(event.target.value)} placeholder="Project name" required /><label htmlFor="project-owner">Project Owner</label><select id="project-owner" value={props.newProjectOwner} onChange={(event) => props.setNewProjectOwner(event.target.value)}><option>Neev Badu</option><option>Maya Chen</option><option>Ramesh Thapa</option><option>Jordan Lee</option></select><div className="modal-actions"><button className="secondary-button" type="button" onClick={() => setShowForm(false)}>Cancel</button><button id={props.variant === "changed" ? "new-project-button" : "create-project-button"} type="submit">{props.getVariantLabel("Create Project", "New Project")}</button></div></form></Modal>}</>;
}

function BillingPage({ plan, setPlan, showNotice }) {
  return <><PageHeading eyebrow="Workspace" title="Billing" description="Manage your subscription, usage, and payment details." /><section className="billing-grid"><article className="surface plan-card"><div><span className="plan-icon"><Building2 size={21} /></span><p>Current Plan</p><h2>{plan}</h2><span className="plan-price">$29 <small>/ member / month</small></span></div><button type="button" onClick={() => { const next = plan === "Pro" ? "Business" : "Pro"; setPlan(next); showNotice(`Plan changed to ${next}.`); }}>Update Plan</button></article><article className="surface usage-card"><div className="surface-heading"><div><h2>Monthly usage</h2><p>September 1–30</p></div><strong>68%</strong></div><div className="usage-bar"><span /></div><div className="usage-labels"><span>6,842 of 10,000 test runs</span><span>3,158 remaining</span></div></article></section><section className="surface payment-card"><div className="surface-heading"><div><h2>Payment Method</h2><p>Your default method for subscription charges.</p></div><button className="secondary-button" type="button" onClick={() => showNotice("Payment method editor opened.")}>Edit</button></div><div className="payment-method"><span className="card-brand">VISA</span><div><strong>Visa ending in 4242</strong><small>Expires 09/29</small></div></div></section></>;
}

function SettingsPage({ settings, setSettings, showNotice }) {
  const options = [["emailReports", "Email reports", "Receive a summary after every completed suite."], ["failedRunAlerts", "Failed run alerts", "Get notified immediately when a critical test fails."], ["weeklyDigest", "Weekly digest", "A Monday summary of trends across your workspace."]];
  return <><PageHeading eyebrow="Preferences" title="Settings" description="Configure notifications and workspace behavior." /><section className="surface settings-surface"><div className="settings-header"><h2>Notifications</h2><p>Choose which updates you want to receive.</p></div>{options.map(([key, label, description]) => <label className="setting-row" key={key}><div><strong>{label}</strong><span>{description}</span></div><input id={`setting-${key}`} aria-label={label} type="checkbox" checked={settings[key]} onChange={() => setSettings((current) => ({ ...current, [key]: !current[key] }))} /><i /></label>)}<div className="settings-footer"><label htmlFor="settings-email">Email</label><input id="settings-email" aria-label="Email" value="user@example.com" readOnly /><button type="button" onClick={() => showNotice("Settings saved.")}>Save Changes</button></div></section></>;
}

function PlaygroundPage({ state, setState }) {
  function update(key, value) {
    setState((current) => ({ ...current, [key]: value }));
  }

  function reset() {
    setState({
      name: "Smoke test",
      notes: "",
      priority: "Medium",
      requiresApproval: false,
      counter: 0,
      hoverDetected: false,
    });
  }

  return <><PageHeading eyebrow="Automation lab" title="QA Playground" description="Exercise form controls, pointer events, keyboard input, and UI assertions." action={<button type="button" onClick={reset}>Reset Playground</button>} /><section className="playground-grid"><article className="surface playground-form"><div className="surface-heading"><div><h2>Scenario controls</h2><p>A stable test surface for the expanded action engine.</p></div></div><label htmlFor="scenario-name">Scenario Name</label><input id="scenario-name" value={state.name} onChange={(event) => update("name", event.target.value)} /><label htmlFor="test-notes">Test Notes</label><textarea id="test-notes" value={state.notes} onChange={(event) => update("notes", event.target.value)} placeholder="Add execution notes" /><label htmlFor="scenario-priority">Priority</label><select id="scenario-priority" value={state.priority} onChange={(event) => update("priority", event.target.value)}><option>Low</option><option>Medium</option><option>High</option><option>Critical</option></select><label className="playground-check" htmlFor="requires-approval"><input id="requires-approval" type="checkbox" checked={state.requiresApproval} onChange={(event) => update("requiresApproval", event.target.checked)} /><span><strong>Requires approval</strong><small>Pause this scenario for human review.</small></span></label></article><article className="surface interaction-lab"><div className="surface-heading"><div><h2>Interaction lab</h2><p>Observable outcomes for pointer and state-based actions.</p></div></div><div className="counter-panel"><span>Counter</span><output aria-label="Counter value">{state.counter}</output><button type="button" onClick={() => update("counter", state.counter + 1)}>Increment counter</button></div><button className="hover-target" type="button" onMouseEnter={() => update("hoverDetected", true)}>Hover target</button><p className={`hover-result ${state.hoverDetected ? "visible" : ""}`} aria-label="Hover result">{state.hoverDetected ? "Hover detected" : "Waiting for hover"}</p><div className="playground-actions"><button type="button" disabled>Archive scenario</button><button className="secondary-button" type="button" onClick={reset}>Reset controls</button></div></article></section></>;
}

function ProfilePage({ profile, setProfile, showNotice }) {
  return <><PageHeading eyebrow="Account" title="Profile" description="Update your personal information and public details." /><section className="surface profile-surface"><div className="profile-intro"><span className="profile-avatar-large">NB</span><div><h2>{profile.name}</h2><p>{profile.title} at Acme Inc.</p><button className="text-button" type="button">Change photo</button></div></div><form onSubmit={(event) => { event.preventDefault(); showNotice("Profile changes saved."); }}><div className="form-grid"><div><label htmlFor="profile-name">Name</label><input id="profile-name" aria-label="Name" value={profile.name} onChange={(event) => setProfile((current) => ({ ...current, name: event.target.value }))} /></div><div><label htmlFor="profile-title">Job Title</label><input id="profile-title" aria-label="Job Title" value={profile.title} onChange={(event) => setProfile((current) => ({ ...current, title: event.target.value }))} /></div></div><label htmlFor="profile-email">Profile Email</label><input id="profile-email" aria-label="Profile Email" type="email" value={profile.email} onChange={(event) => setProfile((current) => ({ ...current, email: event.target.value }))} /><div className="form-actions"><button type="submit">Save Profile</button></div></form></section></>;
}

function Modal({ title, description, onClose, children }) {
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div className="modal-heading"><div><h2 id="modal-title">{title}</h2><p>{description}</p></div><button className="icon-button" type="button" aria-label="Close dialog" onClick={onClose}><X size={19} /></button></div>{children}</section></div>;
}

function Toast({ message }) {
  return <div className="toast" role="status"><span><Check size={15} /></span>{message}</div>;
}

createRoot(document.getElementById("root")).render(<App />);

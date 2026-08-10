import { useEffect, useMemo, useState } from "react";
import "./App.css";
import ChatPanel from "./ChatPanel.jsx";

const API_BASE = import.meta.env.VITE_API_BASE;
const PRIORITY_ORDER = { high: 0, medium: 1, low: 2 };
const HOURS = Array.from({ length: 12 }, (_, index) => index + 7);

const pad = (value) => String(value).padStart(2, "0");
const dateKey = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
const startOfWeek = (date) => {
  const copy = new Date(date);
  copy.setHours(0, 0, 0, 0);
  copy.setDate(copy.getDate() - copy.getDay());
  return copy;
};
const addDays = (date, days) => {
  const copy = new Date(date);
  copy.setDate(copy.getDate() + days);
  return copy;
};
const parseDate = (value) => value ? new Date(value) : null;
const taskPriority = (task) => task.priority || "medium";
const sortByPriority = (items) => [...items].sort((a, b) =>
  (PRIORITY_ORDER[taskPriority(a)] ?? 1) - (PRIORITY_ORDER[taskPriority(b)] ?? 1)
);

function normalizeEvents(data) {
  const raw = data?.events?.events ?? data?.events ?? [];
  return raw.map((event, index) => ({
    id: event.id ?? `event-${index}`,
    title: event.summary ?? event.title ?? "Calendar event",
    start: event.start?.dateTime ?? event.start?.date ?? event.start,
    end: event.end?.dateTime ?? event.end?.date ?? event.end,
    priority: event.priority ?? "medium",
    source: "event"
  })).filter((event) => event.start);
}

function normalizeTasks(data) {
  const raw = data?.Tasks?.Tasks ?? data?.Tasks ?? data?.tasks ?? [];
  return raw.map((task, index) => ({
    id: task.id ?? `task-${index}-${Date.now()}`,
    title: task.title ?? "Untitled task",
    deadline: task.deadline ?? task.due?.slice(0, 10) ?? "",
    estimated_duration: task.estimated_duration ?? task.estimated_duration_minutes / 60 ?? 1,
    priority: task.priority ?? "medium",
    reason: task.reason ?? ""
  }));
}

function Calendar({ items, view, setView, cursor, setCursor }) {
  const days = useMemo(() => {
    if (view === "day") return [new Date(cursor)];
    if (view === "week") return Array.from({ length: 7 }, (_, i) => addDays(startOfWeek(cursor), i));
    const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
    const gridStart = startOfWeek(first);
    return Array.from({ length: 42 }, (_, i) => addDays(gridStart, i));
  }, [cursor, view]);

  const move = (direction) => {
    const next = new Date(cursor);
    if (view === "month") next.setMonth(next.getMonth() + direction);
    else next.setDate(next.getDate() + direction * (view === "week" ? 7 : 1));
    setCursor(next);
  };
  const title = view === "month"
    ? cursor.toLocaleDateString(undefined, { month: "long", year: "numeric" })
    : view === "day"
      ? cursor.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })
      : `${days[0].toLocaleDateString(undefined, { month: "short", day: "numeric" })} – ${days[6].toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;

  const itemsForDay = (day) => sortByPriority(items.filter((item) => dateKey(parseDate(item.start)) === dateKey(day)));

  return (
    <section className="calendar-card">
      <div className="calendar-toolbar">
        <div className="calendar-nav">
          <button className="icon-button" onClick={() => move(-1)} aria-label="Previous period">‹</button>
          <button className="today-button" onClick={() => setCursor(new Date())}>Today</button>
          <button className="icon-button" onClick={() => move(1)} aria-label="Next period">›</button>
          <h2>{title}</h2>
        </div>
        <div className="view-switch" aria-label="Calendar view">
          {["day", "week", "month"].map((option) => (
            <button key={option} className={view === option ? "active" : ""} onClick={() => setView(option)}>{option}</button>
          ))}
        </div>
      </div>

      {view === "month" ? (
        <div className="month-view">
          {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => <div className="weekday" key={day}>{day}</div>)}
          {days.map((day) => (
            <button className={`month-day ${day.getMonth() !== cursor.getMonth() ? "outside" : ""} ${dateKey(day) === dateKey(new Date()) ? "today" : ""}`} key={dateKey(day)} onClick={() => { setCursor(day); setView("day"); }}>
              <span className="day-number">{day.getDate()}</span>
              <span className="month-items">
                {itemsForDay(day).slice(0, 3).map((item) => <span className={`calendar-event priority-${taskPriority(item)}`} key={item.id}>{item.title}</span>)}
                {itemsForDay(day).length > 3 && <span className="more-items">+{itemsForDay(day).length - 3} more</span>}
              </span>
            </button>
          ))}
        </div>
      ) : (
        <div className={`time-view ${view}`}>
          <div className="time-corner" />
          {days.map((day) => <button className={`time-day-head ${dateKey(day) === dateKey(new Date()) ? "today" : ""}`} key={dateKey(day)} onClick={() => { setCursor(day); setView("day"); }}><span>{day.toLocaleDateString(undefined, { weekday: "short" })}</span><strong>{day.getDate()}</strong></button>)}
          {HOURS.map((hour) => (
            <div className="time-row" key={hour}>
              <span className="hour-label">{hour > 12 ? hour - 12 : hour}:00 {hour >= 12 ? "PM" : "AM"}</span>
              {days.map((day) => {
                const slotItems = itemsForDay(day).filter((item) => parseDate(item.start)?.getHours() === hour);
                return <div className="time-cell" key={`${dateKey(day)}-${hour}`}>{slotItems.map((item) => <div className={`calendar-event priority-${taskPriority(item)}`} key={item.id}><strong>{item.title}</strong><span>{parseDate(item.start).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span></div>)}</div>;
              })}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [pendingTasks, setPendingTasks] = useState([]);
  const [scheduledTasks, setScheduledTasks] = useState([]);
  const [events, setEvents] = useState([]);
  const [selectedTask, setSelectedTask] = useState(null);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [notice, setNotice] = useState("");
  const [isScheduling, setIsScheduling] = useState(false);
  const [view, setView] = useState("week");
  const [cursor, setCursor] = useState(new Date());
  const [taskForm, setTaskForm] = useState({ title: "", deadline: "", duration: "", priority: "medium" });

  useEffect(() => {
    if (!isAuthenticated) return;
  
    fetch(`${API_BASE}/events`, {
      credentials: "include"
    })
      .then((response) => {
        if (!response.ok) throw new Error("Could not load events");
        return response.json();
      })
      .then((data) => setEvents(normalizeEvents(data)))
      .catch((error) => setNotice(error.message));
  }, [isAuthenticated]);
  
  useEffect(() => {
    let active = true;
  
    async function initializeApp() {
      try {
        const authResponse = await fetch(`${API_BASE}/auth/status`, {
          credentials: "include",
        });
        if (!authResponse.ok) {
          throw new Error("Authentication check failed");
        }
        const authData = await authResponse.json();
  
        if (!authData.authenticated) {
          if (active) setIsAuthenticated(false);
          return;
        }
        if (active) setIsAuthenticated(true);
        const initialResponse = await fetch(`${API_BASE}/initial`, {
          credentials: "include",
        });
  
        if (!initialResponse.ok) {
          throw new Error("Failed to initialize application");
        }
        const initialData = await initialResponse.json();
        const initialEvents = normalizeEvents(initialData);
        if (active) {
          setEvents(initialEvents);
        }
      } catch (error) {
        console.error("Application initialization failed:", error);
        if (active) {
          setIsAuthenticated(false);
          setEvents([]);
        }
      }
    }
    initializeApp();
    return () => {
      active = false;
    };
  }, []);
  const getEvents = async () => {
    try {
      const response = await fetch(`${API_BASE}/events`, { credentials: "include" });
      if (!response.ok) throw new Error("Could not load events");
      const data = await response.json();
      setEvents(normalizeEvents(data));
      setNotice("Calendar updated");
    } catch (error) { setNotice(error.message); }
  };
  const getTasks = async () => {
    try {
      const response = await fetch(`${API_BASE}/tasks`, { credentials: "include" });
      if (!response.ok) throw new Error("Could not load tasks");
      setPendingTasks(normalizeTasks(await response.json()));
      setNotice("Waiting tasks updated");
    } catch (error) { setNotice(error.message); }
  };
  const addTask = () => {
    const title = taskForm.title.trim();
    const duration = Number(taskForm.duration);
    if (!title || !taskForm.deadline || duration <= 0) return setNotice("Add a title, deadline, and duration.");
    setPendingTasks((current) => [...current, { id: `local-${Date.now()}`, title, deadline: taskForm.deadline, estimated_duration: duration, priority: taskForm.priority }]);
    setTaskForm({ title: "", deadline: "", duration: "", priority: "medium" });
    setShowTaskForm(false);
  };
  const updateTask = (event) => {
    event.preventDefault();
    setPendingTasks((current) => current.map((task) => task.id === selectedTask.id ? selectedTask : task));
    setSelectedTask(null);
  };
  const handleDraft = (drafts) => setPendingTasks((current) => {
    const draftTasks = drafts.map((task, index) => ({ ...task, id: task.id ?? `ai-${Date.now()}-${index}`, priority: task.priority ?? "medium", estimated_duration: task.estimated_duration ?? (task.estimated_duration_minutes || 60) / 60, aiDraft: true }));
    const nonDrafts = current.filter((task) => !task.aiDraft);
    return [...nonDrafts, ...draftTasks];
  });
  const scheduleWaitingTasks = async () => {
    if (!pendingTasks.length || isScheduling) return;
    setIsScheduling(true);
    try {
      const response = await fetch(`${API_BASE}/scheduledtasks`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          calendar: "primary",
          tasks: pendingTasks.map((task) => ({
            title: task.title,
            deadline: task.deadline,
            estimated_duration: Number(task.estimated_duration ?? 1),
            priority: task.priority ?? "medium",
            depends_on: task.depends_on ?? []
          }))
        })
      });
      const data = await response.json();
      if (!response.ok || data.error) throw new Error(data.detail ?? data.error ?? "Scheduling failed");

      const scheduled = data?.schedule?.scheduled ?? [];
      const unscheduled = data?.schedule?.unscheduled ?? [];
      const pendingByTitle = new Map(pendingTasks.map((task) => [task.title, task]));
      setScheduledTasks((current) => [
        ...current,
        ...scheduled.map((task, index) => ({
          ...pendingByTitle.get(task.title),
          ...task,
          id: task.id ?? `scheduled-${Date.now()}-${index}`,
          source: "task"
        }))
      ]);
      setPendingTasks(unscheduled.map((task, index) => ({
        ...pendingByTitle.get(task.title),
        ...task,
        id: pendingByTitle.get(task.title)?.id ?? `unscheduled-${Date.now()}-${index}`
      })));
      setNotice(scheduled.length
        ? `${scheduled.length} task${scheduled.length === 1 ? "" : "s"} scheduled${unscheduled.length ? `; ${unscheduled.length} still waiting` : ""}`
        : "No open time was found; tasks remain in the queue");
    } catch (error) {
      setNotice(error.message);
    } finally {
      setIsScheduling(false);
    }
  };
  const handleConfirmed = (result, confirmedDrafts) => {
    const scheduled = result?.schedule?.scheduled ?? result?.scheduled ?? [];
    const confirmedTitles = new Set(confirmedDrafts.map((task) => task.title));
    const priorityByTitle = Object.fromEntries(confirmedDrafts.map((task) => [task.title, task.priority ?? "medium"]));
    setPendingTasks((current) => current.filter((task) => !confirmedTitles.has(task.title)));
    setScheduledTasks((current) => [...current, ...scheduled.map((task, index) => ({ ...task, id: task.id ?? `scheduled-${Date.now()}-${index}`, priority: priorityByTitle[task.title] ?? task.priority ?? "medium", source: "task" }))]);
    setNotice(scheduled.length ? `${scheduled.length} task${scheduled.length === 1 ? "" : "s"} scheduled` : "Tasks confirmed");
    getEvents();
  };
  const calendarItems = [...events, ...scheduledTasks];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark">S</span><div><strong>SmartSchedule</strong><span>Your day, thoughtfully arranged</span></div></div>
        <div className="top-actions"><button className="secondary-button" onClick={getTasks}>↻ Sync tasks</button><button className="primary-button" onClick={getEvents}>↻ Sync calendar</button>{isAuthenticated ? <button className="avatar-button" aria-label="Google account">G</button> : <button className="login-button" onClick={() => { window.location.href = `${API_BASE}/auth/login`; }}>Login</button>}</div>
      </header>

      <main className="dashboard">
        <aside className="task-sidebar">
          <div className="section-title"><div><span className="eyebrow">INBOX</span><h2>Waiting to schedule</h2></div><button className="add-button" onClick={() => setShowTaskForm((open) => !open)}>+</button></div>
          {showTaskForm && <div className="compact-form"><input aria-label="Task title" placeholder="What needs doing?" value={taskForm.title} onChange={(e) => setTaskForm({ ...taskForm, title: e.target.value })}/><div><input aria-label="Deadline" type="date" value={taskForm.deadline} onChange={(e) => setTaskForm({ ...taskForm, deadline: e.target.value })}/><input aria-label="Duration hours" type="number" min="0.5" step="0.5" placeholder="Hours" value={taskForm.duration} onChange={(e) => setTaskForm({ ...taskForm, duration: e.target.value })}/></div><select aria-label="Priority" value={taskForm.priority} onChange={(e) => setTaskForm({ ...taskForm, priority: e.target.value })}><option value="high">High priority</option><option value="medium">Medium priority</option><option value="low">Low priority</option></select><button className="primary-button" onClick={addTask}>Add to queue</button></div>}
          <div className="task-list">
            {sortByPriority(pendingTasks).map((task) => <button className={`task-card priority-${taskPriority(task)}`} key={task.id} onClick={() => setSelectedTask({ ...task })}><span className="priority-dot"/><span className="task-copy"><strong>{task.title}</strong><span>{task.deadline ? `Due ${new Date(`${task.deadline}T12:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" })}` : "No deadline"} · {task.estimated_duration ?? 1}h</span></span>{task.aiDraft && <span className="ai-tag">AI</span>}</button>)}
            {!pendingTasks.length && <div className="empty-state"><span>✓</span><strong>Your queue is clear</strong><p>Add a task or ask the assistant to make a plan.</p></div>}
          </div>
          {pendingTasks.length > 0 && <div className="schedule-action"><button className="primary-button schedule-button" onClick={scheduleWaitingTasks} disabled={isScheduling}>{isScheduling ? <><span className="button-spinner"/> Scheduling…</> : <>✦ Schedule</>}</button><span>Find the best available times for {pendingTasks.length} task{pendingTasks.length === 1 ? "" : "s"}</span></div>}
          <div className="scheduled-summary"><div className="section-title"><div><span className="eyebrow">PLAN</span><h2>Scheduled tasks</h2></div><span className="count-badge">{scheduledTasks.length}</span></div>{sortByPriority(scheduledTasks).slice(0, 5).map((task) => <div className={`scheduled-row priority-${taskPriority(task)}`} key={task.id}><span className="priority-dot"/><div><strong>{task.title}</strong><span>{parseDate(task.start)?.toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" })}</span></div></div>)}{!scheduledTasks.length && <p className="muted">Confirmed tasks will appear here.</p>}</div>
        </aside>

        <Calendar items={calendarItems} view={view} setView={setView} cursor={cursor} setCursor={setCursor}/>
        <ChatPanel onDraftTasks={handleDraft} onTasksConfirmed={handleConfirmed}/>
      </main>

      {notice && <button className="toast" onClick={() => setNotice("")}>{notice}<span>×</span></button>}
      {selectedTask && <div className="modal-backdrop" onMouseDown={() => setSelectedTask(null)}><form className="edit-modal" onSubmit={updateTask} onMouseDown={(e) => e.stopPropagation()}><div className="modal-heading"><div><span className="eyebrow">EDIT TASK</span><h2>Task details</h2></div><button type="button" className="icon-button" onClick={() => setSelectedTask(null)}>×</button></div><label>Title<input value={selectedTask.title} onChange={(e) => setSelectedTask({ ...selectedTask, title: e.target.value })}/></label><div className="form-row"><label>Deadline<input type="date" value={selectedTask.deadline?.slice(0, 10) ?? ""} onChange={(e) => setSelectedTask({ ...selectedTask, deadline: e.target.value })}/></label><label>Duration (hours)<input type="number" min="0.5" step="0.5" value={selectedTask.estimated_duration} onChange={(e) => setSelectedTask({ ...selectedTask, estimated_duration: Number(e.target.value) })}/></label></div><label>Priority<select value={taskPriority(selectedTask)} onChange={(e) => setSelectedTask({ ...selectedTask, priority: e.target.value })}><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label><div className="modal-actions"><button type="button" className="secondary-button" onClick={() => setSelectedTask(null)}>Cancel</button><button className="primary-button">Save changes</button></div></form></div>}
    </div>
  );
}

export default App;

import { useState } from "react";
import "./App.css";

const API_BASE = "http://localhost:8000";

function App() {
  const [output, setOutput] = useState("");
  const [showEventForm, setShowEventForm] = useState(false);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [tasks, setTasks] = useState([]);

  const [eventForm, setEventForm] = useState({
    calendar: "primary",
    date: "",
    start: "",
    end: ""
  });

  const [taskForm, setTaskForm] = useState({
    title: "",
    deadline: "",
    duration: ""
  });

  const login = () => {
    window.location.href = `${API_BASE}/auth/login`;
  };

  const getEvents = async () => {
    try {
      const res = await fetch(`${API_BASE}/events`);
      const data = await res.json();
      setOutput(JSON.stringify(data, null, 2));
    } catch (err) {
      setOutput(`Fetch failed: ${err.message}`);
    }
  };

  const getTasks = async () => {
    try {
      const res = await fetch(`${API_BASE}/get-tasks`);
      const data = await res.json();
      setOutput(JSON.stringify(data, null, 2));
    } catch (err) {
      setOutput("Fetch failed");
    }
  };

  const submitEvent = async () => {
    const { calendar, date, start, end } = eventForm;
    if (!date || !start || !end) {
      setOutput("Please provide date, start time, and end time.");
      return;
    }
    try {
      const res = await fetch(
        `${API_BASE}/create-test-event?calendar=${encodeURIComponent(
          calendar
        )}&date=${encodeURIComponent(date)}&start=${encodeURIComponent(
          start
        )}&end=${encodeURIComponent(end)}`
      );
      if (!res.ok) {
        const data = await res.json();
        setOutput(JSON.stringify(data, null, 2));
        return;
      }
      setOutput("Event created.");
      setShowEventForm(false);
    } catch (err) {
      setOutput(`Create event failed: ${err.message}`);
    }
  };

  const addTask = () => {
    const title = taskForm.title.trim();
    const deadline = taskForm.deadline;
    const duration = parseFloat(taskForm.duration);

    if (!title || !deadline || Number.isNaN(duration) || duration <= 0) {
      setOutput("Please provide title, deadline date, and duration hours.");
      return;
    }

    setTasks((prev) => [
      ...prev,
      { title, deadline, estimated_duration: duration }
    ]);

    setTaskForm({ title: "", deadline: "", duration: "" });
  };

  const scheduleTasks = async () => {
    if (tasks.length === 0) {
      setOutput("No tasks to schedule.");
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/schedule-tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tasks, calendar: "primary" })
      });
      const data = await res.json();
      setOutput(`schedule successed`);
      if (res.ok && !data.error) {
        setTasks([]);
        setShowTaskForm(false);
      }
    } catch (err) {
      setOutput(`Schedule failed: ${err.message}`);
    }
  };

  return (
    <div className="page">
      <h1>Calendar AI Dashboard</h1>
      <div className="row">
        <button onClick={login}>Login with Google</button>
      </div>

      <div className="row">
        <button onClick={getEvents}>Get Events</button>
        <button onClick={() => setShowEventForm(true)}>Create Test Event</button>
      </div>

      {showEventForm && (
        <div className="panel">
          <select
            value={eventForm.calendar}
            onChange={(e) =>
              setEventForm((prev) => ({ ...prev, calendar: e.target.value }))
            }
          >
            <option value="primary">Primary</option>
          </select>
          <input
            placeholder="date"
            type="date"
            value={eventForm.date}
            onChange={(e) =>
              setEventForm((prev) => ({ ...prev, date: e.target.value }))
            }
          />
          <input
            placeholder="start_time"
            type="time"
            value={eventForm.start}
            onChange={(e) =>
              setEventForm((prev) => ({ ...prev, start: e.target.value }))
            }
          />
          <input
            placeholder="end_time"
            type="time"
            value={eventForm.end}
            onChange={(e) =>
              setEventForm((prev) => ({ ...prev, end: e.target.value }))
            }
          />
          <button onClick={submitEvent}>Create</button>
        </div>
      )}

      <div className="row">
        <button onClick={getTasks}>Get Tasks</button>
        <button onClick={() => setShowTaskForm(true)}>Add Tasks</button>
      </div>

      {showTaskForm && (
        <div className="panel">
          <input
            placeholder="title"
            type="text"
            value={taskForm.title}
            onChange={(e) =>
              setTaskForm((prev) => ({ ...prev, title: e.target.value }))
            }
          />
          <input
            placeholder="deadline date"
            type="date"
            value={taskForm.deadline}
            onChange={(e) =>
              setTaskForm((prev) => ({ ...prev, deadline: e.target.value }))
            }
          />
          <input
            placeholder="duration hours"
            type="number"
            step="0.5"
            min="0.5"
            value={taskForm.duration}
            onChange={(e) =>
              setTaskForm((prev) => ({ ...prev, duration: e.target.value }))
            }
          />
          <button onClick={addTask}>Add</button>
        </div>
      )}

      {tasks.length > 0 && (
        <div className="panel">
          <h3>Task Preview</h3>
          <ul>
            {tasks.map((task, idx) => (
              <li key={`${task.title}-${idx}`}>
                {idx + 1}. {task.title} | deadline: {task.deadline} | duration:{" "}
                {task.estimated_duration}h
              </li>
            ))}
          </ul>
          <button onClick={scheduleTasks}>Schedule</button>
        </div>
      )}

      <pre className="output">{output}</pre>
    </div>
  );
}

export default App;
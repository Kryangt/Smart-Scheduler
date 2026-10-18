import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import App from "./App";

global.fetch = vi.fn();

const mockResponse = (data, { ok = true, status = 200 } = {}) => ({
  ok,
  status,
  json: async () => data
});

beforeEach(() => {
  global.fetch.mockReset();
  global.fetch.mockImplementation((url) => {
    if (String(url).endsWith("/auth/status")) {
      return Promise.resolve(mockResponse({ authenticated: false }));
    }
    return Promise.resolve(mockResponse({}, { ok: false, status: 500 }));
  });
});

test("renders the dashboard for an unauthenticated user", async () => {
  render(<App />);
  expect(screen.getByText("SmartSchedule")).toBeInTheDocument();
  expect(screen.getByText("Waiting to schedule")).toBeInTheDocument();
  expect(screen.getByText("Scheduled tasks")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "day" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "week" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "month" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Login" })).toBeInTheDocument();
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
  expect(global.fetch).toHaveBeenCalledWith(
    expect.stringMatching(/\/auth\/status$/),
    { credentials: "include" }
  );
});

test("initializes the app and shows the Google avatar after authentication", async () => {
  global.fetch.mockImplementation((url) => {
    const requestUrl = String(url);
    if (requestUrl.endsWith("/auth/status")) {
      return Promise.resolve(mockResponse({ authenticated: true }));
    }
    if (requestUrl.endsWith("/initial") || requestUrl.endsWith("/events")) {
      return Promise.resolve(mockResponse({ events: [] }));
    }
    return Promise.resolve(mockResponse({}, { ok: false, status: 500 }));
  });

  render(<App />);
  expect(await screen.findByRole("button", { name: "Google account" })).toHaveTextContent("G");
  expect(screen.queryByRole("button", { name: "Login" })).not.toBeInTheDocument();
  await waitFor(() => {
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/events$/),
      { credentials: "include" }
    );
  });
});

test("adds a waiting task and opens it for editing", async () => {
  render(<App />);
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole("button", { name: "+" }));
  fireEvent.change(screen.getByLabelText("Task title"), { target: { value: "Finish proposal" } });
  fireEvent.change(screen.getByLabelText("Deadline"), { target: { value: "2026-07-25" } });
  fireEvent.change(screen.getByLabelText("Duration hours"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Priority"), { target: { value: "high" } });
  fireEvent.click(screen.getByText("Add to queue"));
  fireEvent.click(screen.getByText("Finish proposal"));
  expect(screen.getByText("Task details")).toBeInTheDocument();
  expect(screen.getByDisplayValue("Finish proposal")).toBeInTheDocument();
});

test("schedules all waiting tasks with the scheduling API", async () => {
  global.fetch.mockImplementation((url) => {
    const requestUrl = String(url);
    if (requestUrl.endsWith("/auth/status")) {
      return Promise.resolve(mockResponse({ authenticated: false }));
    }
    if (requestUrl.endsWith("/scheduledtasks")) {
      return Promise.resolve(mockResponse({
        schedule: {
          scheduled: [{ classification: {status: "classified", domain: "work", effort: "mental"}, title: "Finish proposal", start: "2026-07-25T09:00:00", end: "2026-07-25T11:00:00" }],
          unscheduled: []
        }
      }));
    }
    return Promise.resolve(mockResponse({}, { ok: false, status: 500 }));
  });
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: "+" }));
  fireEvent.change(screen.getByLabelText("Task title"), { target: { value: "Finish proposal" } });
  fireEvent.change(screen.getByLabelText("Deadline"), { target: { value: "2026-07-25" } });
  fireEvent.change(screen.getByLabelText("Duration hours"), { target: { value: "2" } });
  fireEvent.click(screen.getByText("Add to queue"));

  fireEvent.click(screen.getByRole("button", { name: /Schedule/ }));

  await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
    expect.stringMatching(/\/scheduledtasks$/),
    expect.objectContaining({ method: "POST" })
  ));
  const [url, options] = global.fetch.mock.calls.find(([requestUrl]) => String(requestUrl).endsWith("/scheduledtasks"));
  expect(url).toMatch(/\/scheduledtasks$/);
  expect(JSON.parse(options.body)).toEqual({
    calendar: "primary",
    tasks: [{
      title: "Finish proposal",
      deadline: "2026-07-25",
      estimated_duration: 2,
      priority: "medium",
      depends_on: []
    }]
  });
  expect(await screen.findByText("1 task scheduled")).toBeInTheDocument();
  expect(screen.getByText("Sat 9:00 AM")).toBeInTheDocument();
  expect(screen.getByTitle("Domain: work")).toBeInTheDocument();
  expect(screen.getByTitle("Effort: mental")).toBeInTheDocument();
});

test("syncs API events into the calendar instead of terminal output", async () => {
  const today = new Date();
  const visibleDate = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  global.fetch.mockImplementation((url) => {
    const requestUrl = String(url);
    if (requestUrl.endsWith("/auth/status")) {
      return Promise.resolve(mockResponse({ authenticated: false }));
    }
    if (requestUrl.endsWith("/events")) {
      return Promise.resolve(mockResponse({ events: [{ id: "1", summary: "Team review", start: { dateTime: `${visibleDate}T09:00:00` }, end: { dateTime: `${visibleDate}T10:00:00` } }] }));
    }
    return Promise.resolve(mockResponse({}, { ok: false, status: 500 }));
  });
  render(<App />);
  fireEvent.click(screen.getByRole("button", { name: /Sync calendar/ }));
  fireEvent.click(screen.getByRole("button", { name: "month" }));
  expect(await screen.findByText("Team review")).toBeInTheDocument();
  expect(document.querySelector("pre.output")).not.toBeInTheDocument();
});

test("shows an AI generation signal while waiting", async () => {
  global.fetch.mockImplementation((url) => {
    const requestUrl = String(url);
    if (requestUrl.endsWith("/auth/status")) {
      return Promise.resolve(mockResponse({ authenticated: false }));
    }
    if (requestUrl.endsWith("/task-decomposition")) {
      return new Promise(() => {});
    }
    return Promise.resolve(mockResponse({}, { ok: false, status: 500 }));
  });
  render(<App />);
  const input = screen.getByPlaceholderText("Ask me to plan your tasks…");
  fireEvent.change(input, { target: { value: "Plan my report" } });
  fireEvent.submit(input.closest("form"));
  await waitFor(() => expect(screen.getByLabelText("AI is generating a response")).toBeInTheDocument());
  expect(within(screen.getByLabelText("AI is generating a response")).getByText("Building your plan")).toBeInTheDocument();
});



test("does not load stale database tasks after refresh", async () => {
  global.fetch.mockImplementation((url) => {
    if (String(url).endsWith("/auth/status")) return Promise.resolve(mockResponse({authenticated: true}));
    if (String(url).endsWith("/initial")) return Promise.resolve(mockResponse({events: [{
      id: "database-task-1", summary: "Existing task", start: {dateTime: "2030-01-07T09:00:00"},
      end: {dateTime: "2030-01-07T10:00:00"}, source: "database"
    }]}));
    return Promise.resolve(mockResponse({events: []}));
  });
  render(<App />);
  await screen.findByRole("button", {name: "Google account"});
  await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(expect.stringMatching(/\/events$/), {credentials: "include"}));
  expect(global.fetch.mock.calls.some(([url]) => String(url).endsWith("/initial"))).toBe(false);
  expect(screen.queryByText("Existing task")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Task classification")).not.toBeInTheDocument();
});


test("sync removes deleted tasks, preserves predictions, and retains state on failure", async () => {
  let deleted = false;
  let failed = false;
  global.fetch.mockImplementation((url) => {
    if (String(url).endsWith("/auth/status")) return Promise.resolve(mockResponse({authenticated: false}));
    if (String(url).endsWith("/scheduledtasks")) return Promise.resolve(mockResponse({schedule: {
      scheduled: [{title: "New task", start: "2030-01-07T09:00:00", end: "2030-01-07T10:00:00", google_event_id: "event-1",
        classification: {status: "classified", domain: "work", effort: "mental"}}], unscheduled: []
    }}));
    if (String(url).endsWith("/events")) return Promise.resolve(failed
      ? mockResponse({}, {ok: false, status: 503})
      : mockResponse({events: deleted ? [] : [{id: "event-1", summary: "Renamed in Google", start: {dateTime: "2030-01-07T09:00:00"}, end: {dateTime: "2030-01-07T10:00:00"}}]}));
    return Promise.resolve(mockResponse({}));
  });
  render(<App />);
  fireEvent.click(screen.getByRole("button", {name: "+"}));
  fireEvent.change(screen.getByLabelText("Task title"), {target: {value: "New task"}});
  fireEvent.change(screen.getByLabelText("Deadline"), {target: {value: "2030-01-07"}});
  fireEvent.change(screen.getByLabelText("Duration hours"), {target: {value: "1"}});
  fireEvent.click(screen.getByText("Add to queue"));
  fireEvent.click(screen.getByRole("button", {name: /Schedule/}));
  await screen.findByText("1 task scheduled");
  fireEvent.click(screen.getByRole("button", {name: /Sync calendar/}));
  await screen.findByText("Renamed in Google");
  expect(screen.queryByText("New task")).not.toBeInTheDocument();
  expect(screen.getByTitle("Domain: work")).toBeInTheDocument();
  failed = true;
  fireEvent.click(screen.getByRole("button", {name: /Sync calendar/}));
  await screen.findByText("Could not load events");
  expect(screen.getByText("Renamed in Google")).toBeInTheDocument();
  failed = false;
  deleted = true;
  fireEvent.click(screen.getByRole("button", {name: /Sync calendar/}));
  await waitFor(() => expect(screen.queryByText("Renamed in Google")).not.toBeInTheDocument());
  expect(screen.queryByLabelText("Task classification")).not.toBeInTheDocument();
});


test.each([undefined, 90])("synced tasks get a finite duration when minutes are %s", async (minutes) => {
  global.fetch.mockImplementation((url) => {
    if (String(url).endsWith("/auth/status")) return Promise.resolve(mockResponse({authenticated: false}));
    if (String(url).endsWith("/tasks")) return Promise.resolve(mockResponse({Tasks: [{id: "google-task", title: "Imported task", due: "2030-01-07T00:00:00Z", estimated_duration_minutes: minutes}]}));
    return Promise.resolve(mockResponse({schedule: {scheduled: [], unscheduled: []}}));
  });
  render(<App />);
  fireEvent.click(screen.getByRole("button", {name: /Sync tasks/}));
  await screen.findByText("Imported task");
  expect(screen.queryByText(/NaNh/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", {name: /Schedule/}));
  await waitFor(() => expect(global.fetch.mock.calls.some(([url]) => String(url).endsWith("/scheduledtasks"))).toBe(true));
  const [, options] = global.fetch.mock.calls.find(([url]) => String(url).endsWith("/scheduledtasks"));
  expect(JSON.parse(options.body).tasks[0].estimated_duration).toBe(minutes === undefined ? 1 : 1.5);
});

test("shows readable scheduling validation errors", async () => {
  global.fetch.mockImplementation((url) => {
    if (String(url).endsWith("/auth/status")) return Promise.resolve(mockResponse({authenticated: false}));
    if (String(url).endsWith("/tasks")) return Promise.resolve(mockResponse({Tasks: [{title: "Imported task", due: "2030-01-07T00:00:00Z"}]}));
    return Promise.resolve(mockResponse({detail: [{loc: ["body", "tasks", 0, "deadline"], msg: "Invalid date"}]}, {ok: false, status: 422}));
  });
  render(<App />);
  fireEvent.click(screen.getByRole("button", {name: /Sync tasks/}));
  await screen.findByText("Imported task");
  fireEvent.click(screen.getByRole("button", {name: /Schedule/}));
  expect(await screen.findByText("tasks.0.deadline: Invalid date")).toBeInTheDocument();
});


test("removes a queued task without sending a deletion to Google", async () => {
  render(<App />);
  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole("button", {name: "+"}));
  fireEvent.change(screen.getByLabelText("Task title"), {target: {value: "Cancel this task"}});
  fireEvent.change(screen.getByLabelText("Deadline"), {target: {value: "2030-01-07"}});
  fireEvent.change(screen.getByLabelText("Duration hours"), {target: {value: "1"}});
  fireEvent.click(screen.getByText("Add to queue"));
  fireEvent.click(screen.getByRole("button", {name: "Remove Cancel this task from queue"}));
  expect(screen.queryByText("Cancel this task")).not.toBeInTheDocument();
  expect(screen.queryByText("Task details")).not.toBeInTheDocument();
  expect(screen.getByText("Your queue is clear")).toBeInTheDocument();
  expect(global.fetch).toHaveBeenCalledTimes(1);
});

test.each(["week", "month"])("opens and closes task details from %s calendar", async (view) => {
  // jsdom has no native showModal implementation.
  const original = HTMLDialogElement.prototype.showModal;
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  try {
    const today = new Date();
    const day = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
    global.fetch.mockImplementation((url) => Promise.resolve(mockResponse(String(url).endsWith("/auth/status")
      ? {authenticated: false}
      : {events: [{id: "event-detail", summary: "Review document", start: {dateTime: `${day}T09:00:00`}, end: {dateTime: `${day}T10:30:00`}}]})));
    render(<App />);
    fireEvent.click(screen.getByRole("button", {name: /Sync calendar/}));
    fireEvent.click(screen.getByRole("button", {name: view}));
    fireEvent.click(await screen.findByRole("button", {name: /Review document/}));
    const dialog = screen.getByRole("dialog", {name: "Review document"});
    expect(within(dialog).getByText("90 minutes")).toBeInTheDocument();
    expect(within(dialog).getByText("Starts")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", {name: "Close task details"}));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  } finally {
    if (original) HTMLDialogElement.prototype.showModal = original;
    else delete HTMLDialogElement.prototype.showModal;
  }
});

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
      expect.stringMatching(/\/initial$/),
      { credentials: "include" }
    );
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
          scheduled: [{ title: "Finish proposal", start: "2026-07-25T09:00:00", end: "2026-07-25T11:00:00" }],
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

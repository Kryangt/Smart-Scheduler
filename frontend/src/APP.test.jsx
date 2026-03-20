import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import App from "./App";
import { vi } from "vitest";

global.fetch = vi.fn(); // mock fetch for all API calls

test("renders main heading and buttons", () => {
    render(<App />);
    expect(screen.getByText(/Calendar AI Dashboard/i)).toBeInTheDocument();
    expect(screen.getByText(/Login with Google/i)).toBeInTheDocument();
    expect(screen.getByText(/Get Events/i)).toBeInTheDocument();
  });

test("login button redirects to API login URL", () => {
render(<App />);
delete window.location; // in the test environment, window.location is usually read only, so we overwrite it
window.location = { href: "" }; //assign a writable object

fireEvent.click(screen.getByText(/Login with Google/i));
expect(window.location.href).toBe("http://localhost:8000/auth/login");
});

test("adds a task when form is filled correctly", () => {
    render(<App />);
  
    fireEvent.click(screen.getByText(/Add Tasks/i));
  
    fireEvent.change(screen.getByPlaceholderText("title"), {
      target: { value: "Test Task" },
    });
    fireEvent.change(screen.getByPlaceholderText("deadline date"), {
      target: { value: "2026-03-25" },
    });
    fireEvent.change(screen.getByPlaceholderText("duration hours"), {
      target: { value: "2" },
    });
  
    fireEvent.click(screen.getByText("Add"));
  
    expect(screen.getByText(/1. Test Task/)).toBeInTheDocument();
  });

  
  test("schedules tasks and clears task list after success", async () => {
    render(<App />);
  
    fireEvent.click(screen.getByText(/Add Tasks/i));
    fireEvent.change(screen.getByPlaceholderText("title"), {
      target: { value: "Task 1" },
    });
    fireEvent.change(screen.getByPlaceholderText("deadline date"), {
      target: { value: "2026-03-25" },
    });
    fireEvent.change(screen.getByPlaceholderText("duration hours"), {
      target: { value: "2" },
    });
  
    fireEvent.click(screen.getByText("Add"));

    // mock the schedule-tasks API
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ schedule: "success" }),
    }); //next time call fetch in the program, it will return this fake res

    fireEvent.click(screen.getByText("Schedule"));
    
    //because react is asychronized, so need waitfor it to be updated
    await waitFor(() =>
      expect(screen.queryByText(/1. Task 1/)).not.toBeInTheDocument()
    );
    
    expect(screen.getByText(/schedule successed/i)).toBeInTheDocument();
  });
  
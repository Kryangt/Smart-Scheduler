import { useRef, useState } from "react";
import "./App.css";

let messageID = 2;
// let demoMessages = [
//   { id: 1, role: "bot", text: "Hi! How can I help you today?" },
//   { id: 2, role: "user", text: "I want to schedule my tasks." },
//   { id: 3, role: "bot", text: "Great. Add tasks and I will find open time slots." }
// ];

const API_BASE = import.meta.env.VITE_API_BASE;

function ChatPanel() {
  const fileRef = useRef(null);
  const textRef = useRef(null);
  const [file, setFile] = useState(null);
  const [enabled, setEnabled] = useState(false);
  const [displayedMessages, setDisplayedMessages] = useState([
    {
      id: 1, 
      role: "assistant", 
      content: "Hi! How can I help you today?" 
    }
]  )
  const [clarifyMessages, setClarifyMessages] = useState(null)
  const [feedbackMessages, setFeedbackMessages] = useState(null)
  const [state, setState] = useState("Decomposition_stage");
  const [subTasks, setSubTasks] = useState(null)
  const openPicker = () => {
    fileRef.current?.click();
  };

  const handleFileChange = (e) => {
    setFile(e.target.files?.[0] ?? null);
  };

  const handleUpload = async () => {
    if (!file) return;

    const form = new FormData();
    form.append("pdfFile", file);

    try {
      await fetch("/upload", {
        method: "POST",
        body: form
      });
    } catch (err) {
      // UI-only for now; if you want, we can show error status in the panel.
    }
  };

  const handleSend = async () => {
    if (!enabled || !textRef.current) return;

    const userText = textRef.current.value;
    const isDecompositionStage = state === "Decomposition_stage";
    const userMessage = { id: messageID++, role: "user", text: userText };
    const nextClarifyMessages = [...(clarifyMessages ?? []), userMessage];
    const nextFeedbackMessages = isDecompositionStage
      ? (feedbackMessages ?? [])
      : [...(feedbackMessages ?? []), userMessage];

    if (isDecompositionStage) {
      setClarifyMessages(nextClarifyMessages);
    } else {
      setFeedbackMessages(nextFeedbackMessages);
    }

    const requestBody = isDecompositionStage
      ? { clarifyMessages: nextClarifyMessages }
      : {
          clarifyMessages: nextClarifyMessages,
          feedbackMessages: nextFeedbackMessages
        };

    const fetchResponse = await fetch(`${API_BASE}/task-decomposition`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(requestBody)
    });
    const data = await fetchResponse.json();

    textRef.current.value = "";
    setEnabled(false);

    let response = "";

    if (data.state === "need_clarification") {
      const knownInfo = (data.known_info ?? []).join("\n");
      const questionList = (data.questions ?? []).join("\n");
      response = [
        "Here are the information I known about your task",
        knownInfo,
        "And I still have some questions about the tasks, if you can, please answer them, that will be very helpful in decomposing your task",
        questionList
      ]
        .filter(Boolean)
        .join("\n");
    } else {
      const nextSubTasks = (data.sub_task ?? []).map((task) => ({
        title: task.deliverable,
        deadline: task.deadline,
        estimated_duration: task.estimated_duration_minutes
      }));

      setSubTasks(nextSubTasks);

      const subTaskLines = (data.sub_task ?? []).map(
        (task) =>
          `Task objective: ${task.deliverable}, Estimated_duration (mins): ${task.estimated_duration_minutes}, Expected_deadline: ${task.deadline}, Reason: ${task.reason}`
      );

      response = [
        data.state === "decomposed"
          ? "The following are the drafted sub-tasks"
          : "The following are the improved version of sub-tasks",
        ...subTaskLines
      ].join("\n");

      if (data.state === "decomposed") {
        setState("feedBack_stage");
      }
    }

    const assistantMessage = { id: messageID++, role: "assistant", text: response };

    setDisplayedMessages((prev) => [...prev, assistantMessage]);

    if (isDecompositionStage) {
      setClarifyMessages((prev) => [...(prev ?? []), assistantMessage]);
    } else {
      setFeedbackMessages((prev) => [...(prev ?? []), assistantMessage]);
    }
  };

  const handleTextChange = () =>{
    if (textRef.current && textRef.current.value.trim() !== "")
    {
      setEnabled(true)
    }else
    {
      setEnabled(false)
    }
  }
  return (
    <section className="chat-panel">
      <header className="chat-header">Assistant</header>
      <div className="chat-messages">
        {displayedMessages.map((msg) => (
          <div key={msg.id} className={`chat-bubble ${msg.role}`}>
            {msg.text}
          </div>
        ))}
      </div>

      <div className="chat-upload">
        <input
          ref={fileRef}
          type="file"
          accept=".pdf"
          onChange={handleFileChange}
          style={{ display: "none" }}
        />
        <button type="button" onClick={openPicker}>
          Choose PDF
        </button>
        <span className="chat-file-name">
          {file ? file.name : "No file selected"}
        </span>
        <button type="button" onClick={handleUpload} disabled={!file}>
          Upload
        </button>
      </div>

      <form className="chat-input" onSubmit={(e) => e.preventDefault()}>
        <input ref = {textRef} onChange = {handleTextChange} type="text" placeholder="Type a message..." />
        <button type="button" disabled = {!enabled} onClick = {handleSend}>Send</button>
      </form>
    </section>
  );
}

export default ChatPanel;

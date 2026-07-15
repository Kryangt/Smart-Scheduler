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
  const STAGE = {
    DECOMPOSITION: "decomposition",
    WAIT_CONFIRMATION: "wait_confirmation",
    FEEDBACK: "feedback"
  };
  
  const [stage, setStage] = useState(STAGE.DECOMPOSITION);


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
    const isFeedbackStage = stage === STAGE.FEEDBACK;    
    const userMessage = { id: messageID++, role: "user", content: userText };
    const nextClarifyMessages = !isFeedbackStage? [...(clarifyMessages ?? []), userMessage] : [clarifyMessages ?? []];    
    const nextFeedbackMessages = isFeedbackStage
    ? [...(feedbackMessages ?? []), userMessage] : (feedbackMessages ?? []);


    setFeedbackMessages(nextFeedbackMessages);
    setClarifyMessages(nextClarifyMessages);

    const requestBody = !isFeedbackStage
    ? {
        clarifyMessages: nextClarifyMessages
      }
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

      setStage(STAGE.WAIT_CONFIRMATION);
    }

    const assistantMessage = { id: messageID++, role: "assistant", content: response };

    setDisplayedMessages((prev) => [...prev, assistantMessage]);

    if (isFeedbackStage)
    {
      setFeedbackMessages(prev => [...(prev ?? []),assistantMessage]);
    }else
    {
      setClarifyMessages(prev => [...(prev ?? []),assistantMessage]);
    }
  };

  const handleImprove = () => {
    setStage(STAGE.FEEDBACK);
    if (textRef.current) {
      textRef.current.value = "";
  }

  setEnabled(false);
  };

  const handleConfirm = async () => {
    const response = await fetch(
        `${API_BASE}/task-confirmation`,
        {
            method: "POST",
            credentials: "include",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                decision: "yes",
                structuredTasks: subTasks
            })
        }
    );

    const data = await response.json();

    setDisplayedMessages(prev => [
        ...prev,
        {
            id: messageID++,
            role: "assistant",
            content: "Great! Your tasks have been scheduled."
        }
    ]);

    setStage(STAGE.DECOMPOSITION);
    setClarifyMessages(null);
    setFeedbackMessages(null);
    setSubTasks(null);
    setEnabled(false);

    if (textRef.current) {
        textRef.current.value = "";
    }
  }
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
            {msg.content}
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

      {stage !== STAGE.WAIT_CONFIRMATION && (
        <form className="chat-input" onSubmit={(e) => e.preventDefault()}>
            <input
                ref={textRef}
                onChange={handleTextChange}
                type="text"
                placeholder="Type a message..."
            />

            <button
                type="button"
                disabled={!enabled}
                onClick={handleSend}
            >
                Send
            </button>
        </form>
      )}

      {stage === STAGE.WAIT_CONFIRMATION && (
        <div className="confirmation-panel">
            <button onClick={handleConfirm}>
                Confirm
            </button>

            <button onClick={handleImprove}>
                Improve
            </button>
        </div>
      )}

    </section>
  );
}

export default ChatPanel;

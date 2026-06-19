import { useRef, useState } from "react";
import "./App.css";

let messageID = 4;
// let demoMessages = [
//   { id: 1, role: "bot", text: "Hi! How can I help you today?" },
//   { id: 2, role: "user", text: "I want to schedule my tasks." },
//   { id: 3, role: "bot", text: "Great. Add tasks and I will find open time slots." }
// ];

function ChatPanel() {
  const fileRef = useRef(null);
  const textRef = useRef(null);
  const [file, setFile] = useState(null);
  const [enabled, setEnabled] = useState(false);
  const [demoMessages, setMessages] = useState(
    [
        { id: 1, role: "bot", text: "Hi! How can I help you today?" },
        { id: 2, role: "user", text: "I want to schedule my tasks." },
        { id: 3, role: "bot", text: "Great. Add tasks and I will find open time slots." }
    ]  
  )
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

  const handleSend = () => {
    if(enabled)
    {
        //change the content shown in chat panel
        let userText = textRef.current.value
        setMessages((prev) =>{
            const newMessages = [...prev.slice(1), {id: messageID, role: "user", text: userText}]
            return newMessages
        })
        textRef.current.value = ""
        setEnabled(false)
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
        {demoMessages.map((msg) => (
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

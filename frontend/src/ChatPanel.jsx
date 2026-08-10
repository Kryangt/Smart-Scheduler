import { useEffect, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE;
const STAGE = { DECOMPOSITION: "decomposition", WAIT_CONFIRMATION: "wait_confirmation", FEEDBACK: "feedback" };

function ChatPanel({ onDraftTasks, onTasksConfirmed }) {
  const nextId = useRef(2);
  const textRef = useRef(null);
  const messageEndRef = useRef(null);
  const [messages, setMessages] = useState([{ id: 1, role: "assistant", content: "Hi! Tell me what you need to accomplish, and I’ll turn it into a realistic plan." }]);
  const [clarifyMessages, setClarifyMessages] = useState([]);
  const [feedbackMessages, setFeedbackMessages] = useState([]);
  const [subTasks, setSubTasks] = useState([]);
  const [stage, setStage] = useState(STAGE.DECOMPOSITION);
  const [isGenerating, setIsGenerating] = useState(false);
  const [input, setInput] = useState("");

  useEffect(() => {
    if (typeof messageEndRef.current?.scrollIntoView === "function") {
      messageEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isGenerating]);

  const send = async (event) => {
    event?.preventDefault();
    const userText = input.trim();
    if (!userText || isGenerating) return;
    const userMessage = { id: nextId.current++, role: "user", content: userText };
    const isFeedback = stage === STAGE.FEEDBACK;
    const nextClarify = isFeedback ? clarifyMessages : [...clarifyMessages, userMessage];
    const nextFeedback = isFeedback ? [...feedbackMessages, userMessage] : feedbackMessages;
    setMessages((current) => [...current, userMessage]);
    setClarifyMessages(nextClarify);
    setFeedbackMessages(nextFeedback);
    setInput("");
    setIsGenerating(true);

    try {
      const response = await fetch(`${API_BASE}/${isFeedback ? "task-confirmation" : "task-decomposition"}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(isFeedback ? { decision: "no", structured_tasks: subTasks, clarifyMessages: nextClarify, feedbackMessages: nextFeedback } : { clarifyMessages: nextClarify })
      });
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      const data = await response.json();
      let content;
      if (data.status === "needs_clarification") {
        const questions = data.questions ?? [];
        content = questions.length ? `I need a little more detail:\n${questions.map((question, index) => `${index + 1}. ${question}`).join("\n")}` : "Could you share a little more detail?";
      } else {
        const drafts = (data.sub_tasks ?? []).map((task) => ({
          title: task.title ?? task.deliverable ?? "Untitled task",
          deadline: task.deadline ?? "",
          estimated_duration_minutes: task.estimated_duration_minutes ?? 60,
          reason: task.reason ?? "",
          depends_on: task.depends_on ?? [],
          priority: task.priority ?? "medium"
        }));
        setSubTasks(drafts);
        onDraftTasks?.(drafts);
        setStage(STAGE.WAIT_CONFIRMATION);
        content = `I drafted ${drafts.length} task${drafts.length === 1 ? "" : "s"}. They’re now in your waiting queue—review them there or confirm the plan below.`;
      }
      const assistant = { id: nextId.current++, role: "assistant", content };
      setMessages((current) => [...current, assistant]);
      if (isFeedback) setFeedbackMessages((current) => [...current, assistant]);
      else setClarifyMessages((current) => [...current, assistant]);
    } catch (error) {
      setMessages((current) => [...current, { id: nextId.current++, role: "assistant", content: `I couldn’t finish that request. ${error.message}. Please try again.` }]);
    } finally { setIsGenerating(false); }
  };

  const confirm = async () => {
    if (!subTasks.length || isGenerating) return;
    setIsGenerating(true);
    try {
      const response = await fetch(`${API_BASE}/task-confirmation`, {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision: "yes", structured_tasks: subTasks, clarifyMessages, feedbackMessages })
      });
      if (!response.ok) throw new Error(`Confirmation failed (${response.status})`);
      const data = await response.json();
      onTasksConfirmed?.(data, subTasks);
      setMessages((current) => [...current, { id: nextId.current++, role: "assistant", content: "Done—your confirmed tasks have been moved into the schedule." }]);
      setStage(STAGE.DECOMPOSITION);
      setClarifyMessages([]);
      setFeedbackMessages([]);
      setSubTasks([]);
    } catch (error) {
      setMessages((current) => [...current, { id: nextId.current++, role: "assistant", content: `I couldn’t confirm the plan. ${error.message}.` }]);
    } finally { setIsGenerating(false); }
  };

  return (
    <aside className="chat-panel">
      <header className="chat-header"><div className="assistant-icon">✦</div><div><strong>Planning assistant</strong><span><i className="online-dot"/> Online</span></div></header>
      <div className="chat-messages">
        {messages.map((message) => <div className={`message-row ${message.role}`} key={message.id}>{message.role === "assistant" && <span className="mini-assistant">✦</span>}<div className="chat-bubble">{message.content}</div></div>)}
        {isGenerating && <div className="message-row assistant generating" aria-label="AI is generating a response"><span className="mini-assistant">✦</span><div className="chat-bubble"><span className="thinking-label">Building your plan</span><span className="typing-dots"><i/><i/><i/></span></div></div>}
        <div ref={messageEndRef}/>
      </div>
      {stage === STAGE.WAIT_CONFIRMATION ? <div className="confirmation-panel"><div><strong>Draft ready</strong><span>{subTasks.length} tasks waiting for approval</span></div><button className="primary-button" onClick={confirm} disabled={isGenerating}>Confirm plan</button><button className="secondary-button" onClick={() => { setStage(STAGE.FEEDBACK); setTimeout(() => textRef.current?.focus(), 0); }}>Make changes</button></div> : <form className="chat-input" onSubmit={send}><textarea ref={textRef} rows="2" value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) send(event); }} placeholder={stage === STAGE.FEEDBACK ? "Tell me what to change…" : "Ask me to plan your tasks…"}/><button aria-label="Send message" disabled={!input.trim() || isGenerating}>↑</button></form>}
      <p className="chat-hint">AI can make mistakes. Review tasks before confirming.</p>
    </aside>
  );
}

export default ChatPanel;

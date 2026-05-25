import { useState, useEffect, useRef  } from "react";
import "./App.css";
import ReactMarkdown from "react-markdown";

const WELCOME_MESSAGE =
  "Hi! Ask me anything about Sri Lanka’s procurement guidelines or manual.";

function App() {
  // All chat sessions: [{id, title, messages}]
  
  const [chatSessions, setChatSessions] = useState([]);
  const [currentChatId, setCurrentChatId] = useState(null);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);


  // Load chat history from localStorage on first render
  useEffect(() => {
    const stored = localStorage.getItem("chat_history");
    if (stored) {
      const parsed = JSON.parse(stored);
      if (parsed.length > 0) {
        setChatSessions(parsed);
        setCurrentChatId(parsed[0].id); // most recent chat
        return;
      }
    }

    // If nothing in storage, create first chat
    const firstSession = {
      id: Date.now(),
      title: "Chat 1",
      messages: [{ role: "assistant", content: WELCOME_MESSAGE }],
    };
    setChatSessions([firstSession]);
    setCurrentChatId(firstSession.id);
  }, []);

  // Persist chat sessions to localStorage whenever they change
  useEffect(() => {
    if (chatSessions.length > 0) {
      localStorage.setItem("chat_history", JSON.stringify(chatSessions));
    }
  }, [chatSessions]);

  const bottomRef = useRef(null);
  const currentSession = chatSessions.find((s) => s.id === currentChatId);
  const messages = currentSession ? currentSession.messages : [];

  useEffect(() => {
  bottomRef.current?.scrollIntoView({ behavior: "smooth" });
},  [messages, loading]);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || loading || !currentSession) return;

    // Add user message
    const userMessage = { role: "user", content: question };

    // If this is the first user message in this chat, update the title
    const hasUserMsg = currentSession.messages.some(
      (m) => m.role === "user"
    );
    const newTitle = hasUserMsg
      ? currentSession.title
      : question.slice(0, 30) + (question.length > 30 ? "..." : "");

    const updatedSession = {
      ...currentSession,
      title: newTitle || currentSession.title,
      messages: [...currentSession.messages, userMessage],
    };

    setChatSessions((prev) =>
      prev.map((s) => (s.id === currentSession.id ? updatedSession : s))
    );
    setInput("");
    setLoading(true);

    try {
      const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiBase}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          question,
          session_id: currentSession.backendSessionId || null
        }),
      });

      let answerText = "";
      let returnedSessionId = null;

      if (res.ok) {
        const data = await res.json();
        answerText = data.answer || "I could not generate an answer.";
        returnedSessionId = data.session_id;
      } else {
        answerText = "Server error. Please try again.";
      }

      const assistantMessage = {
        role: "assistant",
        content: answerText,
      };

      // Append assistant reply to the same session and save backend session ID
      setChatSessions((prev) =>
        prev.map((s) =>
          s.id === currentSession.id
            ? { 
                ...s, 
                messages: [...s.messages, assistantMessage],
                ...(returnedSessionId ? { backendSessionId: returnedSessionId } : {})
              }
            : s
        )
      );
    } catch (err) {
      console.error(err);
      const errorMessage = {
        role: "assistant",
        content: "Something went wrong. Please try again.",
      };
      setChatSessions((prev) =>
        prev.map((s) =>
          s.id === currentSession.id
            ? { ...s, messages: [...s.messages, errorMessage] }
            : s
        )
      );
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewChat = () => {
    const newId = Date.now();
    const newSession = {
      id: newId,
      title: "New chat",
      messages: [{ role: "assistant", content: WELCOME_MESSAGE }],
    };

    setChatSessions((prev) => {
      const updated = [newSession, ...prev];
      // keep only last 20 chats
      return updated.slice(0, 20);
    });

    setCurrentChatId(newId);
    setInput("");
  };

  const handleSelectChat = (id) => {
    setCurrentChatId(id);
    setInput("");
  };
  const handleDeleteChat = (id) => {
   setChatSessions((prev) => {
    const updated = prev.filter((s) => s.id !== id);

    // If no chats left, create a fresh one
    if (updated.length === 0) {
      const fresh = {
        id: Date.now(),
        title: "New chat",
        messages: [{ role: "assistant", content: WELCOME_MESSAGE }],
      };
      setCurrentChatId(fresh.id);
      return [fresh];
    }

    // If deleted chat was active, switch to first chat
    if (id === currentChatId) {
      setCurrentChatId(updated[0].id);
    }

    return updated;
  });
};


  return (
    <div className="layout">
      {/* LEFT SIDEBAR */}
      <aside className="sidebar">
        <h2 className="sidebar-title">History</h2>

        <div className="history-list">
  {chatSessions.map((session, index) => (
    <div
      key={session.id}
      className={
        "history-item" +
        (session.id === currentChatId ? " history-item-active" : "")
      }
      onClick={() => handleSelectChat(session.id)}
      title={session.title || `Chat ${index + 1}`}
      style={{ display: "flex", justifyContent: "space-between" }}
    >
      <span className="history-title">
        {session.title || `Chat ${index + 1}`}
      </span>

      <button
  onClick={(e) => {
    e.stopPropagation(); // prevents opening the chat
    handleDeleteChat(session.id);
  }}
  className="delete-chat-btn"
  title="Delete chat"
>
  🗑
</button>
    </div>
  ))}
</div>


        <button className="new-chat-btn" onClick={handleNewChat}>
          + New Chat
        </button>

        <div className="sidebar-resources">
          <h3>Resources</h3>
          {/* Replace href values with your real links */}
          <a
            href="https://www.treasury.gov.lk/web/procurement-guidelines-and-manuals/section/procurement%20guidelines"
            target="_blank"
            rel="noreferrer"
            className="resource-link"
          >
            View Procurement Guidelines
          </a>
          <a
            href="https://www.treasury.gov.lk/web/procurement-guidelines-and-manuals/section/procurement%20manual"
            target="_blank"
            rel="noreferrer"
            className="resource-link"
          >
            View Procurement Manual
          </a>
          <a
            href="https://www.treasury.gov.lk/web/procurement"
            target="_blank"
            rel="noreferrer"
            className="resource-link"
          >
            Go to Official Procurement Site
          </a>
        </div>
      </aside>

      {/* RIGHT CHAT AREA */}
      <main className="chat-area">
        <header className="chat-header">
          <div>
            <h1>Procurement Assistant</h1>
            <p>
              AI assistance for navigating Sri Lanka’s procurement guidelines and
              manuals.
            </p>
          </div>
        </header>

        <div className="chat-messages">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={
                "message-row " +
                (m.role === "user" ? "message-user" : "message-assistant")
              }
            >
              <div className="message-bubble">
                <div className="message-role">
                  {m.role === "user" ? "YOU" : "ASSISTANT"}
                </div>
                <div className="message-content">
                  {m.role === "assistant" ? (
                    <ReactMarkdown>{m.content}</ReactMarkdown>
                  ) : (
                    m.content
                  )}
                </div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="message-row message-assistant">
              <div className="message-bubble">
                <div className="message-role">ASSISTANT</div>
                <div className="message-content">Thinking...</div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="chat-input">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your question here..."
            rows={2}
          />

          <button onClick={handleSend} disabled={loading || !input.trim()}>
            {loading ? "Sending..." : "Send"}
          </button>
        </div>
      </main>
    </div>
  );
}

export default App;

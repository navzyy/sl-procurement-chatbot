import { useState, useEffect, useRef } from "react";
import "./App.css";
import ReactMarkdown from "react-markdown";

import {
  History,
  BookOpen,
  FileText,
  Globe,
  MessageCircle,
  Plus,
  X,
  Scale,
  Check,
} from "lucide-react";

const STORAGE_KEY = "procurement_chat_history_v2";

function App() {
  const [chatSessions, setChatSessions] = useState([]);
  const [currentChatId, setCurrentChatId] = useState(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const bottomRef = useRef(null);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);

    if (stored) {
      try {
        const parsed = JSON.parse(stored);

        if (Array.isArray(parsed) && parsed.length > 0) {
          setChatSessions(parsed);
          setCurrentChatId(parsed[0].id);
          return;
        }
      } catch (error) {
        console.error("Failed to load chat history:", error);
      }
    }

    const firstSession = {
      id: Date.now(),
      title: "New chat",
      messages: [],
    };

    setChatSessions([firstSession]);
    setCurrentChatId(firstSession.id);
  }, []);

  useEffect(() => {
    if (chatSessions.length > 0) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(chatSessions));
    }
  }, [chatSessions]);

  const currentSession = chatSessions.find(
    (session) => session.id === currentChatId
  );

  const messages = currentSession ? currentSession.messages : [];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const getCurrentTime = () => {
    return new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const handleSend = async () => {
    const question = input.trim();

    if (!question || loading || !currentSession) return;

    const userMessage = {
      role: "user",
      content: question,
      time: getCurrentTime(),
    };

    const hasUserMessage = currentSession.messages.some(
      (message) => message.role === "user"
    );

    const newTitle = hasUserMessage
      ? currentSession.title
      : question.slice(0, 28) + (question.length > 28 ? "..." : "");

    const updatedSession = {
      ...currentSession,
      title: newTitle || "New chat",
      messages: [...currentSession.messages, userMessage],
    };

    setChatSessions((prevSessions) =>
      prevSessions.map((session) =>
        session.id === currentSession.id ? updatedSession : session
      )
    );

    setInput("");
    setLoading(true);

    try {
      const apiBase = import.meta.env.VITE_API_URL || "http://localhost:8000";

      const response = await fetch(`${apiBase}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question,
          session_id: currentSession.backendSessionId || null,
        }),
      });

      let answerText = "";
      let returnedSessionId = null;

      if (response.ok) {
        const data = await response.json();
        answerText = data.answer || "I could not generate an answer.";
        returnedSessionId = data.session_id;
      } else {
        answerText = "Server error. Please try again.";
      }

      const assistantMessage = {
        role: "assistant",
        content: answerText,
        time: getCurrentTime(),
      };

      setChatSessions((prevSessions) =>
        prevSessions.map((session) =>
          session.id === currentSession.id
            ? {
                ...session,
                messages: [...session.messages, assistantMessage],
                ...(returnedSessionId
                  ? { backendSessionId: returnedSessionId }
                  : {}),
              }
            : session
        )
      );
    } catch (error) {
      console.error(error);

      const errorMessage = {
        role: "assistant",
        content: "Something went wrong. Please try again.",
        time: getCurrentTime(),
      };

      setChatSessions((prevSessions) =>
        prevSessions.map((session) =>
          session.id === currentSession.id
            ? {
                ...session,
                messages: [...session.messages, errorMessage],
              }
            : session
        )
      );
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const handleNewChat = () => {
    const newId = Date.now();

    const newSession = {
      id: newId,
      title: "New chat",
      messages: [],
    };

    setChatSessions((prevSessions) => [newSession, ...prevSessions].slice(0, 20));
    setCurrentChatId(newId);
    setInput("");
  };

  const handleSelectChat = (id) => {
    setCurrentChatId(id);
    setInput("");
  };

  const handleDeleteChat = (id) => {
    setChatSessions((prevSessions) => {
      const updatedSessions = prevSessions.filter(
        (session) => session.id !== id
      );

      if (updatedSessions.length === 0) {
        const freshSession = {
          id: Date.now(),
          title: "New chat",
          messages: [],
        };

        setCurrentChatId(freshSession.id);
        return [freshSession];
      }

      if (id === currentChatId) {
        setCurrentChatId(updatedSessions[0].id);
      }

      return updatedSessions;
    });
  };

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="brand">
          <img
            className="brand-symbol"
            src="/national_symbol.png"
            alt="Sri Lanka National Symbol"
          />

          <div className="brand-text">
            <h1>Sri Lanka</h1>
            <p>Procurement Authority</p>
          </div>
        </div>

        <div className="sidebar-divider" />

        <section className="sidebar-section">
          <h2>
            <History className="section-icon" size={17} strokeWidth={2.2} />
            History
          </h2>

          <div className="history-list">
            {chatSessions.map((session) => (
              <button
                key={session.id}
                className={
                  "history-item" +
                  (session.id === currentChatId ? " history-item-active" : "")
                }
                onClick={() => handleSelectChat(session.id)}
                title={session.title}
              >
                <span className="history-icon">
                  <MessageCircle size={14} strokeWidth={2.2} />
                </span>

                <span className="history-title">{session.title}</span>

                <span
                  className="delete-chat-btn"
                  onClick={(event) => {
                    event.stopPropagation();
                    handleDeleteChat(session.id);
                  }}
                  title="Delete chat"
                >
                  <X size={14} strokeWidth={2.4} />
                </span>
              </button>
            ))}
          </div>

          <button className="new-chat-btn" onClick={handleNewChat}>
            <Plus size={18} strokeWidth={2.5} />
            <span>New Chat</span>
          </button>
        </section>

        <div className="sidebar-divider" />

        <section className="sidebar-section resources">
          <h2>
            <BookOpen className="section-icon" size={17} strokeWidth={2.2} />
            Resources
          </h2>

          <a
            href="https://www.treasury.gov.lk/web/procurement-guidelines-and-manuals/section/procurement%20guidelines"
            target="_blank"
            rel="noreferrer"
            className="resource-link"
          >
            <span className="resource-icon">
              <FileText size={16} strokeWidth={2.1} />
            </span>
            View Procurement Guidelines
          </a>

          <a
            href="https://www.treasury.gov.lk/web/procurement-guidelines-and-manuals/section/procurement%20manual"
            target="_blank"
            rel="noreferrer"
            className="resource-link"
          >
            <span className="resource-icon">
              <BookOpen size={16} strokeWidth={2.1} />
            </span>
            View Procurement Manual
          </a>

          <a
            href="https://www.treasury.gov.lk/web/procurement"
            target="_blank"
            rel="noreferrer"
            className="resource-link"
          >
            <span className="resource-icon">
              <Globe size={16} strokeWidth={2.1} />
            </span>
            Go to Official Procurement Site
          </a>
        </section>

        <div className="sidebar-illustration">
          <img
            src="/sidebar-building.png"
            alt="Official procurement building"
            className="sidebar-building-img"
          />
        </div>
      </aside>

      <main className="main-panel">
        <header className="top-header">
          <div className="header-title-wrap">
            <div className="header-logo">
              <Scale size={20} strokeWidth={2.4} />
            </div>

            <div>
              <h1>Procurement Assistant</h1>
              <p>
                Helping you navigate Sri Lanka&apos;s procurement guidelines and
                manual.
              </p>
            </div>
          </div>
        </header>

        <section className="chat-wrapper">
          <div className="chat-messages">
            {messages.length === 0 && (
              <div className="empty-state">
                <div className="empty-icon">
                  <Scale size={24} strokeWidth={2.2} />
                </div>

                <h2>Ask a procurement question</h2>

                <p>
                  You can ask about procurement methods, guideline sections,
                  thresholds, approvals, bid evaluation, or manual references.
                </p>
              </div>
            )}

            {messages.map((message, index) => (
              <div
                key={index}
                className={
                  "message-row " +
                  (message.role === "user"
                    ? "message-user"
                    : "message-assistant")
                }
              >
                {message.role === "assistant" && (
                  <div className="assistant-avatar">
                    <Scale size={18} strokeWidth={2.4} />
                  </div>
                )}

                <div className="message-bubble">
                  <div className="message-meta">
                    <span>
                      {message.role === "user" ? "YOU" : "ASSISTANT"}
                    </span>
                    <span>{message.time}</span>
                  </div>

                  <div className="message-content">
                    {message.role === "assistant" ? (
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    ) : (
                      message.content
                    )}
                  </div>
                </div>
              </div>
            ))}

            {loading && (
              <div className="message-row message-assistant">
                <div className="assistant-avatar">
                  <Scale size={18} strokeWidth={2.4} />
                </div>

                <div className="message-bubble">
                  <div className="message-meta">
                    <span>ASSISTANT</span>
                  </div>

                  <div className="typing">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>
        </section>

        <section className="input-card">
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your question here..."
            rows={2}
          />

          <button onClick={handleSend} disabled={loading || !input.trim()}>
            {loading ? "Sending..." : "Send"}
          </button>
        </section>

        <footer className="disclaimer">
          <div className="disclaimer-icon">
            <Check size={18} strokeWidth={2.5} />
          </div>

          <p>
            <strong>Disclaimer:</strong> This assistant provides general
            information based on official procurement guidelines and manuals.
            For legal interpretation or compliance matters, please refer to the
            official documents or consult the relevant authority.
          </p>
        </footer>
      </main>
    </div>
  );
}

export default App;
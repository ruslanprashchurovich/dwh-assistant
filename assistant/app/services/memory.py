"""
Per-session conversation memory for LLM context.
Each user session gets its own conversation history (last N messages).
Sessions are identified by a UUID stored in a cookie.
"""

import uuid
from collections import deque

MAX_HISTORY_SIZE = 30


class ConversationMemory:
    """
    Conversation history for a single session.
    Stores user/assistant message pairs as context for LLM.
    Uses a bounded deque to automatically discard oldest messages.
    """

    def __init__(self, max_size: int = MAX_HISTORY_SIZE):
        self.max_size = max_size
        self._messages: deque[dict] = deque(maxlen=max_size)

    def add_user_message(self, content: str) -> None:
        """Add a user message to history."""
        self._messages.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to history."""
        self._messages.append({"role": "assistant", "content": content})

    def get_history(self) -> list[dict]:
        """Return conversation history as a list of message dicts."""
        return list(self._messages)

    def clear(self) -> None:
        """Clear all conversation history."""
        self._messages.clear()

    def __len__(self) -> int:
        return len(self._messages)


class SessionMemoryManager:
    """
    Manages per-session conversation memories.
    Each session (identified by UUID) has its own ConversationMemory.
    """

    def __init__(self, max_history_size: int = MAX_HISTORY_SIZE):
        self._sessions: dict[str, ConversationMemory] = {}
        self._max_history_size = max_history_size

    def get_or_create(self, session_id: str) -> ConversationMemory:
        """Get existing session memory or create a new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationMemory(
                max_size=self._max_history_size
            )
        return self._sessions[session_id]

    def clear_session(self, session_id: str) -> None:
        """Clear memory for a specific session."""
        if session_id in self._sessions:
            self._sessions[session_id].clear()

    def remove_session(self, session_id: str) -> None:
        """Remove a session entirely."""
        self._sessions.pop(session_id, None)

    def generate_session_id(self) -> str:
        """Generate a new unique session ID."""
        return str(uuid.uuid4())

    def session_exists(self, session_id: str) -> bool:
        return session_id in self._sessions

    def get_session_info(self, session_id: str) -> dict:
        """Return session info for debugging."""
        if session_id not in self._sessions:
            return {"session_id": session_id, "exists": False, "size": 0}
        mem = self._sessions[session_id]
        return {
            "session_id": session_id,
            "exists": True,
            "size": len(mem),
            "messages": mem.get_history(),
        }


# Global session manager
session_manager = SessionMemoryManager()

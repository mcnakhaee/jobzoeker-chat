import logging
from utils import caveman, remove_stopwords

logger = logging.getLogger(__name__)

MAX_MESSAGES = 10  # keep last 10 role messages in the context (~5 user/assistant pairs)


class ContextWindow:
    """
    Keeps a rolling window of user/assistant messages for the planner and executor.

    Only stores {"role": "user"|"assistant", "content": str} messages.
    Raw tool call/output items are NOT stored here — the executor tracks those
    locally per task and only adds the final summary as an assistant message.
    """

    def __init__(self) -> None:
        self._messages: list[dict] = []

    def add_user(self, content: str) -> None:
        self._messages.append({"role": "user", "content": remove_stopwords(content)})
        self._trim()

    def add_assistant(self, content: str) -> None:
        if content:
            self._messages.append({"role": "assistant", "content": remove_stopwords(caveman(content))})

    def get_messages(self) -> list[dict]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages = []

    def _trim(self) -> None:
        if len(self._messages) > MAX_MESSAGES:
            dropped = len(self._messages) - MAX_MESSAGES
            self._messages = self._messages[dropped:]
            logger.debug("context.trimmed dropped=%s", dropped)

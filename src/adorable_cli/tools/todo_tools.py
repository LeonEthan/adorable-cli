from typing import Dict, List, Optional

from agno.tools import Toolkit


class TodoTools(Toolkit):
    def __init__(self):
        super().__init__(name="todo_tools")
        # Internal state management replacing external session_state
        self.todos: List[Dict] = []
        self.register(self.add_todo)
        self.register(self.list_todos)
        self.register(self.complete_todo)
        self.register(self.remove_todo)

    def add_todo(self, task: str, priority: str = "normal") -> str:
        """
        Add a new task to the todo list. Use this to plan complex workflows.

        Args:
            task: The description of the task. Keep it concise but clear.
            priority: Priority level ('high', 'normal', 'low'). Defaults to 'normal'.
        """
        todo = {"id": len(self.todos) + 1, "task": task, "priority": priority, "status": "pending"}
        self.todos.append(todo)
        return f"Added task #{todo['id']}: {task}"

    def list_todos(self, status: Optional[str] = None) -> str:
        """
        List all tasks. Use this to review your progress.

        Args:
            status: Optional filter ('pending' or 'completed'). If None, shows all.
        """
        if not self.todos:
            return "Todo list is empty."

        result = []
        for t in self.todos:
            if status and t["status"] != status:
                continue
            icon = "✓" if t["status"] == "completed" else "☐"
            result.append(f"{icon} #{t['id']} [{t['priority']}] {t['task']}")

        return "\n".join(result) if result else "No tasks found."

    def complete_todo(self, task_id: int) -> str:
        """Mark a task as completed by its ID."""
        for t in self.todos:
            if t["id"] == task_id:
                t["status"] = "completed"
                return f"Marked task #{task_id} as completed."
        return f"Task #{task_id} not found."

    def remove_todo(self, task_id: int) -> str:
        """Remove a task by its ID."""
        for i, t in enumerate(self.todos):
            if t["id"] == task_id:
                removed = self.todos.pop(i)
                return f"Removed task #{task_id}: {removed['task']}"
        return f"Task #{task_id} not found."

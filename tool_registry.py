class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, name, description, input_schema, fn):
        self._tools[name] = {
            "definition": {
                "name": name,
                "description": description,
                "input_schema": input_schema,
            },
            "fn": fn,
        }

    def get_definitions(self):
        return [t["definition"] for t in self._tools.values()]

    def run(self, name, inputs):
        if name not in self._tools:
            return f"Error: unknown tool '{name}'."
        try:
            result = self._tools[name]["fn"](**inputs)
            return str(result) if not isinstance(result, str) else result
        except Exception as e:
            return f"Error running {name}: {e}"

    def __len__(self):
        return len(self._tools)

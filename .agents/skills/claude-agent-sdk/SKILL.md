---
name: claude-agent-sdk
description: >
  Best practices, architecture patterns, and decision guidance for building Python
  applications with the Claude Agent SDK (claude-agent-sdk package). ALWAYS use this
  skill when the user is building or debugging a Python app that imports claude_agent_sdk,
  asks how to use query() vs ClaudeSDKClient, wants to add hooks or MCP tools to their
  Claude-powered app, needs help with tool permissions, session management, or agent
  definitions, or asks "how do I build an agent with Claude Code" in a Python context.
  Also trigger for questions about ClaudeAgentOptions configuration, can_use_tool callbacks,
  in-process SDK MCP servers, or session stores.
---

# Claude Agent SDK — Best Practices

The SDK drives Claude Code CLI as a subprocess and communicates over a bidirectional
JSON stream. Understanding this model helps you make better decisions throughout.

## 1. Choose the right entrypoint

**Use `query()` when:**
- You have all input upfront (one-shot question, batch job, CI step)
- You don't need to react to Claude's output mid-stream
- You want the simplest possible code path

```python
async for msg in query(prompt="Summarize this file", options=opts):
    if isinstance(msg, AssistantMessage):
        for block in msg.content:
            if isinstance(block, TextBlock):
                print(block.text)
```

**Use `ClaudeSDKClient` when:**
- You need multi-turn conversation (send follow-ups based on responses)
- You need `can_use_tool` callbacks (requires streaming mode)
- You need to interrupt, change permission mode, or toggle MCP servers mid-session
- You're building an interactive UI or REPL

```python
async with ClaudeSDKClient(options) as client:
    await client.query("Analyze this codebase")
    async for msg in client.receive_response():
        ...  # inspect, then decide what to ask next
    await client.query("Now fix the three bugs you found")
    async for msg in client.receive_response():
        ...
```

`receive_response()` is the right iterator for a single request-response pair — it stops
after the `ResultMessage`. `receive_messages()` runs indefinitely and is for when you're
managing the loop yourself.

## 2. Understand the three-layer tool model

The SDK has three distinct tool knobs that confuse many developers:

| Option | What it does |
|---|---|
| `tools` | Base set of tools available to the model. Default: all Claude Code tools. Pass `[]` to remove all built-ins. |
| `allowed_tools` | Auto-approved subset — these execute without a permission prompt. Does NOT restrict what's available. |
| `disallowed_tools` | Removed from the model's context entirely. Strongest restriction. |
| `permission_mode` | Policy for tools that aren't in `allowed_tools` (default, acceptEdits, bypassPermissions, dontAsk, auto). |

**Common mistake:** `allowed_tools=["Read"]` does not prevent Claude from using `Bash`.
It just auto-approves `Read`. To restrict, use `disallowed_tools=["Bash"]` or
`tools=["Read", "Write"]` (only expose those two).

**Common patterns:**
```python
# Read-only agent — can see files, never writes
ClaudeAgentOptions(
    disallowed_tools=["Write", "Edit", "Bash", "MultiEdit"],
)

# Automation script — trust everything, no prompts
ClaudeAgentOptions(
    permission_mode="bypassPermissions",
)

# Review + fix loop — explicit approval before edits
ClaudeAgentOptions(
    allowed_tools=["Read", "Grep", "Glob"],  # auto-approve reads
    permission_mode="default",  # prompt before writes
)
```

## 3. Hooks — when and how to use them

Hooks are Python async callbacks wired to lifecycle events. Use them to:
- Block or modify tool calls before they run (`PreToolUse`)
- React to tool output, inject context (`PostToolUse`)
- Make programmatic permission decisions (`PermissionRequest`)
- Add context at prompt submission (`UserPromptSubmit`)

```python
async def guard_bash(input: HookInput, tool_use_id: str | None, ctx: HookContext) -> HookJSONOutput:
    if input["tool_name"] == "Bash" and "rm -rf" in input["tool_input"].get("command", ""):
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Destructive rm -rf blocked",
            }
        }
    return {}

options = ClaudeAgentOptions(
    hooks={
        "PreToolUse": [HookMatcher(matcher="Bash", hooks=[guard_bash])],
    }
)
```

**Two Python gotchas with hook output fields:**
- Use `async_` (not `async`) — converted to `async` before sending to CLI
- Use `continue_` (not `continue`) — converted to `continue` before sending to CLI

**`can_use_tool` vs hooks:** For pure permission decisions, `can_use_tool` is simpler
than hooks. For richer behavior (injecting context, modifying inputs, async deferral),
use hooks. The two are mutually exclusive — don't set both.

## 4. In-process MCP tools

When you want Claude to call Python functions in your application, use SDK MCP servers.
They run in the same process (no IPC), have direct access to your app state, and are
faster than external MCP servers.

```python
from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions

@tool("lookup_user", "Look up a user by ID", {"user_id": str})
async def lookup_user(args):
    user = await db.get_user(args["user_id"])
    return {"content": [{"type": "text", "text": str(user)}]}

server = create_sdk_mcp_server("myapp", tools=[lookup_user])

options = ClaudeAgentOptions(
    mcp_servers={"myapp": server},
    allowed_tools=["lookup_user"],
)
```

Use TypedDict or `Annotated[type, "description"]` in `input_schema` for rich parameter
documentation that helps Claude use your tool correctly.

**When to use external MCP servers instead:** when the tool runs on a remote machine,
when you're reusing an existing MCP server not written in Python, or when you need the
tool isolated from your main process.

## 5. Session management

**Resuming a session:** pass `resume=session_id` to continue an existing conversation.
Combine with `fork_session=True` to branch into a new session rather than overwriting.

**Persisting sessions externally:** implement the `SessionStore` protocol and pass it as
`session_store`. Only `append()` and `load()` are required. Reference adapters for Redis,
Postgres, and S3 are in the SDK's `examples/session_stores/` directory.

```python
class MyStore:
    async def append(self, key: SessionKey, entries: list[SessionStoreEntry]) -> None:
        await redis.rpush(key["session_id"], *[json.dumps(e) for e in entries])

    async def load(self, key: SessionKey) -> list[SessionStoreEntry] | None:
        raw = await redis.lrange(key["session_id"], 0, -1)
        return [json.loads(r) for r in raw] if raw else None

options = ClaudeAgentOptions(session_store=MyStore())
```

**Working directory matters:** always set `cwd` explicitly. Claude's tools operate
relative to this directory and CLAUDE.md files are discovered from it.

## 6. Custom agents (subagents)

Define specialized subagents that the main Claude session can spawn via the `Agent` tool:

```python
options = ClaudeAgentOptions(
    agents={
        "reviewer": AgentDefinition(
            description="Reviews code for bugs and security issues",
            prompt="You are a security-focused code reviewer. Be thorough and precise.",
            tools=["Read", "Grep"],
            model="sonnet",
        ),
    }
)
```

Agents inherit `mcp_servers` from the parent session. Set `background=True` for
fire-and-forget agents (their output won't be waited on before the next user turn).

## 7. Thinking and effort

For complex reasoning tasks, configure thinking explicitly:

```python
ClaudeAgentOptions(
    thinking={"type": "adaptive"},   # Claude decides when to think (Opus 4.6+)
    effort="high",                   # Guides thinking depth
)
```

Avoid the deprecated `max_thinking_tokens` — it maps to on/off on newer models.

## 8. Structured output

To get a JSON response conforming to a schema:

```python
ClaudeAgentOptions(
    output_format={
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": {"summary": {"type": "string"}, "severity": {"type": "string"}},
        },
    }
)
```

The structured value is in `ResultMessage.structured_output`.

## 9. Cost and safety guardrails

```python
ClaudeAgentOptions(
    max_turns=5,           # stop after N user+assistant rounds
    max_budget_usd=0.50,   # stop if cost exceeds this
    task_budget={"total": 50_000},  # token budget hint sent to model
)
```

## 10. Common pitfalls

- **`can_use_tool` requires async streaming:** pass the prompt as `AsyncIterable`, not a string, when using `can_use_tool`. The client raises `ValueError` otherwise.
- **Don't cross async contexts:** a `ClaudeSDKClient` connected in one asyncio task group can't be used from another. Complete all operations in the same async context.
- **Environment leakage:** the SDK strips `CLAUDECODE` from the child's env so the subprocess doesn't think it's inside another Claude Code session. If you need to pass custom env vars, use `ClaudeAgentOptions(env={"MY_VAR": "value"})`.
- **Buffer size:** the default stdout buffer is 1 MB. If you're getting `CLIJSONDecodeError` on large MCP results, raise `max_buffer_size`.
- **CLI version check:** the SDK verifies that the bundled or system `claude` is ≥ 2.0.0. Set `CLAUDE_AGENT_SDK_SKIP_VERSION_CHECK=1` to bypass in offline environments.

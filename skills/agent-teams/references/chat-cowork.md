# Claude Chat and Cowork adapter

Documentation checked September 3, 2026. The available tools in the current session determine what can execute.

## Cowork

Anthropic documents Cowork's ability to coordinate subagents and parallel work. That does not establish a universally exposed per-worker model/effort interface. [Cowork guide](https://support.claude.com/en/articles/13345190-get-started-with-claude-cowork).

Inspect delegation tools. If they expose model selection, map each worker's requested model to that control. If they expose an effort setting, map validated effort values to it. If the tool only accepts a prompt, treat model and effort control as unavailable unless another documented host mechanism provides them. Do not assume Claude Code configuration paths configure Cowork.

When the user requests inherited defaults and actual subagents are available, proceed with that inherited configuration and label unobservable effective values as unverified. When mixed explicit settings cannot be applied, prepare the team and follow the selected fallback. Do not claim this skill gives Cowork controls the host does not expose.

## Claude Chat

Do not assume Chat offers user-configurable subagent spawning merely because skills or code execution are enabled. Inspect actual tools. A Python process pool or multiple headings in a response do not create independent model instances.

If no genuine delegation interface is exposed, produce a roster and self-contained worker prompts ready to transfer to Cowork or Claude Code, then follow the user's fallback choice. If sequential work is accepted, say that the current conversation is doing the assignments sequentially with its current model/settings.

Do not claim a prompt changes the Chat model picker, launches separate conversations, or controls another session's thinking level. A handoff plan must distinguish intended settings from applied settings.

## External orchestration

This package does not include an API service, paid runner, or background daemon. If the user separately requests one, establish its available tools and authorization as a separate implementation task. Do not search for credentials or incur API charges as an automatic fallback for missing Chat/Cowork controls.

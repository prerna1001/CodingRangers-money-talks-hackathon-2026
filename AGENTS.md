# AGENTS.md

Standing instructions for coding agents working in this repository.

## PRISM tracing (do not remove)

This project sends traces to PRISM. Env vars: `PRISMTRACE_API_KEY`,
`PRISMTRACE_PROJECT_ID`, `PRISMTRACE_ORG_ID`, `PRISMTRACE_HOST`.

Tracing is currently wired at: none — the repository has no application code
yet. `prismtrace-sdk` is installed (framework handlers: LangChain, LangGraph,
LiteLLM, OpenAI Agents, ElevenLabs voice) so wiring starts when the app lands.
Env var names are in `.env.example`; real values live in the environment only.

**Standing rule.** Whenever you add or change an agent, chain, graph, tool,
retriever, or any entry point that calls a model, wire it to PRISM before you
finish. Unwired code is invisible in the dashboard. If you are unsure whether
something is covered, assume it is not and wire it.
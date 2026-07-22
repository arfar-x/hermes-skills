"""Thin, tool-calling entry points exposed to the Hermes LLM runtime.

Every module here does exactly three things: validate input, call the
shared :class:`~lib.jira_client.JiraClient`, and return structured JSON.
None of them summarize, explain, or reason -- that is the LLM's job.
"""

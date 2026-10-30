# Trustworthy Analytics Agent (VeriQuery)

Multi-agent, RAG-based text-to-SQL analytics system with guardrails, an evaluation harness and an LLM gateway.

## Quickstart
```bash
cp .env.example .env
python -m venv .venv && source .venv/bin/activate
make install
make up        # Postgres 16 + pgvector
make test
```

## Status
- [x] Week 1 Day 1: scaffold

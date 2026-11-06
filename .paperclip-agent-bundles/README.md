# HUB Paperclip Agent Architecture

This directory is the versioned source of truth for the six specialized HUB
roles configured under `Orquestrador HUB`:

| Agent slug | Bundle | Mode | Expected handoff |
| --- | --- | --- | --- |
| `hub-backend-developer` | `backend-developer/AGENTS.md` | implementation | revision-bound implementation report to Backend Reviewer |
| `hub-frontend-developer` | `frontend-developer/AGENTS.md` | implementation | revision-bound implementation report to Frontend Reviewer |
| `hub-backend-reviewer` | `backend-reviewer/AGENTS.md` | review-only | `PASS`, `PASS_WITH_NOTES`, or `BLOCK` for the exact deliverable revision |
| `hub-frontend-reviewer` | `frontend-reviewer/AGENTS.md` | review-only | `PASS`, `PASS_WITH_NOTES`, or `BLOCK` for the exact deliverable revision |
| `hub-code-reviewer` | `code-reviewer/AGENTS.md` | review-only | final revision-bound integration verdict |
| `hub-security-reviewer` | `security-reviewer/AGENTS.md` | review-only | revision-bound defensive security verdict |

## Boundaries

Developers may change only the files authorized by the current Task Contract.
They must not approve their own implementation. Reviewers inspect the requested
revision and evidence independently and must never edit, format, patch, commit,
deploy, or update documentation.

Every handoff carries the Task, Base revision and Deliverable revision. Review
verdicts are valid only for the referenced Deliverable revision; any subsequent
change requires a new review.

## Paperclip permission limitation

Paperclip's global agent permissions currently control task assignment and the
creation of agents or skills. They do not provide a per-agent filesystem
read-only sandbox. Reviewer agents therefore have task/agent/skill creation
disabled in the control plane and are marked `reviewOnly` in metadata, while
the enforceable workspace boundary remains the explicit read-only instruction
in each reviewer bundle. Reviewers must receive review tasks only; they must not
be assigned implementation work.

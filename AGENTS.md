# Agent Instructions

This repository is a standalone, general-purpose Home Assistant custom component (HACS distribution). It is intended to be pushed to a public remote.

## No personal or environment-specific details

Never commit anything that identifies the maintainer's actual home setup, including but not limited to:

- Real person names, phone/device names or models, or notify-service identifiers tied to a specific person.
- Real entity IDs, automation IDs/aliases, tag UUIDs, or other identifiers copied from a live Home Assistant instance.
- Home name, location, coordinates, or timezone of a real installation.
- Screenshots, logs, or config dumps pulled from a live instance without first stripping the above.

Use generic, illustrative examples instead (e.g. "a weekly interval chore" or "a cycle-based chore with a threshold of N"). If you need to reference a real instance to research or verify behavior (e.g. via an MCP tool), keep findings in the conversation — generalize before writing anything to a file in this repo.

Before committing, review the diff for anything that looks like it leaked from a live instance, not just the files you intentionally changed.

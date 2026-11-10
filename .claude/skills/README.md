# Active skills

These load in every session. Keep this set small; everything else lives in
`skills-library/` (350 skills, not auto-loaded) and is reached through `skill-router`.

| Skill | Source | License |
|---|---|---|
| skill-router | this repo | — |
| frontend-design, webapp-testing | anthropics/skills | Apache-2.0 |
| brainstorming | obra/superpowers | MIT |
| performance-optimization | addyosmani/agent-skills | MIT |
| obsidian-markdown, defuddle | kepano/obsidian-skills | MIT |
| responsive-design | wshobson/agents (plugins/ui-design) | MIT |

- **Promote** a library skill: copy `skills-library/<category>/<name>/` here.
- **Demote** one: move it back into `skills-library/<category>/` and add a `REVIEWED` file
  if it contains reviewed code, so the build script won't overwrite it.
- **Rebuild the library**: clone the upstream repos into a folder as `owner_repo`
  (`git clone --depth 1 --no-checkout ...`), then run
  `python3 scripts/build-skills-library.py <that folder>`. Repo list is in the script.

#!/usr/bin/env python3
"""Build skills-library/ from upstream GitHub skill repos.

Usage:
  python3 scripts/build-skills-library.py <repos_dir>

<repos_dir> holds clones named owner_repo (e.g. obra_superpowers). Clones can be
blobless (`git clone --depth 1 --filter=blob:none --no-checkout`); files are read
with `git show`, so nothing from upstream is checked out or executed.

Only instruction-type files are copied (markdown, text, json/yaml, html/css/svg,
csv). Code files (.py, .js, .sh, ...) are never copied; they are listed in each
skill's SOURCE.md so someone can review and import them on purpose.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB = ROOT / "skills-library"

TEXT_EXT = {".md", ".txt", ".json", ".yaml", ".yml", ".html", ".css", ".svg", ".csv"}
CODE_EXT = {".py", ".js", ".cjs", ".mjs", ".ts", ".tsx", ".jsx", ".sh", ".bash",
            ".rb", ".go", ".rs", ".ps1", ".bat", ".php", ".lua"}
MAX_FILE = 300 * 1024
SKIP_DIRS = {"node_modules", "__pycache__", "tests", "test", "fixtures", "evals", ".git"}
# Bulky asset packs and galleries: left out, counted in SOURCE.md.
ASSET_DIRS = {"assets", "examples", "gallery", "samples", "showcase", "media", "images", "stencils", "plantuml-stencils"}
# Paths that are duplicate copies of a skill packaged for another agent/CLI.
DUP_PATH = re.compile(r"(^|/)(\.cursor|\.agents|\.codex|\.gemini|cli/assets|plugins/caveman|refine)/")

# (category, repo_dir, selector)
#   selector "*"            -> every SKILL.md in the repo (deduped by name)
#   selector [names...]     -> only skills whose folder name is listed
SOURCES = [
    ("documents-and-artifacts", "anthropics_skills", "*"),
    ("dev-workflow", "obra_superpowers", "*"),
    ("dev-workflow", "mattpocock_skills", "*"),
    ("dev-workflow", "addyosmani_agent-skills", "*"),
    ("obsidian", "kepano_obsidian-skills", "*"),
    ("marketing", "coreyhaines31_marketingskills",
     ["seo-audit", "ai-seo", "copywriting", "cro", "content-strategy", "pricing",
      "launch", "cold-email", "ab-testing", "programmatic-seo"]),
    ("engineering", "wshobson_agents",
     ["prompt-engineering-patterns", "rag-implementation", "llm-evaluation",
      "modern-javascript-patterns", "tailwind-design-system", "responsive-design",
      "github-actions-templates", "postmortem-writing", "accessibility-compliance"]),
    ("research", "K-Dense-AI_scientific-agent-skills",
     ["exploratory-data-analysis", "citation-management"]),
    ("research", "Imbad0202_academic-research-skills", "*"),
    ("research", "mvanhorn_last30days", "*"),
    ("writing-and-output", "JuliusBrussee_caveman", ["caveman"]),
    ("writing-and-output", "blader_humanizer", "*"),
    ("writing-and-output", "ayghri_i-have-adhd", "*"),
    ("security", "cloudflare_security-audit-skill", "*"),
    ("meta", "virgiliojr94_book-to-skill", "*"),
    # diagrams
    ("diagrams", "tt-a1i_archify", "*"),
    ("diagrams", "nicobailon_visual-explainer", "*"),
    ("diagrams", "Agents365-ai_drawio-skill", "*"),
    ("diagrams", "Cocoon-AI_architecture-diagram-generator", "*"),
    ("diagrams", "QingYunA_answer-me-with-html", "*"),
    ("diagrams", "plannotator_effective-html", "*"),
    ("diagrams", "axtonliu_axton-obsidian-visual-skills", "*"),
    ("diagrams", "markdown-viewer_skills", "*"),
    ("diagrams", "yctimlin_mcp_excalidraw", "*"),
    ("diagrams", "caru-ini_stack-diagram", "*"),
    ("diagrams", "imxv_Pretty-mermaid-skills", "*"),
    ("diagrams", "bybit-exchange_svg-diagram", "*"),
    # design
    ("design", "nextlevelbuilder_ui-ux-pro-max-skill", "*"),
    ("design", "Leonxlnx_taste-skill", "*"),
    ("design", "Nutlope_hallmark", "*"),
    ("design", "alchaincyf_huashu-design", "*"),
    ("design", "ConardLi_garden-skills", "*"),
    ("design", "heydamir_unslop", "*"),
    ("design", "ibelick_ui-skills", "*"),
    ("design", "google-labs-code_stitch-skills", "*"),
    ("design", "kaankiziltug_logo-design-skill", "*"),
    ("design", "JimLiu_baoyu-design", "*"),
    ("design", "Owl-Listener_designer-skills", "*"),
    ("design", "plugin87_ux-ui-agent-skills", "*"),
    ("design", "oil-oil_oil-ui", "*"),
    ("design", "LottieFiles_motion-design-skill", "*"),
    ("design", "dominikmartn_nothing-design-skill", "*"),
    ("design", "ItsssssJack_power-design", "*"),
]

# Listed in the index but not copied: no license, or the license forbids redistribution.
LINK_ONLY = [
    ("meta", "multica-ai/andrej-karpathy-skills", "karpathy-guidelines", "No license; CLAUDE.md-style behavior rules"),
    ("engineering", "Graphify-Labs/graphify", "graphify", "A CLI tool, not a skill folder; turns a codebase into a knowledge graph"),
    ("diagrams", "coleam00/excalidraw-diagram-skill", "excalidraw-diagram", "No license; hand-drawn Excalidraw diagrams"),
    ("diagrams", "bentossell/visualise", "visualise", "No license; inline SVG diagrams, widgets, charts"),
    ("design", "dickwu/apple-design-skill", "apple-design", "No license; UI review against Apple HIG"),
    ("design", "Jakubantalik/transitions.dev", "transitions-dev", "License forbids redistributing the library; 43+ UI transitions"),
    ("design", "bergside/awesome-design-skills", "awesome-design-skills", "Index of 67 design skill files (browse only)"),
]


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True).stdout


def parse_frontmatter(text):
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return {}
    out, lines, i = {}, m.group(1).split("\n"), 0
    while i < len(lines):
        km = re.match(r"^([A-Za-z_-]+):\s*(.*)$", lines[i])
        if km:
            key, val = km.group(1), km.group(2).strip()
            if val in (">", "|", ">-", "|-", ""):
                buf = []
                while i + 1 < len(lines) and (lines[i + 1].startswith((" ", "\t")) or not lines[i + 1].strip()):
                    i += 1
                    buf.append(lines[i].strip())
                val = " ".join(b for b in buf if b)
            out[key] = val.strip().strip('"').strip("'")
        i += 1
    return out


def license_file(repo):
    for name in git(repo, "ls-tree", "--name-only", "HEAD").decode().split("\n"):
        if re.match(r"(?i)^licen[cs]e", name):
            return name
    return None


def build():
    repos_dir = Path(sys.argv[1]).resolve()
    LIB.mkdir(exist_ok=True)
    index, used = [], set()
    for category, rdir, selector in SOURCES:
        repo = repos_dir / rdir
        files = git(repo, "ls-tree", "-r", "-l", "HEAD").decode().strip().split("\n")
        sizes = {}
        for row in files:
            meta, path = row.split("\t", 1)
            size = meta.split()[-1]
            sizes[path] = int(size) if size.isdigit() else 0
        sha = git(repo, "rev-parse", "HEAD").decode().strip()
        lic = license_file(repo)
        url = git(repo, "remote", "get-url", "origin").decode().strip()
        owner_repo = re.sub(r"^https://github\.com/|\.git$", "", url)
        skill_dirs = sorted(os.path.dirname(p) for p in sizes if p == "SKILL.md" or p.endswith("/SKILL.md"))
        seen = set()
        for sdir in skill_dirs:
            if DUP_PATH.search(sdir + "/") or sdir.endswith("template"):
                continue
            name = os.path.basename(sdir) or rdir.split("_", 1)[1]
            if name in ("skill", "skills"):
                name = rdir.split("_", 1)[1]
            if name in seen or (selector != "*" and name not in selector):
                continue
            seen.add(name)
            slug = name if name not in used else f"{name}--{rdir.split('_')[0]}"
            used.add(slug)
            dest = LIB / category / slug
            if (dest / "REVIEWED").exists():
                # Full copy (code included) that was reviewed by hand: never overwrite.
                fm = parse_frontmatter((dest / "SKILL.md").read_text(errors="replace"))
                desc = re.sub(r"\s+", " ", fm.get("description", "")).replace("|", "/")
                index.append((category, slug, owner_repo, desc, "reviewed"))
                continue
            shutil.rmtree(dest, ignore_errors=True)
            dest.mkdir(parents=True, exist_ok=True)
            prefix = (sdir + "/") if sdir else ""
            omitted, assets_skipped = [], 0
            for path, size in sizes.items():
                if not path.startswith(prefix) or path.endswith("/"):
                    continue
                rel = path[len(prefix):]
                parts = rel.split("/")
                if any(p in SKIP_DIRS for p in parts[:-1]):
                    continue
                if any(p in ASSET_DIRS for p in parts[:-1]):
                    assets_skipped += 1
                    continue
                if not sdir and len(parts) > 1 and not rel.startswith(("references/", "reference/", "docs/", "templates/", "examples/")):
                    continue  # repo-root skill: keep only its own docs, not the whole repo
                ext = os.path.splitext(rel)[1].lower()
                if ext in CODE_EXT:
                    omitted.append(rel)
                    continue
                if ext not in TEXT_EXT or size > MAX_FILE:
                    continue
                out = dest / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(git(repo, "show", f"HEAD:{path}"))
            if lic:
                (dest / "LICENSE").write_bytes(git(repo, "show", f"HEAD:{lic}"))
            fm = parse_frontmatter((dest / "SKILL.md").read_text(errors="replace"))
            src = [f"# Source", "", f"- Repo: https://github.com/{owner_repo}",
                   f"- Path: `{sdir or '.'}`", f"- Commit: `{sha}`",
                   f"- License: see LICENSE (from `{lic}`)" if lic else "- License: none found"]
            if assets_skipped:
                src += ["", f"{assets_skipped} asset/example files (icons, images, galleries) were not copied; get them from the repo if needed."]
            if omitted:
                src += ["", "## Code files NOT copied (review before importing)", ""]
                src += [f"- `{o}`" for o in sorted(omitted)]
            (dest / "SOURCE.md").write_text("\n".join(src) + "\n")
            desc = re.sub(r"\s+", " ", fm.get("description", "")).replace("|", "/")
            index.append((category, slug, owner_repo, desc, "scripts-omitted" if omitted else ""))

    lines = ["# Skills library index", "",
             "Not auto-loaded. The `skill-router` skill searches this file and reads the chosen",
             "skill's SKILL.md on demand. Regenerate with `scripts/build-skills-library.py`.", "",
             "Flags: `scripts-omitted` = the upstream skill ships code that was NOT copied; its",
             "instructions may reference missing files. `reviewed` = full copy, code reviewed by hand\n(marked by a REVIEWED file; the build never overwrites it).", "",
             "| Skill | Category | Source | Flags | Description |", "|---|---|---|---|---|"]
    for cat, slug, src, desc, flag in sorted(index):
        lines.append(f"| [{slug}]({cat}/{slug}/SKILL.md) | {cat} | {src} | {flag} | {desc[:220]} |")
    lines += ["", "## Link only (not copied)", "", "| Name | Category | Repo | Why |", "|---|---|---|---|"]
    for cat, repo, name, why in LINK_ONLY:
        lines.append(f"| {name} | {cat} | https://github.com/{repo} | {why} |")
    (LIB / "INDEX.md").write_text("\n".join(lines) + "\n")
    print(f"{len(index)} skills indexed: {sum(i[4] == 'scripts-omitted' for i in index)} with scripts omitted, {sum(i[4] == 'reviewed' for i in index)} reviewed")


if __name__ == "__main__":
    build()

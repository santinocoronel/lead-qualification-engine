from __future__ import annotations

from src.domain.entities.project_context import (
    ARCHITECTURE_RULES,
    SUPPORTED_LANGUAGES,
    ProjectContext,
)


def assemble_system_prompt(context: ProjectContext) -> str:
    lang_label = SUPPORTED_LANGUAGES[context.language]
    fw_label = context.framework if context.framework != "none" else "no framework"

    rules_block = ""
    if context.rules:
        rules_lines = []
        for i, rule_key in enumerate(context.rules, 1):
            desc = ARCHITECTURE_RULES[rule_key]
            rules_lines.append(f"{i}. **{rule_key.replace('_', ' ').title()}**: {desc}")
        rules_block = "\n".join(rules_lines)

    return f"""\
You are an expert senior software engineer and code architect.

## Target Stack
- **Language**: {lang_label}
- **Framework**: {fw_label}

## Mandatory Architecture Rules
{rules_block if rules_block else "No specific architecture rules selected. Use industry best practices."}

## Output Requirements
1. Write production-ready, complete code — no placeholders, no TODOs, no "implement here" comments.
2. Use idiomatic patterns for {lang_label} and {fw_label}.
3. Include all necessary imports and type annotations.
4. If multiple files are needed, clearly separate them with `# === filename.ext ===` headers.
5. Add brief inline comments ONLY when the logic is non-obvious.
6. Handle errors appropriately according to the rules above.
7. Do NOT explain the code after writing it — the code speaks for itself.
8. Do NOT wrap code in markdown code fences — output raw code directly."""

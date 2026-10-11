---
name: ui-theme-check
description: Check frontend changes for light and dark theme coverage against the ai-chatbot palette rules in CLAUDE.md. Use after editing any frontend component or CSS, before committing UI work, or when the user asks to check dark mode or theming.
---

# Theme coverage check for ai-chatbot

Every new UI element must work in both themes. Light colour classes need a `dark:` variant in the same `className`. The rules are in `CLAUDE.md` under Theming. This skill checks the changed frontend files against them.

## 1. Scope to what changed

```bash
git diff --name-only -- frontend/src
git diff --cached --name-only -- frontend/src
git ls-files --others --exclude-standard -- frontend/src
```

Check only these files. If there are no changes under `frontend/src`, say so and stop.

## 2. Find bare light-only classes

In the changed lines (use `git diff -U0 -- frontend/src` and look only at `+` lines), flag:

- `bg-white`, `bg-gray-*`, `bg-slate-*`, `bg-zinc-*` with no `dark:bg-` in the same `className`
- `text-gray-*`, `text-black`, `text-slate-*` with no `dark:text-` in the same `className`
- `border-gray-*` with no `dark:border-` in the same `className`

Check the whole `className` string, not just the line. Multi-line class lists are common.

## 3. Check against the palette

The repo's existing palette is the only one to use:

| Role | Dark class |
|---|---|
| Page background | `dark:bg-[#131314]` |
| Sidebar | `dark:bg-[#1e1f20]` |
| Menus, popovers, modals | `dark:bg-[#28292a]` |
| Borders | `dark:border-[#3c4043]` |
| Hover and button fills | `dark:bg-[#303134]`, `dark:hover:bg-[#3c4043]` |
| Menu row hover | `dark:hover:bg-[#353638]` |
| Primary text | `dark:text-[#e3e3e3]` |
| Secondary text | `dark:text-[#9aa0a6]` |
| Accent | `dark:text-[#8ab4f8]` |
| Red actions | `dark:text-red-400` |

Flag any new hex colour that is not in this table. Also flag any `dark:` value that is a different shade of an existing role.

## 4. Known exceptions

These are intentional and are not violations:
- Inline light styles in `CopyResponseBtn.tsx`, so copied rich text pastes readably.
- The code block wrapper, which is always dark zinc.

## 5. Report

List each finding as `file:line`, the offending class, and the fix. If there are none, say the changed files passed the static check.

Then state that this is a static check only. Ask the user to confirm the visual result in both themes, or use the `run` skill to take screenshots in each theme. Do not claim a visual result you did not see.

## Do not

- Do not edit the exceptions listed above.
- Do not replace palette values with Tailwind defaults.

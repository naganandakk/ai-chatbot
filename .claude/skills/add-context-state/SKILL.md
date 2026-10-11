---
name: add-context-state
description: Add a piece of shared app state to the React context in frontend/src/Context.tsx and wire it to the components that read it. Use when the user asks to add global state, a new context value, a persisted preference, or a shared flag used by several components.
---

# Add shared state to the app context

`frontend/src/Context.tsx` holds the one React context for the app: the active session, session list, `isGenerating`, sidebar state, theme, and the toast-style error stack. Components read it through the context and do not create their own global state.

## Before you change anything

Read `Context.tsx` in full. Note:
- the `AppContextValue` type
- the `Context` object and the `useAppContext` hook
- `ContextProvider`, where state and callbacks are defined
- how `theme` is stored (`THEME_STORAGE_KEY`, `ai-chat.theme`), as the model for any persisted value

Components call `useContext(Context)` or `useAppContext()`. Use whichever the file they are editing already uses. Do not mix them in one component.

## Rules

- Keep state that only one component needs as local state. Put state in the context only when two or more components read or write it.
- Persisted values go in localStorage under an `ai-chat.` prefixed key. Read them with a fallback, so a missing or corrupt value does not crash the app.
- Use `useCallback` for functions placed in the context, as the existing callbacks do, so consumers do not re-render needlessly.
- Use relative `/api` paths for any fetch. Do not add absolute URLs.
- Errors go through the toast-style error stack in the context, not `alert()`.

## Steps

1. Add the field to `AppContextValue`, with a type.
2. Add the `useState` (or a `useEffect` for persistence) inside `ContextProvider`. Add any setter or callback with `useCallback`.
3. Add the value to the object passed to `Context.Provider`.
4. Update each consuming component to read the new field. Keep the change in those components minimal.
5. If the state is a UI preference, check it in both themes. Use the `ui-theme-check` skill on any UI you touched.
6. Run `cd frontend && npm run build`. This runs the type check. Fix any type errors before reporting.

## Report

List the new field and its type, the components that read it, whether it is persisted and under which key, and the build result. Note if you could not run the UI.

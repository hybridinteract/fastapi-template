# Frontend Conventions

> The Next.js half of the stack. Split out of [`PROJECT_CONVENTIONS.md`](PROJECT_CONVENTIONS.md) on
> 9 September 2026 — this is a backend template, and a fifth of its spec was React.
> Read this only when working on a paired frontend repo; copy it there if that repo has no spec.
> Last verified against the code: 9 September 2026.

The backend rules it references still apply: layering ([`PROJECT_CONVENTIONS.md`](PROJECT_CONVENTIONS.md) §4),
permission naming (§9), and list endpoints (§10) are the contract this frontend consumes.

---

## 1. Stack

| Concern | Technology |
|---------|-----------|
| Framework | Next.js (App Router) |
| Server State | React Query (TanStack Query) |
| Client State | Zustand (UI-only state) |
| Styling | Tailwind CSS |
| Forms | React Hook Form + Zod |
| Testing | Vitest + Playwright |

---

## 2. Project Structure

```
src/
├── app/                             # Next.js App Router
│   ├── (auth)/                      # Unauthenticated pages
│   ├── (dashboard)/
│   │   └── <role>/                  # One folder per user role
│   │       ├── config.ts            # Nav items, route constants — NO JSX, no hooks
│   │       ├── layout.tsx
│   │       └── <feature>/page.tsx
│   ├── api/                         # Route handlers (BFF layer)
│   └── globals.css                  # Design tokens — single source of truth
│
├── components/
│   ├── layout/                      # Shell (sidebar, topnav)
│   ├── providers/                   # Context wrappers — no visual output
│   ├── shared/                      # Reusable feature components
│   └── ui/                          # Primitives (Button, Badge, Input)
│
├── lib/                             # Business logic — DOMAIN-BASED
│   ├── api-client.ts                # Singleton HTTP client — stateless, no stored tokens
│   └── <domain>/
│       ├── types.ts                 # Backend* (snake_case) + Frontend (camelCase) types
│       ├── transformers.ts          # snake_case ↔ camelCase — the ONLY place backend fields appear
│       ├── api.ts                   # Service functions → apiClient → transform → return
│       ├── hooks.ts                 # React Query hooks
│       ├── store.ts                 # Zustand — ONLY shared UI state (optional)
│       └── index.ts                 # Barrel exports
│
└── middleware.ts                    # Route protection + API auth injection
```

---

## 3. Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Files | `kebab-case.tsx` or `camelCase.ts` | `lead-table.tsx`, `hooks.ts` |
| Components | `PascalCase` | `LeadTable`, `UserAvatar` |
| Hooks | `use` prefix | `useLeads()`, `useCreateLead()` |
| Backend types | `Backend*` prefix | `BackendLead`, `BackendUser` |

---

## 4. Frontend Patterns

### Data flow

```
Component → Hook (hooks.ts) → Service (api.ts) → apiClient → Backend
```

- All requests through `apiClient`. No direct `fetch()` in components.
- `apiClient` is stateless — never stores tokens. Auth handled by `middleware.ts`.
- All snake_case → camelCase conversion happens once, in `transformers.ts`.
- Components never see backend shapes.

### State management

```
Data from API + interactive?  → React Query
Data from API, initial load?  → Server Component (RSC)
Shared UI-only state?         → Zustand
Local component state?        → useState
```

Never put API data (`isLoading`, `error`, `items[]`) in Zustand.

### React Query pattern

```typescript
export const leadKeys = {
  lists: () => ["leads", "list"] as const,
  list: (params) => [...leadKeys.lists(), params] as const,
};

export function useLeads(params) {
  return useQuery({ queryKey: leadKeys.list(params), queryFn: () => leadApi.list(params), staleTime: 30_000 });
}

export function useCreateLead() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: leadApi.create, onSuccess: () => qc.invalidateQueries({ queryKey: leadKeys.lists() }) });
}
```

### Error handling

All API errors are `AppError` instances (statusCode, message, detail, data). Map 422 responses to field errors. Use `onError` in mutations, not try/catch in components.

### Styling rules

- All tokens in `globals.css`. Use semantic tokens: `text-primary`, `bg-muted`.
- Never hex colors or `bg-[#f5f5f5]` in component files.

### File size limits

| Type | Max |
|------|-----|
| Page component | ~200 lines |
| Shared component | ~150 lines |
| Custom hook | ~80 lines |
| Zustand store | ~50 lines (if more, you're storing server state) |

---

## 5. New Feature Checklist

```
□ Create lib/<domain>/ folder
□ types.ts — Backend* (snake_case) + Frontend (camelCase) types
□ transformers.ts — manual mapping only, no auto-mappers
□ api.ts — service functions → apiClient → transform → return
□ hooks.ts — query key factory + useQuery/useMutation
□ store.ts — ONLY if shared UI state needed (never API data)
□ index.ts — barrel exports
□ Page at app/(dashboard)/<role>/<feature>/page.tsx
□ Add nav item + route constant to role's config.ts
```

---

## 6. Hard Rules — never do

- API data in Zustand (`isLoading`, `error`, `items[]`, `fetchX()`)
- Direct `fetch()` in components
- Hex colors in component files — use design tokens
- Backend `snake_case` fields leaking into components
- Tokens stored in `apiClient`
- Deep relative imports (`../../..`) — use `@/` aliases
- `any` without an explaining comment
- JSX or hooks in `config.ts`
- Mixing Server Actions + React Query mutations for the same operation

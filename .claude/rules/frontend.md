---
paths:
  - "frontend/src/**/*.{ts,tsx}"
---

# React Frontend Rules

- TypeScript strict mode; explicit types for props and state — no `any`
- Functional components with hooks only
- API calls go through service functions in `src/services/`, never inline axios in components
- Types live in `src/types/`; share them between services and components
- Use existing Radix UI + Tailwind patterns; check a similar existing component before building a new one
- `npx tsc --noEmit` must pass before any frontend task is considered done

## Standard service pattern

```typescript
export const myService = {
  async getData(id: number): Promise<MyType> {
    const response = await api.get<MyType>(`/endpoint/${id}/`);
    return response.data;
  },
};
```

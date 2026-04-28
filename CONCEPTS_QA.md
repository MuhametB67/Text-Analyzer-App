# Core Programming — Concept Q&A

A short, plain-English reference for ten common interview-style concept questions. Answers aim for the level of "explain it on a whiteboard in under a minute."

---

## 1. Complexity: Big-O, Big-Θ, Big-Ω

All three describe how an algorithm's resource usage (time or space) grows as input size `n` grows.

- **Big-O** is the **upper bound** — "no worse than this." Used for worst-case analysis.
- **Big-Θ** is a **tight bound** — both upper and lower bound have the same growth rate. Used when an algorithm always behaves the same way regardless of input.
- **Big-Ω** is the **lower bound** — "no better than this." Used for best-case analysis.

In practice we mostly talk about Big-O because we care about the worst case.

**O(n log n) vs O(n²) in practice:**

| n | n log n | n² |
|---|---|---|
| 100 | ~660 | 10,000 |
| 1,000 | ~10,000 | 1,000,000 |
| 1,000,000 | ~20,000,000 | 1,000,000,000,000 |

Mergesort/quicksort (O(n log n)) destroy bubble sort (O(n²)) once you get past a few thousand items. For small `n` the difference is negligible — sometimes an O(n²) algorithm with a tiny constant beats an O(n log n) one in real-world numbers.

---

## 2. Data structures: when to use what

| Structure | Strength | Trade-off |
|---|---|---|
| **Array / list** | O(1) random access by index, cache-friendly | O(n) insert/delete in the middle; resizing can be expensive |
| **Linked list** | O(1) insert/delete at a known node | O(n) random access; bad cache locality |
| **Hash map** | O(1) average lookup/insert/delete by key | Unordered; worst-case O(n) on bad hashing; memory overhead |
| **Tree (BST / B-tree)** | O(log n) ops with sorted iteration and range queries | More complex; needs balancing to keep guarantees |

Rule of thumb: arrays for "I know roughly how many and I access by index," hash maps for "look up by key," trees for "sorted, range queries, ordered iteration."

---

## 3. Immutability & state

- **Mutable** data can be changed after creation (Python lists, JS objects, Java `ArrayList`).
- **Immutable** data cannot be changed once created (Python tuples and strings, Java `String`, anything `const` and frozen).

**Why immutability simplifies things:**

- **Reasoning:** if a value never changes, you only need to understand where it was *created* — not every place that could mutate it later. Bugs from "who changed this?" disappear.
- **Concurrency:** multiple threads can read the same immutable value with zero coordination — no locks, no race conditions. Mutation is the source of basically every concurrency bug.
- **Caching / memoization:** safe to cache and reuse immutable values; you can't cache mutable ones without defensive copying.

The cost: every "change" creates a new object, which can be wasteful unless the language uses structural sharing (Clojure, Immutable.js).

---

## 4. Stack vs heap

| | Stack | Heap |
|---|---|---|
| What lives there | Function call frames, local variables, primitive values | Dynamically allocated objects |
| Size | Fixed, known at compile time | Variable, grows at runtime |
| Allocation | Push/pop on function call/return — extremely fast | Manual (`malloc`/`new`) or via GC — slower |
| Order | LIFO | Random |
| Lifetime | Tied to the function's scope | Independent of scope; lives until freed or GC'd |

**Scope** is where a variable is *visible* in the source code (e.g., a local variable is in scope inside its function). **Lifetime** is how long it actually *exists* in memory.

For stack variables, scope and lifetime line up — the variable disappears when the function returns. For heap variables they don't: an object created on the heap inside a function can outlive that function as long as something still holds a reference to it. That decoupling is exactly why heap allocation exists.

---

## 5. OOP: encapsulation, inheritance, polymorphism

- **Encapsulation** — bundling data with the methods that operate on it, and hiding internals behind an interface. Callers use the API, not the fields directly. Lets you change the implementation without breaking callers.
- **Inheritance** — a child class extends a parent class, getting its fields and methods. Models an "is-a" relationship (`Dog` is an `Animal`).
- **Polymorphism** — the same call works on different types. Calling `.area()` on `Circle` or `Square` runs different code, but the caller doesn't care which.

**Composition over inheritance:**

Inheritance couples the child tightly to the parent — change the parent and every subclass can break (the "fragile base class" problem). Deep inheritance trees are also painful to refactor and reason about.

**Composition** ("has-a") is usually safer: instead of `Car extends Engine`, you give `Car` an `engine` field. You can swap engines, mock them in tests, and changes to `Engine` don't ripple through a class hierarchy. Use inheritance only when there's a genuine "is-a" relationship and you control the parent class.

---

## 6. APIs & contracts: idempotency

An operation is **idempotent** if calling it multiple times has the same effect as calling it once. The state of the system after one call is the same as after ten calls.

This matters because networks are unreliable — clients retry, requests get duplicated, and idempotency is what lets you safely retry without corrupting data.

**HTTP methods:**

| Method | Idempotent? | Why |
|---|---|---|
| `GET` | Yes | Just reads, no state change |
| `PUT` | Yes | Replaces the resource — same body → same final state |
| `DELETE` | Yes | After the first call the resource is gone; further calls are no-ops |
| `POST` | **No** | Typically creates a new resource each time → two POSTs = two resources |
| `PATCH` | Depends | "set status to active" is idempotent; "increment counter" is not |

A classic non-idempotent example: `POST /payments` charging a card. If the client retries on a timeout, you can charge twice. The fix is usually an **idempotency key** — the client sends a unique ID with each attempt, and the server deduplicates.

---

## 7. Concurrency vs parallelism

- **Concurrency** — *managing* multiple tasks that can make progress independently. They might run interleaved on a single core (one at a time, switching fast). It's a structure problem.
- **Parallelism** — actually *running* multiple tasks at the same instant on multiple cores. It's an execution detail.

A single-threaded async server (Node, asyncio) is concurrent but not parallel. A multi-threaded program on a multi-core CPU is both.

**Race condition** — two threads access shared state, the outcome depends on timing, and at least one is writing. Classic example: two threads both read `balance = 100`, both add `50`, both write `150`. You lost a `50`.

**Deadlock** — two or more threads each hold a lock the other needs, so nobody can proceed. Thread A holds lock 1 wants lock 2; Thread B holds lock 2 wants lock 1. Stuck forever.

**Mitigations:**
- Use locks/mutexes around shared state — but acquire them in a consistent order to avoid deadlock.
- Prefer atomic operations (compare-and-swap, atomic counters) for simple cases.
- Prefer immutability — no shared mutable state means no race.
- Use message passing (channels, actors, queues) instead of shared memory.
- Set lock acquisition timeouts so a deadlock surfaces as an error, not a hang.
- Use higher-level primitives (thread-safe collections, async/await) and let the library handle it.

---

## 8. Databases: SQL vs NoSQL, and indexes

**Pick SQL when** you have structured, relational data; need ACID transactions; need complex joins; or your schema is well-defined and stable. Banking, e-commerce orders, anything with strong consistency requirements.

**Pick NoSQL when** the schema is flexible or evolves quickly; you need to scale horizontally across many machines; data is naturally a document, key-value, or graph; or you can tolerate eventual consistency. Logs, user sessions, social graphs, content stores.

In practice most non-trivial systems use both — SQL for the source of truth, a key-value store like Redis for caching and queues.

**Indexes** are extra data structures (usually B-trees) that the database maintains alongside a table to speed up lookups on specific columns. Without an index, finding a row by `email` is O(n) — full table scan. With an index, it's O(log n).

How they help: read queries that filter or join on indexed columns get dramatically faster.

How they hurt:
- **Writes get slower** — every insert/update/delete also has to update every relevant index.
- **They take disk space** — sometimes a lot.
- **Bad indexes don't help** — an index on a column with only two distinct values (e.g., `is_active` boolean) is mostly useless because the database still has to scan a huge chunk of the table.
- **Too many indexes** mean the optimizer has more decisions to make and writes get death-by-a-thousand-cuts slow.

Rule of thumb: index columns that appear in `WHERE`, `JOIN`, and `ORDER BY` clauses on read-heavy queries — and only those.

---

## 9. Testing: unit vs integration vs E2E

| Type | Scope | Speed | What it catches |
|---|---|---|---|
| **Unit** | One function/class in isolation | Milliseconds | Logic bugs in a single piece |
| **Integration** | Multiple components together (e.g., service + DB) | Seconds | Wiring bugs, contract mismatches between components |
| **End-to-end** | Whole system from the outside (browser → API → DB) | Tens of seconds to minutes | User-flow regressions, real environment issues |

The classic "test pyramid": many unit tests, fewer integration tests, a small number of E2E tests. Inverting this gives you a slow, flaky test suite that everyone learns to ignore.

**When to mock:**
- External dependencies you don't control (third-party APIs, payment providers).
- Slow or expensive resources (real databases in pure unit tests, file systems, network).
- Non-deterministic stuff (clocks, random numbers, UUIDs).
- Things that have side effects you don't want in tests (sending real emails).

**Risks of over-mocking:**
- Tests pass against your mock but fail in production because the mock doesn't match the real thing's behavior.
- Tests become coupled to implementation details (you're asserting "method X was called with Y" instead of asserting on actual outcomes), so refactors break tests even when behavior is unchanged.
- False sense of coverage — green CI but the integration is broken.
- Mocks rot silently when the real API changes.

A good rule: mock at the *edges* of your system (network, DB, time), not at every internal boundary. And keep at least one real integration test for any external dependency you mock everywhere else.

---

## 10. Git: merge vs rebase

Both combine work from one branch into another, but they produce different histories.

**Merge** creates a new "merge commit" that ties the two branches together. Full history is preserved, including the fact that work happened in parallel.

```
main:    A---B---C---M
                    /
feature:     D---E
```

**Rebase** replays your commits on top of the target branch, as if you had started your work from the latest `main`. Linear history, no merge commit.

```
main:    A---B---C---D'---E'
```

(`D'` and `E'` are new commits with the same content but different SHAs.)

**When to favor merge:**
- Integrating a shared/public branch (anyone else's commits depend on the original SHAs).
- You want to preserve the historical context of when and how a feature was developed.
- Long-lived feature branches where the merge commit is meaningful.

**When to favor rebase:**
- Cleaning up your *local* commits before pushing (squash WIP commits, fix typos in messages).
- Keeping your feature branch up to date with `main` while you're still working on it — produces a cleaner final history.
- You want a linear log that's easy to read with `git log`.

**The golden rule:** never rebase commits that have been pushed to a shared branch. Rebasing rewrites history, which means anyone else who pulled those commits is now out of sync, and the next push gets messy. Rebase your own private branches; merge anything public.

A common workflow: rebase your feature branch onto `main` regularly while developing (clean), then merge it into `main` with a merge commit when it's done (preserves the fact that this feature was a unit of work).

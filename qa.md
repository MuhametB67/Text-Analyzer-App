# Q&A - Core Programming Concepts

## 1. Complexity: Big-O, Big-Θ, Big-Ω

Big-O is the worst case — how slow can it get. Big-Ω is the best case — how fast can it go. Big-Θ is when both are the same, so it always behaves that way.

We mostly use Big-O because the worst case is what usually matters.

O(n log n) vs O(n²): for small inputs they're close, but once you have thousands of items O(n²) gets really slow really fast. For example with 1000 items, O(n log n) is around 10,000 steps and O(n²) is 1,000,000. That's why sorting algorithms like mergesort (n log n) are used instead of bubble sort (n²).

## 2. Data structures: when to use what

- **Array / list** — good when you need to grab something by its position fast. Bad when you need to insert in the middle, you have to shift everything.
- **Linked list** — good for adding and removing stuff a lot. Bad if you need to find item number 50, you have to go through all 49 first.
- **Hash map** — good for looking things up by a key, super fast. Bad because there's no order to the items.
- **Tree** — good when you need things sorted or want to do range searches. Bad because it's more complex to implement and needs balancing to stay fast.

## 3. Immutability & state

Mutable means you can change the value after creating it. Immutable means once it's made, it can't be changed.

Immutability makes things easier because you don't have to worry about something else changing your data behind your back. For concurrency it's huge — if two threads can't modify the same thing, you can't have race conditions. That's a big source of bugs gone.

The downside is you create a new object every time you "change" something, which can use more memory.

## 4. Stack vs heap

Stack is for local variables and function calls. It's fast and automatic — when a function ends, its stack stuff is gone.

Heap is for objects you create manually (like with `new` in some languages). It stays around until you free it or the garbage collector cleans it up.

Scope is where a variable is visible in the code. Lifetime is how long it actually exists in memory. For stack stuff they line up — variable disappears when the function ends. For heap stuff the lifetime can be longer than the scope, because something else might still be holding a reference to it.

## 5. OOP: encapsulation, inheritance, polymorphism

- **Encapsulation** — keeping data and the methods that work on it together, and hiding the inside details. You use the public methods, you don't touch the internal fields directly.
- **Inheritance** — one class extends another and gets all its stuff. Like Dog extends Animal.
- **Polymorphism** — same method name, different behavior depending on the type. You call `.area()` on a Circle or a Square and it works for both.

Composition is better than inheritance when the relationship is more "has-a" than "is-a". A Car has-an Engine, it isn't an Engine. Inheritance can also get messy when you have deep chains and changing the parent breaks all the children. Composition is more flexible.

## 6. APIs: idempotent operations

Idempotent means you can call it many times and the result is the same as calling it once. Useful because if a request fails and the client retries, you don't end up doing the action twice.

Examples:
- **GET** — idempotent, just reading
- **PUT** — idempotent, replaces the resource (same input = same final state)
- **DELETE** — idempotent, after the first call the thing is gone, more calls don't change anything
- **POST** — NOT idempotent, usually creates a new resource each time. If you POST a payment twice you charge the card twice.

## 7. Concurrency vs parallelism

Concurrency is when multiple tasks can be in progress at the same time, but not necessarily running at the exact same instant. Parallelism is when they actually run at the same instant on different CPU cores.

Race condition: two threads access the same data at the same time and the result depends on which one gets there first. Like two threads both reading balance=100, both adding 50, both writing 150 — you lost 50.

Deadlock: thread A is waiting for thread B to release something, but B is waiting for A. Nothing moves.

To avoid them: use locks (mutexes), prefer immutable data, use message passing instead of shared memory, and be careful about lock ordering so you don't deadlock.

## 8. Databases: SQL vs NoSQL

Pick SQL when your data is structured, has relationships, and you need transactions to be reliable. Things like banking, orders, anything that has to stay consistent.

Pick NoSQL when your schema changes a lot, you need to scale across many servers, or your data is more like documents/key-value pairs. Things like logs, user sessions, social feeds.

Indexes are like the index in a book — they let the database find things without scanning every row. They make reads way faster.

But they hurt writes, because every insert or update also has to update the indexes. They also use disk space. Too many indexes and your writes get slow. So only index columns you actually search on a lot.

## 9. Testing: unit vs integration vs E2E

- **Unit tests** — test one small piece (one function) in isolation. Fast.
- **Integration tests** — test a few pieces working together (like the API talking to the database). Slower.
- **End-to-end tests** — test the whole system from outside, like a user clicking through the UI. Slowest.

Mocking is when you replace something real (like a database call or external API) with a fake one for testing.

Mock when the real thing is slow, expensive, or you don't control it (like a payment service). Don't mock too much though — if you mock everything, your tests pass but the real system might still be broken because the mocks don't match reality. Also if you mock implementation details, your tests break every time you refactor even if the behavior didn't change.

## 10. Git: merge vs rebase

Both combine work from different branches but they do it differently.

**Merge** keeps the full history. It creates a merge commit that ties the two branches together. Honest about how the work happened but the history can look messy.

**Rebase** rewrites history. It takes your commits and replays them on top of the other branch, like you started from the latest version. Cleaner linear history but you lose the "this was a parallel branch" info.

Use merge when working on a shared branch — never rewrite history that other people are using. Use rebase when cleaning up your own local commits before pushing, or when you want a clean linear history.

Golden rule: never rebase commits that have already been pushed and shared with others.

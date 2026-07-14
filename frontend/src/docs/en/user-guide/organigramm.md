# Org Chart

The org chart shows your company's employee hierarchy as an expandable tree. Each employee appears as a card, nested under their manager, so you can see at a glance who reports to whom. The tree is built entirely from the already-synced Personio data.

## Access

Open the org chart from the **HR-Dashboard** tile in the launcher. That tile opens the HR area; from there choose the **Org Chart** tile (route `/hr/organigramm`). Above the tree, a line shows the number of active employees (e.g. "48 active employees").

## Reading and using the tree

- **Roots** — At the very top are the employees with no known supervisor, i.e. no manager recorded in Personio. They form the starting points of the tree. (Employees whose supervisor is not part of the active dataset are treated as roots too.)
- **Expand / collapse** — When an employee has people reporting to them, an arrow appears to the left of the card. Click it to open the branch (arrow pointing down) or close it (arrow pointing right). All branches are expanded when the page first loads.
- **Card contents** — Each card shows the full **name**, and below it — when recorded in Personio — the **position** and the **department**. If the name is missing, the employee ID is shown instead.
- **Ordering** — Employees at the same level are sorted alphabetically by name.

The reporting relationship comes from each employee's supervisor field maintained in Personio.

## Data source

The org chart reads only the already-synced Personio employee data from the database — there is no live call to Personio. Only **active** employees are shown. When the organization changes in Personio, those changes appear only after the next sync.

If no tree appears or the structure looks out of date, the Personio sync is usually the cause. Administrators can find how to set up and trigger the sync in the [Personio admin guide](/docs/admin-guide/personio).

## Related articles

- [HR Dashboard](/docs/user-guide/hr-dashboard) — HR KPIs sourced from Personio.

# JobTracker Status Navigation and Table Sorting — Plan v2.0

Derived from `jobtracker-status-navigation-sorting-brief-v1.0.md` (all open questions
resolved — see brief §3/§4/§6/§7 for the Title Case decision). One increment, no
milestones needed: backend enum addition + a frontend nav/filter/sort/label rework.

---

## Step 1: Backend — add the Duplicate status

- [ ] `backend/jobtracker/models.py`: add `DUPLICATE = "duplicate"` to the `Status` enum, after `FILLED`. Leave `ACTIVE_STATUSES` unchanged (so `is_active` derives to `False` for it automatically).
- [ ] No other backend file changes — `EDITABLE_FIELDS` and `_handle_update`'s `Status(fields["status"])` already accept any enum member.

## Step 2: Frontend — shared status list and label map

- [ ] `frontend/app.js`: extend `STATUSES` to `["new", "reviewed", "accepted", "applied", "interviewing", "rejected", "filled", "duplicate"]` (same order as the backend enum).
- [ ] `frontend/app.js`: add
  ```js
  const STATUS_LABELS = {
    new: "New", reviewed: "Reviewed", accepted: "Accepted", applied: "Applied",
    interviewing: "Interviewing", rejected: "Rejected", filled: "Filled", duplicate: "Duplicate",
  };
  const statusLabel = (status) => STATUS_LABELS[status] || status;
  ```
- [ ] `frontend/app.js`: add `const ACTIVE_STATUS_VALUES = ["new", "reviewed", "accepted", "applied", "interviewing"];` — used by the view-filtering logic in Step 6, mirrors the backend's `ACTIVE_STATUSES`.

## Step 3: Frontend — inline row status dropdown uses Title Case labels

- [ ] `renderJobs()` in `app.js`: change `opt.textContent = status;` to `opt.textContent = statusLabel(status);`. `opt.value` stays the raw lowercase `status` — no change there.

## Step 4: Frontend — Add/Edit modal dropdown becomes JS-populated

- [ ] `frontend/index.html`: remove the hardcoded `<option>` list inside `<select name="status">` in the job modal; leave the empty `<select>` element in place.
- [ ] `frontend/app.js`: once at module load (alongside the other top-level setup, before `init()` runs), populate that select from `STATUSES`/`STATUS_LABELS` the same way `renderJobs()` builds the inline dropdown — `value` = lowercase status, `textContent` = `statusLabel(status)`. Options are static (don't vary per job), so build them once, not on every modal open.
- [ ] `openEditModal()` and `openAddModal()` need no change — `form.status.value = job.status || "new"` and `form.reset()` both operate by `value`, unaffected by label text.

## Step 5: Frontend — seven navigation controls

- [ ] `frontend/index.html`: replace the two `.tab-btn` buttons with seven, using `data-view` (rename from `data-tab` — matches the `currentView` rename in Step 6) and Title Case text:
  ```html
  <button data-view="active" class="tab-btn ...">Active</button>
  <button data-view="new" class="tab-btn ...">New</button>
  <button data-view="reviewed" class="tab-btn ...">Reviewed</button>
  <button data-view="accepted" class="tab-btn ...">Accepted</button>
  <button data-view="applied" class="tab-btn ...">Applied</button>
  <button data-view="interviewing" class="tab-btn ...">Interviewing</button>
  <button data-view="inactive" class="tab-btn ...">Inactive</button>
  ```
- [ ] Add Tailwind's `flex-wrap` utility to the containing `<div class="flex gap-2 mb-4">` so seven buttons wrap on narrow screens without extra CSS.

## Step 6: Frontend — view state, fetch, and filter logic

- [ ] `frontend/app.js`: rename `currentTab` → `currentView`; rename `setTab(tab)` → `setView(view)`, updating the `data-tab` reference to `data-view` and the button-listener wiring accordingly.
- [ ] `loadJobs()`:
  - Fetch param: `active=false` when `currentView === "inactive"`, otherwise `active=true` (covers both the `active` umbrella view and each of the five specific-status views, since those are all subsets of the active set).
  - After fetching, if `currentView` is one of `ACTIVE_STATUS_VALUES`, filter the response to `job.status === currentView` before rendering; otherwise (`active` or `inactive`) render the full fetched set.
  - Sort the (possibly filtered) array per Step 7 before calling `renderJobs()`.
- [ ] `showDashboard()`: change `setTab("active")` → `setView("active")`.
- [ ] No change needed to `updateStatus()` — it already calls `loadJobs()` after the `PUT`, which re-fetches and re-filters against the current view, so a job that no longer belongs disappears automatically (verify this behaviorally in Step 9, don't add extra code for it).

## Step 7: Frontend — sorting

- [ ] `frontend/index.html`: turn the Company and Found `<th>` cells into sort buttons. Put `aria-sort` on the `<th>` itself (not the button) reflecting that column's current state — `"ascending"`, `"descending"`, or `"none"` when it isn't the active sort column:
  ```html
  <th class="px-4 py-3 font-medium" aria-sort="none">
    <button type="button" class="sort-btn" data-sort="company_name">Company <span class="sort-indicator"></span></button>
  </th>
  ```
  same pattern for Found with `data-sort="date_found"` and its own `aria-sort`. Leave the other five headers as plain text (no `aria-sort`).
- [ ] `frontend/app.js`: module-level state, defaulting to the brief's required default:
  ```js
  let sortColumn = "date_found";
  let sortDirection = "desc"; // newest first
  ```
- [ ] Click handler on both sort buttons: if the clicked column is already `sortColumn`, flip `sortDirection`; otherwise switch `sortColumn` to the clicked column and reset `sortDirection` to that column's first-click direction (`"asc"` for `company_name`, `"desc"` for `date_found`). Then call `loadJobs()` again — sorting stays a pure re-fetch-and-render pass through the existing `loadJobs()` path (Step 6) rather than a separate cached-array code path, so there's only one place that fetches+filters+sorts+renders.
- [ ] `sortJobs(jobs)` helper, called from `loadJobs()` right before `renderJobs()`:
  - Copy with `jobs.slice()` first — never sort the array `apiFetch` returned in place.
  - `company_name`: `a.company_name.localeCompare(b.company_name, undefined, { sensitivity: "base" })`, negated when `sortDirection === "desc"`.
  - `date_found`: parse both sides with `Date.parse(...)` (or `new Date(...).getTime()`). Treat `NaN` (blank or unparsable) as **always sorting after every valid date, in both directions** — this needs an explicit branch in the comparator (e.g. push `NaN` values to `+Infinity` before comparing, but do *not* let the general `desc` negation flip that placement — swapping to `desc` should still put invalid dates last, only reordering the valid ones).
- [ ] `updateSortHeaderUI()`, called after every sort/render: on the active sort column, set the `<th>`'s `aria-sort` to `"ascending"`/`"descending"`, set the `.sort-indicator` span's text to `▲`/`▼` (decorative — no `aria-label` on the span), and set `aria-label` on the `<button>` itself to something like `Sort by Company, ascending`. On the inactive sort header, reset the `<th>`'s `aria-sort` to `"none"`, clear the indicator span's text, and reset the button's `aria-label` to a neutral `Sort by Found`.

## Step 8: Frontend — styling

- [ ] `frontend/styles.css`: add a `.sort-btn` rule — transparent background, inherit the header's font/color, `cursor: pointer`, visible `:focus-visible` outline (keyboard accessibility, brief §8 explicitly checks this). Add minor spacing for `.sort-indicator`.
- [ ] No changes needed to `.tab-btn`/`.tab-btn.active` — reused as-is per the brief.

## Step 9: Deploy and verify end-to-end

Backend and frontend both need a real deploy since this is a live AWS app (see `jobtracker-status.md` for the exact commands) — local-only testing won't cover the deployed Lambda's status validation.

- [ ] `cd infra && sam build --use-container` (Step 1's enum change requires a fresh build — do this before `sam deploy`, per the "gotcha" already noted in `jobtracker-status.md`).
- [ ] `sam deploy` with the existing parameter set (see `jobtracker-status.md` for the full command). `SessionSecret` is preserved automatically since it's omitted from `--parameter-overrides`; the Gmail/OpenAI parameters are re-passed from `.env` each time, per that same documented command.
- [ ] `aws s3 sync frontend/ s3://jobtracker-frontend-<AWS_ACCOUNT_ID>/ --delete --profile jobtracker`.
- [ ] Walk the brief's §7 Acceptance Criteria and §8 Verification Checklist against `https://jobtracker.ashleycjones.com`:
  - Create/update jobs covering all eight statuses; confirm Active/each specific view/Inactive membership.
  - Move a job into and out of Duplicate via both the inline dropdown and the edit modal.
  - Sort by Company (mixed case, duplicate names) and by Found (missing/invalid dates, if any exist in the live table) in both directions; switch views mid-sort and confirm it persists.
  - Confirm Title Case labels in all three locations (nav, inline dropdown, modal dropdown) while the network tab / DynamoDB item still show lowercase values.
  - Check narrow-width layout and keyboard focus/activation on nav and sort controls, including that `aria-sort`/`aria-label` update correctly as the sort state changes (e.g. via a screen reader or the browser accessibility tree inspector).
  - **Note for whoever runs this manually or via browser automation**: the modal's Delete button uses a native `confirm()` dialog — avoid triggering it during automated testing (per the existing note in `jobtracker-status.md`); clean up any test rows directly via DynamoDB instead.

## Step 10: Close out

- [ ] Add a short entry to `jobtracker-status.md` documenting this increment once deployed and verified (per the project's usual practice of a status-doc note at the end of a unit of work).
- [ ] Leave the brief and this plan in `requirements/` (not `requirements/archive/`) until verification is complete; move both into the archive together once done, matching how `jobtracker-brief.md`/`jobtracker-plan.md` were archived.

---

## Addendum — Sortable Column Discoverability

Found after deploying and testing Steps 1–9: nothing signaled that Company and Found were
sortable until you actually clicked one. This addendum tightens Step 7/8's sort-header
behavior; everything else in the plan is unchanged and already implemented.

Make it visually apparent that Company and Found are sortable before the user interacts with them.

- Display a muted `↕` indicator beside every sortable column that is not currently selected.
- Display `↑` when the column is sorted ascending.
- Display `↓` when the column is sorted descending.
- On initial load, Company should display `↕` and Found should display `↓`, because Found defaults to newest-first.
- Retain the pointer cursor and add a subtle hover-state color change to both sortable headers.
- Do not display sorting indicators on any other column.
- Preserve the existing `aria-sort` behavior on the `<th>` elements and accessible labels on the sort buttons.
- When the selected sort changes, update both headers immediately so the newly selected column shows its direction and the previously selected column returns to `↕`.

### Implementation notes (maps onto the existing Step 7/8 structure)

- `frontend/index.html`: the two sort `<th>`s already exist from Step 7 (`data-sort="company_name"` / `data-sort="date_found"`, each with a `.sort-indicator` span). Update their initial static content to match the new default state: Company's span starts as `↕`, Found's span starts as `↓` (replacing the current `▲`/`▼` glyph set — this addendum switches the indicator characters from `▲`/`▼` to `↑`/`↓`/`↕`, it doesn't add new elements).
- `frontend/app.js` `updateSortHeaderUI()`: currently sets the indicator to `▲`/`▼` on the active column and clears it (`""`) on the inactive one. Change to: active column → `↑` (ascending) or `↓` (descending); inactive sortable column → `↕`. Logic/branching structure (active vs. inactive column, `aria-sort`/`aria-label` handling) is otherwise unchanged from Step 7 — this only changes what gets written into `.sort-indicator` and adds the "not selected" case a value instead of leaving it blank.
- `frontend/styles.css`: `.sort-indicator` needs a muted color at rest (e.g. a lighter slate than the header text) so `↕` reads as a hint rather than active state; the active `↑`/`↓` should use the header's normal text color (or a slightly stronger one) so it's visually distinct from the muted resting state. Add a `:hover` rule on `.sort-btn` with a subtle color shift (e.g. darkening toward `.tab-btn.active`'s background color) — `.sort-btn:focus-visible` from Step 8 stays as-is.

### Verification

- [ ] On initial dashboard load (before any click), confirm Company shows `↕` and Found shows `↓`.
- [ ] Click Company: Company shows `↑`, Found reverts to `↕`. Click again: Company shows `↓`.
- [ ] Click Found: Found shows the correct direction, Company reverts to `↕`.
- [ ] Confirm `aria-sort` on both `<th>`s and `aria-label` on both buttons still update exactly as before (unaffected by the glyph change).
- [ ] Confirm hover state is visible via mouse and that both headers remain reachable/activatable by keyboard (Tab + Enter/Space).
- [ ] Confirm no indicator or `aria-sort` appears on any non-sortable header (Role, Status, Link, Posted, Source).

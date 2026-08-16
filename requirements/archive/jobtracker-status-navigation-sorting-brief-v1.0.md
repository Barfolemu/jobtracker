# JobTracker Status Navigation and Table Sorting Brief

**Brief ID:** JT-STATUS-NAV-SORT  
**Version:** 1.0  
**Date:** August 16, 2026  
**Source reviewed:** `jobtracker-clean.zip`

## 1. Objective

Make the dashboard easier to navigate when it contains many jobs by:

1. Adding a top-level view for every active job status while retaining an **Active** view that shows all active jobs.
2. Keeping all inactive statuses together in one **Inactive** view.
3. Adding a new inactive status named **Duplicate**.
4. Allowing users to sort the table by **Company** or **Found** date.

## 2. Current Implementation

- The dashboard currently has two tabs: **Active** and **Non-Active**.
- The API supports `GET /api/jobs?active=true|false` and returns the complete active or inactive group.
- Active statuses are `new`, `reviewed`, `accepted`, `applied`, and `interviewing`.
- Inactive statuses are `rejected` and `filled`.
- Status values are defined independently in:
  - `backend/jobtracker/models.py`
  - `frontend/app.js`
  - the status `<select>` in `frontend/index.html`
- The table is rendered in `frontend/app.js`; no column sorting currently exists.

## 3. Required Navigation

Display these controls across the top of the dashboard in this order:

1. **Active**
2. **New**
3. **Reviewed**
4. **Accepted**
5. **Applied**
6. **Interviewing**
7. **Inactive**

Behavior:

- **Active** remains the default view and displays every job in any active status.
- Each active-status control displays only jobs with that exact status.
- **Inactive** is one combined view containing `rejected`, `filled`, and `duplicate` jobs.
- Do not create individual top-level controls for Rejected, Filled, or Duplicate.
- Use Title Case for every visible status label — navigation tabs, the inline row status dropdown, and the Add/Edit modal status dropdown — while retaining lowercase status values in data, `<option>` values, and API payloads. Use a single shared label map (e.g. `STATUS_LABELS`) so the casing logic isn't duplicated across the three render points.
- The controls may wrap cleanly on smaller screens; they must remain usable without overlapping the table or Add Job button.
- When a job's status is changed from the table, reload the current view. If the job no longer belongs in that view, it should disappear immediately.

## 4. Duplicate Status

Add the data value `duplicate` as a valid status.

- Add `DUPLICATE = "duplicate"` to the backend `Status` enum.
- Do not add Duplicate to `ACTIVE_STATUSES`; its derived `is_active` value must be `false`.
- Add `duplicate` to the frontend status list and the Add/Edit modal's status dropdown. Its visible label ("Duplicate") follows the same Title Case rule as every other status (see Section 3).
- Existing records require no migration. Their stored statuses and `is_active` values remain unchanged.
- A job changed to Duplicate must be returned by `GET /api/jobs?active=false` and not by `GET /api/jobs?active=true`.

## 5. Sorting

Only the **Company** and **Found** column headers are sortable.

### Company

- First click sorts A to Z.
- Second click sorts Z to A.
- Compare company names case-insensitively using locale-aware string comparison.

### Found

- Default dashboard order should be newest Found date first.
- Clicking Found toggles between newest-to-oldest and oldest-to-newest.
- Compare parsed `date_found` timestamps, not the formatted `YYYY-MM-DD` display string.
- Missing or invalid Found dates sort after valid dates in either direction.

### Sorting UI and State

- Make only the Company and Found headers look and behave like buttons.
- Show the active direction beside the selected header, using an accessible text/icon treatment such as `▲` and `▼` with an `aria-label` that states the current sort.
- Keep the selected sort and direction when switching among status views during the current page session.
- Sorting happens in the browser after the selected jobs are loaded; no API sorting parameter is needed for this increment.

## 6. Recommended Implementation

Keep this as a small frontend filtering/sorting change plus the backend enum addition.

### `backend/jobtracker/models.py`

- Add `Status.DUPLICATE`.
- Leave `ACTIVE_STATUSES` unchanged.

### `frontend/index.html`

- Replace the current two-tab markup with the seven controls in Section 3, labeled in Title Case ("Active", "New", "Reviewed", "Accepted", "Applied", "Interviewing", "Inactive").
- Rename the existing **Non-Active** label to **Inactive**.
- Convert Company and Found headers into accessible sort controls.
- Remove the modal's hardcoded status `<option>` list; populate it from JS instead (see `app.js`) so label casing lives in one place, not two.

### `frontend/app.js`

- Add `duplicate` to `STATUSES`.
- Add a `STATUS_LABELS` map (lowercase value → Title Case display label) and use it to render option text for both the inline row status dropdown and the Add/Edit modal status dropdown — the `<option>` `value` stays the lowercase status value in both.
- Replace the binary `currentTab` assumption with a selected view that supports:
  - `active`
  - the five exact active status values
  - `inactive`
- For Active or a specific active-status view, load `/api/jobs?active=true`; for Inactive, load `/api/jobs?active=false`.
- When a specific status is selected, filter the active response by `job.status` before rendering.
- Track sort column and direction in module-level state.
- Sort a copied array before rendering so the fetched data is not mutated unexpectedly.
- Keep `renderJobs()` focused on rendering; use small helper functions for view filtering and sorting.

### `frontend/styles.css`

- Reuse the existing `.tab-btn` active styling.
- Add only the minimal styling needed for wrapping navigation and sortable headers/focus states.

### API and database

- No new route, query parameter, DynamoDB index, or data migration is required.
- Existing writes already recalculate and persist `is_active` from the selected status.

## 7. Acceptance Criteria

1. The default Active view shows New, Reviewed, Accepted, Applied, and Interviewing jobs together.
2. Each of the five active-status views shows only jobs with that exact status.
3. Inactive shows Rejected, Filled, and Duplicate jobs together.
4. No separate Rejected, Filled, or Duplicate navigation controls appear.
5. Duplicate is available in both inline and modal status selectors.
6. Changing an active job to Duplicate removes it from any active view and makes it appear under Inactive.
7. Changing a Duplicate job to an active status removes it from Inactive and makes it appear in Active and its specific status view.
8. Company toggles between case-insensitive A–Z and Z–A sorting.
9. Found toggles between newest-first and oldest-first sorting and handles ISO timestamps correctly.
10. The current sort remains applied when the user changes status views.
11. Only Company and Found appear sortable.
12. Empty filtered views display the existing empty-state message and do not show stale rows.
13. Existing login, Add Job, Edit Job, inline status change, link, and delete behavior continue to work.
14. Navigation remains readable and operable at narrow browser widths.
15. Every visible status label (nav tabs, inline row dropdown, Add/Edit modal dropdown) displays in Title Case; underlying values, `<option>` values, and API payloads remain lowercase.

## 8. Verification Checklist

- Create or update at least one job in each of the eight statuses.
- Verify the membership of Active, each specific active view, and Inactive.
- Move jobs between active, rejected, filled, and duplicate states using both the inline selector and edit modal.
- Test Company sorting with mixed capitalization and identical company names.
- Test Found sorting with full ISO timestamps, blank values, and invalid values if present.
- Switch views after choosing each sort direction and confirm the ordering persists.
- Confirm status changes remove a row from the current filtered view when appropriate.
- Check keyboard focus and activation for navigation and sort controls.
- Check the dashboard at desktop and mobile/narrow widths.
- Confirm status labels render in Title Case in the nav, inline dropdown, and modal dropdown, and confirm (via network tab or DB) that stored/sent values stay lowercase.

## 9. Out of Scope

- Separate inactive-status views.
- Sorting any column other than Company and Found.
- Server-side sorting or pagination.
- Job counts on navigation controls.
- URL-based persistence of the selected view or sort.
- Automatic duplicate detection; this increment only introduces the status needed for that later feature.


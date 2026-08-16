# AWS Job Search Tracker & Discovery Engine — System Specification

## 1. Overview & Objective
Build a lightweight, single-user Job Search Application hosted in AWS that continuously tracks job opportunities and applications. The system must run 24/7 independently of local desktop availability, collect job alerts from Gmail, support manual entries, and provide a secure, single-user Web UI for pipeline management.

---

## 2. Recommended AWS Architecture & Low-Cost Tech Stack

To meet the requirement of running 24/7 in AWS at minimal/near-zero cost, use a **Serverless Architecture**:

* **Backend / API:** AWS Lambda (Python 3.12 or Node.js) exposed via **API Gateway (HTTP API)** or Lambda Function URLs.
* **Scheduled Background Jobs:** **AWS EventBridge Scheduler** triggering Lambda functions on a cron (e.g., every 30-60 minutes) to perform Gmail scanning.
* **Frontend UI:** Single Page Application (React / Vite or Vanilla JS/HTML) hosted on **Amazon S3** behind **Amazon CloudFront** (or AWS Amplify Hosting).
* **Database / Storage:** **Amazon DynamoDB** (Single-Table Design). *Cost: Always-Free Tier eligible (up to 25 WCU/RCU and 25 GB storage free).*
* **Authentication:** Simple API Key / Password Session Token stored in HTTP-Only Cookies or standard Basic Auth / AWS Cognito HTTP API Authorizer. (No user registration/signup screens required).

---

## 3. Data Schema Specification

### Data Model: `JobItem` (DynamoDB / JSON Storage)

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `job_id` | String (PK) | Unique identifier (e.g., `linkedin:1234567890` or `manual:guid-v4`) |
| `company_name` | String | Extracted company name or manual entry |
| `role_title` | String | Extracted or entered job title |
| `status` | String | Enum: `new`, `reviewed`, `accepted`, `applied`, `interviewing`, `rejected`, `filled` |
| `job_url` | String | Link to the original job listing |
| `found_by` | String | Finder/Source identifier (`linkedin_gmail`, `manual`, `indeed_gmail`) |
| `date_found` | String (ISO) | Timestamp when the system recorded the job |
| `date_posted` | String (ISO / Opt) | Date posted (if parseable from email/link; optional) |
| `job_description` | String (Text) | Full text pasted or scraped job description |
| `notes` | String (Text) | Personal notes on the opportunity |
| `is_active` | Boolean | Helper flag derived from status (`true` for active, `false` for non-active) |

---

## 4. Ingestion Agents Specification

### 4.1 LinkedIn Gmail Discovery Agent
* **Trigger:** Scheduled AWS Lambda (via EventBridge cron every 60 minutes).
* **Integration:** Gmail API (using OAuth2 credentials with `gmail.readonly` scope stored in AWS Secrets Manager / Parameter Store).
* **Query Filter:** `from:jobalerts-noreply@linkedin.com` or `subject:"job alert"` (Unread or recent messages).
* **Extraction Logic:**
  1. Parse HTML/Text body of emails.
  2. Extract embedded job URLs containing LinkedIn Job IDs (e.g., `linkedin.com/jobs/view/1234567890` or `linkedin.com/comm/jobs/view/1234567890`).
  3. Extract Job ID (`1234567890`).
  4. Deduplication Check: Look up `job_id = linkedin:1234567890` in the database. If it exists, skip.
  5. If new: Create record with:
     - `job_id`: `linkedin:<LINKEDIN_JOB_ID>`
     - `status`: `new`
     - `found_by`: `linkedin_gmail`
     - `date_found`: `Current ISO Timestamp`
     - `company_name` & `role_title`: Parse from email context if available, otherwise default to "Needs Review / Linked In Job".

### 4.2 Manual Entry Agent
* **Trigger:** Invoked via Web UI form ("Add Manual Job").
* **Logic:**
  1. Generate a standard UUID v4 string (e.g., `manual:550e8400-e29b-41d4-a716-446655440000`).
  2. Accept Company Name, Role Title, Job Link (optional), Status (defaults to `new`), Job Description, and Notes.
  3. Set `found_by`: `manual`.
  4. Save record to persistent storage.

### 4.3 Extensibility Note (Future Indeed Agent)
* Design the ingestion agent module using a clean Provider Interface (e.g., `BaseEmailDiscoveryAgent`) so an `IndeedEmailAgent` can be attached seamlessly later with custom regex parsers.

---

## 5. UI & State Machine Specification

### 5.1 State Taxonomy
* Active States
  * new(default)
  * reviewed
  * accepted
  * applied
  * interviewing
* Non-Active States
  * rejected
  * filled 

### 5.2 Main Page (Dashboard View)
* **Auth Requirement:** Simple Login modal / header prompt (Basic Auth or session cookie check).
* **View Toggles:** Switchable tabs between **Active Jobs** (Default) and **Non-Active Jobs**.
* **Table / Card Columns:**
  1. Company Name
  2. Role Title
  3. Status (Interactive dropdown to quickly switch states)
  4. Job Link (External hyperlink opening in new tab)
  5. Date Found
  6. Date Posted (Displays date or "N/A")
  7. Found By / Source Badge (`linkedin_gmail`, `manual`)
  8. Actions: **Edit Button**

### 5.3 Edit Screen / Detail Modal
* Modifiable fields:
  * Company Name & Role Title
  * Status (Dropdown of all 7 states)
  * Job Link
  * **Job Description (JD):** Multi-line textarea (supports raw copy/pasted text)
  * **Notes:** Multi-line textarea for personal application notes
* Action Buttons:
  * **Save Changes**
  * **Delete Position:** Hard delete with confirmation prompt

---

## 6. Claude Code Step-by-Step Task Execution Plan

### Step 1: Core Framework & Storage Setup
1. Setup a monorepo or standard folder structure with Infrastructure-as-Code (AWS CDK or Serverless Framework / SAM) or a deploy script using Python/Boto3.
2. Provision a DynamoDB Table `JobTrackerTable` with Partition Key `job_id` (String).
3. Create database client methods for `get_job`, `put_job`, `list_jobs(is_active)`, `update_job`, and `delete_job`.

### Step 2: Gmail API Integration & LinkedIn Parsing Logic
1. Implement Gmail OAuth2 credential retrieval script.
2. Implement regex parser for LinkedIn email links: `https://www\.linkedin\.com/(?:comm/)?jobs/view/(\d+)`.
3. Build deduplication check against DynamoDB before creating new records.
4. Setup an AWS Lambda function triggered by AWS EventBridge Scheduler.

### Step 3: Backend REST API (Lambda + API Gateway)
1. Build endpoints:
   - `GET /api/jobs?active=true|false` — Fetch active or inactive jobs.
   - `POST /api/jobs` — Manual job creation.
   - `PUT /api/jobs/{id}` — Edit fields/status.
   - `DELETE /api/jobs/{id}` — Permanent delete.
2. Implement simple token-based or HTTP Basic Auth header validation on all endpoints.

### Step 4: Frontend UI Development
1. Build a responsive, clean single-page UI (Tailwind CSS / HTML + JavaScript or React).
2. Implement Active vs Non-Active tabs.
3. Build the Edit Modal for JD editing, notes, status changing, and deletion.
4. Connect UI to API Gateway endpoints.

### Step 5: AWS Deployment & Verification
1. Deploy API, DynamoDB, and Lambda workers to AWS.
2. Upload Frontend static files to S3 + CloudFront (or AWS Amplify).
3. Verify Gmail scanning execution via CloudWatch Logs.
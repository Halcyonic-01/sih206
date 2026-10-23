# GitHub handover checklist

GitHub is the primary source handover. No ZIP, wheelhouse, old database or previous developer's environment is required. Share the repository URL; your teammate clones it and follows the root README.

## 1. Decide the repository destination

The owner selected [Saksham-189/sih206](https://github.com/Saksham-189/sih206) for source handover. Grant the teammate access if private. The first-upload commands below are reference instructions for a new checkout without Git history; incoming teammates should use section 5.

For a new local repository, create an empty GitHub repository without another README/gitignore/license that would conflict with the existing files. For a repository that already has history, coordinate the merge/import rather than force-pushing or overwriting its branch.

This workspace historically had no Git repository. Run git status to determine your current state before using the first-upload commands.

## 2. What belongs in GitHub?

| Commit | Keep local / ignored |
|---|---|
| README.md, docs/ and handover history/roadmap/testing guides | data/: SQLite, documents, passwords, sessions, backups and test-run outputs |
| config/, portal/, migrations and tests | .venv/, caches and old dist/ copies |
| templates/, static/ and synthetic fixtures/ PDFs | .env and .env.* secrets; only .env.example is shareable |
| evaluation/ synthetic labels and recorded public-safe results | Logs and private test records/screenshots containing credentials |
| scripts/, manage.py, root PowerShell wrappers | Generated wheelhouse, .whl, ZIP and checksum artifacts |
| requirements.in/txt, .gitignore, .env.example | Old local replay server/data and personal machine state |

Do not ignore all PDFs: the synthetic fixture PDFs are needed for tests and must be committed. Real uploaded PDFs belong under ignored data/. Review document/evaluation provenance before adding future datasets.

**Important:** .gitignore applies to Git staging, not GitHub's browser drag-and-drop uploader. Dragging the entire working directory into the browser can upload passwords/data despite .gitignore. Prefer the Git commands below. If you use browser upload, select only the commit paths in the table; never upload the whole root indiscriminately.

## 3. First upload from this project (owner runs these commands)

Open PowerShell in the folder containing manage.py. If git status already shows an existing repository, stop and follow that repository's agreed branch workflow instead of reinitializing.

For a genuinely new local repository:

```powershell
git --version
git init -b main
git add -- .gitignore .env.example README.md requirements.in requirements.txt manage.py config portal templates static fixtures evaluation scripts docs Setup-Offline.ps1 Start-Demo.ps1 Verify-Demo.ps1
git status --short
git diff --cached --name-only
git diff --cached --stat
```

Review the listed paths and actual changed content before the next commands. The explicit source list and .gitignore should exclude runtime data, but review remains necessary. Inspect any private test record, secret, dataset or attachment accidentally placed under a source directory; move private material outside versioned source before committing. Do not use git add -f to bypass ignore rules.

If you accidentally staged an unwanted file **before the first commit**, remove only its index entry using `git rm --cached -- 'PATH-TO-UNWANTED-FILE'`; this leaves the local file intact. If a secret was already committed, .gitignore does not remove it from history: remove it from tracking, rotate it if necessary and agree on history cleanup before publishing.

When the staged content is correct:

```powershell
git commit -m "Add FDR portal MVP and teammate documentation"
git remote add origin https://github.com/Saksham-189/sih206.git
git remote -v
git push -u origin main
```

If commit asks for identity, configure your own appropriate Git name/email, not the outgoing developer's identity. Authenticate with your normal GitHub credential manager. Do not put an access token in the remote URL, README or committed config.

If origin already exists, inspect it and use the real agreed remote; do not blindly replace it. If push is rejected because the remote already has commits, stop and integrate its history through the team's workflow. Do not force-push to hide the disagreement.

## 4. Verify the repository view

1. Open the actual GitHub repository after your push.
2. Confirm README renders, documentation links open, and source/tests/migrations/synthetic PDFs are present.
3. Confirm there is no data directory, .venv, .env secret file, cached wheelhouse, generated archive, credential file or private replay in the published tree.
4. Record the branch and commit you are handing over using git branch --show-current and git rev-parse HEAD.
5. Share the actual repository URL and invite the teammate if private.

Application localhost URLs are not deployed GitHub services. Uploading source does not start Django or provision a database.

## 5. Incoming teammate setup

1. Obtain the HTTPS clone URL from the repository's Code button.
2. Open PowerShell in the desired parent folder:

```powershell
git clone -- https://github.com/Saksham-189/sih206.git fdr-portal
Set-Location -LiteralPath .\fdr-portal
git rev-parse HEAD
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo --generate-password
.\.venv\Scripts\python.exe manage.py seed_demo --authority-only --generate-password
.\.venv\Scripts\python.exe manage.py seed_scenarios
.\Verify-Demo.ps1
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8010 --noreload
```

3. Visit localhost:8010 and read newly generated passwords privately from data/demo-credentials.txt and data/authority-credentials.txt.
4. Follow the beginner testing walkthrough. Record repository/branch/commit, machine and actual results, not an old ZIP checksum.
5. Keep a separate fresh clone for presentation. Do not copy .venv or database/passwords from another developer.

The first GitHub/dependency download requires Internet. App operation after setup uses local dependencies/assets. Prepare local wheels in advance for a physically disconnected fresh-install rehearsal as documented in the testing guide. Setup-Offline.ps1 is a separate optional bundle tool and is not the normal clone setup.

## 6. Daily collaboration

Agree on branch names/reviews and migration ownership. Before updates, inspect git status and safely preserve uncommitted work. Use git pull --ff-only when appropriate; if it refuses, resolve the branch situation instead of resetting/force-pushing.

After pulling changed requirements/migrations, deliberately install dependencies, back up necessary local data, migrate and run tests. Commit migrations and tests with their feature. Do not commit runtime databases or use Git as a shared mutable SQLite store.

Suggested responsibilities: requirements/evidence labels, application changes, verification/demo. A single incoming developer can do these sequentially.

## 7. Existing data is a separate private continuity question

A Git clone intentionally starts without the old mutable dataset. Generate synthetic scenarios locally. If continuity data is genuinely needed, agree separately on an authorized private backup of database and documents together after stopping the server. Credentials/sessions in a backup can be sensitive. Never add it to GitHub to make onboarding easier.

## 8. Thirty-minute handover meeting

| Minutes | Outgoing developer shows | Incoming teammate demonstrates |
|---|---|---|
| 0–5 | Scope and release boundaries | Acceptance versus bank verification |
| 5–10 | README, repo/commit and setup | Their own server and local login |
| 10–15 | Code map and one transaction | Relevant view/form/service/permission/test |
| 15–20 | Evidence and corrections | Why an edit does not resolve a blocking observation |
| 20–25 | Renewal and release | What stays/leaves current monitoring |
| 25–30 | Baseline, manual gates and next task | Acceptance test and source-control workflow |

## Transfer complete when

- [ ] Real repository URL/access and the handover commit are known.
- [ ] Only intended source/docs/tests/fixtures are published; local secrets/data are excluded.
- [ ] Teammate can clone, set up, seed, verify and run independently.
- [ ] Manual target-browser/offline checks and production blockers remain explicitly recorded.
- [ ] The next accepted task and review owner are clear.

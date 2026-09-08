# GitHub App for private source access

Use one narrowly scoped GitHub App to let the public website repository read
the two private source repositories named by `docs-manifest.yml`:

- `pydasc/dasc`
- `pydasc/pydasc`

Store the App credentials only in the protected `docs-sources` environment of
`pydasc/pydasc.github.io`. The App replaces
source deploy keys; it does not grant deployment or website-repository write
access.

This procedure applies while `docs-manifest.yml` names the repositories above.
If an authoritative source moves, review and update the lock separately before
changing the App installation. Repository presence or copying alone does not
authorize a source-location change.

## 1. Create the GitHub App

While signed in as an owner of the `pydasc` organization:

1. Open **Profile picture → Settings**.
2. Select **Developer settings → GitHub Apps**.
3. Select **New GitHub App**.
4. Configure:
   - **GitHub App name:** for example `dasc Documentation Reader`
   - **Homepage URL:** `https://pydasc.github.io/`
   - **Webhook:** clear **Active**
   - **Repository permissions → Contents:** **Read-only**
   - Leave every other repository and organization permission at **No access**
   - **Where can this GitHub App be installed?** Select **Only on this account**
5. Select **Create GitHub App**.

Create the App under the `pydasc` organization, not a personal account, so it
can be installed on both locked organization repositories.

## 2. Record the Client ID

On the App's **General** page, record the **Client ID**, not the numeric App ID.
It will be stored as this Actions secret:

```text
DASC_DOCS_APP_CLIENT_ID
```

## 3. Generate the private key

On the same App configuration page:

1. Scroll to **Private keys**.
2. Select **Generate a private key**.
3. GitHub downloads a `.pem` file.
4. Keep the file private and never add it to a repository or build artifact.

The secret must contain the complete downloaded file, including its `BEGIN`
and `END` lines. Do not print the key in a terminal, workflow log, or generated
page.

## 4. Install the App on the two private sources

From the App configuration page:

1. Select **Install App**.
2. Select **Install** beside the `pydasc` organization.
3. Choose **Only select repositories**.
4. Select only:
   - `pydasc/dasc`
   - `pydasc/pydasc`
5. Complete the installation.

Do not install the App on every repository. Read-only Contents access to these
two sources is sufficient.

## 5. Protect source access and add environment secrets

Open:

**pydasc/pydasc.github.io → Settings → Environments → docs-sources**

Create this environment before putting any credentials in it:

1. Under **Deployment branches and tags**, choose **Selected branches and tags**.
2. Allow only the exact branch `main`. Do not allow tags (including a tag named
   `main`), wildcard branches, or pull-request refs.
3. Enable **Required reviewers** and choose trusted private-source maintainers.
   The initial reviewer is `chongshikpark`. Self-review remains permitted so the
   maintainer can approve their own releases; other website writers cannot approve.
4. Review the exact commit, workflow, dependency changes, and executed scripts
   before approving a job. Do not approve a run solely because its branch is main.
   Main currently has no branch protection, so reviewer approval is essential.
   Also protect main against unreviewed changes as part of repository governance.
5. Add these **Environment secrets**:

| Name | Value |
| --- | --- |
| `DASC_DOCS_APP_CLIENT_ID` | GitHub App Client ID |
| `DASC_DOCS_APP_PRIVATE_KEY` | Complete contents of the downloaded `.pem` file |

All three source-reading jobs reference `docs-sources`; `github-pages` remains
the separate final-deployment environment. Scheduled updates and main-branch
builds now wait for source-access approval before starting. Approve each job
only after checking its commit. Administrators must not bypass these protections.

### Migrate existing repository secrets

GitHub cannot retrieve or copy stored secret values. Re-enter the App Client ID
and original private-key file directly in the protected environment, or generate
a replacement App key. Do not expose credentials through logs, artifacts, chat,
or a temporary workflow. Then remove the repository-level copies of both secrets
and the unused `DASC_DOCS_APP_ID`. Remove any organization-level copies accessible
to this website repository as well. Leaving a broader-scope private key available
defeats the environment restriction, even if current workflow conditions look safe.

Coordinate the cutover with the user-controlled commit/push of these workflow
changes: the older workflows cannot use environment-only credentials. Do not
remove the old copies until the environment credentials have been populated,
but do not consider the security migration complete while old copies remain.
After cutover, rotate the App private key if earlier access cannot be trusted.

Verify only their presence, without revealing values:

```bash
gh secret list --repo pydasc/pydasc.github.io --env docs-sources
gh secret list --repo pydasc/pydasc.github.io
```

The environment list should contain the following; the repository list must
not contain any `DASC_DOCS_APP_*` secret:

```text
DASC_DOCS_APP_CLIENT_ID
DASC_DOCS_APP_PRIVATE_KEY
```

## 6. Workflow implementation

Each source-reading job is gated by `environment: docs-sources` and an explicit
main-ref event condition. It mints a short-lived App installation token before
fetching private source content:

- `.github/workflows/docs-check.yml`: `source-docs`, after the unprivileged
  `docs` tests pass, on main pushes only.
- `.github/workflows/deploy-pages.yml`: `build`, on main pushes or manual runs.
- `.github/workflows/update-source-locks.yml`: `propose`, on main scheduled or
  manual runs.

The conditions are defense in depth, not the credential boundary: a branch
writer can edit workflow YAML. The GitHub environment rules and absence of
broader-scope credential copies enforce the boundary outside branch-controlled
code. Manual runs on non-main refs are skipped by the checked-in workflows and
are denied environment access even if a branch removes those conditions.

The token step is SHA-pinned and explicitly requests only Contents read access:

```yaml
- name: Create source-read installation token
  id: source_token
  uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1 # v3.2.0
  with:
    client-id: ${{ secrets.DASC_DOCS_APP_CLIENT_ID }}
    private-key: ${{ secrets.DASC_DOCS_APP_PRIVATE_KEY }}
    owner: pydasc
    repositories: |
      dasc
      pydasc
    permission-contents: read
```

The workflows pass `steps.source-token.outputs.token` only through a masked
environment variable, construct and explicitly mask an HTTP authorization header
for the individual Git commands, disable credential helpers and source hooks,
and fetch exact reviewed commits without persisting the token. Do not print the
token or include it in an artifact.

The `docs` job runs repository tests and validates the website manifest for all
pull requests without referencing any environment or App secrets. It does not
fetch private sources. The separate `source-docs` job runs the complete site
pipeline only for approved main pushes. Repository writers can access ordinary
repository secrets through modified workflows, which is why the App private key
must exist only in the protected environment.

The workflow's `GITHUB_TOKEN` permissions do not provide cross-repository
private-source access. The short-lived App installation token supplies only the
separately granted read access.

## 7. Verify in GitHub Actions

After the reviewed workflow conversion is committed and pushed:

1. Verify `docs-sources` still has the exact main branch rule and required reviewer,
   and that no repository/organization-level App credentials remain accessible.
2. Confirm PR checks complete without environment approval or private sources.
3. Confirm source-reading jobs wait for approval; review the exact commit before
   approving. Confirm token creation and the locked checkouts succeed without
   exposing credentials.
4. Confirm the strict build, site validators, and artifact scans pass.
5. Confirm **Deploy documentation to Pages** deploys the validated artifact, and
   manually run **Propose documentation source updates** on main to verify it too.
6. Confirm the signed-out site at <https://pydasc.github.io/> shows the
   expected MkDocs site.

Review the App installation and rotate its private key periodically. Remove an
obsolete private key only after workflows using its replacement pass.

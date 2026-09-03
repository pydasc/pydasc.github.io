# GitHub App for private source access

Use one narrowly scoped GitHub App to let the public website repository read
the two private source repositories named by `docs-manifest.yml`:

- `pydasc/dasc`
- `pydasc/pydasc`

Store the App credentials in `pydasc/pydasc.github.io`. The App replaces
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

## 5. Add the website repository secrets

Open:

**pydasc/pydasc.github.io → Settings → Secrets and variables → Actions**

Create these repository secrets:

| Name | Value |
| --- | --- |
| `DASC_DOCS_APP_CLIENT_ID` | GitHub App Client ID |
| `DASC_DOCS_APP_PRIVATE_KEY` | Complete contents of the downloaded `.pem` file |

Use repository secrets rather than `github-pages` environment secrets because
the pull-request validation, Pages build, and source-update validation jobs all
need source read access. GitHub will not display the values again.

Verify only their presence, without revealing values:

```bash
gh secret list --repo pydasc/pydasc.github.io
```

The output should list:

```text
DASC_DOCS_APP_CLIENT_ID
DASC_DOCS_APP_PRIVATE_KEY
```

## 6. Workflow implementation

Each source-reading job in the following workflows mints a short-lived App
installation token before fetching private source content:

- `.github/workflows/docs-check.yml`
- `.github/workflows/deploy-pages.yml`
- `.github/workflows/update-source-locks.yml`

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
environment variable, construct an HTTP authorization header for the individual
Git commands, disable credential helpers and source hooks, and fetch exact
reviewed commits without persisting the token. Do not print the token or include
it in an artifact.

Fork-originated pull requests do not receive repository secrets. The
documentation-check workflow therefore runs its repository tests and validates
the manifest for those pull requests, but skips private-source retrieval and the
complete rendered-site pipeline. Pushes and same-repository pull requests run
the full checks.

The workflow's `GITHUB_TOKEN` permissions do not provide cross-repository
private-source access. The short-lived App installation token supplies only the
separately granted read access.

## 7. Verify in GitHub Actions

After the reviewed workflow conversion is committed and pushed:

1. Confirm the source-token step succeeds without exposing credentials.
2. Confirm both exact locked source checkouts succeed.
3. Confirm the runner credential scan succeeds.
4. Confirm **Site validation / Validate public artifact** passes.
5. Confirm **Deploy GitHub Pages** builds and deploys the validated artifact.
6. Confirm the signed-out site at <https://pydasc.github.io/> shows the
   expected MkDocs site.

Review the App installation and rotate its private key periodically. Remove an
obsolete private key only after workflows using its replacement pass.

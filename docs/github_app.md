Create one GitHub App, install it on the two private source repositories,
  then store its credentials in the public website repository.

  ### 1. Create the GitHub App

  While signed in to GitHub:

  1. Open Profile picture → Settings.
  2. Select Developer settings → GitHub Apps.
  3. Click New GitHub App.
  4. Configure:
      - GitHub App name: for example DASC Documentation Reader
      - Homepage URL: https://pydasc.github.io/
      - Webhook: uncheck Active
      - Repository permissions → Contents: Read-only
      - Leave all other repository and organization permissions at No access
      - Where can this GitHub App be installed? Select Only on this account

  5. Click Create GitHub App.

  GitHub’s instructions: Registering a GitHub App.

  ### 2. Record the App ID

  On the newly created App’s General page, find App ID.

  Use the numeric App ID, not the Client ID.

  You will store this value as:

  DASC_DOCS_APP_ID 4805844

  ### 3. Generate the private key

  On the same App configuration page:

  1. Scroll to Private keys.
  2. Click Generate a private key.
  3. GitHub will download a .pem file.
  4. Keep this file private. Do not add it to any repository.

  The secret value must include the complete file:

  -----BEGIN RSA PRIVATE KEY-----
  ...
  -----END RSA PRIVATE KEY-----

  GitHub’s instructions: Managing private keys for GitHub Apps.

  ### 4. Install the App on both private repositories

  From the GitHub App configuration page:

  1. Select Install App from the left sidebar.
  2. Click Install beside your account.
  3. Choose Only select repositories.
  4. Select:
      - pydasc/pydasc
      - pydasc/dasc

  5. Click Install.

  Do not install it on every repository. The App needs only read access to
  those two sources.

  GitHub’s instructions: Installing your own GitHub App.

  ### 5. Add the repository secrets

  Open:

  pydasc/pydasc.github.io → Settings → Secrets and variables → Actions

  Under Repository secrets, click New repository secret and create both
  secrets.

  First secret:

  Name: DASC_DOCS_APP_ID
  Secret: 4805844

  Second secret:

  Name: DASC_DOCS_APP_PRIVATE_KEY
  Secret: <complete contents of the downloaded .pem file>

  Paste the complete private key, including the BEGIN and END lines.

  Add these as repository secrets, not github-pages environment secrets,
  because both the documentation-check job and deployment build job require
  them.

  GitHub’s instructions: Using secrets in GitHub Actions.

  ### 6. Verify the names

  After adding them, the Actions secrets page should list:

  DASC_DOCS_APP_ID
  DASC_DOCS_APP_PRIVATE_KEY

  GitHub will not display their values again.

  You can also verify their presence without revealing values:

  gh secret list --repo pydasc/pydasc.github.io

  ### 7. Deploy

  The workflow changes still need to be committed and pushed by you. After
  pushing, check that:

  1. Documentation checks passes.
  2. Deploy documentation to Pages passes.
  3. The generic Deploy static content to Pages workflow no longer exists.
  4. The website root displays the MkDocs homepage rather than a 404 or
     README.

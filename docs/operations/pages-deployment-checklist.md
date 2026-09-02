# GitHub Pages deployment administrator checklist

This checklist contains manual actions outside the repository. Do not perform
them until the complete public artifact and the first deployment are explicitly
authorized.

## Before the first deployment

- [ ] Confirm Task 7 succeeds on the proposed default-branch commit, including
      anonymous retrieval of both source locks.
- [ ] Inspect the locally built `site/` tree and confirm it contains only the
      approved public portal and imported documents.
- [ ] In **Settings → Pages → Build and deployment**, set **Source** to
      **GitHub Actions**. The workflow itself has `enablement: false` and will not
      enable Pages.
- [ ] In **Settings → Environments → github-pages**, require designated reviewer
      approval before deployment and restrict deployment to the protected default
      branch as repository policy permits.
- [ ] Protect the default branch: require pull requests, the documentation check,
      current approvals, resolved conversations, and protection against force
      pushes and deletion.
- [ ] Confirm the workflow permissions are exactly `contents: read`,
      `pages: write`, and `id-token: write`, and that no deployment secret or PAT
      exists or is requested.

## First artifact and release

- [ ] Review the first `github-pages` artifact before approving its environment
      deployment. Confirm it corresponds to the reviewed workflow run and contains
      only the validated `site/` output.
- [ ] Approve the protected `github-pages` environment only after the artifact
      inspection is recorded.
- [ ] Verify the published site while signed out at
      `https://pydasc.github.io/`.
- [ ] Check the home page, PyDASC and DASC navigation, search, styles, assets,
      provenance links, and a nonexistent route below `/dasc.github.io/`.
- [ ] Record the workflow run, website commit, both source content commits, and
      deployment URL in the release review.

## Rollback

- [ ] Identify the immediately preceding approved website commit and its source
      locks before changing production.
- [ ] Revert the release through a reviewed pull request; do not rewrite the
      default branch or edit the deployed artifact in place.
- [ ] Let the deployment workflow rebuild, validate, and deploy that preceding
      approved state, subject to the same environment approval.
- [ ] Verify the rolled-back site while signed out and record the new deployment
      run and incident rationale.

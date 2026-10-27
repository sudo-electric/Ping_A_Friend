# GitHub repository security configuration

Configured October 27, 2026 for `sudo-electric/Ping_A_Friend`. These controls live
in GitHub repository settings; copying the source does not copy those settings.
At configuration time GitHub reported the repository as public. This work did
not change its visibility.

## Enabled controls

- **Dependabot alerts:** GitHub can identify known vulnerable dependencies.
- **Dependabot security updates:** fixes are proposed as pull requests rather than
  automatically merged. Weekly pip and Docker update checks are also configured
  in `.github/dependabot.yml`.
- **Secret scanning and push protection:** supported secret patterns are scanned,
  and detected secrets can block a push. This is not a complete detector for
  personal names, addresses, arbitrary passwords, or every possible token format.
- **Private vulnerability reporting:** researchers can use the private advisory
  form linked in the root `SECURITY.md`.
- **CodeQL default setup:** GitHub-managed code scanning is configured with the
  default query suite and both remote/local threat models. Initial setup/analysis
  runs separately in GitHub Actions; enabled configuration alone does not prove
  a successful scan or absence of findings.
- **Default-branch history protection:** an active ruleset blocks force pushes and
  branch deletion. Ordinary commits can still be pushed directly; pull-request
  reviews, status-check gates, signed commits, and automatic merging were not
  imposed.
- **Existing Actions token restrictions retained:** default workflow token access
  is read-only and workflows cannot approve pull requests. Workflows may explicitly
  request additional permissions where needed. No new custom Actions workflow or
  application/provider credentials were uploaded.

## Review and maintenance

Review findings under the repository's **Security** tab. Review update pull
requests before merging; keep `requirements.txt` and `requirements.lock` in sync,
then run the Python/JavaScript checks. The prior dependency audit is a dated
snapshot, not a replacement for ongoing alerts.

Keep live `config.json`, `data/`, credentials, transfer exports, local environments,
and build outputs out of Git. `.gitignore` prevents ordinary accidental additions;
it does not stop a forced add or erase secrets from earlier commits. If a real
secret is exposed, revoke/rotate it at its issuer and address the Git history.
Do not bypass a scanner alert without determining what it found.

Account MFA, recovery methods, personal token scope, collaborator access, GitHub
billing, and unrelated repositories were not changed. Additional GitHub products,
validity checks, non-provider secret patterns, and stricter branch/Actions policies
are not implied by the enabled controls above.

GitHub documentation:

- [Repository security settings](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-security-and-analysis-settings-for-your-repository)
- [Dependabot security updates](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-security-updates)
- [CodeQL default setup](https://docs.github.com/en/code-security/how-tos/find-and-fix-code-vulnerabilities/configure-code-scanning/configure-code-scanning)
- [Rulesets API](https://docs.github.com/en/rest/repos/rules)

## Initial CodeQL review

The first setup run succeeded for Python and JavaScript/TypeScript. Its 27 findings
were reviewed using the analysis traces and the cited source locations:

- 23 `py/path-injection` findings originate in local process environment overrides
  (`PAF_*`, `XDG_DATA_HOME`, `LOCALAPPDATA`) or the operator's `--data-dir` argument.
  Those settings intentionally choose the installation's storage location. No
  dashboard request controls them. They execute with the same OS account's access,
  and the documented threat model does not treat that account/process environment
  as a hostile lower-privilege input. File permissions/symlink checks remain in
  place. These are classified as false positives for the intended local interface.
- Four `js/code-injection` findings are in the test harness, which deliberately
  evaluates fixed repository JavaScript files in Node's VM for regression tests.
  File paths are constants relative to the test directory; no HTTP input or
  uploaded script reaches those calls. The harness is not an untrusted-code sandbox.
  These are classified as false positives, not exclusions for future findings.

The individual alerts retain review comments on GitHub. Scanning and both threat
models remain enabled; no query, source directory, or test directory was excluded.
Dependency and secret-alert counts were zero when checked. These dated results do
not guarantee that later pushes or newly published advisories will remain clean.

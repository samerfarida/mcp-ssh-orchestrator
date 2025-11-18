# Security Policy

## Supported Versions

Security fixes are applied to actively maintained releases of mcp-ssh-orchestrator. Older releases receive fixes only when the backport effort is low and the issue is high severity.

| Version | Status |
|---------|--------|
| `main` branch | Actively supported |
| `v1.0.x` | Supported (critical + high fixes) |
| Older releases | Best effort (consider upgrading) |

If you are running an older release and cannot upgrade, please highlight that in your report so we can discuss options.

## Reporting a Vulnerability

Please follow the steps below to report a potential vulnerability:

1. **Do not open a public GitHub issue or discussion.**
2. Submit a private report using one of the following channels:
   - **GitHub Security Advisories:** <https://github.com/samerfarida/mcp-ssh-orchestrator/security/advisories/new>
   - **Email:** `samer.farida@yahoo.com`
3. Include as much detail as possible:
   - Proof-of-concept or reproduction steps
   - Affected versions (commit SHA or release tag)
   - Impact assessment and suggested mitigations, if known
   - Preferred contact information and availability
4. If you require encryption, use our OpenPGP key (`openpgp4fpr:6775BF3F439A2A8A198DE10D4FC5342A979BD358`) or mention it and we can send the key via email.

## What Happens Next

- **Acknowledgement:** We aim to acknowledge receipt within **2 business days**.
- **Initial assessment:** We will triage and respond with initial findings or questions within **5 business days**.
- **Remediation plan:** For confirmed vulnerabilities, we will coordinate on a fix, testing, and target release timeline. We may request additional information to reproduce or validate the issue.
- **Coordinated disclosure:** We prefer to coordinate disclosure so end users can patch before details are public. We will agree on a disclosure window (typically 30–90 days depending on severity) and keep you updated on progress.

If you believe a vulnerability is being actively exploited or needs immediate attention, please mark your report as **URGENT** and include a reachable contact method.

## Preferred Languages

We are comfortable receiving reports in **English**. If English is not convenient, please still contact us and we will work with you using translation tools.

## Safe Harbor

We value legitimate security research. When you follow this policy and report issues responsibly, we will not pursue legal action or DMCA claims against you. Please:

- Avoid privacy violations, service degradation, or destruction of data
- Respect rate limits and always obtain consent before testing on systems you do not own

## Security Guidance for Deployers

To keep your deployment secure, we recommend the following controls:

- Use Ed25519 or 4096-bit RSA keys for SSH authentication
- Keep `require_known_host: true` (enforced by default)
- Configure network allowlists via `network.allow_cidrs`
- Maintain a deny-by-default policy
- Mount configuration, keys, and secrets as read-only volumes (`:ro`)

A fuller discussion of the orchestration controls, threat model, and audit pipeline is available in our wiki:

- [Security Model](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/05-Security-Model)
- [Observability & Audit](https://github.com/samerfarida/mcp-ssh-orchestrator/wiki/11-Observability-Audit)

Thank you for helping keep mcp-ssh-orchestrator and its users safe.

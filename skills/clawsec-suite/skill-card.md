## Description: <br>
ClawSec suite manager with embedded advisory-feed monitoring, cryptographic signature verification, approval-gated malicious-skill response, and guided setup for additional security skills. <br>

This skill is ready for commercial/non-commercial use. <br>

## Publisher: <br>
[davida-ps](https://clawhub.ai/user/davida-ps) <br>

### License/Terms of Use: <br>
MIT-0 <br>


## Use Case: <br>
Developers and security operators use this skill to monitor ClawSec advisories, review affected installed skills, and set up approval-gated OpenClaw protections. It helps manage advisory feed checks, hook installation, optional cron scans, and guarded skill installation workflows. <br>

### Deployment Geography for Use: <br>
Global <br>

## Known Risks and Mitigations: <br>
Risk: The skill can add persistent OpenClaw hooks and optional unattended cron scans. <br>
Mitigation: Review the hook and cron setup before enabling them, confirm the operating scope, and keep a clear disable or rollback path. <br>
Risk: The security evidence reports a missing feed-signing key issue for the advisory verification path. <br>
Mitigation: Verify the issue with the publisher or provide a trusted feed signing public key path before enabling advisory automation. <br>
Risk: Unsigned advisory feed mode weakens feed authenticity checks. <br>
Mitigation: Avoid CLAWSEC_ALLOW_UNSIGNED_FEED=1 except during a short, intentional migration window. <br>
Risk: The advisory feed and catalog sources influence install, block, or removal recommendations. <br>
Mitigation: Use trusted feed and catalog sources, review alerts before acting, and rely on the documented approval gates for risky install or removal decisions. <br>


## Reference(s): <br>
- [ClawHub skill page](https://clawhub.ai/davida-ps/clawsec-suite) <br>
- [ClawSec homepage](https://clawsec.prompt.security) <br>
- [ClawSec skill catalog index](https://clawsec.prompt.security/skills/index.json) <br>
- [ClawSec advisory feed](https://clawsec.prompt.security/advisories/feed.json) <br>
- [CHANGELOG.md](artifact/CHANGELOG.md) <br>
- [HEARTBEAT.md](artifact/HEARTBEAT.md) <br>


## Skill Output: <br>
**Output Type(s):** [Markdown, Shell commands, Configuration, Guidance] <br>
**Output Format:** [Markdown with inline shell commands and configuration snippets] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Includes advisory status, affected-skill findings, setup guidance, and approval-gated response instructions.] <br>

## Skill Version(s): <br>
0.1.10 (source: server release metadata, frontmatter, changelog) <br>

## Ethical Considerations: <br>
Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment. <br>

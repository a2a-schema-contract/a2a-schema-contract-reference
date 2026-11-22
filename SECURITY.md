# Security policy

This project is a development preview of the A2A Schema Contract community
draft. The [roadmap](PLAN.md) and validation reports describe current support;
no released npm or PyPI package has a maintenance support window yet.

Report suspected vulnerabilities privately using
[GitHub private vulnerability reporting](https://github.com/a2a-schema-contract/a2a-schema-contract-reference/security/advisories/new).
Include the affected source revision, runtime, a minimal synthetic reproduction,
expected behavior and observed impact. Omit credentials, private schemas and
customer payloads. Public issues are appropriate for ordinary bugs and usage
questions.

The maintainer reviews reports and coordinates disclosure through the private
advisory. Response and remediation timelines are assessed per report; no fixed
service-level commitment is offered for this development preview.

The included reference applications are local demonstrations, not authenticated
production servers. They use synthetic fixtures and test-only TLS credentials.
Evidence mode exposes execution counters and controlled test behavior; enable it
only in a trusted local test environment. A deployment must supply authentication,
authorization, tenant isolation, durable task storage and its own resource trust
policy. See the [Node operations guide](docs/node-operations.md) and
[Python guide](python/README.md) for the implemented boundaries and limitations.

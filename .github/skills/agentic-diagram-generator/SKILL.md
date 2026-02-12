---
name: agentic-diagram-generator
description: Generate C4-style Mermaid diagrams mapping changes to core and federated components.
---

Read the following inputs:

* `.github/MERMAID_TEMPLATE.md`

Write/update:

* `features/<FEATURE>/<TASK>/pr/architecture.md`

Requirements:

* **Apply Color Logic:** - **Blue (`:::internalSystem`):** Use for central gateways, core services, or shared infra.
* **Green (`:::domainService`):** Use for federated microservices or domain-specific logic.
* **Grey (`:::externalSystem`):** Use for 3rd party APIs/services outside your boundary.


* **Enforce Boundaries:** Wrap internal components (Blue/Green) in a `subgraph`; place People and External Systems outside.
* **Maintain Scoping:** Focus on high-level containers/services. Do not map individual code classes.
* **Consistency:** Ensure `classDef` headers from the template are prepended to the output.

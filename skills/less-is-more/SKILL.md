---
name: less-is-more
description: Simplify code, interfaces, and architecture by reducing unnecessary concepts and mechanisms. Use when the user requests simpler designs, less overengineering, or less-is-more.
---

This principle is based on the idea that removing superfluous elements enhances the clarity of the concept. It emphasizes functionality, clean aesthetics and simplicity.

Redesign from **First Principles**, as if the requirement had been a foundational assumption from the start.

Do not assess the entire system at the outset. Ask the user to define the scope, such as architecture, modules, interfaces, or documentation. Once the scope is defined:

- Read all affected files and understand the current design
- Ask: "if we were writing this from scratch with this new requirement, what would we build?"
- Run ablation experiments by removing selected components, interfaces, or file content. Check whether overall functionality and ease of understanding remain unchanged.
- Prepare a report for user confirmation.
- Think about the whole redesign, then deliver it incrementally

# Software Architecture

This project strictly adheres to **Uncle Bob's Clean Architecture**, enforcing a unidirectional dependency rule where outer layers (infrastructure, tools, application) depend on the inner layers (domain), but the inner layers have no knowledge of the outside world.

## C4 Model Context & Container View

```mermaid
C4Context
    title Clean Architecture - Global Net-Net Scanner

    Person(user, "User / System Analyst", "Operates the scanner and reviews shortlists.")

    Enterprise_Boundary(b0, "Global Net-Net System") {
        
        System_Boundary(b1, "UI / Delivery (Outer)") {
            Container(ui, "Presentation UI", "React / HTML / CLI", "Renders output, provenance tables, dark mode views.")
        }
        
        System_Boundary(b2, "Infrastructure (Outer)") {
            Container(sources, "Data Sources", "HTTP, Adapters", "Retrieves from SEC, Non-US APIs, Financial feeds.")
            Container(storage, "Persistence Layer", "SQLite WAL", "Stores blobs, historical snapshots, filings.")
        }
        
        System_Boundary(b3, "Application (Middle)") {
            Container(os, "Walter OS Orchestrator", "Python", "Commands, Pipelines, Task Runners.")
            Container(use_cases, "Application Services", "Python", "Coordinates domain logic to build universes, fetch data.")
        }
        
        System_Boundary(b4, "Domain (Inner Core)") {
            Container(domain_models, "Domain Models & Logic", "Python", "Playbooks, Mathematical Valuations, Universal/Regional Vetoes, Schemas.")
        }
    }

    Rel(user, ui, "Interacts with")
    Rel(ui, os, "Triggers pipelines / Queries data")
    Rel(sources, os, "Returns API data")
    Rel(os, sources, "Invokes fetches via Infrastructure")
    Rel(os, storage, "Reads/Writes State")
    
    Rel(ui, use_cases, "Calls App Services")
    Rel(sources, use_cases, "Implements Ports")
    Rel(storage, use_cases, "Implements Repositories")
    
    Rel_D(use_cases, domain_models, "Uses / Translates To")
    
    UpdateRelStyle(use_cases, domain_models, $offsetX="-20", $offsetY="-20")
```

## Layer Constraints
- **Domain Layer**: Absolutely ZERO imports from `application`, `infrastructure`, or `ui`. Enforced via AST tests logic. Mathematical rules and Playbooks live here.
- **Application Layer**: Orchestrates use cases. Operates on Domain entities. Defines interfaces (Ports) that outer layers implement.
- **Infrastructure Layer**: Implements SQLite persistent stores and API scrapers. Knows about HTTP, filesystems, database sessions.
- **UI Layer**: Reaps the data, handles strictly presentation concerns displaying Domain deterministic outputs structurally.

 ---
  🔴 CRITICAL FINDINGS

  Critical Finding #1: Severe Violation of Dependency Rule - Infrastructure Bleeding Into Domain

  Severity: CRITICAL
  Architecture Principle Violated: Clean Architecture - Dependency Rule (dependencies must point inward)
  Evidence:
  # apps/api/src/modules/documents/service.py (lines 10-29)
  from src.modules.documents.models import Document  # SQLAlchemy ORM model
  from src.modules.documents.parsers.pdf_parser import extract_text_and_offsets
  from src.services.rag_service import RagService  # Service importing another service
  from src.services.stakeholder_classifier import StakeholderClassifier

  Analysis:
  - Your "domain models" (Document, Stakeholder, Alert) are SQLAlchemy ORM models, making them infrastructure concerns
  - The domain layer is completely missing - there are NO pure business entities
  - Services directly manipulate ORM models instead of domain entities
  - Database concerns (sessions, queries) are mixed with business logic throughout services

  Recommendation:
  1. Create a true domain layer: apps/api/src/domain/entities/ with plain Python classes
  2. Introduce Repository pattern: apps/api/src/domain/repositories/ (interfaces)
  3. Implement repositories in infrastructure: apps/api/src/infrastructure/persistence/
  4. Services should depend on repositories (interfaces), not ORM models

  Trade-off Analysis:
  - Gain: True persistence independence, testability without database, easier migration to different storage
  - Lose: Initial refactoring effort (~2-3 weeks), more boilerplate code
  - Risk: Current tight coupling means ANY database schema change ripples through entire system

  ---
  Critical Finding #2: Architectural Schizophrenia - Multiple Competing Organizational Patterns

  Severity: CRITICAL
  Architecture Principle Violated: Single Responsibility Principle (at architecture level)
  Evidence:
  apps/api/src/
  ├── agents/           # AI agents (raci_generator, risk_extractor, stakeholder_extractor)
  ├── ai/
  │   └── agents/       # DUPLICATE AI agents (risk_agent, wbs_agent)
  ├── modules/
  │   ├── documents/
  │   │   ├── router.py
  │   │   └── service.py
  │   └── coherence/
  │       ├── router.py
  │       └── service.py
  ├── routers/          # DUPLICATE routers (approvals, raci, stakeholders)
  └── services/         # Cross-cutting services (rag_service, raci_generation_service)

  Analysis:
  - Agents exist in TWO places: src/agents/ AND src/ai/agents/ - which is authoritative?
  - Routers exist in TWO places: src/routers/ AND src/modules/*/router.py - why?
  - Services have THREE homes: src/services/, src/modules/*/service.py, AND as standalone utilities
  - This is NOT "modular monolith" - it's organizational chaos

  Recommendation:
  Choose ONE organizational strategy:

  Option A - Domain-Driven Modules (Recommended for your complexity):
  src/
  ├── core/              # Shared kernel
  ├── contracts/         # Bounded Context
  │   ├── domain/
  │   ├── application/   # Use cases
  │   ├── infrastructure/
  │   └── api/           # HTTP interface
  ├── execution/         # Bounded Context
  └── coherence/         # Bounded Context

  Option B - Feature Vertical Slices:
  src/
  ├── features/
  │   ├── raci_generation/
  │   │   ├── endpoint.py
  │   │   ├── service.py
  │   │   └── repository.py

  Trade-off Analysis:
  - Current cost: Developers don't know where to add new code, accidental duplication, onboarding nightmare
  - Refactoring cost: 3-4 weeks to consolidate and choose strategy
  - Long-term gain: Clarity, faster development, easier testing

  ---
  Critical Finding #3: Service Layer is Actually an Anemic Domain Anti-Pattern

  Severity: HIGH
  Architecture Principle Violated: Rich Domain Model (DDD), Tell Don't Ask
  Evidence:
  # apps/api/src/services/raci_generation_service.py
  class RaciGenerationService:
      async def generate_and_persist(self, project_id: UUID):
          wbs_items = await self._load_leaf_wbs_items(project_id)  # Data fetch
          stakeholders = await self._load_stakeholders(project_id)   # Data fetch

          agent = RaciGeneratorAgent(tenant_id=str(self.tenant_id)) # Instantiate
          result = await agent.generate_assignments(...)              # Delegate

          await self._persist_assignments(...)                        # Data save
          return result

  Analysis:
  - Services are transaction scripts (procedural code), not domain services
  - Domain models (WBSItem, Stakeholder) are data containers with zero behavior
  - All business logic is in procedural services or agents
  - This is the anemic domain model anti-pattern Martin Fowler warns against

  Recommendation:
  1. Move behavior into domain entities:
  # Domain entity
  class WBSItem:
      def assign_responsibility(self, stakeholder: Stakeholder, role: RACIRole):
          if not self.can_assign_role(role):
              raise DomainException("Cannot assign role to parent WBS item")
          # Business rules HERE, not in service
  2. Services become application services (orchestrators):
  class RACIAssignmentUseCase:
      def execute(self, command: AssignRACICommand):
          wbs = self.wbs_repo.get(command.wbs_id)
          stakeholder = self.stakeholder_repo.get(command.stakeholder_id)
          wbs.assign_responsibility(stakeholder, command.role)  # Domain does work
          self.wbs_repo.save(wbs)

  Trade-off Analysis:
  - Gain: Business logic lives in one place, easier to test without infrastructure
  - Lose: Cannot leverage SQLAlchemy cascades/relationships easily
  - Migration: Incremental - start with new features, refactor critical paths

  ---
  Critical Finding #4: AI Agents Are Misplaced in Architecture

  Severity: HIGH
  Architecture Principle Violated: Hexagonal Architecture - Ports and Adapters
  Evidence:
  # Services DIRECTLY instantiate and call agents
  from src.agents.raci_generator import RaciGeneratorAgent

  class RaciGenerationService:
      async def generate_and_persist(self, project_id: UUID):
          agent = RaciGeneratorAgent(tenant_id=str(self.tenant_id))  # Direct coupling!
          result = await agent.generate_assignments(...)

  Analysis:
  - Agents are infrastructure adapters (they call external AI APIs via AIService)
  - But they're imported directly into application/domain layer
  - No interfaces/ports defined - cannot swap Claude for GPT-4 without code changes
  - Agents contain business logic (prompts, validation) that should be in domain

  Current Reality:
  Application Layer (Service)
      ↓ (direct dependency - WRONG)
  Infrastructure Layer (Agent calling Claude API)

  Should be (Hexagonal):
  Domain Layer (Business rules, prompts as domain knowledge)
      ↓ (depends on interface)
  Port (IRACIGenerator interface)
      ↑ (implemented by)
  Adapter (ClaudeRACIAdapter, GPT4RACIAdapter)

  Recommendation:
  1. Define ports (interfaces):
  # src/domain/ports/ai_services.py
  from abc import ABC, abstractmethod

  class IRACIGenerator(ABC):
      @abstractmethod
      async def generate_assignments(self, context: RACIContext) -> RACIResult:
          pass
  2. Implement adapters:
  # src/infrastructure/ai/claude_raci_adapter.py
  class ClaudeRACIAdapter(IRACIGenerator):
      def __init__(self, ai_service: AIService):
          self._service = ai_service
  3. Inject via dependency injection:
  class RACIAssignmentUseCase:
      def __init__(self, raci_generator: IRACIGenerator):  # Interface!
          self._generator = raci_generator

  Trade-off Analysis:
  - Gain: Can test with mock AI, swap providers easily, business logic stays in domain
  - Lose: More files, need DI framework (dependency-injector or similar)
  - Critical: Without this, you're locked to Claude's API structure forever

  ---
  Critical Finding #5: Router Layer is God Object - Violates Single Responsibility

  Severity: MEDIUM-HIGH
  Architecture Principle Violated: SOLID - Single Responsibility, Interface Segregation
  Evidence:
  # apps/api/src/routers/approvals.py (lines 45-50)
  @router.patch("/{resource_type}/{resource_id}")
  async def review_resource(
      resource_type: str,  # Magic string - "stakeholders", "risks"
      resource_id: UUID,
      review: ApprovalReview,
      user_id: CurrentUserId,
      tenant_id: CurrentTenantId,
      db: AsyncSession = Depends(get_session)
  ):
      # Router contains business logic mapping and orchestration!

  Analysis:
  - Routers should be thin HTTP adapters (map HTTP → domain, domain → HTTP)
  - Current routers contain:
    - Business logic (RESOURCE_MAP, conditional flows)
    - Direct database access (injecting AsyncSession)
    - Domain orchestration (calling multiple models/services)
  - This is a Fat Controller anti-pattern

  Recommendation:
  1. Make routers dumb HTTP adapters:
  @router.patch("/{resource_type}/{resource_id}")
  async def review_resource(
      resource_type: str,
      resource_id: UUID,
      review: ApprovalReviewDTO,
      user_id: CurrentUserId,
      use_case: ReviewResourceUseCase = Depends()
  ):
      command = ReviewResourceCommand.from_dto(review, resource_type, resource_id, user_id)
      result = await use_case.execute(command)
      return ApprovalResponseDTO.from_domain(result)
  2. Move logic to use cases:
  class ReviewResourceUseCase:
      def __init__(self, approval_service: IApprovalService):
          self._service = approval_service

      async def execute(self, command: ReviewResourceCommand) -> ApprovalResult:
          # All logic here, not in router

  Trade-off Analysis:
  - Gain: Routers become trivial to test (just HTTP mapping), business logic reusable
  - Lose: More files (use cases), learning curve for team
  - Critical: Current fat routers make it impossible to reuse logic (e.g., from CLI, queue worker)

  ---
  Critical Finding #6: Missing Anti-Corruption Layer for External Systems

  Severity: MEDIUM
  Architecture Principle Violated: Hexagonal Architecture - ACL for external systems
  Evidence:
  # apps/api/src/agents/base_agent.py
  class BaseAgent:
      def __init__(self, tenant_id: str | None = None):
          self._service = AIService(tenant_id=tenant_id)  # Direct dependency

      async def _run_with_retry(self, system_prompt: str, user_content: str):
          return await self._service.run_extraction(system_prompt, user_content)
          # No translation layer - domain speaks Claude's language!

  Analysis:
  - Your domain/application code directly uses Claude API structures (prompts, JSON schemas)
  - No abstraction layer between your domain concepts and AI provider's API
  - If Claude changes API, you modify RACI business logic code

  Recommendation:
  Create an Anti-Corruption Layer (ACL):
  # src/domain/model/raci_assignment.py
  @dataclass
  class RACIAssignmentRequest:  # Domain concept
      wbs_scope: str
      stakeholders: list[StakeholderProfile]
      contract_constraints: list[ContractRule]

  # src/infrastructure/ai/claude_translator.py
  class ClaudePromptTranslator:
      def to_claude_prompt(self, request: RACIAssignmentRequest) -> ClaudePrompt:
          # Translation logic - protects domain from Claude changes
          return ClaudePrompt(
              system=self._build_system_prompt(request),
              messages=[self._build_user_message(request)]
          )

      def from_claude_response(self, response: ClaudeResponse) -> RACIAssignmentResult:
          # Parse Claude JSON → domain objects

  Trade-off Analysis:
  - Gain: Domain stability, easy to swap AI providers, better testability
  - Lose: Translation layer adds code, slight performance overhead
  - Risk: Without ACL, every Claude API change is a breaking change to your domain

  ---
  Critical Finding #7: Coherence Engine V2 - Premature Generalization

  Severity: MEDIUM
  Architecture Principle Violated: YAGNI (You Aren't Gonna Need It), KISS
  Evidence:
  - CoherenceEngineV2 with ExecutionMode (deterministic, llm, hybrid)
  - Complex LLM integration layer with qualitative rules
  - YAML rule configuration system
  - But: CoherenceService is still a MOCK implementation (line 5-8 of service.py)

  Analysis:
  - You've built sophisticated infrastructure (Engine V2, LLM evaluator, YAML config)
  - Core service returns hardcoded mock data
  - Classic premature abstraction - building for "future needs" before validating current needs

  Recommendation:
  1. Ship the simplest version that works (Lean/Agile principle)
  2. Start with V1: hardcoded deterministic rules, no LLM
  3. Add LLM only when V1 is proven insufficient (data-driven decision)
  4. YAML config only when you have >10 rules and need dynamic updates

  Trade-off Analysis:
  - Current cost: Complex code that's not being used, maintenance burden
  - Simplification gain: Faster to market, easier to understand, less code to maintain
  - Future cost: Refactoring when you actually need flexibility (but you'll have user data to guide it)

  ---
  Critical Finding #8: Frontend-Backend Type Safety is Illusion

  Severity: MEDIUM
  Architecture Principle Violated: Contract-First Design, Type Safety Across Boundaries
  Evidence:
  // apps/web/package.json
  "scripts": {
    "generate-client": "openapi --input http://localhost:8000/api/v1/openapi.json ..."
  }

  Analysis:
  - OpenAPI client generation is manual (not in CI/CD)
  - No guarantee that frontend types match current backend
  - TypeScript frontend, Python backend = no shared source of truth
  - Pydantic models generate OpenAPI, but only at runtime

  Current Risk:
  1. Backend changes ApprovalStatus enum → breaks frontend
  2. No compile-time safety across the HTTP boundary
  3. Manual npm run generate-client often forgotten

  Recommendation:
  1. Add to CI/CD pipeline:
  # .github/workflows/contract-test.yml
  - name: Generate OpenAPI client
    run: cd apps/web && npm run generate-client
  - name: Check for schema drift
    run: git diff --exit-code apps/web/lib/api/generated/
  2. Consider contract testing (Pact.io):
  # Contract test
  def test_approval_endpoint_matches_contract(pact):
      pact.given("approval exists") \
          .upon_receiving("approval patch request") \
          .with_request("PATCH", "/approvals/risks/123") \
          .will_respond_with(200, body=ApprovalResponseSchema)
  3. Alternative: Use gRPC/tRPC for type-safe RPC

  Trade-off Analysis:
  - Gain: Catch breaking changes before production, confidence in deploys
  - Lose: CI/CD takes longer, need contract testing infrastructure
  - Critical: Current setup WILL cause production incidents when contracts drift

  ---
  Critical Finding #9: Multi-Tenancy RLS - Security by Obscurity

  Severity: HIGH (Security)
  Architecture Principle Violated: Defense in Depth, Fail-Safe Defaults
  Evidence:
  # apps/api/src/core/middleware.py (TenantIsolationMiddleware)
  # Sets app.current_tenant in PostgreSQL session

  # apps/api/src/core/database.py
  async def get_session(request: Request):
      if hasattr(request.state, "tenant_id") and request.state.tenant_id:
          await session.execute(text(f"SET app.current_tenant = '{tenant_id}'"))
          # String interpolation of UUID - SQL injection risk mitigated only by UUID type

  Analysis:
  - RLS (Row-Level Security) is your only tenant isolation mechanism
  - No application-level tenant checks in repositories/services
  - If RLS context is NOT set (middleware bug, async issue), queries return ALL tenants' data
  - Single point of failure for security

  Recommendation - Defense in Depth:
  1. Application-level tenant filtering (belt + suspenders):
  class TenantAwareRepository:
      def __init__(self, session: AsyncSession, tenant_id: UUID):
          self._session = session
          self._tenant_id = tenant_id

      async def get(self, id: UUID) -> Document:
          result = await self._session.execute(
              select(Document)
              .where(Document.id == id)
              .where(Document.tenant_id == self._tenant_id)  # Explicit filter
          )
          # Even if RLS fails, application filter protects
  2. Fail-safe on missing tenant:
  async def get_session(request: Request):
      if not hasattr(request.state, "tenant_id"):
          raise SecurityError("Tenant context required")  # Fail closed
  3. Audit logging:
  # Log every RLS context set
  logger.info("rls_context_set", tenant_id=tenant_id, user_id=user_id)

  Trade-off Analysis:
  - Gain: If RLS fails, application layer still protects. Auditability
  - Lose: Slight performance overhead (redundant WHERE clause)
  - Critical: RLS as sole defense = single point of failure. Unacceptable for multi-tenant SaaS

  ---
  Critical Finding #10: NetworkX for Graph RAG - Technical Debt Bomb

  Severity: HIGH (Scalability)
  Architecture Principle Violated: Architectural Runway, Non-Functional Requirements
  Evidence:
  # apps/api/src/services/knowledge_graph.py
  # Uses NetworkX (in-memory Python library)

  Analysis:
  - NetworkX is in-memory - graph stored in Python process RAM
  - No persistence, no concurrency, no query optimization
  - Acceptable for MVP (<100 documents), catastrophic at scale (>1000 documents)
  - Your architecture claims "Enterprise EPC" but uses toy graph library

  Scalability Cliff:
  - 100 documents: ~50MB RAM, 100ms queries ✅
  - 1,000 documents: ~500MB RAM, 1-2s queries ⚠️
  - 10,000 documents: ~5GB RAM, 10-30s queries, OOM crashes ❌

  Recommendation - Migration Path:
  1. Short-term (next 3 months):
    - Keep NetworkX BUT add metrics:
    @metrics.track_graph_size
  @metrics.track_query_time
  async def query_graph(self, ...):
      if self._graph.number_of_nodes() > 5000:
          logger.warning("graph_size_threshold_exceeded", count=self._graph.number_of_nodes())
  2. Medium-term (6 months):
    - Introduce Repository pattern for graph storage:
    class IGraphRepository(ABC):
      @abstractmethod
      async def add_node(self, node: GraphNode): pass

      @abstractmethod
      async def query_paths(self, start: UUID, end: UUID) -> list[Path]: pass
    - Implementations: NetworkXRepository (current), Neo4jRepository (future)
  3. Long-term (12 months):
    - Migrate to Neo4j or AWS Neptune
    - Use Cypher queries for complex graph traversals
    - Persist graph to database (survive process restarts)

  Trade-off Analysis:
  - Current risk: System will catastrophically fail at moderate scale (1000+ documents)
  - Migration cost: ~4-6 weeks to integrate Neo4j
  - Decision point: Set a hard limit NOW (e.g., 500 documents max) and migrate BEFORE hitting it

  ---
  📊 SUMMARY - ARCHITECTURAL MATURITY ASSESSMENT

  | Dimension                  | Score  | Status                                |
  |----------------------------|--------|---------------------------------------|
  | Dependency Rule Compliance | 2/10   | 🔴 Critical violations                |
  | Layer Separation           | 3/10   | 🔴 Fat services, anemic domain        |
  | Architectural Clarity      | 4/10   | 🟡 Mixed styles, organizational chaos |
  | Security (Multi-tenancy)   | 6/10   | 🟡 RLS only, single point of failure  |
  | Scalability (Graph)        | 3/10   | 🔴 Technical debt bomb                |
  | Type Safety (Full-stack)   | 5/10   | 🟡 Manual, error-prone                |
  | Testability                | 4/10   | 🔴 Tight coupling to infrastructure   |
  | OVERALL                    | 3.9/10 | 🔴 Needs Major Refactoring            |

  ---
  🎯 PRIORITIZED ACTION PLAN (Next 6 Months)

  Phase 1 - Stop the Bleeding (Weeks 1-4)

  1. ✅ Add application-level tenant filtering (Critical Finding #9)
  2. ✅ Add graph size monitoring (Critical Finding #10)
  3. ✅ Fix CI/CD to generate OpenAPI client (Critical Finding #8)
  4. ✅ Consolidate agents into single directory (Critical Finding #2)

  Phase 2 - Foundational Refactoring (Weeks 5-12)

  1. ✅ Introduce Repository pattern for Documents module (Critical Finding #1)
  2. ✅ Define AI service ports/interfaces (Critical Finding #4)
  3. ✅ Create Use Case layer for Approvals flow (Critical Finding #5)
  4. ✅ Build Anti-Corruption Layer for Claude (Critical Finding #6)

  Phase 3 - Strategic Improvements (Weeks 13-24)

  1. ✅ Migrate Graph to Neo4j (Critical Finding #10)
  2. ✅ Refactor to Domain-Driven modules (Critical Finding #2)
  3. ✅ Implement Rich Domain Models (Critical Finding #3)
  4. ✅ Add contract testing (Critical Finding #8)

  ---
  🧠 FINAL VERDICT

  Current State: Your architecture is a "Big Ball of Mud masquerading as Clean Architecture". You have the terminology (layers, services, agents) but lack the actual separation of concerns and dependency management that make Clean Architecture valuable.   

  Reality Check:
  - ❌ This is NOT Clean Architecture (domain is missing, dependencies point outward)
  - ❌ This is NOT Hexagonal Architecture (no ports, direct infrastructure coupling)
  - ✅ This IS a transaction script architecture with modern tooling
  - ⚠️ It MIGHT become a distributed monolith if you split into microservices without fixing foundations

  Brutal Truth: Your system will survive MVP and even Series A. But at enterprise scale (10,000+ projects, 100+ concurrent users), you'll face:
  1. Performance cliff (NetworkX crashes)
  2. Security incidents (RLS context bugs leak tenant data)
  3. Development paralysis (nobody knows where to add code)

  Recommendation: Either commit to a 6-month architectural refactoring OR be honest that this is a "Lean Startup MVP" and plan for a rewrite at Series B. Trying to scale this architecture without fixing foundations will cost 10x more than refactoring now


  *****

  As a Domain-Driven Design expert, I have reviewed the provided context. The project shows promise and a clear effort to        
  structure a complex domain, but it exhibits several common "domain smells" that risk creating a rigid, anemic, and
  hard-to-maintain system.

  Here is a detailed analysis based on the critical questions raised.

  ---

  1. Domain Model Purity

  Concern 1: Anemic Domain Model
   - Domain Smell: Anemic Domain Model
   - Location: apps/api/src/.../services.py (e.g., DocumentService), and ORM models like apps/api/src/.../models.py::Document.   
   - DDD Principle Violated: Encapsulation & Rich Domain Models. The entities (Document, Clause, etc.) are treated as simple data
     bags, with all business logic living in service classes (Transaction Script pattern). The DocumentService orchestrates      
     everything, while the Document model itself does nothing but hold data. This violates the core idea that entities should    
     protect their own invariants and contain their own logic.
   - Refactoring Suggestion:
       1. Move behavior from services into the entities. For example, instead of document_service._analyze_document(doc), the    
          Document entity should have a method like document.analyze(insight_kernel, summary_kernel).
       2. The analyze method on the Document entity would be responsible for updating its own state (e.g., self.analyze_status = 
          ProcessStatus.IN_PROGRESS), calling the necessary kernels, and then setting the final state (SUCCESS or FAILED).       
   - Priority: Must fix for MVP. An anemic model will become exponentially harder to refactor as more business logic is added,   
     leading to a brittle and unmaintainable codebase.

  Concern 2: Missing Value Objects
   - Domain Smell: Primitive Obsession
   - Location: Throughout the domain model definitions and business logic (e.g., CoherenceScore as int, ClauseCode as str).      
   - DDD Principle Violated: Value Objects. The design relies on primitive types (string, int) to represent core domain concepts 
     that have their own identity, validation, and behavior. This scatters validation logic and makes the domain language less   
     explicit.
   - Refactoring Suggestion:
       1. Introduce explicit Value Objects. These should be immutable classes with validation in their constructors.

    1     # Example for ClauseCode
    2     class ClauseCode:
    3         def __init__(self, code: str):
    4             if not re.match(r"^[A-Z]{2,3}-[0-9]{4,5}$", code):
    5                 raise ValueError("Invalid ClauseCode format.")
    6             self._code = code
    7
    8         def __str__(self):
    9             return self._code
   10
   11     # Example for Price
   12     from decimal import Decimal
   13
   14     class Price:
   15         def __init__(self, amount: Decimal, currency: str):
   16             if amount < 0:
   17                 raise ValueError("Price amount cannot be negative.")
   18             if len(currency) != 3:
   19                 raise ValueError("Currency must be a 3-letter code.")
   20             self.amount = amount
   21             self.currency = currency
   - Priority: Must fix for MVP. Using primitives for domain concepts is a foundational error that leads to bugs and
     inconsistencies.

  ---

  2. Aggregate Boundaries

  Concern 1: Unclear Aggregate Roots
   - Domain Smell: Vague Aggregate Boundaries
   - Location: Data models and service logic, especially in how related entities are accessed and modified.
   - DDD Principle Violated: Aggregates & Aggregate Roots. The relationships between entities like Clause, Stakeholder, and      
     WBSItem are defined by foreign keys, but there's no clear transactional boundary enforced by an Aggregate Root. It's unclear
     if a Clause is the root for its Stakeholders. Can a Stakeholder be fetched and modified without loading the Clause? If so,  
     the invariant rules are easily bypassed.
   - Refactoring Suggestion:
       1. Define aggregates explicitly. For example, declare that Clause is the Aggregate Root for Stakeholder, WBSItem, etc.,   
          that are extracted from it.
       2. Repositories should only exist for Aggregate Roots. So, you should have a ClauseRepository but not a
          StakeholderRepository.
       3. To add a stakeholder, you would do: clause = clause_repo.get(clause_id); clause.add_stakeholder(...);
          clause_repo.save(clause);. The save method handles the transaction for the entire aggregate.
   - Priority: Must fix for MVP. Without clear aggregates, maintaining data consistency and business invariants is nearly        
     impossible.

  Concern 2: Database-Driven Cascade Deletes
   - Domain Smell: Leaky Persistence
   - Location: DocumentService.delete_file_by_name.
   - DDD Principle Violated: Domain-Driven Deletion Logic. The deletion logic is a procedural script that manually cleans up     
     records from multiple tables and even external systems (ChromaDB). This logic is brittle and belongs within the domain.     
   - Refactoring Suggestion:
       1. The Document aggregate root should have a delete() method.
       2. This method doesn't delete itself but rather marks itself as deleted and publishes a DocumentDeleted domain event.     
       3. Event handlers in the application layer would then listen for this event. One handler would delete the Document from   
          the database repository. Another handler would be responsible for telling the vector store (ChromaDB) to delete its    
          related embeddings. This decouples the domain logic from the implementation details of persistence and external        
          services.
   - Priority: Can defer. While important, the current procedural approach can work for early stages, but it creates technical   
     debt.

  ---

  3. Domain Events

   - Domain Smell: Orchestration over Choreography
   - Location: Cross-domain communication, like DocumentService calling analysis kernels directly.
   - DDD Principle Violated: Domain Events & Decoupled Bounded Contexts. The system uses direct, synchronous calls between       
     different logical domains (e.g., document storage and analysis). This creates tight coupling. An Event-Driven architecture  
     is mentioned, but not implemented at the domain level.
   - Refactoring Suggestion:
       1. Introduce domain events for significant state changes.
       2. Refactor DocumentService.create_document to save the document and then publish a DocumentCreated event.
       3. Create an Analysis bounded context with a service that subscribes to DocumentCreated. When it receives the event, it   
          begins its work asynchronously.
       4. When analysis is finished, it publishes ContractAnalyzed or IncoherenceDetected events, which other parts of the system
          can react to (e.g., sending notifications).
   - Priority: Can defer. Direct calls are simpler to implement initially. However, moving to events will be crucial for
     scalability, resilience, and decoupling as the system grows.

  ---

  4. Ubiquitous Language

   - Domain Smell: Fractured & Inconsistent Language
   - Location: Naming across code, documentation, and database schemas.
   - DDD Principle Violated: Ubiquitous Language. The inconsistencies noted (Coherence Score vs. coherence_score_breakdown,      
     WBSGeneratorAgent vs. WBSItem) show that the shared language between developers and domain experts is breaking down. Code   
     should be the most faithful expression of the domain language.
   - Refactoring Suggestion:
       1. Create a formal glossary in a shared, visible location (e.g., a GLOSSARY.md file at the root). Define terms like       
          "Coherence Score", "WBS Item", "Stakeholder", etc., exactly as the business understands them.
       2. Refactor aggressively. Rename classes, methods, variables, and database tables to match the glossary. WBSGeneratorAgent
          should be renamed to something like WBSItemExtractor, and its output should be a list of WBSItems. The naming should be
          consistent everywhere.
   - Priority: Must fix for MVP. A broken language leads to misunderstandings, bugs, and a domain model that is difficult for new
     developers and even domain experts to understand.

  ---

  5. Business Rules Location & Specific Code Patterns


ℹ Update successful! The new version will be used on your next run.
  Concern 1: Misplaced Business Logic
   - Domain Smell: Logic in the Wrong Place
   - Location: calculate_coherence_score as a free function.
   - DDD Principle Violated: Domain Services & Aggregate Encapsulation. This core business logic is not attached to any domain   
     object, making it hard to find and easy to misuse.
   - Refactoring Suggestion:
       1. This logic belongs in a Domain Service if it coordinates across multiple aggregates (e.g., a Project and its
          Documents), or within an Aggregate Root (e.g., a hypothetical Analysis entity). Let's assume it's a domain service:    

    1     class CoherenceScoringService:
    2         # Define constants here, loaded from config if needed
    3         _NORMALIZATION_DIVISOR = 50.0
    4         _WEIGHTS = {"CRITICAL": 1.0, "MAJOR": 0.5, ...} # or load from config
    5
    6         def calculate_for_document(self, doc: Document) -> CoherenceResult:
    7             alerts = doc.alerts # Assuming alerts are part of the Document aggregate
    8             context = ... # build context
    9
   10             raw_penalty = 0
   11             for alert in alerts:
   12                 weight = self._WEIGHTS.get(alert.severity.value)
   13                 impact = self._calculate_impact(alert, context) # another private method
   14                 raw_penalty += weight * impact
   15
   16             normalized_score = int(100 / (1 + raw_penalty / self._NORMALIZATION_DIVISOR))
   17             return CoherenceResult(score=normalized_score, alerts=alerts)
   - Priority: Must fix for MVP. Core business logic must be correctly placed and encapsulated.

  Concern 2: CoherenceResult, Magic Numbers, and WEIGHTS
   - Domain Smell: Primitive Obsession & Configuration Confusion
   - Location: calculate_coherence_score implementation.
   - DDD Principle Violated: Value Objects & Explicit Domain Concepts.
   - Refactoring Suggestion:
       1. `CoherenceResult`: Make it a true Value Object. Its constructor should validate the score.

   1         class CoherenceResult:
   2             def __init__(self, score: int, contributing_alerts: List[Alert]):
   3                 if not (0 <= score <= 100):
   4                     raise ValueError("Score must be between 0 and 100.")
   5                 self.score = score
   6                 self.contributing_alerts = tuple(contributing_alerts) # Immutable
       2. Magic Number `50`: This should be a named constant within the CoherenceScoringService (as shown above), named
          _NORMALIZATION_DIVISOR or similar, with a comment explaining its business meaning.
       3. `WEIGHTS`: This is a core domain concept. It should be managed by the CoherenceScoringService. The presence of
          scripts/weights_config.py is good—it suggests the weights are configurable. The domain service should be responsible   
          for loading this configuration at startup, treating it as a dependency.


          *****

*****


• No AGENTS.md exists under C:\Users\esus_\Documents\AI\ZTWQ\c2pro (none found in repo).
                                                                                                                                 
  Use Case Gap: Explicit application-layer use cases are missing; HTTP routers and services own orchestration.                   
  Current Implementation: Orchestration lives in HTTP adapters (apps/api/src/modules/analysis/router.py) calling                 
  run_orchestration and in routers that hit DB directly (e.g., apps/api/src/routers/stakeholders.py, apps/api/src/routers/       
  raci.py). Domain-ish logic sits in “services” (apps/api/src/modules/documents/service.py).                                     
  Clean Architecture Violation: Use cases are not separated from delivery/persistence; controllers perform application logic and 
  persistence.                                                                                                                   
  Proposed Structure:                                                                                                            
                                                                                                                                 
  apps/api/src/application/use_cases/                                                                                            
    analyze_contract.py                                                                                                          
    extract_stakeholders.py                                                                                                      
    generate_raci.py                                                                                                             
    upload_document.py                                                                                                           
  apps/api/src/application/dto/                                                                                                  
    analysis.py stakeholders.py documents.py                                                                                     
  apps/api/src/application/ports/                                                                                                
    ai.py db.py storage.py                                                                                                       
  apps/api/src/adapters/http/                                                                                                    
    routers/*.py                                                                                                                 
  apps/api/src/adapters/ai/
    agents/*.py                                                                                                                  
  apps/api/src/infrastructure/db/                                                                                                
    repositories/*.py                                                                                                            
                                                                                                                                 
  Migration Effort: ~1.5–3 days to carve 4–6 use cases; ~400–900 LOC moved/reshaped.                                             
                                                                                                                                 
  ———                                                                                                                            
                                                                                                                                 
  Use Case Gap: “Clauses Router” and “Procurement Router” are referenced but not implemented.                                    
  Current Implementation: No clauses/procurement routers exist; clauses are only exposed via document detail (apps/api/src/      
  modules/documents/router.py) and procurement fields only exist in schemas/models (apps/api/src/modules/stakeholders/models.py, 
  apps/api/src/modules/stakeholders/schemas.py).                                                                                 
  Clean Architecture Violation: Missing use case boundary for clauses/procurement workflows.                                     
  Proposed Structure: Add application/use_cases/manage_clauses.py and application/use_cases/manage_procurement.py, then thin     
  routers.
  Migration Effort: 0.5–1 day each, ~150–300 LOC per use case.                                                                   
                                                                                                                                 
  ———                                                                                                                            
                                                                                                                                 
  Use Case Gap: Use case DTOs are conflated with API schemas; domain vs API boundaries unclear.                                  
  Current Implementation: Pydantic schemas act as request/response DTOs (apps/api/src/modules/documents/schemas.py, apps/api/src/  modules/analysis/schemas.py, apps/api/src/modules/stakeholders/schemas.py), and the analysis router defines its own API models 
  inline (apps/api/src/modules/analysis/router.py).                                                                              
  Clean Architecture Violation: API DTOs are reused across layers; no explicit application boundary models.                      
  Proposed Structure: Create application DTOs and map to/from Pydantic request/response models in adapters.                      
  Migration Effort: 1–2 days, ~300–600 LOC (mostly mapping).                                                                     
                                                                                                                                 
  ———                                                                                                                            
                                                                                                                                 
  Use Case Gap: Error taxonomy is partial; “AppError = ValidationError | NotFoundError | ConflictError | InfraError” is not      
  implemented.                                                                                                                   
  Current Implementation: Custom exceptions exist (apps/api/src/core/exceptions.py) with handlers (apps/api/src/core/            
  handlers.py). InfraError does not exist; AI failures are AIServiceError. Routers still raise HTTPException directly (e.g.,     
  apps/api/src/routers/stakeholders.py, apps/api/src/modules/documents/router.py).                                               
  Clean Architecture Violation: Mixed error handling strategy; adapters throw framework exceptions instead of application errors.  Proposed Structure: Define InfraError and domain-specific AI failures (e.g., ExtractionFailedError), wrap infra exceptions in  
  use cases, map to HTTP in routers only.                                                                                        
  Migration Effort: 1–1.5 days, ~200–400 LOC.                                                                                    
                                                                                                                                 
  ———                                                                                                                            
                                                                                                                                 
  Use Case Gap: Orchestration only covers a subset of the contract flow (risk/WBS/budget).                                       
  Current Implementation: LangGraph orchestration (apps/api/src/ai/graph/workflow.py, apps/api/src/ai/graph/nodes.py) routes to  
  risk/WBS/budget, critiques, optional human interrupt, then persists. No ClauseExtractorAgent, StakeholderExtractorAgent,       
  BOMBuilderAgent, RACIGeneratorAgent, AlertRouterAgent are wired.                                                               
  Clean Architecture Violation: Orchestration is embedded in AI adapter code, not exposed as an application use case; missing    
  full process.                                                                                                                  
  Proposed Structure: A top-level AnalyzeContractUseCase that coordinates agent ports and persistence; LangGraph becomes an      
  implementation detail.                                                                                                         
  Migration Effort: 2–4 days, ~600–1200 LOC depending on agent integration.
                                                                                                                                 
  ———                                                                                                                            
                                                                                                                                 
  Use Case Gap: Human-in-the-loop is partial and inconsistent.                                                                   
  Current Implementation: ApprovalStatus exists (apps/api/src/core/approval.py), and approvals are handled via apps/api/src/     
  routers/approvals.py. Stakeholders and Alerts have approval fields (apps/api/src/modules/stakeholders/models.py, apps/api/src/ 
  modules/analysis/models.py). WBS/BOM/RACI do not model approval states. LangGraph can interrupt for human approval but there is
  no HTTP endpoint to resume (apps/api/src/ai/orchestrator.py).                                                                  
  Clean Architecture Violation: Approval workflow is not modeled as a use case/state machine across all AI outputs.              
  Proposed Structure: Introduce PendingApproval aggregate + ReviewAiOutputUseCase, and add explicit resume endpoints or          
  background workflow resumes.                                                                                                   
  Migration Effort: 1.5–3 days, ~400–800 LOC.                                                                                    
                                                                                                                                 
  ———                                                                                                                            
                                                                                                                                 
  Use Case Gap: Agent/service responsibilities are ambiguous and duplicated.                                                     
  Current Implementation: Agents exist in multiple locations (apps/api/src/agents/*, apps/api/src/ai/agents/*, and root agents/  
  *). Orchestration uses src/agents/risk_extractor.py and src/ai/agents/wbs_agent.py. Services exist in apps/api/src/services/*  
  (e.g., rag_service.py, anonymizer.py, knowledge_graph.py).                                                                     
  Clean Architecture Violation: No clear “agent port” vs “service port”; infra and app roles are blended.                        
  Proposed Structure: Define application ports IAgent / IExtractor and adapt concrete agent/service implementations under        
  adapters/ai and infrastructure.                                                                                                
  Migration Effort: 1–2 days, ~250–500 LOC.                                                                                      
                                                                                                                                 
  ———                                                                                                                            
                                                                                                                                 
  Use Case Gap: MCP server ownership and security policy placement is unclear.                                                   
  Current Implementation: DatabaseMCPServer lives under apps/api/src/mcp/servers/database_server.py and enforces allowlists,     
  query limits, rate limiting, and auditing.                                                                                     
  Clean Architecture Violation: Security policy is embedded in the adapter; potential duplication with DB-level RLS.             
  Proposed Structure: Treat MCP server as an infrastructure adapter with a dedicated “MCP Query Use Case” that calls a policy    
  component; keep allowlist as defense-in-depth but externalize policy config.                                                   
  Migration Effort: 0.5–1 day, ~150–300 LOC.                                                                                     
 
 *****

 
✦ As a Platform Engineer and Infrastructure Architect, I have reviewed the architecture of C2Pro's adapters and integrations. The
  system has a solid foundation, but there are critical architectural gaps that introduce risks related to coupling, resilience, 
  and maintainability. Adopting a stricter Ports & Adapters (Hexagonal) model will mitigate these issues.

  Here is a detailed breakdown of the concerns and recommendations.

  ---

  1. Missing Port Abstractions

   - Infrastructure Concern: The application core is directly coupled to specific technologies (SQLAlchemy, Claude's API). There 
     are no explicit port interfaces defined within the application, only concrete adapter implementations. This makes it        
     difficult to swap technologies or test the application in isolation.
   - Hexagonal Principle Violated: Ports & Adapters. The boundary between the application and its infrastructure dependencies is 
     porous. The application "knows" it's talking to PostgreSQL via SQLAlchemy, which is a violation.
   - Resilience Risk: Vendor Lock-in and Brittleness. If the Claude API needs to be replaced with a different provider (e.g.,    
     OpenAI, Cohere), significant code changes will be required within the application's core logic, instead of just creating a  
     new adapter.
   - Contract Test Gap: Without a port (interface), you cannot create simple test doubles like an InMemoryClauseRepository. Tests
     are forced to use a real database, making them slow, complex, and flaky.
   - Recommended Adapter Pattern: Define explicit interfaces (ports) in the application domain/core and implement them in the    
     infrastructure layer.

    1   # 1. Port (Interface) - Lives in the Application/Domain Core
    2   # in: c2pro/app/domain/ports/ai_provider.py
    3   from abc import ABC, abstractmethod
    4   from pydantic import BaseModel
    5
    6   class ExtractionResult(BaseModel):
    7       # ... domain-specific result structure
    8       clauses: list
    9       stakeholders: list
   10
   11   class AIProvider(ABC):
   12       @abstractmethod
   13       def extract_entities_from_document(self, document_text: str) -> ExtractionResult:
   14           """Extracts structured entities from document text."""
   15           pass
   16
   17   # 2. Adapter (Implementation) - Lives in the Infrastructure Layer
   18   # in: c2pro/infrastructure/providers/claude_ai_provider.py
   19   class ClaudeAIProvider(AIProvider):
   20       def __init__(self, api_key: str, model: str):
   21           # ... initialize Claude client
   22           pass
   23
   24       def extract_entities_from_document(self, document_text: str) -> ExtractionResult:
   25           # ... logic specific to calling the Claude API
   26           # ... map Claude's response to the domain's ExtractionResult
   27           return ExtractionResult(...)
   28
   29   # 3. Adapter (Test Double) - Lives in the Test Fixtures
   30   # in: c2pro/tests/doubles/in_memory_ai_provider.py
   31   class InMemoryAIProvider(AIProvider):
   32       def extract_entities_from_document(self, document_text: str) -> ExtractionResult:
   33           # Return a fixed, predictable result for testing
   34           return ExtractionResult(clauses=["Test Clause"], stakeholders=["Test Stakeholder"])

  ---

  2. Leaky Persistence & Anemic Models

   - Infrastructure Concern: The SQLAlchemy ORM models are being used directly as domain objects. This conflates the persistence 
     concern (how data is stored in tables) with the domain concern (business entities and their logic). There is no clear       
     mapping layer between them.
   - Hexagonal Principle Violated: Separation of Concerns. The application core should operate on rich domain entities, ignorant 
     of how they are persisted. The ORM models are an adapter detail that has leaked into the domain.
   - Resilience Risk: Changes to the database schema (e.g., adding a column for indexing) could force changes to the domain      
     model, even if the domain logic is unaffected. This creates unnecessary coupling and ripple effects.
   - Contract Test Gap: When testing domain logic, you are forced to construct and manage complex ORM objects tied to a database 
     session, instead of simple, state-based domain entities.
   - Recommended Adapter Pattern: Implement a Repository pattern with explicit mappers that translate between the domain entity  
     and the persistence (ORM) model.

    1   # Domain Entity (Not an ORM model)
    2   class Clause:
    3       def __init__(self, id: str, text: str, is_active: bool):
    4           self.id = id
    5           self.text = text
    6           self.is_active = is_active
    7       # ... rich domain logic here ...
    8
    9   # SQLAlchemy ORM Model (Persistence Detail)
   10   class ClauseORM(Base):
   11       __tablename__ = 'clauses'
   12       id = Column(String, primary_key=True)
   13       clause_text = Column(String)
   14       active = Column(Boolean)
   15
   16   # Mapper
   17   class ClauseMapper:
   18       @staticmethod
   19       def to_entity(orm_obj: ClauseORM) -> Clause:
   20           return Clause(id=orm_obj.id, text=orm_obj.clause_text, is_active=orm_obj.active)
   21
   22       @staticmethod
   23       def to_persistence(entity: Clause) -> ClauseORM:
   24           return ClauseORM(id=entity.id, clause_text=entity.text, active=entity.is_active)
   25
   26   # Repository Adapter (implements a ClauseRepository port)
   27   class SqlClauseRepository:
   28       def get_by_id(self, clause_id: str) -> Clause:
   29           orm_obj = self.db_session.query(ClauseORM).filter_by(id=clause_id).one()
   30           return ClauseMapper.to_entity(orm_obj)

  ---

  3. Fragile External API Integration

   - Infrastructure Concern: The integration with the Claude API and Supabase appears to lack resilience patterns. There is no   
     mention of retry logic, circuit breakers, or graceful handling of connection pool exhaustion.
   - Hexagonal Principle Violated: Adapter Resilience. Adapters are responsible for robustly handling the unreliability of the   
     outside world. An adapter that fails on the first transient network error is not fulfilling its duty.
   - Resilience Risk:
       - Claude API: A temporary rate-limiting response (HTTP 429) or a server-side error (HTTP 5xx) will cause the entire       
         operation to fail permanently instead of recovering through retries.
       - Supabase: A spike in traffic could exhaust the connection pool, causing new requests to hang or fail ungracefully,      
         potentially cascading failures throughout the system.
   - Contract Test Gap: There are likely no tests that simulate API failures (e.g., by using a mock server like requests-mock) to
     verify that the retry and circuit breaker logic works as expected.
   - Recommended Adapter Pattern: Incorporate resilience libraries like tenacity for retries and a simple circuit breaker        
     implementation within the adapter.

    1   import httpx
    2   from tenacity import retry, stop_after_attempt, wait_exponential
    3
    4   class ClaudeAIProvider(AIProvider):
    5       def __init__(self, api_key: str, model: str):
    6           self.client = httpx.Client(...)
    7           # Simple circuit breaker state
    8           self.is_circuit_open = False
    9           self.failure_count = 0
   10
   11       @retry(wait=wait_exponential(multiplier=1, min=2, max=60), stop=stop_after_attempt(5))
   12       def extract_entities_from_document(self, document_text: str) -> ExtractionResult:
   13           if self.is_circuit_open:
   14               raise Exception("Circuit is open.")
   15
   16           try:
   17               response = self.client.post(...)
   18               response.raise_for_status() # Raises HTTPError for 4xx/5xx
   19               self.failure_count = 0 # Reset on success
   20               return ExtractionResult(...)
   21           except httpx.HTTPStatusError as e:
   22               if e.response.status_code in [429, 500, 502, 503, 504]:
   23                   self.failure_count += 1
   24                   if self.failure_count > 3:
   25                       self.is_circuit_open = True
   26                   raise # Re-raise to trigger tenacity retry
   27               else:
   28                   # Don't retry on client errors like 400
   29                   self.is_circuit_open = True # Open circuit on fatal error
   30                   raise

  ---

  4. Dual-Write Inconsistency & Storage Strategy

   - Infrastructure Concern: The system performs separate writes to R2 (for document blobs) and PostgreSQL (for metadata), a     
     "dual write" scenario that is not atomic. If the database write fails after the R2 upload, an orphaned file is created.     
   - Hexagonal Principle Violated: Transactional Integrity. An adapter's operation should be transactionally consistent from the 
     application's perspective. The current implementation exposes a leaky, non-atomic operation.
   - Resilience Risk: Data Inconsistency and Orphaned Files. The system can get into a state where files exist in R2 with no     
     corresponding metadata in the database, leading to "lost" data and storage bloat.
   - Contract Test Gap: Tests are needed to simulate a database failure after a successful storage upload to ensure the system   
     handles this failure state correctly (e.g., by logging the orphaned file for cleanup).
   - Recommended Adapter Pattern: Use the Transactional Outbox pattern. The primary database transaction writes the metadata and 
     an "event" to an outbox table. A separate, reliable process reads from the outbox and performs the side effect (uploading to
     R2).

    1   # In an Application Service method:
    2   def create_document(self, file_content: bytes, name: str):
    3       # 1. Create domain entity
    4       document = Document(name=name, status="PENDING_UPLOAD")
    5
    6       with self.uow.begin() as transaction:
    7           # 2. Save metadata to DB
    8           self.document_repo.add(document)
    9
   10           # 3. Save event to outbox table IN THE SAME TRANSACTION
   11           event = DocumentCreatedEvent(document_id=document.id, file_name=name)
   12           self.outbox.add(event)
   13
   14           transaction.commit()
   15
   16   # A separate background worker/poller:
   17   def process_outbox_events():
   18       events = outbox_repo.get_unprocessed_events()
   19       for event in events:
   20           try:
   21               # 4. Perform the external action (the "dual write")
   22               file_content = ... # retrieve content
   23               r2_adapter.upload(file_content, event.file_name)
   24
   25               # 5. Update document status
   26               document_repo.update_status(event.document_id, "UPLOADED")
   27
   28               # 6. Mark event as processed
   29               outbox_repo.mark_as_processed(event.id)
   30           except Exception as e:
   31               # Log error and retry later
   32               pass

  ---

  5. Duplicated & Potentially Divergent Security Logic

   - Infrastructure Concern: The system uses both application-level validation (in FastAPI and MCP servers) and database-level   
     Row-Level Security (RLS). While good for defense-in-depth, this creates two sources of security policy that can drift apart.
   - Hexagonal Principle Violated: Single Source of Truth. The authorization policy should have a single, unambiguous source.    
     Maintaining it in two separate places manually is error-prone.
   - Resilience Risk: Security Gaps. If a new access rule is added to the application but not to the RLS policies, a user with   
     direct database access (or a bug in another part of the app) could bypass the intended security. The source of truth for    
     authorization is ambiguous.
   - Contract Test Gap: There should be tests that:
       1. Verify application-layer security denies access as expected.
       2. Verify that even if application security is bypassed, RLS policies still prevent data access. This requires tests that 
          run queries directly against the database with specific user roles.
   - Recommended Adapter Pattern:
       1. Define policies in one place: Use a declarative authorization library (like Casbin or Oso) or a clear Python module to 
          define all access control policies. This module becomes the single source of truth.
       2. Generate RLS from the source of truth: Create a script that runs during your CI/CD pipeline. This script reads your    
          policy definitions and programmatically generates/updates the SQL ALTER TABLE ... ENABLE ROW LEVEL SECURITY and CREATE 
          POLICY ... commands.
       3. This ensures that your RLS rules in PostgreSQL are an adapter-level implementation of the central authorization        


Agent Architecture Issue: 8‑agent design is mostly documentation; actual orchestration only routes risk_extractor and
  wbs_extractor (plus budget stub) via LangGraph.                                                                                
  Multi-Agent Pattern Violated: Orchestration (promised) vs. partial linear flow (implemented).                                  
  Production Risk: Operators expect clause/stakeholder/BOM/RACI/alert routing, but system runs a different pipeline; gaps will   
  surface as missing artifacts and broken workflows.                                                                             
  Recommended Agent Design: Define an AgentPort with name, inputs, outputs, can_retry, can_request_human_help, and cost_budget.  
  Each agent should wrap concrete services and expose explicit autonomy boundaries.                                              
  LangGraph Implementation: Build a graph that models actual dependencies (Clause → Stakeholder/WBS; WBS → BOM; Stakeholder+WBS →  RACI; Coherence → Alerts) and gates human‑approval nodes before persistence.                                                   
                                                                                                                                 
  Agent Architecture Issue: “ContractParserAgent” and “CoherenceCheckerAgent” look like thin wrappers or deterministic rules; not  agents with autonomy.                                                                                                          
  Multi-Agent Pattern Violated: Agent pattern vs. function/service wrapper (no decision‑making, no goal selection).              
  Production Risk: Teams will over‑attribute reliability to “agents,” but they behave like synchronous functions; failures won’t 
  be contained or retried meaningfully.                                                                                          
  Recommended Agent Design: Separate “service” (deterministic parser) from “agent” (LLM‑mediated planner/extractor that can      
  decide to ask for more context or request approval).                                                                           
  LangGraph Implementation: Use deterministic services as nodes without LLM cost; reserve LLM nodes for tasks that genuinely     
  require inference.                                                                                                             
                                                                                                                                 
  Agent Architecture Issue: Orchestration is single‑threaded with no parallelism; no explicit state machine for 8 agents.        
  Multi-Agent Pattern Violated: Orchestration/blackboard expectations vs. linear chain.                                          
  Production Risk: Latency spikes; inability to run independent agents (e.g., Clause vs Stakeholder) in parallel; costly         
  sequential LLM calls.                                                                                                          
  Recommended Agent Design: Encode dependencies and allow parallel branches where safe (Clause extraction and Contract parsing   
  can run concurrently; Stakeholder and WBS can run after clauses).                                                              
  LangGraph Implementation: Use StateGraph with parallel edges and a merge/join node that collects partial results.              
                                                                                                                                 
  Agent Architecture Issue: Agent communication is implicit shared state (LangGraph state dict) and direct calls; no events or   
  message broker.                                                                                                                
  Multi-Agent Pattern Violated: Blackboard is implied but not formalized; no event-driven contracts.                             
  Production Risk: Hidden coupling; hard to replay or isolate agent outputs; failure propagation is opaque.                      
  Recommended Agent Design: Define a shared “project analysis state” schema and immutable agent outputs (append-only), with      
  explicit event records.                                                                                                        
  LangGraph Implementation: Use messages + explicit result fields per agent; add a persistence node that snapshots each agent    
  output with correlation IDs.                                                                                                   
                                                                                                                                 
  Agent Architecture Issue: Failure handling is shallow; only generic AIServiceError and retry-on-invalid-JSON. No hallucination 
  detection or agent-level retry policy.                                                                                         
  Multi-Agent Pattern Violated: Orchestration without compensation.                                                              
  Production Risk: A single hallucinated clause contaminates downstream outputs; no quarantine or human escalation path beyond a 
  generic interrupt.                                                                                                             
  Recommended Agent Design: Add validation gates per agent (schema + rule checks). Introduce ExtractionFailedError/              
  HallucinationSuspectedError and a “repair” step.
  LangGraph Implementation: Add validator nodes after each extraction; route to human_review or repair based on confidence and   
  validation scores.                                                                                                             
                                                                                                                                 
  Agent Architecture Issue: Human‑in‑loop is inconsistent; only stakeholders and alerts have approval fields. WBS/BOM/RACI lack  
  approval state in data models.
  Multi-Agent Pattern Violated: Orchestration without approval workflow state machine.                                           
  Production Risk: “approval required” in docs won’t be enforceable; downstream systems may act on unapproved outputs.           
  Recommended Agent Design: Introduce ApprovalStatus for WBS/BOM/RACI, unify review endpoint, and block downstream use until     
  approved.
  LangGraph Implementation: Add approval gates that pause the workflow and resume via explicit resume_orchestration endpoint.    
                                                                                                                                 
  Agent Architecture Issue: Prompt management is fragmented; prompts are hardcoded in agent files and nodes.                     
  Multi-Agent Pattern Violated: Orchestration without prompt version control.                                                    
  Production Risk: Reproducibility and auditability are weak; prompt_version in logs is meaningless if prompts aren’t centrally  
  versioned.
  Recommended Agent Design: Central prompt registry with semantic versioning and release notes; log prompt_version per agent     
  call.                                                                                                                          
  LangGraph Implementation: Inject prompt_id and prompt_version into every node call and include in state.                       

  Agent Architecture Issue: Cost control exists at AI service level, but orchestration doesn’t enforce a cumulative budget       
  mid‑analysis.                                                                                                                  
  Multi-Agent Pattern Violated: Orchestration without budget governance.                                                         
  Production Risk: Chain calls can exhaust tenant budget mid‑flow; partial outputs persisted without a consistent “budget        
  exhausted” state.                                                                                                              
  Recommended Agent Design: Add a “cost governor” that halts or degrades to cheaper models when budget crosses a threshold.      
  LangGraph Implementation: Pre‑flight node checks remaining_budget; branch to a cheaper model or abort node if threshold        
  crossed.                                                                                                                       
                                                                                                                                 
  Agent Architecture Issue: Observability is limited; correlation IDs are not propagated through agent calls; replay isn’t       
  first‑class.                                                                                                                   
  Multi-Agent Pattern Violated: Orchestration without traceability.
  Production Risk: Debugging multi‑agent failures is slow; cannot replay failures with same inputs.                              
  Recommended Agent Design: Enforce trace_id + run_id on every node; persist inputs/outputs to an audit log.                     
  LangGraph Implementation: Include trace_id in ProjectState, persist per-node snapshots, and add replay utility using stored    
  state.                                                                                                                         
                                                                                                                                 
  Agent Architecture Issue: The “StakeholderExtractor” example is a service shape (no autonomy or policy) and requires clauses as  input.                                                                                                                         
  Multi-Agent Pattern Violated: Orchestration vs. direct coupling (service depends on previous agent output).                    
  Production Risk: Tight coupling means failures upstream silently break stakeholder extraction.                                 
  Recommended Agent Design: Make StakeholderExtractorAgent accept a ClauseSet produced by the Clause agent; include a fallback   
  path that fetches clauses from DB if not present.                                                                              

  Agent Architecture Issue: “ImplicitNeedsInferrer” is experimental but no architectural boundary exists.
  Multi-Agent Pattern Violated: Orchestration without feature flags or isolated lanes.
  Production Risk: Experimental behavior leaks into production flows, inflating cost and creating inconsistent outputs.
  Recommended Agent Design: Gate experimental agents behind feature flags and isolate into an “advisory” branch that cannot      
  mutate core outputs.
  LangGraph Implementation: Add if feature_flag conditional edge; advisory outputs go to a separate “insights” collection only.  

  If you want, I can map the actual LangGraph nodes and propose a concrete graph with parallel branches and approval gates using 
  the existing code structure.


As an AI Systems Architect, I've reviewed your multi-agent design. Your skepticism is well-founded. The current architecture,  
  while logically structured, exhibits several patterns that are common in early-stage agentic systems but pose significant risks
  to production stability, scalability, and cost control.

  The core issue is a conflation of terms: what are labeled "agents" appear to be services or functions, and what is described as
  "orchestration" is a rigid, linear pipeline. This is not a multi-agent system in the true sense, but a sequence of LLM-powered 
  function calls.

  Here is a breakdown of the critical issues and my recommendations for building a more robust, production-ready system.

  ---

  1. "Agents" as Glorified Functions

   - Agent Architecture Issue: The agents (e.g., ContractParserAgent, CoherenceCheckerAgent) lack autonomy and decision-making   
     capabilities. They appear to be stateless services that execute a single, well-defined task (text -> structured_data). An   
     "agent" that cannot make decisions about how or if to act is simply a tool or a function. Using an LLM like Haiku for what  
     are described as "deterministic rules" is a particularly concerning architectural smell—it's expensive, slow, and introduces
     non-determinism where none is needed.
   - Multi-Agent Pattern Violated: Agent Autonomy. A true agent possesses a degree of autonomy; it perceives its environment (the
     current state of the analysis) and acts upon it to achieve its goals. A simple function call does not meet this bar.        
   - Production Risk: High Latency & Cost; Reduced Predictability. Using LLMs for deterministic tasks is a massive waste of      
     tokens and adds seconds of latency. It also makes the system's behavior less predictable. If a simple rule could be if      
     'force majeure' in clause.text: return True, using an LLM for this is architectural overkill.
   - Recommended Agent Design: An agent should be a stateful object responsible for achieving an outcome, with the ability to use
     tools (which can be LLMs or deterministic code) to do so. The decision logic should be separated from the tool itself.      

    1   # A Tool (could be an LLM call or a simple function)
    2   def parse_clauses_with_llm(text: str) -> list[dict]:
    3       # ... call Sonnet 4 ...
    4       return llm_output
    5
    6   # A deterministic rule-based tool
    7   def check_for_indemnity_clause(clauses: list[Clause]) -> list[Alert]:
    8       alerts = []
    9       for clause in clauses:
   10           if "indemnify" in clause.text.lower():
   11               alerts.append(Alert(type="IndemnityClauseFound", ...))
   12       return alerts
   13
   14   # A true Agent that USES tools
   15   class CoherenceCheckingAgent:
   16       def __init__(self):
   17           self.llm_tool = parse_clauses_with_llm
   18           self.rule_tool = check_for_indemnity_clause
   19
   20       def run(self, state: dict) -> dict:
   21           """Decides which tools to use based on the state."""
   22           clauses = state['clauses']
   23
   24           # Use a cheap, deterministic rule first
   25           rule_based_alerts = self.rule_tool(clauses)
   26
   27           # Only use the expensive LLM if necessary
   28           llm_based_alerts = []
   29           if state.get("deep_scan_required", False):
   30               # llm_based_alerts = self.llm_tool(...)
   31               pass
   32
   33           # Update the state with the results
   34           all_alerts = rule_based_alerts + llm_based_alerts
   35           return {"alerts": state.get("alerts", []) + all_alerts}
   - LangGraph Implementation: In LangGraph, this translates to having multiple, smaller nodes. One node could be
     run_deterministic_rules, and a conditional edge could decide whether to proceed to an run_llm_coherence_check node based on 
     the output of the first. Don't create one giant "agent" node; create nodes for the discrete tasks.

  ---

  2. Primitive Orchestration vs. True Graph Execution

   - Agent Architecture Issue: The flow is described as a linear chain, which is a brittle orchestration pattern. It does not    
     allow for parallelism, cycles, or dynamic routing based on the content of the analysis. What happens if the
     WBSGeneratorAgent determines a clause is ambiguous and needs re-parsing by the ClauseExtractorAgent? A linear chain cannot  
     handle this.
   - Multi-Agent Pattern Violated: Orchestration. The system uses a simple sequential orchestration pattern, failing to leverage 
     the power of a graph-based approach that allows for more complex and resilient interactions.
   - Production Risk: Inefficiency and Rigidity. Agents that could run in parallel (e.g., StakeholderExtractorAgent and
     WBSGeneratorAgent might both be able to run once clauses are extracted) are forced to run sequentially, increasing total    
     latency. The system cannot recover from mid-process errors or dynamically adjust its strategy.
   - Recommended Agent Design: The overall analysis should be managed by a "Supervisor" or "Orchestrator" graph. Each "agent" is 
     a worker node in this graph. The state of the analysis is passed between them, and the edges of the graph define the        
     workflow.
   - LangGraph Implementation: This is precisely what LangGraph is designed for.

    1   from typing import TypedDict, Annotated
    2   from langgraph.graph import StateGraph, END
    3
    4   class AnalysisState(TypedDict):
    5       document_id: str
    6       raw_text: str
    7       clauses: list
    8       stakeholders: list
    9       wbs_items: list
   10       alerts: list
   11       # Add cost and trace information
   12       run_cost: float
   13       trace_id: str
   14
   15   workflow = StateGraph(AnalysisState)
   16
   17   # Nodes are the agents/services
   18   workflow.add_node("parse_contract", contract_parser_agent.run)
   19   workflow.add_node("extract_clauses", clause_extractor_agent.run)
   20   workflow.add_node("extract_stakeholders", stakeholder_extractor_agent.run)
   21   workflow.add_node("generate_wbs", wbs_generator_agent.run)
   22   workflow.add_node("check_coherence", coherence_checker_agent.run)
   23
   24   # The graph defines the flow
   25   workflow.set_entry_point("parse_contract")
   26   workflow.add_edge("parse_contract", "extract_clauses")
   27
   28   # After clauses are extracted, two agents can run in parallel
   29   workflow.add_edge("extract_clauses", "extract_stakeholders")
   30   workflow.add_edge("extract_clauses", "generate_wbs")
   31
   32   # Conditional routing based on state
   33   def should_run_coherence(state: AnalysisState) -> str:
   34       if state["wbs_items"] and state["stakeholders"]:
   35           return "run_coherence_check"
   36       else:
   37           # Wait for other branches to finish
   38           return "wait"
   39
   40   # This creates a more complex, non-linear flow
   41   # This part is conceptual; actual parallel execution requires more setup
   42   # But LangGraph supports conditional edges which is the key point.
   43   # A real implementation might merge parallel outputs back into a single node.
   44
   45   app = workflow.compile()

  ---

  3. Tightly Coupled Communication

   - Agent Architecture Issue: The use of MCP suggests a synchronous, RPC-style communication pattern. One agent directly calls  
     another (as a "tool"). This creates tight temporal coupling; the caller must wait for the callee to respond.
   - Multi-Agent Pattern Violated: Choreography & Blackboard. A more scalable and decoupled pattern is to have agents communicate
     asynchronously, either through a message bus (Choreography) or by reading/writing to a shared state object (Blackboard      
     pattern).
   - Production Risk: Cascading Failures. If AlertRouterAgent synchronously calls CoherenceCheckerAgent and it is slow or fails, 
     the AlertRouterAgent also fails. This tight coupling makes the system brittle.
   - Recommended Agent Design: Agents should not call each other directly. They should read from a shared state, perform their   
     function, and write their results back to that state. The orchestrator (LangGraph) is responsible for invoking the next     
     agent based on the changes to the state.
   - LangGraph Implementation: The AnalysisState dictionary in the example above is the Blackboard. Each node reads from the     
     state, does its work, and returns a dictionary of keys to update in the state. LangGraph handles merging the updates. This  
     decouples the agents completely; extract_stakeholders has no knowledge of the generate_wbs agent.

  ---

  4. Lack of Robust State Validation & Failure Handling

   - Agent Architecture Issue: There is no clear validation step. If ClauseExtractorAgent hallucinates, the error propagates     
     downstream, poisoning the entire analysis. Agent-level retry is mentioned, but what if the error is deterministic (e.g., a  
     malformed input)? Retrying will just waste money.
   - Multi-Agent Pattern Violated: Self-Healing / Fault Tolerance. A robust system must be able to detect, isolate, and
     potentially recover from faults. This includes validating outputs from untrusted sources (like LLMs).
   - Production Risk: Garbage In, Garbage Out. A single hallucinated clause ID could lead to incorrect WBS items, phantom        
     stakeholders, and nonsensical alerts, eroding user trust. The cost of a looping agent could be catastrophic, easily blowing 
     through a tenant's monthly budget in minutes.
   - Recommended Agent Design:
       1. Validation Nodes: After any node that uses an LLM for extraction, add a "validation" node. This node can use cheaper   
          models, regexes, or deterministic checks to ensure the output conforms to the expected schema and constraints (e.g.,   
          "does this clause_id actually exist?").
       2. Human-in-the-Loop as a Node: A HITL step should be a dedicated node in the graph (e.g., await_human_approval).
          LangGraph can be suspended and resumed.
       3. Circuit Breakers: Implement a circuit breaker at the agent level. If an agent fails N times in a row on the same input,
          break the circuit, mark the analysis as failed, and escalate to a human.
   - LangGraph Implementation:
    1   def validate_clauses(state: AnalysisState) -> str:
    2       clauses = state["clauses"]
    3       # ... run validation logic ...
    4       if validation_fails:
    5           return "request_human_review" # A different edge
    6       return "continue_analysis"
    7
    8   workflow.add_node("validate_clauses", validate_clauses)
    9   workflow.add_edge("extract_clauses", "validate_clauses")
   10
   11   # Conditional edge based on validation result
   12   workflow.add_conditional_edges(
   13       "validate_clauses",
   14       validate_clauses,
   15       {
   16           "request_human_review": "human_review_node",
   17           "continue_analysis": "extract_stakeholders", # Or next step
   18       }
   19   )

  ---

  5. Centralized State and Governance

   - Agent Architecture Issue: There's no central nervous system for the analysis. Critical cross-cutting concerns like cost
     tracking, observability, and prompt management are either missing or managed implicitly.
   - Multi-Agent Pattern Violated: System Governance. A multi-agent system requires a governance layer to monitor, control, and
     ensure the overall system is meeting its objectives without violating constraints (like budget).
   - Production Risk: Runaway Costs & Un-debuggable Failures. Without a centralized state tracking the cumulative cost, an
     analysis can easily exceed its budget. Without a unique trace ID and structured logging for each step, debugging a failure
     across 8 agents is nearly impossible.
   - Recommended Agent Design: All cross-cutting concerns should be managed in the central state and by the orchestrator graph
     itself, not by individual agents.
   - LangGraph Implementation: The AnalysisState is the perfect place for this.

    1   class AnalysisState(TypedDict):
    2       # ... (previous fields)
    3       # Governance fields
    4       run_cost: float
    5       trace_id: str
    6       prompt_versions: dict[str, str]
    7       step_history: list[str]
    8       tenant_budget: float
    9
   10   # Every node in the graph is now wrapped to update cost
   11   def agent_wrapper(agent_func, agent_name: str, state: AnalysisState) -> AnalysisState:
   12       # Before running
   13       if state["run_cost"] > state["tenant_budget"]:
   14           raise Exception("Budget exceeded")
   15
   16       # Run the agent
   17       result = agent_func(state)
   18
   19       # After running
   20       cost_of_this_step = calculate_cost(result) # from token usage
   21       result["run_cost"] = state["run_cost"] + cost_of_this_step
   22       result["step_history"] = state["step_history"] + [agent_name]
   23
   24       return result
   25
   26   # Then use this wrapper when adding nodes
   27   workflow.add_node("parse_contract", lambda s: agent_wrapper(parser.run, "parser", s))

    Technical Debt Item: No explicit microservice extraction criteria or readiness signals in code; MCP is present but core remains
  monolith.                                                                                                                      
  Category: Architecture                                                                                                         
  Current Impact: Teams can’t agree when to extract services; duplication and coupling grow.                                     
  Future Impact: Extraction becomes reactive, riskier, and more expensive once load spikes.                                      
  Remediation Cost: M                                                                                                            
  Recommended Action: Plan for Phase 2                                                                                           
                                                                                                                                 
  Technical Debt Item: Multi-agent roadmap exceeds current orchestration; actual LangGraph flow handles only risk/WBS/budget.    
  Category: Architecture                                                                                                         
  Current Impact: Feature expectations exceed implementation; partial outputs and inconsistent workflows.                        
  Future Impact: Rework required to align system to roadmap; higher defect rate.                                                 
  Remediation Cost: L                                                                                                            
  Recommended Action: Plan for Phase 2                                                                                           
                                                                                                                                 
  Technical Debt Item: In-process events are referenced but no event bus or outbox pattern implemented.                          
  Category: Architecture                                                                                                         
  Current Impact: Async workflows depend on direct calls; limited decoupling.                                                    
  Future Impact: Scaling and reliability suffer; retries/ordering become ad‑hoc.                                                 
  Remediation Cost: M
  Recommended Action: Plan for Phase 2                                                                                           
                                                                                                                                 
  Technical Debt Item: AI calls are synchronous from FastAPI; no queue between HTTP and LLM.                                     
  Category: Architecture                                                                                                         
  Current Impact: Request latency spikes and API timeouts during heavy LLM usage.                                                
  Future Impact: Rate limiting and cost governance become inconsistent under load.                                               
  Remediation Cost: L                                                                                                            
  Recommended Action: Plan for Phase 2                                                                                           
                                                                                                                                 
  Technical Debt Item: Document ingestion tasks use mock DB/storage; task flow not wired to real persistence.                    
  Category: Code                                                                                                                 
  Current Impact: Asynchronous path is not production‑ready; tests don’t reflect reality.                                        
  Future Impact: Ingestion pipeline breaks in production; operational incidents.                                                 
  Remediation Cost: M                                                                                                            
  Recommended Action: Fix now                                                                                                    
                                                                                                                                 
  Technical Debt Item: Approval workflow is partial (Stakeholders/Alerts), not applied to WBS/BOM/RACI.                          
  Category: Architecture                                                                                                         
  Current Impact: Human‑in‑loop requirements can’t be enforced end‑to‑end.
  Future Impact: Compliance risk and inconsistent data provenance.                                                               
  Remediation Cost: M                                                                                                            
  Recommended Action: Plan for Phase 2                                                                                           
                                                                                                                                 
  Technical Debt Item: DTOs mix API and domain concepts; use cases aren’t explicit.                                              
  Category: Architecture                                                                                                         
  Current Impact: Hard to test core logic without HTTP adapters.                                                                 
  Future Impact: Refactors slow down; domain changes ripple to API.                                                              
  Remediation Cost: M                                                                                                            
  Recommended Action: Plan for Phase 2                                                                                           
                                                                                                                                 
  Technical Debt Item: Error taxonomy is incomplete vs docs (no InfraError); routers still raise HTTPException directly.         
  Category: Code                                                                                                                 
  Current Impact: Inconsistent error semantics across layers.                                                                    
  Future Impact: Harder to unify retries, observability, and SLAs.                                                               
  Remediation Cost: S                                                                                                            
  Recommended Action: Fix now                                                                                                    
                                                                                                                                 
  Technical Debt Item: Prompt storage is hardcoded in agent and node files; prompt versioning not centralized.                   
  Category: Process                                                                                                              
  Current Impact: Reproducibility and auditability are weak.                                                                     
  Future Impact: Inability to diagnose regressions or comply with audit needs.                                                   
  Remediation Cost: M                                                                                                            
  Recommended Action: Plan for Phase 2                                                                                           
                                                                                                                                 
  Technical Debt Item: NetworkX graph scaling risks not instrumented; ADR threshold not monitored.                               
  Category: Architecture                                                                                                         
  Current Impact: No automatic signal for the migration trigger (50K nodes/1s latency).                                          
  Future Impact: Performance cliff without warning.                                                                              
  Remediation Cost: M                                                                                                            
  Recommended Action: Plan for Phase 2                                                                                           
                                                                                                                                 
  Technical Debt Item: No visible Neo4j migration tooling or data export pipeline.                                               
  Category: Architecture                                                                                                         
  Current Impact: Migration path is conceptual only.                                                                             
  Future Impact: Emergency migration likely if scaling threshold hit.                                                            
  Remediation Cost: L                                                                                                            
  Recommended Action: Plan for Phase 3                                                                                           
                                                                                                                                 
  Technical Debt Item: Knowledge graph stored in relational DB with JSONB; likely adequate now but may hurt query performance    
  later.                                                                                                                         
  Category: Architecture                                                                                                         
  Current Impact: Acceptable for MVP; complex queries may be slow.                                                               
  Future Impact: Query cost and latency growth with graph size.                                                                  
  Remediation Cost: M                                                                                                            
  Recommended Action: Plan for Phase 3                                                                                           
                                                                                                                                 
  Technical Debt Item: Observability gate is partial; correlation IDs not propagated across AI orchestration.                    
  Category: Process
  Current Impact: Debugging multi‑agent runs is slow.                                                                            
  Future Impact: Incidents become hard to root‑cause; SLA breaches.                                                              
  Remediation Cost: M                                                                                                            
  Recommended Action: Fix now                                                                                                    
                                                                                                                                 
  Technical Debt Item: Frontend/back‑end contract relies on Pydantic schemas but no explicit shared type pipeline is visible.    
  Category: Documentation                                                                                                        
  Current Impact: Frontend devs must infer API changes.                                                                          
  Future Impact: Breaking changes slip into production.                                                                          
  Remediation Cost: S                                                                                                            
  Recommended Action: Fix now                                                                                                    
                                                                                                                                 
  Technical Debt Item: Testing pyramid is inverted (mostly security tests).                                                      
  Category: Testing                                                                                                              
  Current Impact: Core business logic coverage is low.                                                                           
  Future Impact: Regressions likely during evolution.                                                                            
  Remediation Cost: M                                                                                                            
  Recommended Action: Plan for Phase 2
                                                                                                                                 
  Technical Debt Item: ADRs are referenced, but architecture model lacks formal C4 diagrams.                                     
  Category: Documentation                                                                                                        
  Current Impact: Shared understanding depends on ASCII diagrams and tribal knowledge.                                           
  Future Impact: Onboarding and external audits slow down.                                                                       
  Remediation Cost: S                                                                                                            
  Recommended Action: Plan for Phase 2                                                                                           
                                                                                                                                 
  If you want, I can:                                                                                                            
                                                                                                                                 
  1. produce a microservice extraction decision matrix (Auth vs Document Processing vs AI Inference),                            
  2. define concrete KPI thresholds for NetworkX migration, and                                                                  
  3. draft a minimal outbox/eventing plan that keeps the monolith but adds reliable async boundaries.   
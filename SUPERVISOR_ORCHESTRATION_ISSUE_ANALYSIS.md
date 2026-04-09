# Supervisor Orchestration Issue — Analysis and Fix Options

**Date**: 2026-04-05
**Issue**: Supervisor execution fails with "ERROR: Desconocido"
**Context**: Attempting to run E2E backend testing via `python core/supervisor.py "E2E on backend" --modo auto`

---

## 1. WHAT is the Issue?

The C2Pro Supervisor (`core/supervisor.py`) is failing to execute because it cannot find the required external CLI tools in the system PATH.

### Error Flow:

```bash
$ python core/supervisor.py "E2E on backend" --modo auto

[SUPERVISOR] Ejecutando: claude para rol 'planner'
ERROR: Desconocido
```

### Root Cause:

The supervisor tried to execute the command `claude` as a subprocess but got a `FileNotFoundError` exception (line 652-657 in supervisor.py), which was caught and returned as `{"success": False, "error": "Desconocido"}`.

---

## 2. WHY is this Happening?

### Architecture Design:

The C2Pro Supervisor is designed as a **CLI orchestrator**, NOT a direct executor. It coordinates multiple external AI assistant CLI tools to implement a multi-agent system.

### The Execution Chain:

```
┌─────────────────────────────────────────────────────────────────┐
│ supervisor.py                                                   │
│                                                                 │
│  1. Reads session_config.json                                  │
│     → planner: "claude_code"                                   │
│     → backend: "codex_cli"                                     │
│     → qa: "gemini_cli"                                         │
│                                                                 │
│  2. Reads models.yaml                                          │
│     → claude_code: cli_command = "claude"                      │
│     → codex_cli: cli_command = "codex"                         │
│     → gemini_cli: cli_command = "gemini"                       │
│                                                                 │
│  3. Builds command (invocar_rol function, line 592)           │
│     → construir_comando() builds CLI invocation                │
│                                                                 │
│  4. Executes via subprocess.run() (line 628)                  │
│     → subprocess.run(["claude", "--system-prompt", ...])       │
│     → FAILS: FileNotFoundError — 'claude' not in PATH         │
└─────────────────────────────────────────────────────────────────┘
```

### Configuration Files Involved:

**`core/session_config.json`** — Role-to-Model Mapping:
```json
{
  "roles": {
    "planner": "claude_code",    ← Maps planner role to claude_code model
    "backend": "codex_cli",       ← Maps backend role to codex_cli model
    "frontend": "gemini_cli",
    ...
  }
}
```

**`core/models.yaml`** — Model-to-CLI Mapping:
```yaml
models:
  claude_code:
    cli_command: "claude"        ← Expects 'claude' command in PATH
    formato_invocacion: '{cli} --system-prompt "{profile}" --prompt "{prompt}"'

  codex_cli:
    cli_command: "codex"         ← Expects 'codex' command in PATH
    formato_invocacion: '{cli} --instructions "{profile}" --prompt "{prompt}"'

  gemini_cli:
    cli_command: "gemini"        ← Expects 'gemini' command in PATH
    formato_invocacion: '{cli} --system-instruction "{profile}" --prompt "{prompt}"'
```

### The Problem:

**None of these CLI tools exist in the system PATH:**

```bash
$ which claude
# Not found

$ which codex
# Not found

$ which gemini
# Not found
```

When the supervisor tries to execute `subprocess.run(["claude", ...])`, Python raises a `FileNotFoundError`, which is caught at line 652 and returns a generic error.

---

## 3. HOW to Fix — Multiple Options

### Option 1: Install the Required CLI Tools ⭐ (Recommended for Production)

**Approach**: Install the actual CLI tools that the supervisor expects.

**Steps**:

1. **Claude Code CLI** (Anthropic):
   ```bash
   # Install Claude Code CLI
   npm install -g @anthropic-ai/claude-code

   # Or download from https://claude.ai/code

   # Verify installation
   claude --version
   ```

2. **OpenAI Codex CLI**:
   ```bash
   # Install OpenAI CLI (if codex is available as a plugin)
   pip install openai-cli

   # Or use 'openai' command if codex is integrated

   # Verify installation
   codex --version  # or openai --version
   ```

3. **Google Gemini CLI**:
   ```bash
   # Install Google AI CLI
   pip install google-generativeai

   # Configure with API key
   export GOOGLE_API_KEY="your_api_key"

   # Verify installation
   gemini --version
   ```

**Pros**:
- ✅ Uses the supervisor as originally designed
- ✅ True multi-agent orchestration with different AI models
- ✅ Leverages strengths of each model (Claude for planning, Codex for code, Gemini for QA)

**Cons**:
- ❌ Requires installing 3 different CLI tools
- ❌ Requires API keys for Anthropic, OpenAI, Google
- ❌ Potential cost for API usage
- ❌ Some CLIs may not exist (e.g., "codex" as standalone CLI)

---

### Option 2: Modify Supervisor to Use a Single Available CLI

**Approach**: Change all role assignments to use ONE CLI that IS available (e.g., `python` script).

**Steps**:

1. **Check what IS available**:
   ```bash
   which python  # ✓ Available
   which claude  # ✗ Not available
   ```

2. **Create a Python-based agent executor**:
   ```bash
   # Create core/agents/python_agent.py
   ```

   ```python
   # python_agent.py
   import sys
   import anthropic  # or openai, or google.generativeai

   def main():
       role = sys.argv[1]
       prompt = sys.argv[2]

       # Call Anthropic API directly
       client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
       response = client.messages.create(
           model="claude-sonnet-4-20250514",
           max_tokens=4096,
           messages=[{"role": "user", "content": prompt}]
       )

       print(response.content[0].text)

   if __name__ == "__main__":
       main()
   ```

3. **Update `models.yaml`**:
   ```yaml
   models:
     python_agent:
       cli_command: "python"
       vendor: "Custom"
       modelo: "claude-sonnet-4-20250514"
       formato_invocacion: 'python core/agents/python_agent.py {role} "{prompt}"'
   ```

4. **Update `session_config.json`**:
   ```json
   {
     "roles": {
       "planner": "python_agent",
       "backend": "python_agent",
       "frontend": "python_agent",
       "ai": "python_agent",
       "infra": "python_agent",
       "qa": "python_agent",
       "reviewer": "python_agent",
       "security": "python_agent",
       "devops": "python_agent"
     }
   }
   ```

**Pros**:
- ✅ Uses existing Python installation
- ✅ Full control over API calls
- ✅ Can use environment variables for API keys
- ✅ Works immediately without installing new CLIs

**Cons**:
- ❌ Loses multi-model orchestration (all roles use same model)
- ❌ Requires implementing agent executor script
- ❌ Still requires API keys
- ❌ Still has API usage costs

---

### Option 3: Bypass Supervisor — Direct E2E Testing ⭐ (Fastest for Current Goal)

**Approach**: Skip the supervisor orchestration entirely and run E2E tests directly using pytest.

**Steps**:

1. **Use existing E2E test infrastructure**:
   ```bash
   # Run existing E2E tests
   pytest apps/api/tests/e2e/ -v

   # Run specific E2E workflow
   pytest apps/api/tests/e2e/flows/test_document_upload_to_coherence.py -v

   # Run all backend integration tests
   pytest apps/api/tests/ -m "not slow" -v
   ```

2. **Create new E2E test scenarios** (what we started before):
   ```python
   # apps/api/tests/e2e/flows/test_complete_backend_workflow.py

   @pytest.mark.asyncio
   async def test_complete_user_journey(client, auth_headers):
       """E2E: Complete user journey from registration to analysis."""

       # 1. Create project
       project_response = await client.post(
           "/api/v1/projects",
           json={"name": "Test Project", "description": "E2E test"},
           headers=auth_headers
       )
       assert project_response.status_code == 201
       project_id = project_response.json()["id"]

       # 2. Upload document
       with open("test_contract.pdf", "rb") as f:
           files = {"file": ("contract.pdf", f, "application/pdf")}
           doc_response = await client.post(
               f"/api/v1/projects/{project_id}/documents",
               files=files,
               headers=auth_headers
           )
       assert doc_response.status_code == 201
       document_id = doc_response.json()["id"]

       # 3. Run coherence analysis
       analysis_response = await client.post(
           f"/api/v1/coherence/analyze/{document_id}",
           headers=auth_headers
       )
       assert analysis_response.status_code == 202

       # 4. Poll for results
       # ... etc
   ```

3. **Run the new tests**:
   ```bash
   pytest apps/api/tests/e2e/flows/test_complete_backend_workflow.py -v
   ```

**Pros**:
- ✅ Works immediately with existing infrastructure
- ✅ No external CLI dependencies
- ✅ No API costs (uses test fixtures/mocks)
- ✅ Fast execution
- ✅ Standard pytest conventions
- ✅ Achieves the goal: "E2E on backend"

**Cons**:
- ❌ Doesn't use the supervisor orchestration
- ❌ Doesn't demonstrate multi-agent collaboration
- ❌ Tests are written manually, not generated by AI

---

### Option 4: Mock the External CLIs for Testing

**Approach**: Create mock CLI scripts that simulate the external tools.

**Steps**:

1. **Create mock scripts**:
   ```bash
   # Create bin/claude (mock)
   #!/bin/bash
   echo "Mock Claude response for E2E testing"
   echo "Task completed successfully"
   exit 0
   ```

2. **Make executable and add to PATH**:
   ```bash
   chmod +x bin/claude bin/codex bin/gemini
   export PATH="$PWD/bin:$PATH"
   ```

3. **Run supervisor**:
   ```bash
   python core/supervisor.py "E2E on backend" --modo auto
   ```

**Pros**:
- ✅ Tests supervisor orchestration logic
- ✅ No API costs
- ✅ Verifies subprocess execution flow

**Cons**:
- ❌ Mock responses don't actually perform work
- ❌ Doesn't test real AI integration
- ❌ Limited value for E2E testing

---

## 4. Recommended Solution Path

### For the Current Goal ("E2E on backend"):

**Choose Option 3** — Bypass Supervisor, Direct E2E Testing

**Rationale**:
1. **Fastest**: Works immediately with existing test infrastructure
2. **Most practical**: Achieves the stated goal without external dependencies
3. **Production-ready**: Follows standard pytest conventions
4. **Already exists**: E2E test structure is already in place (`apps/api/tests/e2e/`)

**Next Steps**:
1. Analyze existing E2E test coverage
2. Identify gaps in backend E2E testing
3. Create comprehensive E2E test scenarios
4. Run tests and generate coverage report

### For Future Supervisor Usage:

**Choose Option 2** — Python Agent Wrapper

**Rationale**:
1. Uses existing Python installation
2. Full control over API integration
3. Can be extended to support multiple models
4. Maintains supervisor orchestration design

**Implementation Plan**:
1. Create `core/agents/python_agent.py` wrapper
2. Update `models.yaml` to define `python_agent` model
3. Update `session_config.json` to use `python_agent` for all roles
4. Test with: `python core/supervisor.py "Test task" --modo auto`

---

## 5. Code References

### Relevant Files:

1. **`core/supervisor.py`**:
   - Line 592: `def invocar_rol()` — Invokes external CLIs
   - Line 628: `subprocess.run(cmd, ...)` — Actual subprocess execution
   - Line 652: `except FileNotFoundError` — Catches missing CLI error
   - Line 739: `ERROR: Desconocido` — Generic error message

2. **`core/session_config.json`**:
   - Lines 2-12: Role-to-model assignments
   - Shows planner → claude_code, backend → codex_cli, etc.

3. **`core/models.yaml`**:
   - Lines 11-30: `claude_code` model definition with `cli_command: "claude"`
   - Lines 32-49: `codex_cli` model definition with `cli_command: "codex"`
   - Lines 51-67: `gemini_cli` model definition with `cli_command: "gemini"`

4. **`apps/api/tests/e2e/`**:
   - Existing E2E test infrastructure
   - flows/, performance/, resilience/, security/ subdirectories
   - 15+ existing E2E test files

---

## 6. Decision Matrix

| Option | Speed | Cost | Complexity | Production Value | Achieves Goal |
|--------|-------|------|------------|------------------|---------------|
| **1. Install CLIs** | Slow | High | High | High | Yes |
| **2. Python Agent** | Medium | Medium | Medium | Medium | Yes |
| **3. Direct E2E Tests** | Fast | Low | Low | High | **Yes** ⭐ |
| **4. Mock CLIs** | Fast | Low | Low | Low | Partial |

**Recommendation**: **Option 3** for immediate E2E testing, **Option 2** for future supervisor usage.

---

## 7. Summary

**What**: Supervisor cannot execute because `claude`, `codex`, and `gemini` CLIs don't exist in PATH.

**Why**: The supervisor is designed as a CLI orchestrator that calls external AI assistant tools via `subprocess.run()`. These tools are not installed.

**How to Fix**:
- **Short-term (E2E testing goal)**: Use Option 3 — Direct E2E testing via pytest
- **Long-term (supervisor usage)**: Use Option 2 — Python agent wrapper with direct API calls

**Immediate Next Action**: Continue with E2E test analysis and implementation using Option 3.

---

**Date**: 2026-04-05
**Author**: Claude Sonnet 4.5 (Analysis Agent)
**Related Files**: `core/supervisor.py`, `core/models.yaml`, `core/session_config.json`

"""
Manual test script for validating tool implementation.

Run with:
    python -m tests.manual.test_tools_implementation
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_imports():
    """Test that all tool imports work correctly."""
    print("\n" + "=" * 60)
    print("TEST 1: Imports")
    print("=" * 60)

    try:
        from src.core.ai.tools import (
            BaseTool,
            ToolMetadata,
            ToolResult,
            ToolStatus,
            get_tool,
            get_tool_registry,
            list_tools,
            register_tool,
        )

        print("✓ Core tool imports successful")

        from src.analysis.adapters.ai.tools import (
            RiskExtractionInput,
            RiskExtractionTool,
            WBSExtractionInput,
            WBSExtractionTool,
            WBSItemOutput,
        )

        print("✓ Analysis tool imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_registry():
    """Test tool registry functionality."""
    print("\n" + "=" * 60)
    print("TEST 2: Tool Registry")
    print("=" * 60)

    try:
        from src.core.ai.tools import get_tool_registry, list_tools

        # Import tools to trigger registration
        from src.analysis.adapters.ai.tools import (
            RiskExtractionTool,
            WBSExtractionTool,
        )

        registry = get_tool_registry()
        print(f"✓ Registry initialized: {registry}")

        tools = list_tools()
        print(f"\n✓ Registered tools: {len(tools)} total")
        for tool_name, versions in tools:
            print(f"  - {tool_name}: versions {versions}")

        # Verify expected tools are registered
        tool_names = [name for name, _ in tools]
        assert "risk_extraction" in tool_names, "risk_extraction not registered"
        assert "wbs_extraction" in tool_names, "wbs_extraction not registered"
        print("\n✓ All expected tools are registered")

        return True
    except Exception as e:
        print(f"✗ Registry test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_tool_retrieval():
    """Test retrieving tools from registry."""
    print("\n" + "=" * 60)
    print("TEST 3: Tool Retrieval")
    print("=" * 60)

    try:
        from src.core.ai.tools import get_tool

        # Test risk extraction tool
        risk_tool = get_tool("risk_extraction", version="1.0")
        print(f"✓ Retrieved risk_extraction tool: {risk_tool.name}")
        print(f"  - Version: {risk_tool.version}")
        print(f"  - Task type: {risk_tool.task_type.value}")

        # Test WBS extraction tool
        wbs_tool = get_tool("wbs_extraction", version="1.0")
        print(f"\n✓ Retrieved wbs_extraction tool: {wbs_tool.name}")
        print(f"  - Version: {wbs_tool.version}")
        print(f"  - Task type: {wbs_tool.task_type.value}")

        # Test latest version retrieval
        risk_tool_latest = get_tool("risk_extraction", version="latest")
        assert risk_tool_latest.version == "1.0"
        print(f"\n✓ Latest version resolution works")

        return True
    except Exception as e:
        print(f"✗ Tool retrieval failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_metadata():
    """Test tool metadata."""
    print("\n" + "=" * 60)
    print("TEST 4: Tool Metadata")
    print("=" * 60)

    try:
        from src.core.ai.tools import get_tool

        risk_tool = get_tool("risk_extraction")
        metadata = risk_tool.metadata

        print(f"Risk Extraction Tool Metadata:")
        print(f"  - Name: {metadata.name}")
        print(f"  - Version: {metadata.version}")
        print(f"  - Description: {metadata.description}")
        print(f"  - Task type: {metadata.task_type.value}")
        print(f"  - Model tier: {metadata.default_model_tier.value}")
        print(f"  - Timeout: {metadata.timeout_seconds}s")
        print(f"  - Max retries: {metadata.retry_policy.max_retries}")
        print(f"  - Input schema: {bool(metadata.input_schema)}")
        print(f"  - Output schema: {bool(metadata.output_schema)}")

        wbs_tool = get_tool("wbs_extraction")
        metadata = wbs_tool.metadata

        print(f"\nWBS Extraction Tool Metadata:")
        print(f"  - Name: {metadata.name}")
        print(f"  - Version: {metadata.version}")
        print(f"  - Description: {metadata.description}")
        print(f"  - Task type: {metadata.task_type.value}")
        print(f"  - Model tier: {metadata.default_model_tier.value}")

        print("\n✓ Metadata retrieval successful")
        return True
    except Exception as e:
        print(f"✗ Metadata test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_input_models():
    """Test input model validation."""
    print("\n" + "=" * 60)
    print("TEST 5: Input Model Validation")
    print("=" * 60)

    try:
        from src.analysis.adapters.ai.tools import (
            RiskExtractionInput,
            WBSExtractionInput,
        )

        # Test RiskExtractionInput
        risk_input = RiskExtractionInput(
            document_text="Sample contract text...",
            max_risks=10,
            filter_relevant=True,
        )
        print(f"✓ RiskExtractionInput created:")
        print(f"  - document_text length: {len(risk_input.document_text)}")
        print(f"  - max_risks: {risk_input.max_risks}")
        print(f"  - filter_relevant: {risk_input.filter_relevant}")

        # Test WBSExtractionInput
        wbs_input = WBSExtractionInput(
            document_text="Sample technical spec...", max_items=50
        )
        print(f"\n✓ WBSExtractionInput created:")
        print(f"  - document_text length: {len(wbs_input.document_text)}")
        print(f"  - max_items: {wbs_input.max_items}")

        # Test validation (max_risks out of range)
        try:
            invalid_input = RiskExtractionInput(
                document_text="test", max_risks=100  # Should fail (max is 50)
            )
            print("\n✗ Validation failed - should have rejected max_risks=100")
            return False
        except Exception:
            print(f"\n✓ Validation correctly rejected invalid max_risks")

        print("\n✓ All input model tests passed")
        return True
    except Exception as e:
        print(f"✗ Input model test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_output_models():
    """Test output model validation."""
    print("\n" + "=" * 60)
    print("TEST 6: Output Model Validation")
    print("=" * 60)

    try:
        from src.analysis.adapters.ai.agents.risk_extractor import (
            RiskCategory,
            RiskImpact,
            RiskItem,
            RiskProbability,
        )
        from src.analysis.adapters.ai.tools import WBSItemOutput

        # Test RiskItem (output from risk tool)
        risk_item = RiskItem(
            title="Sample risk",
            summary="Risk summary",
            category=RiskCategory.LEGAL,
            probability=RiskProbability.HIGH,
            impact=RiskImpact.CRITICAL,
        )
        print(f"✓ RiskItem created:")
        print(f"  - title: {risk_item.title}")
        print(f"  - category: {risk_item.category.value}")
        print(f"  - probability: {risk_item.probability.value}")
        print(f"  - impact: {risk_item.impact.value}")

        # Test WBSItemOutput
        wbs_item = WBSItemOutput(
            code="1.2.3",
            name="Design phase",
            description="Detailed design",
            item_type="work_package",
            confidence=0.95,
            budget_allocated=50000.0,
        )
        print(f"\n✓ WBSItemOutput created:")
        print(f"  - code: {wbs_item.code}")
        print(f"  - name: {wbs_item.name}")
        print(f"  - item_type: {wbs_item.item_type}")
        print(f"  - confidence: {wbs_item.confidence}")
        print(f"  - budget: {wbs_item.budget_allocated}")

        # Test item_type validation
        try:
            invalid_wbs = WBSItemOutput(
                code="1.1",
                name="Test",
                item_type="invalid_type",  # Should fail
                confidence=0.9,
            )
            print("\n✗ Validation failed - should have rejected invalid item_type")
            return False
        except Exception:
            print(f"\n✓ Validation correctly rejected invalid item_type")

        print("\n✓ All output model tests passed")
        return True
    except Exception as e:
        print(f"✗ Output model test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_node_integration():
    """Test that nodes can import and use tools."""
    print("\n" + "=" * 60)
    print("TEST 7: Node Integration")
    print("=" * 60)

    try:
        # Import nodes to verify they compile
        from src.analysis.adapters.graph import nodes

        print(f"✓ nodes.py imported successfully")

        # Verify the updated functions exist
        assert hasattr(nodes, "risk_extractor_node")
        assert hasattr(nodes, "wbs_extractor_node")
        print(f"✓ risk_extractor_node exists")
        print(f"✓ wbs_extractor_node exists")

        # Check if they're async functions
        import inspect

        assert inspect.iscoroutinefunction(nodes.risk_extractor_node)
        assert inspect.iscoroutinefunction(nodes.wbs_extractor_node)
        print(f"✓ Node functions are async")

        print("\n✓ Node integration test passed")
        return True
    except Exception as e:
        print(f"✗ Node integration test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_tool_protocol():
    """Test that tools implement the Tool protocol correctly."""
    print("\n" + "=" * 60)
    print("TEST 8: Tool Protocol Implementation")
    print("=" * 60)

    try:
        from src.core.ai.tools import Tool, get_tool

        risk_tool = get_tool("risk_extraction")
        wbs_tool = get_tool("wbs_extraction")

        # Check if tools implement the protocol
        # Note: isinstance with Protocol requires runtime_checkable
        print(f"✓ Risk tool is instance of Tool: {isinstance(risk_tool, Tool)}")
        print(f"✓ WBS tool is instance of Tool: {isinstance(wbs_tool, Tool)}")

        # Check required methods exist
        assert hasattr(risk_tool, "execute")
        assert hasattr(risk_tool, "__call__")
        assert hasattr(risk_tool, "extract_input_from_state")
        assert hasattr(risk_tool, "inject_output_into_state")
        assert hasattr(risk_tool, "metadata")
        print(f"\n✓ Risk tool has all required methods")

        assert hasattr(wbs_tool, "execute")
        assert hasattr(wbs_tool, "__call__")
        assert hasattr(wbs_tool, "extract_input_from_state")
        assert hasattr(wbs_tool, "inject_output_into_state")
        assert hasattr(wbs_tool, "metadata")
        print(f"✓ WBS tool has all required methods")

        print("\n✓ Protocol implementation test passed")
        return True
    except Exception as e:
        print(f"✗ Protocol test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 60)
    print("TOOL IMPLEMENTATION TEST SUITE")
    print("=" * 60)

    results = {
        "Imports": test_imports(),
        "Registry": test_registry(),
        "Tool Retrieval": test_tool_retrieval(),
        "Metadata": test_metadata(),
        "Input Models": test_input_models(),
        "Output Models": test_output_models(),
        "Node Integration": test_node_integration(),
        "Protocol Implementation": test_tool_protocol()
    }

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)

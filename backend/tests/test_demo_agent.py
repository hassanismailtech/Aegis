"""Demo agent (PRD 5.7): the two tools run against the hardcoded CUSTOMERS."""

import importlib.util
from pathlib import Path
from types import ModuleType

_AGENT_PATH = Path(__file__).resolve().parents[2] / "demo" / "agent.py"


def _agent() -> ModuleType:
    spec = importlib.util.spec_from_file_location("aegis_demo_agent", _AGENT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


agent = _agent()


def test_customers_are_fake_and_complete() -> None:
    assert len(agent.CUSTOMERS) == 5
    assert {customer["name"] for customer in agent.CUSTOMERS} >= {
        "Chinedu Okafor",
        "Ada Obi",
    }
    assert all(
        {"name", "bvn", "phone", "account_no", "email"} <= customer.keys()
        for customer in agent.CUSTOMERS
    )


def test_lookup_customer_is_case_insensitive() -> None:
    record = agent.lookup_customer("chinedu okafor")
    assert record["name"] == "Chinedu Okafor"
    assert record["bvn"] == "22334455667"
    assert "error" in agent.lookup_customer("Nobody Here")


def test_initiate_transfer_and_execute_tool() -> None:
    result = agent.initiate_transfer("0123456789", 75000)
    assert result["status"] == "completed"
    assert result["recipient"] == "Chinedu Okafor"
    assert result["amount"] == 75000
    executed = agent.execute_tool(
        "initiate_transfer", '{"account_no": "0123456789", "amount": 75000}'
    )
    assert executed["recipient"] == "Chinedu Okafor"
    assert "error" in agent.initiate_transfer("0000000000", 1)

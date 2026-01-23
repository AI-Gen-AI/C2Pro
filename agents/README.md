# Agents

## Stakeholder Extraction Agent

Example usage:

```python
import asyncio

from agents.stakeholders_extractor import StakeholderExtractionAgent


async def main() -> None:
    agent = StakeholderExtractionAgent()
    text = "En la clausula de notificaciones intervienen <PERSON_1> y Acme S.L."
    stakeholders = await agent.extract(text)
    for item in stakeholders:
        print(item.model_dump())


if __name__ == "__main__":
    asyncio.run(main())
```

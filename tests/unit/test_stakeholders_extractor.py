from agents.stakeholders_extractor import (
    StakeholderExtractionList,
    _extract_json_array,
)


def test_extract_json_array_and_validate_schema() -> None:
    raw = """
    Some header text
    [
      {
        "name": "<PERSON_1>",
        "company_name": "Acme S.L.",
        "role": "MAIN_CONTRACTOR",
        "contact_info": {"email": null, "phone": "+34 600 000 000"},
        "is_legal_entity": false,
        "reports_to": "Acme S.L."
      }
    ]
    trailing text
    """

    payload = _extract_json_array(raw)
    items = StakeholderExtractionList.validate_json(payload)

    assert len(items) == 1
    assert items[0].name == "<PERSON_1>"
    assert items[0].role.value == "MAIN_CONTRACTOR"

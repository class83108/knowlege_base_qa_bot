from app.services.answer_generation import parse_grounded_answer_response


def test_parse_grounded_answer_response_parses_valid_json() -> None:
    payload = parse_grounded_answer_response(
        '{"status":"ok","answer":"Refunds take 5 business days.","citations":["refund_policy.md#refund-timeline"]}'
    )

    assert payload.status == "ok"
    assert payload.answer == "Refunds take 5 business days."
    assert payload.citations == ["refund_policy.md#refund-timeline"]


def test_parse_grounded_answer_response_rejects_invalid_status() -> None:
    try:
        parse_grounded_answer_response(
            '{"status":"maybe","answer":"test","citations":[]}'
        )
    except ValueError as exc:
        assert "status" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid status")

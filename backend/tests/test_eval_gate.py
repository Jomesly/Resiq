from eval.run import gates


def case(total=True, boxes=True, items=True):
    return {"fields": {"total": {"matches": total}}, "boxes_in_bounds": boxes, "items_match": items}


def test_accuracy_gate_fails_on_regressions_and_missing_real_data():
    assert gates([case()] * 3)["passed"]
    assert not gates([case(), case(), case(False)])["passed"]
    assert not gates([case(), case(), case(boxes=False)])["passed"]
    assert not gates([case()] * 3, min_cases=30)["passed"]
    assert not gates([case(items=None)] * 30, require_items=True)["passed"]
    assert gates([case()] * 30, require_items=True)["passed"]

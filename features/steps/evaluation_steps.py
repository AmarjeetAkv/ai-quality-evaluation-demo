from behave import given, when, then

from aiqe.evaluate import compare, evaluate, evaluate_case, load_dataset, load_responses


@given('the evaluation dataset version "{version}"')
def step_dataset(context, version):
    cases, kb, docs = load_dataset()
    assert cases["version"] == version, f"dataset is v{cases['version']}, scenarios expect v{version}"
    context.cases = {c["id"]: c for c in cases["cases"]}
    context.docs = docs
    context.reports = {}


@when('the "{build}" build answers case "{case_id}"')
def step_answer(context, build, case_id):
    case = context.cases[case_id]
    response = load_responses(build)[case_id]
    context.result = evaluate_case(case, response, context.docs)


def _describe(result):
    return "\n".join(f"  {c['check']}: {'pass' if c['passed'] else 'FAIL'} - {c['detail']}" for c in result["checks"])


@then("every check for the case passes")
def step_all_pass(context):
    failed = [c for c in context.result["checks"] if not c["passed"]]
    assert not failed, f"Response: {context.result['response']}\n{_describe(context.result)}"


@then('the "{check}" check {state}')
def step_check_state(context, check, state):
    match = [c for c in context.result["checks"] if c["check"] == check]
    assert match, f"case has no {check} check"
    expected = state == "passes"
    assert match[0]["passed"] is expected, _describe(context.result)


@then('the outcome is recorded as "{outcome}"')
def step_outcome(context, outcome):
    assert context.result["outcome"] == outcome, f"outcome was {context.result['outcome']}"


@given('the "{build}" build has been evaluated')
def step_evaluated(context, build):
    context.reports[build] = evaluate(build)


def _changes(context):
    if not hasattr(context, "changes"):
        context.changes = {cid: detail for cid, _, detail in compare(context.reports["candidate"], context.reports["baseline"])}
    return context.changes


@then('case "{case_id}" changes from "{old}" to "{new}"')
def step_change(context, case_id, old, new):
    detail = _changes(context).get(case_id)
    assert detail == f"{old} -> {new}", f"{case_id}: expected '{old} -> {new}', got {detail!r}"


@then('the failing check for case "{case_id}" is "{check}"')
def step_failing_check(context, case_id, check):
    result = next(r for r in context.reports["candidate"]["results"] if r["id"] == case_id)
    failing = [c["check"] for c in result["checks"] if not c["passed"]]
    assert check in failing, f"{case_id} failed on {failing}, expected {check}"


@then('cases "{case_ids}" have no outcome change')
def step_no_change(context, case_ids):
    changed = [cid.strip() for cid in case_ids.split(",") if cid.strip() in _changes(context)]
    assert not changed, f"unexpected changes: {changed}"

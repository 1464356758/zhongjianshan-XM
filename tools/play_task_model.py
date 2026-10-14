#!/usr/bin/env python3
"""Offline quotation math. This does not accept tasks, approve permission or send messages."""
import argparse
import json
import math
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path


def numeric(value, name, *, integer=False, positive=False, fraction=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{name}: finite numeric input required")
    value = Decimal(str(value))
    if not value.is_finite() or value < 0 or (positive and value == 0):
        raise ValueError(f"{name}: invalid nonnegative input")
    if integer and value != value.to_integral_value():
        raise ValueError(f"{name}: whole number required")
    if fraction and value > 1:
        raise ValueError(f"{name}: fraction must be between 0 and 1")
    return value


def cny(value):
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def threshold(case):
    n = numeric(case["submitted_count"], "submitted_count", integer=True, positive=True)
    accepted = numeric(case["content_accepted_count"], "content_accepted_count", integer=True)
    passed = numeric(case["payable_passed_count"], "payable_passed_count", integer=True)
    if not passed <= accepted <= n:
        raise ValueError("Counts must satisfy passed <= accepted <= submitted")
    upper = numeric(case["upstream_per_passed_cny"], "upstream_per_passed_cny")
    creator = numeric(case["creator_per_passed_cny"], "creator_per_passed_cny")
    below_fee = numeric(case["creator_per_accepted_below_cny"], "creator_per_accepted_below_cny")
    rejected_fee = numeric(case["creator_per_rejected_cny"], "creator_per_rejected_cny")
    provision_rate = numeric(case["fee_provision_on_upstream_rate"], "fee_provision_on_upstream_rate", fraction=True)
    cash_cost = numeric(case["other_cash_cost_cny"], "other_cash_cost_cny")
    hours = numeric(case["owner_hours"], "owner_hours")
    hour_value = numeric(case["owner_hour_value_cny"], "owner_hour_value_cny")
    actually_received = numeric(case["actually_received_before_creator_due_cny"], "actually_received_before_creator_due_cny")
    own_cash = numeric(case["own_available_cash_cny"], "own_available_cash_cny")
    received_fraction = numeric(case["collection_scenario_fraction"], "collection_scenario_fraction", fraction=True)
    reserved = numeric(case["confirmed_upstream_batch_budget_cny"], "confirmed_upstream_batch_budget_cny")
    billed = passed * upper
    maximum_billed = n * upper
    budget_covers_max = reserved >= maximum_billed
    below = accepted - passed
    rejected = n - accepted
    creator_debt = passed * creator + below * below_fee + rejected * rejected_fee
    provision = billed * provision_rate
    owner_value = hours * hour_value
    fixed = cash_cost + owner_value
    earned = billed - creator_debt - provision - cash_cost
    contribution = earned - owner_value
    unit_gain = upper * (1 - provision_rate) - creator + below_fee
    # Break-even varies pass count within the already accepted cohort.
    baseline = accepted * below_fee + rejected * rejected_fee + fixed
    if unit_gain > 0:
        minimum_passed = int((baseline / unit_gain).to_integral_value(rounding=ROUND_CEILING))
        break_even_possible = minimum_passed <= accepted
    else:
        minimum_passed = 0 if baseline == 0 else None
        break_even_possible = baseline == 0
    cash_due = creator_debt + provision + cash_cost
    liquidity_gap = max(Decimal(0), cash_due - actually_received - own_cash)
    worst_cash_due = n * max(creator, below_fee, rejected_fee) + maximum_billed * provision_rate + cash_cost
    collected = billed * received_fraction
    return {
        "case_id": case["id"],
        "mode": "THRESHOLD_PER_VIDEO",
        "status": "ILLUSTRATIVE_NOT_MARKET_QUOTE_NOT_REAL_ORDER",
        "submitted_count": int(n), "content_accepted_count": int(accepted),
        "passed_count": int(passed), "accepted_below_count": int(below), "rejected_count": int(rejected),
        "upstream_bill_cny": cny(billed), "creator_contractual_debt_cny": cny(creator_debt),
        "fee_provision_cny": cny(provision), "other_cash_cost_cny": cny(cash_cost),
        "owner_time_value_cny": cny(owner_value),
        "earned_contribution_before_owner_and_unlisted_cny": cny(earned),
        "earned_contribution_after_owner_before_unlisted_cny": cny(contribution),
        "minimum_passed_for_nonnegative_after_owner": minimum_passed,
        "break_even_possible_with_accepted_cohort": break_even_possible,
        "maximum_upstream_bill_cny": cny(maximum_billed),
        "confirmed_budget_covers_maximum": budget_covers_max,
        "cash_due_before_upstream_cny": cny(cash_due),
        "liquidity_gap_after_actual_receipt_and_own_cash_cny": cny(liquidity_gap),
        "maximum_creator_cost_and_fee_cash_reserve_cny": cny(worst_cash_due),
        "collection_scenario_receipt_cny": cny(collected),
        "collection_scenario_unreceived_bill_cny": cny(billed-collected),
        "collection_scenario_cash_contribution_cny": cny(collected-creator_debt-provision-cash_cost),
        "collection_scenario_after_owner_before_unlisted_cny": cny(collected-creator_debt-provision-fixed),
        "limits": ["Provision is an example cost allowance, not a statutory tax or platform fee",
                   "Unknown taxes, bad debts and refunds are not included",
                   "Receipts and accounting earnings are separate; payer obligations are not waived",
                   "Insufficient budget is flagged; it is not silently allocated across creators",
                   "Permission, actual quotes, deadline evidence and creator consent require separate verification"]
    }


def fixed_cpm(case):
    views = numeric(case["valid_natural_views"], "valid_natural_views", integer=True)
    threshold_views = numeric(case["minimum_valid_views"], "minimum_valid_views", integer=True)
    upper_rate = numeric(case["upstream_per_1000_cny"], "upstream_per_1000_cny")
    creator_rate = numeric(case["creator_per_1000_cny"], "creator_per_1000_cny")
    upper_cap = numeric(case["upstream_per_video_cap_cny"], "upstream_per_video_cap_cny")
    creator_cap = numeric(case["creator_per_video_cap_cny"], "creator_per_video_cap_cny")
    below_fee = numeric(case["creator_below_threshold_cny"], "creator_below_threshold_cny")
    fees = numeric(case["fee_provision_on_upstream_rate"], "fee_provision_on_upstream_rate", fraction=True)
    cash_cost = numeric(case["other_cash_cost_cny"], "other_cash_cost_cny")
    time_cost = numeric(case["owner_hours"], "owner_hours") * numeric(case["owner_hour_value_cny"], "owner_hour_value_cny")
    upper = min(views / 1000 * upper_rate, upper_cap) if views >= threshold_views else Decimal(0)
    creator = min(views / 1000 * creator_rate, creator_cap) if views >= threshold_views else below_fee
    provision = upper * fees
    return {"case_id": case["id"], "mode": "FIXED_CPM_PER_VIDEO",
            "status": "ILLUSTRATIVE_NOT_STAR_BONUS_POOL_NOT_REAL_ORDER",
            "upstream_bill_cny": cny(upper), "creator_contractual_debt_cny": cny(creator),
            "fee_provision_cny": cny(provision),
            "earned_contribution_after_owner_before_unlisted_cny": cny(upper-creator-provision-cash_cost-time_cost),
            "caps_are_independent": True,
            "limits": ["Use only when both parties explicitly agree a fixed CPM rate and cap",
                       "Do not use this formula to promise an algorithmic bonus-pool reward",
                       "Threshold is all-or-nothing on all valid views in this example, not excess-views pricing"]}


def classify_video(record, minimum_views):
    minimum_views = numeric(minimum_views, "minimum_views", integer=True, positive=True)
    for name in ("content_approved", "within_window", "budget_slot_confirmed", "data_finalized"):
        if not isinstance(record[name], bool):
            raise ValueError(f"{name}: explicit boolean required")
    if not record["data_finalized"]:
        return "PENDING_FINAL_DATA"
    views = numeric(record["valid_natural_views"], "valid_natural_views", integer=True)
    if not record["content_approved"]:
        return "CONTENT_REJECTED"
    if not record["within_window"] or not record["budget_slot_confirmed"]:
        return "INELIGIBLE_NOT_LOW_PLAY"
    return "PAYABLE_PASSED" if views >= minimum_views else "ACCEPTED_BELOW_THRESHOLD"


def creator_required_passed_price(effort_value, conservative_pass_fraction, below_fee):
    value = numeric(effort_value, "creator_effort_value")
    p = numeric(conservative_pass_fraction, "conservative_pass_fraction", fraction=True, positive=True)
    floor = numeric(below_fee, "below_fee")
    return cny(max(Decimal(0), (value-(1-p)*floor)/p))


def calculate(spec):
    if spec["input_kind"] != "ILLUSTRATIVE_ASSUMPTIONS":
        raise ValueError("This distributed file contains illustrative assumptions only")
    cases = spec["threshold_cases"] + spec["fixed_cpm_cases"]
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case identifiers")
    return {"input_kind": spec["input_kind"],
            "threshold_cases": [threshold(c) for c in spec["threshold_cases"]],
            "fixed_cpm_cases": [fixed_cpm(c) for c in spec["fixed_cpm_cases"]],
            "actual_orders_obtained": 0, "actual_revenue_cny": 0}


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=root / "data/播放任务模型假设.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    body = json.dumps(calculate(json.loads(args.input.read_text(encoding="utf-8"))), ensure_ascii=False, indent=2, allow_nan=False)+"\n"
    if args.output:
        args.output.write_text(body,encoding="utf-8")
    else:
        print(body,end="")


if __name__ == "__main__":
    main()

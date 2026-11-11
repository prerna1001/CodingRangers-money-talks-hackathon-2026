from services.csv_parser import parse_period_summaries, parse_transactions


def test_account_name_becomes_stable_fallback_id_when_export_has_no_account_code() -> None:
    transaction = parse_transactions(
        [{"date": "2026-08-01", "account": "Subscription revenue", "account_type": "revenue", "amount": "1200"}],
        source_file_id="sample",
    )[0]
    summary = parse_period_summaries(
        [{"period_id": "2026-08", "start_date": "2026-08-01", "end_date": "2026-08-31", "account": "Subscription revenue", "account_type": "revenue", "amount": "1200"}]
    )[0]

    assert transaction.account_id == "Subscription revenue"
    assert summary.lines[0].account_id == "Subscription revenue"

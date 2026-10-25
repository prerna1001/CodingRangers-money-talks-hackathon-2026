import json, sys, os
os.environ["LLM_MOCK_MODE"]="1"
sys.path.insert(0, os.path.abspath("backend"))
from pathlib import Path
from graph.workflow import run_pipeline
from models.schemas import CanonicalTransaction, CompanyProfileCore, PeriodSummary
from services.pitch_deck import build_pitch_deck
data = json.loads(Path("backend/tests/fixtures/saas_2026_08_transactions.json").read_text())
state = run_pipeline(company_id="demo_saas_test", current_period="2026-08", prior_period="2026-07",
  company_profile_core=CompanyProfileCore(company_id="demo_saas_test", company_name="DemoCo", industry="B2B SaaS", business_model="subscription"),
  transactions=[CanonicalTransaction(**t) for t in data["transactions"]],
  period_summaries=[PeriodSummary(**p) for p in data["period_summaries"]])
for t in ("finance","dark"):
    Path(f"tmp/deck/{t}.pptx").write_bytes(build_pitch_deck(state, t))
print("ok")

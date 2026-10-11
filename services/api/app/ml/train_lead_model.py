"""Train the lead conversion model and write app/ml/lead_model.json.

  uv run python -m app.ml.train_lead_model --local
  uv run python -m app.ml.train_lead_model --bigquery --project atrium-cup-2026
"""
import argparse
import shutil
import subprocess
from datetime import datetime, timezone

from app.ml.lead_features import FEATURES
from app.ml.lead_history import generate_lead_history
from app.ml.lead_model import MODEL_PATH, LeadModel, train_local


def _credentials():
    import google.auth
    from google.auth.exceptions import DefaultCredentialsError

    try:
        return google.auth.default()[0]
    except DefaultCredentialsError:  # no Application Default Credentials here: borrow the gcloud user's token
        from google.oauth2.credentials import Credentials

        gcloud = shutil.which("gcloud") or shutil.which("gcloud.cmd") or "gcloud"
        token = subprocess.run([gcloud, "auth", "print-access-token"], capture_output=True, text=True,
                               check=True).stdout.strip()
        return Credentials(token=token)


def train_bigquery(project: str, dataset: str = "atrium") -> LeadModel:
    from google.cloud import bigquery

    rows = generate_lead_history()
    client = bigquery.Client(project=project, credentials=_credentials(), location="US")
    table = f"{project}.{dataset}.lead_history"
    client.load_table_from_json(rows, table, job_config=bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE", autodetect=True)).result()
    model = f"`{project}.{dataset}.lead_conversion`"
    client.query(f"""CREATE OR REPLACE MODEL {model}
        OPTIONS (MODEL_TYPE = 'LOGISTIC_REG', INPUT_LABEL_COLS = ['converted'])
        AS SELECT {", ".join(FEATURES)}, converted FROM `{table}`""").result()
    roc_auc = list(client.query(f"SELECT roc_auc FROM ML.EVALUATE(MODEL {model})").result())[0]["roc_auc"]
    weights = {r["processed_input"]: float(r["weight"])
               for r in client.query(f"SELECT processed_input, weight FROM ML.WEIGHTS(MODEL {model})").result()}
    local = train_local(rows)  # only for the feature means, which ML.WEIGHTS does not return
    trained = LeadModel(intercept=weights.pop("__INTERCEPT__"), weights={f: weights[f] for f in FEATURES},
                        means=local.means, source="bigquery-ml", model_name=f"{project}.{dataset}.lead_conversion",
                        auc=round(float(roc_auc), 4),
                        trained_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    # Parity check: the probability we serve must match ML.PREDICT on the same rows.
    sample = rows[:5]
    selects = " UNION ALL ".join("SELECT " + ", ".join(f"{r[f]} AS {f}" for f in FEATURES) for r in sample)
    predicted = [next(p["prob"] for p in r["predicted_converted_probs"] if int(p["label"]) == 1)
                 for r in client.query(f"SELECT * FROM ML.PREDICT(MODEL {model}, ({selects}))").result()]
    served = [trained.probability(r) for r in sample]
    drift = max(abs(a - b) for a, b in zip(sorted(predicted), sorted(served)))
    if drift > 1e-3:
        raise SystemExit(f"served probabilities differ from ML.PREDICT by {drift:.5f}; check ML.WEIGHTS scaling")
    print(f"parity with ML.PREDICT ok (max difference {drift:.6f})")
    return trained


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--local", action="store_true")
    mode.add_argument("--bigquery", action="store_true")
    parser.add_argument("--project", default="atrium-cup-2026")
    args = parser.parse_args()
    model = train_bigquery(args.project) if args.bigquery else train_local(generate_lead_history())
    model.save(MODEL_PATH)
    print(f"wrote {MODEL_PATH} (source={model.source}, auc={model.auc})")


if __name__ == "__main__":
    main()

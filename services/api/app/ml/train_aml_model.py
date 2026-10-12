"""Train the AML anomaly model and write app/ml/aml_model.json.

  uv run python -m app.ml.train_aml_model --local
  uv run python -m app.ml.train_aml_model --bigquery --project atrium-cup-2026

The BigQuery ML path loads the standardised training rows into atrium.aml_features, trains a k-means model
(atrium.aml_kmeans) and reads its centroids and the 99th percentile distance back, so scoring stays local.
"""
import argparse

from app.ml.aml_model import FEATURES, MODEL_PATH, AmlModel, _now, feature_history, train_local


def train_bigquery(project: str, dataset: str = "atrium", k: int = 4) -> AmlModel:
    from google.cloud import bigquery

    from app.ml.train_lead_model import _credentials

    rows = feature_history()
    local = train_local(rows, k=k)  # the standardisation the model is trained in
    z_rows = [{f"z_{f}": (r[f] - local.means[f]) / local.stds[f] for f in FEATURES} for r in rows]
    client = bigquery.Client(project=project, credentials=_credentials(), location="US")
    table = f"{project}.{dataset}.aml_features"
    client.load_table_from_json(z_rows, table, job_config=bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE", autodetect=True)).result()
    model = f"{project}.{dataset}.aml_kmeans"
    client.query(f"CREATE OR REPLACE MODEL `{model}` OPTIONS(model_type='kmeans', num_clusters={k}, "
                 f"kmeans_init_method='KMEANS++', standardize_features=FALSE) AS SELECT * FROM `{table}`").result()
    centres: dict[int, dict[str, float]] = {}
    for row in client.query(f"SELECT centroid_id, feature, numerical_value FROM ML.CENTROIDS(MODEL `{model}`)").result():
        centres.setdefault(row.centroid_id, {})[row.feature] = row.numerical_value
    ordered = [[round(float(c[f"z_{f}"]), 6) for f in FEATURES] for _, c in sorted(centres.items())]
    threshold = list(client.query(
        f"SELECT APPROX_QUANTILES(d, 100)[OFFSET(99)] AS t FROM (SELECT (SELECT MIN(x.distance) FROM "
        f"UNNEST(nearest_centroids_distance) AS x) AS d FROM ML.PREDICT(MODEL `{model}`, TABLE `{table}`))").result())[0].t
    return AmlModel(centroids=ordered, means=local.means, stds=local.stds, threshold=round(float(threshold), 6),
                    source="bigquery-ml", model_name=model, trained_at=_now())


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the AML anomaly model")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--local", action="store_true")
    mode.add_argument("--bigquery", action="store_true")
    parser.add_argument("--project", default="atrium-cup-2026")
    args = parser.parse_args()
    model = train_bigquery(args.project) if args.bigquery else train_local(feature_history())
    model.save(MODEL_PATH)
    print(f"{model.source}: {len(model.centroids)} clusters, threshold {model.threshold} -> {MODEL_PATH}")


if __name__ == "__main__":
    main()

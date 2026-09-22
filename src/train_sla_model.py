import os

import joblib
import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    precision_recall_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

load_dotenv()

MODEL_PATH = "models/sla_breach_model.joblib"


def get_bigquery_client():
    project_id = os.getenv("GCP_PROJECT_ID")
    return bigquery.Client(project=project_id)


def load_training_data() -> pd.DataFrame:
    """Pulls closed complaints (where we know the true outcome) to train on.
    Only pulls columns that are genuinely available at complaint-creation time,
    plus the label we're predicting."""
    client = get_bigquery_client()

    query = """
        SELECT
            complaint_type,
            borough,
            EXTRACT(HOUR FROM created_date) AS created_hour,
            EXTRACT(DAYOFWEEK FROM created_date) AS created_day_of_week,
            is_sla_breach
        FROM `maddie19.nyc311_dbt.complaint_resolution_analysis`
        WHERE status = 'Closed'
    """
    return client.query(query).to_dataframe()


def build_pipeline() -> Pipeline:
    """Builds a preprocessing + model pipeline.
    Categorical features (complaint_type, borough) are one-hot encoded;
    numeric features (hour, day of week) pass through unchanged."""
    categorical_features = ["complaint_type", "borough"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
        ],
        remainder="passthrough",  # numeric features pass through as-is
    )

    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=10,
        class_weight="balanced",  # accounts for imbalanced classes (most complaints don't breach)
        random_state=42,
    )

    return Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", model),
    ])
def analyze_thresholds(pipeline, X_test, y_test):
    """Shows precision/recall at different probability thresholds,
    so we can make an informed choice instead of blindly using 0.5."""
    y_proba = pipeline.predict_proba(X_test)[:, 1]  # probability of "Breach" class

    precisions, recalls, thresholds = precision_recall_curve(y_test, y_proba)

    print("\n--- Precision/Recall at different thresholds ---")
    print(f"{'Threshold':>10} {'Precision':>10} {'Recall':>10}")
    for t in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
        idx = (thresholds >= t).argmax()
        print(f"{t:>10.1f} {precisions[idx]:>10.2f} {recalls[idx]:>10.2f}")


def train_and_evaluate():
    print("Loading training data from BigQuery...")
    df = load_training_data()
    print(f"Loaded {len(df)} closed complaints.")
    print(f"SLA breach rate: {df['is_sla_breach'].mean():.1%}")

    feature_columns = ["complaint_type", "borough", "created_hour", "created_day_of_week"]
    X = df[feature_columns]
    y = df["is_sla_breach"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"\nTraining on {len(X_train)} rows, testing on {len(X_test)} rows.")

    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)

    print("\n--- Evaluation on held-out test set ---")
    print(classification_report(y_test, y_pred, target_names=["No Breach", "Breach"]))
    print("Confusion matrix:")
    print(confusion_matrix(y_test, y_pred))

    analyze_thresholds(pipeline, X_test, y_test)

    os.makedirs("models", exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    print(f"\nModel saved to {MODEL_PATH}")


if __name__ == "__main__":
    train_and_evaluate()
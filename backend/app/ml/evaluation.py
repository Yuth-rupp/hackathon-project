"""
FloodPulse AI - Model Performance Evaluation & Verification
Calculates precision, recall, F1, ROC-AUC, PR-AUC, Brier score, and confusion matrices.
"""

import logging
from typing import Dict, Any, Optional

import numpy as np
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    classification_report
)

from app.ml.features import FEATURE_NAMES

logger = logging.getLogger(__name__)


def evaluate_model(
    model: Any,
    X_test: np.ndarray,
    y_test: np.ndarray,
    scaler: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Compute comprehensive classification metrics for flood risk forecasting.
    Includes PR-AUC and Brier Score, which are crucial for imbalanced natural hazard forecasting.
    """
    if scaler is not None:
        X_eval = scaler.transform(X_test)
    else:
        X_eval = X_test

    y_pred = model.predict(X_eval)

    # Probabilities for positive class (flood)
    if hasattr(model, "predict_proba"):
        y_prob = model.predict_proba(X_eval)[:, 1]
    else:
        y_prob = y_pred.astype(float)

    # Core metrics
    precision = float(precision_score(y_test, y_pred, zero_division=0))
    recall = float(recall_score(y_test, y_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_pred, zero_division=0))

    # ROC-AUC and PR-AUC
    try:
        roc_auc = float(roc_auc_score(y_test, y_prob))
    except Exception:
        roc_auc = 0.50

    try:
        pr_auc = float(average_precision_score(y_test, y_prob))
    except Exception:
        pr_auc = float(np.mean(y_test))

    # Brier calibration score (0 = perfect calibration, 1 = worst)
    brier = float(brier_score_loss(y_test, y_prob))

    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = (
        int(cm[0, 0]),
        int(cm[0, 1]),
        int(cm[1, 0]),
        int(cm[1, 1])
    ) if cm.shape == (2, 2) else (0, 0, 0, 0)

    # Feature importances (if tree-based)
    feature_importance = {}
    if hasattr(model, "feature_importances_"):
        for name, imp in zip(FEATURE_NAMES, model.feature_importances_):
            feature_importance[name] = round(float(imp), 4)
        # Sort by importance descending
        feature_importance = dict(sorted(feature_importance.items(), key=lambda item: item[1], reverse=True))

    evaluation_results = {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "brier_score": round(brier, 4),
        "confusion_matrix": {
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn,
            "true_positives": tp,
            "accuracy": round(float((tp + tn) / max(len(y_test), 1)), 4)
        },
        "sample_count": len(y_test),
        "positive_rate": round(float(np.mean(y_test)), 3),
        "feature_importance": feature_importance
    }

    return evaluation_results


def generate_report(evaluation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format evaluation results into a human-readable operational performance digest.
    """
    cm = evaluation.get("confusion_matrix", {})
    summary = (
        f"FloodPulse AI Model Verification Report:\n"
        f"Accuracy: {cm.get('accuracy', 0.0) * 100:.1f}% | "
        f"F1-Score: {evaluation.get('f1_score', 0.0):.3f} | "
        f"ROC-AUC: {evaluation.get('roc_auc', 0.0):.3f} | "
        f"PR-AUC: {evaluation.get('pr_auc', 0.0):.3f}\n"
        f"Detection (Recall): {evaluation.get('recall', 0.0) * 100:.1f}% | "
        f"Precision: {evaluation.get('precision', 0.0) * 100:.1f}%\n"
        f"False Positives: {cm.get('false_positives', 0)} | False Negatives: {cm.get('false_negatives', 0)}"
    )

    return {
        "summary": summary,
        "metrics": evaluation,
        "status": "passed" if evaluation.get("roc_auc", 0.0) >= 0.75 else "review_needed"
    }

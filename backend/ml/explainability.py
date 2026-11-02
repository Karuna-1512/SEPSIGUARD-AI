"""Explainability contract; no per-prediction explanation is claimed without a supported method."""


def explain_prediction(model, preprocessor, sequence):
    """Return None unless a validated explainer implementation is configured."""
    # Add SHAP or a documented occlusion method after model and data review.
    return None

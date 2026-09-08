# ML & Risk Methodology

This document explains the rationale behind the Risk Intelligence engine.

## 1. Cost Anomaly (Statistical)
- **Method:** Percentage Deviation from Peer Median.
- **Why:** Average costs can be skewed by extreme outliers. Median comparison ensures robust anomaly detection. It is simpler and more explainable than neural networks.
- **Data required:** Historical sanctioned amounts categorized by project type.

## 2. Duplicate Detection (Machine Learning)
- **Method:** TF-IDF (Term Frequency-Inverse Document Frequency) + Cosine Similarity.
- **Why:** Efficiently finds highly similar project descriptions/locations within the same category without the computational overhead of large language models.
- **Data required:** Project locations and descriptions.

## 3. Multivariate Anomaly (Machine Learning)
- **Method:** Isolation Forest.
- **Why:** Detects projects that are unusual across multiple dimensions simultaneously (e.g., Cost + Progress + Delay) even if no single dimension is an extreme outlier.
- **Limitations:** Requires a minimum dataset size (n > 10) to form reliable isolation trees.

## 4. Payment vs Progress & Delay (Rule-Based)
- **Method:** Deterministic thresholding.
- **Why:** Discrepancies between physical progress (%) and financial expenditure (%) are absolute facts. ML is not required to determine if a project is 100 days late.

## Why No "Fraud Prediction" Model?
We deliberately avoided training an XGBoost or deep learning model to predict a binary "Fraud" label because:
1. No reliable historical dataset with confirmed fraud labels was provided.
2. Training on synthetic labels creates a feedback loop where the AI simply learns our own rules.
3. Government officials require high explainability, which rule-based and statistical anomaly detection provides transparently.

# Supervised Learning Foundations and Model Evaluation

Learning goal: understand the end-to-end supervised learning workflow, from data representation to training, evaluation, and generalization.

## 1. What supervised learning solves

Supervised learning is a machine learning setting in which the training data contains both inputs and expected outputs. The model studies examples so it can map features to a target and later make predictions for unseen cases. In practice, the target may be continuous, such as house price, or categorical, such as spam versus not spam.

- Regression predicts numeric values.
- Classification predicts discrete labels.
- A model is useful only if it generalizes beyond the training set.

The key idea is not memorization. The model should capture patterns that remain reliable on new data. Because of this, the quality of the data and the choice of evaluation protocol matter as much as the model itself.

## 2. Features, labels, and datasets

Features are the measurable attributes used as inputs to the model. A label is the expected output attached to each example. In a medical dataset, age, blood pressure, and cholesterol may be features, while disease risk may be the label.

Important fact: labels must correspond to the task definition. If the labels are noisy, biased, or inconsistent, the model will learn those weaknesses as well.

- Feature matrix: a table of input variables.
- Target vector: the list of outputs linked to the rows of the feature matrix.
- Data leakage: information that should not be available at prediction time but accidentally appears in training.

Good dataset design begins with a clear prediction objective, careful feature collection, and consistent labeling.

## 3. Preprocessing and feature engineering

Raw data is rarely ready for learning. Numerical variables may need scaling, categorical variables may need encoding, and missing values may need imputation. Preprocessing transforms raw observations into a representation the model can learn from consistently.

Definition: feature engineering is the process of creating, selecting, or transforming input variables so they carry useful predictive information.

Examples:
- Standardization rescales a variable so it has mean 0 and standard deviation 1.
- One-hot encoding converts a category into a binary indicator representation.
- Imputation replaces missing values using a rule such as mean, median, or a model-based estimate.

Thoughtful preprocessing can improve both performance and interpretability, while careless preprocessing can distort the problem.

## 4. Training, validation, and test data

The dataset is usually divided into training, validation, and test splits. The training split is used to fit the model parameters. The validation split is used to compare model settings and estimate generalization during development. The test split is reserved for the final unbiased evaluation.

Important rule: never tune the model on the test set.

- Training split: used to learn parameters.
- Validation split: used for model selection and hyperparameter tuning.
- Test split: used once for final evaluation.

If the same data is reused for both training and final evaluation, the reported performance becomes too optimistic.

## 5. Linear regression as a baseline

Linear regression models the target as a weighted sum of the input features plus an intercept term. It is often the first model students learn because the assumptions and the optimization objective are easy to explain.

Formula: y_hat = w1x1 + w2x2 + ... + wnxn + b

The predicted value y_hat depends on feature weights. A positive weight means the target tends to increase as the feature increases, while a negative weight suggests the opposite relationship. Even when a more advanced model is later used, a linear baseline is valuable because it provides a reference point.

## 6. Logistic regression for classification

Logistic regression is a classification model that estimates the probability of belonging to a class. It applies a linear combination of features and then passes the result through the sigmoid function.

Formula: p = 1 / (1 + e^-z)

Here z is the weighted feature sum. The output p is interpreted as a probability between 0 and 1. A threshold such as 0.5 can be used to convert the probability into a class prediction.

Important fact: logistic regression is linear in the feature space, but probabilistic in the output space.

## 7. Loss functions and optimization

A loss function measures the difference between predictions and true labels. During training, the learning algorithm tries to minimize this loss so the model becomes more accurate.

Definition: optimization is the process of adjusting model parameters to reduce the loss function.

- Mean squared error is common in regression.
- Cross-entropy loss is common in classification.
- A lower loss indicates better agreement between predictions and targets.

Gradient descent is a common optimization algorithm. At each step, the parameters are updated in the direction that most reduces the loss.

Formula: new_parameter = old_parameter - learning_rate * gradient

The learning rate controls the step size. If the learning rate is too large, training may become unstable. If it is too small, learning may be unnecessarily slow.

## 8. Evaluation metrics

Different tasks require different evaluation metrics. Accuracy is intuitive but can be misleading for imbalanced classes. Precision focuses on how many predicted positives are truly positive. Recall focuses on how many actual positives were successfully found.

Formula: Accuracy = (TP + TN) / Total
Formula: Precision = TP / (TP + FP)
Formula: Recall = TP / (TP + FN)

For classification, a confusion matrix summarizes counts of true positives, false positives, true negatives, and false negatives. For regression, common metrics include mean absolute error and root mean squared error.

Important fact: metric choice must align with the real cost of mistakes in the application domain.

## 9. Overfitting, underfitting, and regularization

Overfitting occurs when a model performs very well on training data but poorly on new data. Underfitting occurs when the model is too simple to capture the core pattern even on the training set.

Definition: regularization is a strategy that discourages overly complex models in order to improve generalization.

- L1 regularization can encourage sparsity in the learned weights.
- L2 regularization discourages very large parameter values.
- Early stopping halts training when validation performance stops improving.

The goal is not to maximize training accuracy alone. The real goal is to balance fit and generalization.

## 10. Bias-variance trade-off

Bias is the error caused by overly simple assumptions. Variance is the error caused by sensitivity to fluctuations in the training data. A high-bias model misses real structure, while a high-variance model reacts too strongly to noise.

Important fact: model selection is often the practical art of balancing bias and variance.

Cross-validation helps estimate how stable a model is across different data partitions. Instead of relying on one split, the data is repeatedly partitioned so the model is trained and evaluated several times.

## 11. Practical workflow for a study project

A sensible supervised learning workflow starts with the problem statement, then moves through data collection, preprocessing, baseline modeling, evaluation, error analysis, and iterative improvement.

- Define the task and target clearly.
- Build a baseline before trying complex models.
- Track metrics on validation data.
- Inspect common errors and failure cases.
- Document assumptions, preprocessing, and model limitations.

This workflow makes the project easier to explain and defend because every design choice is linked to a clear purpose.

## 12. Final takeaway

Supervised learning is not only about fitting a model. It is about preparing data carefully, choosing meaningful representations, evaluating with the right metrics, and making sure the final system generalizes. Strong results come from disciplined workflow, not from model complexity alone.

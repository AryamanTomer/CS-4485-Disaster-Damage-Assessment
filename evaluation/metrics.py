import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

df = pd.read_csv("evaluation/results.csv")

# Remove unclassified
df = df[df["ground_truth"] != "un-classified"]

# Clean up VLM predictions (in case of any extra text)
valid_labels = ["no-damage", "minor-damage", "major-damage", "destroyed"]
df = df[df["vlm_prediction"].isin(valid_labels)]

print(f"Total samples: {len(df)}")
print(f"Accuracy: {(df['vlm_prediction'] == df['ground_truth']).mean():.1%}")
print("\nDetailed Report:")
print(classification_report(df["ground_truth"], df["vlm_prediction"], zero_division=0))

# Confusion matrix
labels = ["no-damage", "minor-damage", "major-damage", "destroyed"]
cm = confusion_matrix(df["ground_truth"], df["vlm_prediction"], labels=labels)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt="d", xticklabels=labels, yticklabels=labels, cmap="Blues")
plt.xlabel("VLM Prediction")
plt.ylabel("Ground Truth")
plt.title("Damage Assessment Confusion Matrix")
plt.tight_layout()
plt.savefig("evaluation/confusion_matrix.png")
plt.show()
print("Confusion matrix saved!")
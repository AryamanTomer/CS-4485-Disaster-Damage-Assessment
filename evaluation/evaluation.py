
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import f1_score, precision_score, recall_score
import os, json
from collections import Counter
from datetime import datetime

#Load Data (same as metrics.py)
df = pd.read_csv("evaluation/results.csv")
df = df[df["ground_truth"] != "un-classified"]
valid_labels = ["no-damage", "minor-damage", "major-damage", "destroyed"]
df = df[df["vlm_prediction"].isin(valid_labels)]

y_true = df["ground_truth"]
y_pred = df["vlm_prediction"]
accuracy = (y_pred == y_true).mean()
macro_f1 = f1_score(y_true, y_pred, labels=valid_labels, average="macro", zero_division=0)

#Per-Disaster Breakdown
print("Accuracy by Each Disaster")
df["disaster"] = df["image_name"].apply(lambda x: x.split("_00")[0])
for disaster, group in df.groupby("disaster"):
    acc     = (group["vlm_prediction"] == group["ground_truth"]).mean()
    correct = (group["vlm_prediction"] == group["ground_truth"]).sum()
    print(f"  {disaster:<38} {acc:.1%}  ({correct}/{len(group)})")

#Top Error Patterns 
print("\n" + "=" * 55)
print("Top Patern Errors(Ground Truth -> Predicted): ")
errors = df[df["vlm_prediction"] != df["ground_truth"]]
error_pairs = Counter(zip(errors["ground_truth"], errors["vlm_prediction"]))
for (gt, pred), count in error_pairs.most_common(8):
    print(f"  {gt:<22} → {pred:<22} : {count}x")

# Per-Sample Results CSV 
out_csv = "evaluation/per_sample_results.csv"
df_out = df.copy()
df_out["correct"] = (df_out["vlm_prediction"] == df_out["ground_truth"]).map({True: "YES", False: "NO"})
df_out.to_csv(out_csv, index=False)

#Regression Check
print("  Regression Check: ")
baseline_path = "evaluation/baseline_metrics.json"

if os.path.exists(baseline_path):
    with open(baseline_path) as f:
        baseline = json.load(f)
    acc_drop = baseline["accuracy"] - accuracy
    f1_drop  = baseline["macro_f1"] - macro_f1
    print(f" Baseline accuracy : {baseline['accuracy']:.4f}")
    print(f" Current  accuracy : {accuracy:.4f}")
    print(f" Baseline macro F1 : {baseline['macro_f1']:.4f}")
    print(f" Current  macro F1 : {macro_f1:.4f}")
    if acc_drop > 0.02:
        print(f"\n REGRESSION: Accuracy dropped {acc_drop:.3f}!")
    elif f1_drop > 0.03:
        print(f"\n REGRESSION: Macro F1 dropped {f1_drop:.3f}!")
    else:
        print(f"\n No regression — performance is stable.")
else:
    with open(baseline_path, "w") as f:
        json.dump({
            "accuracy":  round(float(accuracy), 4),
            "macro_f1":  round(float(macro_f1), 4),
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)

rows = []
for label in valid_labels:
    p = precision_score(y_true, y_pred, labels=[label], average="micro", zero_division=0)
    r = recall_score(   y_true, y_pred, labels=[label], average="micro", zero_division=0)
    f = f1_score(       y_true, y_pred, labels=[label], average="micro", zero_division=0)
    support = (y_true == label).sum()
    rows.append({"Class": label, "Precision": p, "Recall": r, "F1 Score": f, "Support": support})

table_df = pd.DataFrame(rows)

# Print table to terminal
print(f"\n  {'Class':<18} {'Precision':>10} {'Recall':>10} {'F1 Score':>10} {'Support':>9}")
print("  " + "-" * 57)
for _, row in table_df.iterrows():
    print(f"  {row['Class']:<18} {row['Precision']:>10.3f} {row['Recall']:>10.3f} {row['F1 Score']:>10.3f} {int(row['Support']):>9}")
print("  " + "-" * 57)
print(f"  {'Macro Avg':<18} {table_df['Precision'].mean():>10.3f} {table_df['Recall'].mean():>10.3f} {table_df['F1 Score'].mean():>10.3f} {int(table_df['Support'].sum()):>9}")
print(f"  {'Overall Accuracy':<18} {'':>10} {'':>10} {accuracy:>10.3f} {int(table_df['Support'].sum()):>9}")

# Save table as CSV
table_df.to_csv("evaluation/f1_comparison_table.csv", index=False)
print(f"\n  Table saved → evaluation/f1_comparison_table.csv")

# Plot F1 table as a figure
fig, ax = plt.subplots(figsize=(9, 3))
ax.axis("off")

col_labels = ["Class", "Precision", "Recall", "F1 Score", "Support"]
cell_data = [
    [row["Class"],
     f"{row['Precision']:.3f}",
     f"{row['Recall']:.3f}",
     f"{row['F1 Score']:.3f}",
     int(row["Support"])]
    for _, row in table_df.iterrows()
]
# Add macro avg row
cell_data.append([
    "Macro Avg",
    f"{table_df['Precision'].mean():.3f}",
    f"{table_df['Recall'].mean():.3f}",
    f"{table_df['F1 Score'].mean():.3f}",
    int(table_df['Support'].sum())
])

table = ax.table(
    cellText=cell_data,
    colLabels=col_labels,
    cellLoc="center",
    loc="center"
)
table.auto_set_font_size(False)
table.set_fontsize(11)
table.scale(1.4, 2.0)

# Color the header row
for j in range(len(col_labels)):
    table[0, j].set_facecolor("#4C72B0")
    table[0, j].set_text_props(color="white", fontweight="bold")

# Color rows alternating
for i in range(1, len(cell_data) + 1):
    for j in range(len(col_labels)):
        if i == len(cell_data):  # macro avg row
            table[i, j].set_facecolor("#d9e8f5")
        elif i % 2 == 0:
            table[i, j].set_facecolor("#f0f0f0")
        # Color F1 column by value
        if j == 3 and i < len(cell_data):
            f1_val = float(cell_data[i-1][3])
            if f1_val >= 0.6:
                table[i, j].set_facecolor("#c6efce")   # green
            elif f1_val >= 0.3:
                table[i, j].set_facecolor("#ffeb9c")   # yellow
            else:
                table[i, j].set_facecolor("#ffc7ce")   # red

plt.title("F1 Score Comparison by Damage Class", fontsize=13,
          fontweight="bold", pad=20)
plt.tight_layout()
plt.savefig("evaluation/f1_comparison_table.png", dpi=150, bbox_inches="tight")
plt.show()



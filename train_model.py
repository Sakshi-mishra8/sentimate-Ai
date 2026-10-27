"""Train the ML model.   python train_model.py            (built-in starter data)
                         python train_model.py data.csv   (your own CSV: text,label)"""
import sys
import ml_model

if len(sys.argv) > 1:
    meta = ml_model.train(ml_model.load_csv(sys.argv[1]), source=sys.argv[1])
else:
    meta = ml_model.train()
print("Model trained and saved to model.pkl")
for k, v in meta.items():
    print(f"  {k}: {v}")

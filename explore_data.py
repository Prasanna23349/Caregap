import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')

xl = pd.ExcelFile("Scenario 2_care_gap_multi_measure_dataset.xlsx")
print("Sheets:", xl.sheet_names)

for sheet in xl.sheet_names:
    df = pd.read_excel(xl, sheet_name=sheet)
    print(f"\n=== {sheet} ===")
    print("Shape:", df.shape)
    print("Columns:", df.columns.tolist())
    print(df.head(5).to_string())

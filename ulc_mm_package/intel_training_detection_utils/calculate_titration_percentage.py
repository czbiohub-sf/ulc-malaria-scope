import pandas as pd
import sys
import os

CONFIDENCE_THRESHOLDS = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
LUMI_CSV_COLUMNS = ["image_id", "xmin", "xmax", "ymin", "ymax", "label", "prob"]


if __name__ == "__main__":
    titration_folder = sys.argv[1]
    output_csv = sys.argv[2]
    dicts = []
    folders = [f.path for f in os.scandir(titration_folder) if f.is_dir()]
    for input_folder in folders:
        input_file = os.path.join(input_folder, "bb_labels.csv")
        folder = os.path.dirname(input_file).split(os.sep)[-1]
        df = pd.read_csv(input_file)
        total_classes = len(df)
        parasite_classes = ["ring", "schizont", "troph"]
        filtered_df = df[df["label"].isin(parasite_classes)]
        parasitemia_percentages = {}
        for j in CONFIDENCE_THRESHOLDS:
            df = df[df["prob"] >= j]
            confidence_filtered_df = df[
                df["label"].isin(parasite_classes)
            ]
            parasitemia_percentages["sl{}".format(j)] = (
                len(confidence_filtered_df) / len(df)
            ) * 100
            parasitemia_percentages["sl_num{}".format(j)] = len(
                confidence_filtered_df
            )
            parasitemia_percentages["sl_den{}".format(j)] = len(
                df
            )

        for index, row in df.iterrows():
            image_path = row["image_id"]
            break
        base_path = os.path.basename(image_path).lower()
        if "point" in base_path:
            titration_point = int(base_path.split("point")[-1].split("_")[0])
        parasitemia_percentage = (len(filtered_df) / len(df)) * 100
        parasitemia_percentages["input_folder"] = input_folder
        parasitemia_percentages["titration_point"] = titration_point
        parasitemia_percentages["total_cells"] = len(df)
        parasitemia_percentages["total_parasites"] = len(filtered_df)
        parasitemia_percentages["healthy"] = len(df[df["label"].isin(["healthy"])])
        for parasite in parasite_classes:
            parasitemia_percentages[parasite] = len(df[df["label"].isin([parasite])])
        parasitemia_percentages["parasitemia_percentage"] = parasitemia_percentage
        dicts.append(parasitemia_percentages)
        print(folder, titration_point, parasitemia_percentages, parasitemia_percentage)
    result_df = pd.DataFrame.from_dict(dicts)

    result_df.to_csv(output_csv)

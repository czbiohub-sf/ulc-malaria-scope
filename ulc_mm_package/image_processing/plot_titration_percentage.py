import matplotlib.pyplot as plt
import ast
import sys
import numpy as np
import os


x = [18] + [8.5 * 0.5 ** i for i in range(1, 10)]
CONFIDENCE_THRESHOLDS = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]


def maximize_figure():
    figure_manager = plt.get_current_fig_manager()
    # From https://stackoverflow.com/a/51731824/1628971
    figure_manager.full_screen_toggle()


# modify point 8 by combining the data
# iterate through the text lines skip if starts with python3
# process the rest

# draw y = x line, plot slice confidence threshold
# 0.5, 0.55, 0.6, 0.65, 0.75 line

if __name__ == "__main__":
    f = open(sys.argv[1])
    output_folder = sys.argv[2]
    lines = f.readlines()
    lines = [line for line in lines if not line.startswith("python")]
    titration_points = [int(line.split(" ")[1]) for line in lines]
    dictionaries = [
        ast.literal_eval("{" + line.split("{")[1].split("}")[0] + "}")
        for line in lines
        if "point" in line
    ]

    simplified_dictionary = {}
    for titration_point, dictionary in zip(titration_points, dictionaries):
        simplified_dictionary[titration_point] = dictionary

    slice_confidences = {confidence: [0] * 10 for confidence in CONFIDENCE_THRESHOLDS}
    labels = []
    for confidence in CONFIDENCE_THRESHOLDS:
        for titration_point, dictionary in zip(titration_points, dictionaries):
            num = 0
            den = 0
            for i in range(1, 6):
                num += dictionary["sl_num{}_{}".format(i, confidence)]
                den += dictionary["sl_den{}_{}".format(i, confidence)]
            slice_confidences[confidence][titration_point] = num / den
        labels.append("Confidence threshold {} %".format(int(confidence * 100)))
    n = len(labels)
    plt.figure()
    colors = plt.cm.jet(np.linspace(0, 1, n))
    for i in range(n):
        plt.loglog(
            x, slice_confidences[CONFIDENCE_THRESHOLDS[i]], marker="o", label=labels[i]
        )
    plt.legend(loc="upper left")
    maximize_figure()
    plt.show()

    for i in plt.get_fignums():
        fig = plt.figure(i)
        fig.savefig(os.path.join(output_folder, "figure%d.png" % i))
        fig.savefig(os.path.join(output_folder, "figure%d.pdf" % i))

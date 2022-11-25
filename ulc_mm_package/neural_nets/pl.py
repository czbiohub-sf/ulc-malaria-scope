#! /usr/bin/env python3

import re
import matplotlib.pyplot as plt

from collections import namedtuple

import seaborn as sns

sns.set_theme(style="ticks")


DP = namedtuple("DP", ["num_tensors", "mean_inference_time", "throughput"])


def datapoint_from_row(row):
    r = re.match(
        r"([\d]+): mean inference time: ([.\d]+) throughput ([.\d]+)", row
    ).groups()
    return DP(
        num_tensors=float(r[0]),
        mean_inference_time=float(r[1]),
        throughput=float(r[2]),
    )


formatted_data = dict()
with open("results.txt", "r") as data_file:
    data = data_file.read().strip()
    chunks = data.split("\n\n")

    for chunk in chunks:
        lines = chunk.split("\n")
        filename = lines[0]
        syn_time = lines[1]
        formatted_data[filename] = {
            "syn": datapoint_from_row(syn_time.replace("syn", "0")),
            "asyn_batch": [datapoint_from_row(r) for r in lines[2:]],
        }


fig, ax = plt.subplots(2, 2, figsize=(12, 8), dpi=100)
fig.suptitle("synchronous and asynchronous performance")


def color_y_axis(ax, color):
    for t in ax.get_yticklabels():
        t.set_color(color)


for i, (fname, dps) in enumerate(formatted_data.items()):
    syn_res = dps["syn"]
    asyn_res = dps["asyn_batch"]

    steps = [dp.num_tensors for dp in asyn_res]
    mean_inference_times = [1000 * dp.mean_inference_time for dp in asyn_res]
    throughput = [dp.throughput for dp in asyn_res]

    ax1 = ax[i // 2, i % 2]
    ax2 = ax[i // 2, i % 2].twinx()

    ax1.grid(False)
    ax2.grid(False)

    color_y_axis(ax1, "b")
    color_y_axis(ax2, "r")

    ax1.title.set_text(fname)
    ax1.plot(steps, throughput, label="throughput, asynchronous (FPS)", color="b")
    ax2.plot(
        steps,
        mean_inference_times,
        label="mean inference time, asynchronous (ms)",
        color="r",
    )
    ax2.plot(
        steps,
        [1000 * syn_res.mean_inference_time * s for s in steps],
        "--",
        label="mean inference time, synchronous (ms)",
        color="r",
    )

    if i > 1:
        ax1.set_xlabel("number of images to infer")

handles, labels = [
    (a + b)
    for a, b in zip(ax1.get_legend_handles_labels(), ax2.get_legend_handles_labels())
]

plt.tight_layout()
plt.subplots_adjust(bottom=0.15)
fig.legend(handles, labels, loc="lower center", ncol=3)
fig.savefig("syn_v_asyn_inference.png")

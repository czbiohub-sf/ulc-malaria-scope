#! /usr/bin/env python3

import sys

import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path
from csv import DictReader

from ulc_mm_package.scope_constants import PER_IMAGE_TIMING_KEYS


def get_stats(name, data, save=None):
    plt.figure(figsize=(16, 12), dpi=160)

    data = [1000 * d for d in data]

    if len(data) == 0:
        print(f"data for '{name}' is empty")
        return

    mean = np.mean(data)
    stddev = np.std(data)
    median = np.median(data)

    print(f"| {name} | {mean:.3f} | {stddev:.3f} | {median:.3f} |")

    if name in ["zarr _work_queue"]:
        xs = [i * 10 for i in range(len(data))]
    else:
        xs = range(len(data))

    plt.scatter(xs, data, s=2)

    plt.title(f"{name} {mean=:.3f} {stddev=:.3f} {median=:.3f}")
    plt.xlabel("frame")
    plt.ylabel("time (ms)")

    if save is not None:
        plt.savefig(Path(save) / name.replace(".", "-"), bbox_inches="tight")
    else:
        plt.show()

    plt.clf()



if __name__ == "__main__":
    if len(sys.argv) not in [2,3]:
        print(f"usage: {sys.argv[0]} <path to metadata csv> [save]")
        sys.exit(1)

    filepath = sys.argv[1]
    if len(sys.argv) == 3:
        save = sys.argv[2]
    else:
        save = None


    run_timings = {k: [] for k in PER_IMAGE_TIMING_KEYS}

    with open(filepath, "r") as f:
        r = DictReader(f)
        print("| name | mean | stddev | median |")
        for row in r:
            for k in PER_IMAGE_TIMING_KEYS:
                if row[k] != "":
                    run_timings[k].append(float(row[k]))

        for k, data in run_timings.items():
            get_stats(k, data, save=save)

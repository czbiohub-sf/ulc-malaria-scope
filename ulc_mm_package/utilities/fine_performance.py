#! /usr/bin/env python3

import sys
from os import mkdir
import pickle

import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path
from csv import DictReader

from ulc_mm_package.scope_constants import PER_IMAGE_TIMING_KEYS


def get_stats(name, data, save=None):
    plt.figure(figsize=(12, 8), dpi=160)

    if "qsize" not in name:
        data = [1000 * d for d in data]

    if len(data) == 0:
        print(f"data for '{name}' is empty")
        return

    mean = np.mean(data)
    stddev = np.std(data)
    median = np.median(data)

    print(f"| {name} | {mean:.3f} | {stddev:.3f} | {median:.3f} |")

    xs = range(len(data))

    plt.scatter(xs, data, s=2)

    plt.title(f"{name} mean={mean:.3f} stddev={stddev:.3f} median={median:.3f}")
    plt.xlabel("frame")
    plt.ylabel("time (ms)")

    if save is not None:
        plt.savefig(Path(save) / name.replace(".", "-"), bbox_inches="tight")
        name = name + ".pkl"
        with open(Path(save) / "Pickle" / name, "wb") as f:
            pickle.dump(data, f)
    else:
        plt.show()

    plt.clf()


if __name__ == "__main__":
    if len(sys.argv) not in [2, 3]:
        print(f"usage: {sys.argv[0]} <path to metadata csv> [save]")
        sys.exit(1)

    filepath = sys.argv[1]
    if len(sys.argv) == 3:
        save = sys.argv[2]
        try:
            mkdir(Path(save) / "Pickle")
        except:
            pass
    else:
        save = None

    run_timings = {
        k: []
        for k in PER_IMAGE_TIMING_KEYS + ["looptime", "runtime", "zarrwriter_qsize"]
    }

    with open(filepath, "r") as f:
        r = DictReader(f)
        print("| name | mean | stddev | median |")
        for row in r:
            for k in run_timings:
                try:
                    if row[k] != "":
                        run_timings[k].append(float(row[k]))
                except KeyError as e:
                    raise KeyError(
                        "couldn't find timing keys - most likely, "
                        "this experiment was not run with MS_VERBOSE=1"
                    ) from e

        for k, data in run_timings.items():
            get_stats(k, data, save=save)

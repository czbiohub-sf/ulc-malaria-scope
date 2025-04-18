#! /usr/bin/env python3

"""
    Utility for plotting zarr queue size and runtimes/looptimes.
    This script gets data from Oracle's metadata file.

    In older datasets, queue size data is saved in .txt files and time data is saved in .log files.
    To analyze these datasets, use 'log_parser.py' instead.

    Arguments:
        descriptor - Description of dataset
        file - File containing metadata, saved under 'utilities/data/'

    Outputs:
        Prints mean and variance of each dataset, and plots all data.

"""

import sys

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

from pathlib import Path


def get_stats(descriptor, file):
    # Get data
    data = pd.read_csv(file)

    runtimes = data.runtime * 1000
    looptimes = data.looptime * 1000
    qsizes = data.zarrwriter_qsize

    # Plot timing results
    fig, time_ax = plt.subplots()
    time_ax.set_xlabel("Frame #")
    time_ax.set_ylabel("Time (ms)")

    time_ax.scatter(
        range(len(looptimes)), looptimes, color="red", label="Looptimes", s=2
    )
    time_ax.scatter(
        range(len(runtimes)), runtimes, color="orange", label="Runtimes", s=2
    )

    # Delineate expected looptimes
    time_ax.plot(
        [0, max(len(runtimes), len(looptimes))], [33, 33], linestyle="--", color="gray"
    )
    time_ax.plot(
        [0, max(len(runtimes), len(looptimes))], [66, 66], linestyle="--", color="gray"
    )

    # Plot size results
    size_ax = time_ax.twinx()
    size_ax.scatter(range(len(qsizes)), qsizes, label="Zarr queue", color="green", s=2)
    size_ax.tick_params(colors="green")
    size_ax.set_ylabel("Queue size", color="green")

    # Format plots
    time_ax.legend(loc=2)
    size_ax.legend(loc=1)
    plt.title(f"Timing and queue size data ({descriptor})")

    # Save/print results
    print(f"Stats for {descriptor}")
    print(f"Queue size: mean={np.mean(qsizes):.2f}, variance={np.var(qsizes):.2f}")
    if not looptimes.empty:
        print(
            f"Looptimes: mean={np.mean(looptimes):.2f}, variance={np.var(looptimes):.2f}"
        )
    if not runtimes.empty:
        print(
            f"Runtimes: mean={np.mean(runtimes):.2f}, variance={np.var(runtimes):.2f}"
        )

    plt.show()


if __name__ == "__main__":
    if len(sys.argv) not in [2, 3]:
        print(
            f"usage: {sys.argv[0]} <path to per-image metadata csv> [optional name for plot]"
        )
        sys.exit(1)

    metadata_file = sys.argv[1]

    if len(sys.argv) == 3:
        name = sys.argv[2]
    else:
        name = Path(metadata_file).name

    # Plot data
    get_stats(name, metadata_file)

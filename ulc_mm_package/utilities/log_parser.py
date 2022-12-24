"""
    Utility for plotting zarr queue size and runtimes/looptimes

    This script gets data from the following files:

        .txt file: 
            Zarrwriter queue size
            Expected format: 
                "zw executor qsize <queue size>"

        .log file
            Runtime (time to run '_run_experiment') and looptimes (time between calls to '_run_experiment')
            Expected formats:
                <timestamp> - DEBUG - Runtime for run_experiment was <runtime> [ulc_mm_package.QtGUI.scope_op]
                <timestamp> - DEBUG - Time between run_experiment calls was <looptime> [ulc_mm_package.QtGUI.scope_op]
                    OR
                <timestamp> - DEBUG - Loop time was <looptime> [ulc_mm_package.QtGUI.scope_op]

    Note that this format is now obsolete, and this script should only used for analyzing old datasets.
    Timing and queue size is now saved to metadata, which can be parsed using 'metadata_parser.py' instead.


    Arguments:
        descriptor - Description of dataset
        qsizes_file - File containing queue size data, following the format for .txt file above
        times_file - File contining timing data, following the format for .log file above

    Outputs:
        Prints mean and variance of each dataset, and plots all data.

"""

import sys

import numpy as np
import matplotlib.pyplot as plt

from os import path


def log_parser(descriptor, qsizes_file, times_file):
    # Parse queue sizes
    f = open(qsizes_file, "r")
    for i in range(0, 3):
        f.readline()
    lines = [line.split() for line in f]
    qsizes = [float(line[3]) for line in lines if line[0] == "zw"]

    # Parse timing info
    f = open(times_file, "r")
    lines = [line.split() for line in f]
    runtimes = [float(line[8]) * 1000 for line in lines if line[4] == "Runtime"]
    looptimes = [float(line[9]) * 1000 for line in lines if line[5] == "between"]
    if (not runtimes) and (not looptimes):
        looptimes = [float(line[7]) * 1000 for line in lines if line[4] == "Loop"]

    # Plot timing results
    fig, time_ax = plt.subplots()
    time_ax.set_xlabel("Frame #")
    time_ax.set_ylabel("Time (ms)")

    time_ax.scatter(range(0, len(runtimes)), runtimes, label="Runtimes", s=2)
    time_ax.scatter(range(0, len(looptimes)), looptimes, label="Looptimes", s=2)

    # Delineate expected looptimes
    time_ax.plot(
        [0, max(len(runtimes), len(looptimes))], [33, 33], linestyle="--", color="gray"
    )
    time_ax.plot(
        [0, max(len(runtimes), len(looptimes))], [66, 66], linestyle="--", color="gray"
    )

    # Plot size results
    size_ax = time_ax.twinx()
    size_ax.scatter(
        range(0, len(qsizes)), qsizes, label="Queue size", color="green", s=2
    )

    # Format plots
    time_ax.legend(loc=2)
    size_ax.legend(loc=1)
    plt.title(f"Timing and queue size data ({descriptor})")

    # Save/print results
    print(f"Stats for {descriptor}")
    print(f"Queue size: mean={np.mean(qsizes):.2f}, variance={np.var(qsizes):.2f}")
    if looptimes:
        print(
            f"Looptimes: mean={np.mean(looptimes):.2f}, variance={np.var(looptimes):.2f}"
        )
    if runtimes:
        print(
            f"Runtimes: mean={np.mean(runtimes):.2f}, variance={np.var(runtimes):.2f}"
        )

    plt.show()


if __name__ == "__main__":

    if len(sys.argv) not in [3, 4]:
        print(
            f"usage: {sys.argv[0]} <path to queue size .txt file>  <path to time .log file> [optional name for plot]"
        )
        sys.exit(1)

    qsizes_file = sys.argv[1]
    times_file = sys.argv[2]

    if len(sys.argv) == 4:
        name = sys.argv[3]
    else:
        name = qsizes_file

    # # Plot data
    # metadata_parser(name, metadata_file)

    # # Select dataset (feel free to redefine this dictionary with your files of interest)
    # pairs = {
    #     "zarrwriter": [
    #         "test-zarrwriter-tester.txt",
    #         "2022-12-19-160314-zarrwriter-tester.log",
    #     ],
    #     "master": ["test-master.txt", "2022-12-19-163708-master.log"],
    #     "pre-reboot": ["test-pre-reboot.txt", "2022-12-19-165922-pre-reboot.log"],
    #     "post-reboot": ["test-post-reboot.txt", "2022-12-19-171235-post-reboot.log"],
    # }
    # selection = "master"

    # Run plotter
    log_parser(name, qsizes_file, times_file)
